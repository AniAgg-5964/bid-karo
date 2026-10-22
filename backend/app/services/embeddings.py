"""Embeddings for the retrieval index.

The chat-completion model and the embedding model are different things, so the
embedding side has its own small abstraction, mirroring the pattern in
``app/integrations/ai.py``: a protocol, a factory and a provider that reports
itself as unconfigured when it cannot run.

Two providers ship here:

``hashing``
    Deterministic, needs no download and costs nothing. It is a signed hashing
    projection of the tokens, so it behaves like a lexical vectoriser. It is
    weak on meaning and exact on wording, which is useful for clause numbers,
    thresholds and certificate names. This is the default so the pipeline always
    runs.

``model2vec``
    A small local static-embedding model. It is more semantic, it costs
    nothing to run, and it downloads the model once (~30 MB) the first time. If
    the model cannot be fetched the provider reports itself unavailable and the
    caller decides what to do; it never silently falls back.

The dimension is a property of the provider, never a constant chosen for an
assumed provider.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from app.core.config import Settings, get_settings

DEFAULT_HASHING_DIMENSION = 384
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class EmbeddingError(RuntimeError):
    """Any failure while producing embeddings."""


class EmbeddingUnavailable(EmbeddingError):
    """The provider is selected but cannot run on this machine."""


class EmbeddingProvider(Protocol):
    """A provider of text embeddings."""

    name: str
    model: str

    @property
    def dimension(self) -> int:
        """The number of components in every vector this provider returns."""
        ...

    @property
    def available(self) -> bool:
        """False when the provider cannot run; the caller must not index."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""
        ...


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


class HashingEmbeddingProvider:
    """A deterministic, dependency-free embedding.

    Every token is hashed into a bucket and a sign, weighted by the token's
    length, and the vector is normalised. The same text always produces the
    same vector, on any machine, with nothing downloaded.
    """

    name = "hashing"

    def __init__(
        self,
        *,
        model: str = "hashing-v1",
        dimension: int = DEFAULT_HASHING_DIMENSION,
    ) -> None:
        if dimension < 8:
            raise EmbeddingError("The embedding dimension must be at least 8.")
        self.model = model
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def available(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        tokens = _tokens(text)
        if not tokens:
            return vector
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        for token, count in counts.items():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self._dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            weight = (1.0 + math.log(count)) * (1.0 + math.log(1.0 + len(token)))
            vector[bucket] += sign * weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector


class Model2VecEmbeddingProvider:
    """A small local static-embedding model, downloaded once."""

    name = "model2vec"
    DEFAULT_MODEL = "minishlab/potion-base-8M"

    def __init__(self, *, model: str | None = None) -> None:
        self.model = model or self.DEFAULT_MODEL
        self._encoder = None
        self._dimension = 0
        self._error: str | None = None

    @property
    def dimension(self) -> int:
        if not self._dimension:
            raise EmbeddingUnavailable(self._error or "The model has not been loaded.")
        return self._dimension

    @property
    def available(self) -> bool:
        self._load()
        return self._encoder is not None

    def _load(self) -> None:
        if self._encoder is not None or self._error:
            return
        try:
            from model2vec import StaticModel  # type: ignore[import-not-found]

            model = StaticModel.from_pretrained(self.model)
            self._encoder = model
            probe = model.encode(["dimension probe"])
            self._dimension = int(len(probe[0]))
        except Exception as exc:  # noqa: BLE001 - an unavailable model is reported
            self._error = f"The local embedding model could not be loaded: {exc}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._load()
        if self._encoder is None:
            raise EmbeddingUnavailable(self._error or "The local embedding model is not available.")
        vectors = self._encoder.encode(list(texts))
        return [[float(value) for value in vector] for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


class UnavailableEmbeddingProvider:
    """Used when the selected provider cannot run."""

    def __init__(self, reason: str) -> None:
        self.name = "unavailable"
        self.model = ""
        self.reason = reason

    @property
    def dimension(self) -> int:
        raise EmbeddingUnavailable(self.reason)

    @property
    def available(self) -> bool:
        return False

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingUnavailable(self.reason)

    def embed_query(self, text: str) -> list[float]:
        raise EmbeddingUnavailable(self.reason)


def build_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """The configured embedding provider.

    The dimension is read from the provider, never assumed.
    """
    current = settings or get_settings()
    provider = (current.embedding_provider or "hashing").strip().lower()
    if provider == "model2vec":
        candidate = Model2VecEmbeddingProvider(model=current.embedding_model or None)
        if candidate.available:
            if current.embedding_dimension and current.embedding_dimension != candidate.dimension:
                return UnavailableEmbeddingProvider(
                    "EMBEDDING_DIMENSION does not match the model's dimension "
                    f"({candidate.dimension}). Leave it at 0 to use the model's own."
                )
            return candidate
        return UnavailableEmbeddingProvider(candidate._error or "The model is not available.")
    if provider == "hashing":
        return HashingEmbeddingProvider(
            model=current.embedding_model or "hashing-v1",
            dimension=current.embedding_dimension or DEFAULT_HASHING_DIMENSION,
        )
    return UnavailableEmbeddingProvider(
        f"Unsupported EMBEDDING_PROVIDER '{current.embedding_provider}'. "
        "Use 'hashing' or 'model2vec'."
    )
