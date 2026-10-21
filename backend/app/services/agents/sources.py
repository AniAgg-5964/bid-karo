"""Which sources the legal assistant may use, and for what.

The legal assistant is only useful if every clause it shows is a real
provision from a real official source. So the rule is narrow on purpose:

* the assistant may read **official** pages only - the central list below,
  plus, for the state-specific topics, a state government domain;
* a law firm blog, a news site, a tender portal or an aggregator is refused
  rather than warned about;
* what it may not do is state an obligation, threshold or penalty that is
  not in a quote from one of those pages, and it never gives an opinion on
  whether a clause is enforceable or fair.

The topic map says which official source answers which kind of question, so
the agent looks in the right place instead of wandering the web. The search
terms are the names of the instruments themselves ("code on wages 2019"), and
the domain is named in the query, because that is what actually returns
official pages.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

# The central official sources. A URL whose host is not on this list (or an
# allowed state domain for a state-specific topic) is refused.
OFFICIAL_HOSTS: frozenset[str] = frozenset(
    {
        "labour.gov.in",
        "indiacode.nic.in",
        "indiacode.gov.in",
        "egazette.gov.in",
        "epfindia.gov.in",
        "esic.gov.in",
        "cbic-gst.gov.in",
        "incometaxindia.gov.in",
        "msme.gov.in",
        "udyamregistration.gov.in",
        "cpwd.gov.in",
        "mohua.gov.in",
        "morth.nic.in",
        "bis.gov.in",
        "mca.gov.in",
        "roc.gov.in",
        "moef.gov.in",
        "parivesh.nic.in",
        "gem.gov.in",
        "eprocure.gov.in",
        "cppp.gov.in",
        "doe.gov.in",
        "gfr.gov.in",
    }
)

# Government domains that may be used for the state-specific topics only
# (a state's minimum wages notification, a state PWD's contractor rules).
STATE_SOURCE_SUFFIXES: tuple[str, ...] = (".gov.in",)

LABOUR = "labour"
TAX = "tax"
PWD = "pwd"
ENVIRONMENT = "environment"
COMPANY = "company"
STANDARDS = "standards"
PROCUREMENT = "procurement"
GENERAL = "general"

# What to search for, which host to name, and where to start when the search
# returns nothing usable.
TOPIC_SOURCES: dict[str, dict] = {
    LABOUR: {
        "hosts": ("labour.gov.in", "indiacode.gov.in", "epfindia.gov.in", "esic.gov.in"),
        "terms": (
            "code on wages 2019",
            "code on social security 2020",
            "code on bonus 2019",
            "code on industrial relations 2020",
            "occupational safety health working conditions code 2020",
        ),
        "start": ("https://labour.gov.in/acts-and-rules",),
    },
    TAX: {
        "hosts": ("cbic-gst.gov.in", "incometaxindia.gov.in", "msme.gov.in", "udyamregistration.gov.in"),
        "terms": (
            "CGST Act 2017",
            "SGST Act 2017",
            "income tax act 1961",
            "MSMED act 2006",
        ),
        "start": (
            "https://cbic-gst.gov.in/gst-acts.html",
            "https://incometaxindia.gov.in/pages/acts/income-tax-act-1961.aspx",
        ),
    },
    PWD: {
        "hosts": ("cpwd.gov.in", "mohua.gov.in", "morth.nic.in", "gfr.gov.in", "doe.gov.in"),
        "terms": (
            "contractor registration classification",
            "general financial rules 2017",
            "model tender document",
            "muster roll measurement book",
        ),
        "start": ("https://eprocure.gov.in/", "https://www.morth.nic.in/"),
    },
    ENVIRONMENT: {
        "hosts": ("moef.gov.in", "parivesh.nic.in"),
        "terms": ("environment protection act 1986", "consent to establish", "EIA notification"),
        "start": ("https://moef.gov.in/", "https://parivesh.nic.in/"),
    },
    COMPANY: {
        "hosts": ("mca.gov.in", "roc.gov.in"),
        "terms": ("companies act 2013",),
        "start": ("https://www.mca.gov.in/",),
    },
    STANDARDS: {
        "hosts": ("bis.gov.in",),
        "terms": ("bureau of indian standards", "IS code specification"),
        "start": ("https://bis.gov.in/",),
    },
    PROCUREMENT: {
        "hosts": ("gfr.gov.in", "doe.gov.in", "cppp.gov.in", "gem.gov.in", "eprocure.gov.in"),
        "terms": ("general financial rules", "public procurement portal", "e procurement"),
        "start": ("https://eprocure.gov.in/",),
    },
    GENERAL: {
        "hosts": ("labour.gov.in", "indiacode.gov.in"),
        "terms": ("code on wages 2019", "code on social security 2020"),
        "start": ("https://labour.gov.in/acts-and-rules",),
    },
}

# Words in a clause that point at a topic. The first match wins.
TOPIC_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        LABOUR,
        (
            "wage", "wages", "bonus", "gratuity", "epf", "provident fund", "esi",
            "employee state insurance", "labour", "labor", "workmen",
            "employment", "industrial relation", "minimum wage", "safety", "occupational",
            "mgnrega", "unemployment", "leave", "overtime", "shift", "contract labour",
            "pf ", "esic", "maternity", "termination of employment", "equal remuneration",
            "labour welfare", "factory", "establishment", "working hours",
            "blacklist", "debar", "debarred", "pension", "labour licence",
            "bonus", "gratuity", "provident",
        ),
    ),
    (
        TAX,
        (
            "gst", "goods and services tax", "tds", "tax deduction", "income tax",
            "msme", "udyam", "turnover tax", "customs", "exempt", "input tax credit",
        ),
    ),
    (
        PWD,
        (
            "pwd", "cpwd", "public works", "mohua", "morth", "road construction",
            "highway", "bridge", "grading", "nbo", "contractor registration",
            "contractor classification", "executive engineer", "engineer in charge",
            "muster roll", "measurement book", "bill of quantities", "completion period",
            "defect liability", "liquidated damages", "retention", "performance guarantee",
        ),
    ),
    (
        ENVIRONMENT,
        ("environment", "environmental", "eia", "consent to establish", "pollution", "forest", "wildlife", "noise"),
    ),
    (
        COMPANY,
        ("companies act", "memorandum of association", "articles of association", "roc", "company secretary"),
    ),
    (
        STANDARDS,
        ("as per is", "is code", "is standard", "bis", "national standard", "code of practice"),
    ),
    (
        PROCUREMENT,
        ("gem", "e-procurement", "eprocure", "dppp", "gfr", "general financial rules", "gec", "bid security", "earnest money", "performance security"),
    ),
)

# Topics where a state government source is also authoritative.
STATE_ALLOWED_TOPICS: frozenset[str] = frozenset({LABOUR, PWD, TAX, ENVIRONMENT})

STATE_KEYWORDS: tuple[str, ...] = (
    "minimum wages",
    "shops and establishments",
    "state government",
    "state pwd",
    "state industrial",
)


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    """The sources that may be read for one question."""

    hosts: frozenset[str]
    allow_state_sources: bool
    topic: str

    def allows(self, url: str) -> bool:
        return allows(url, self)


def host_of(url: str) -> str:
    try:
        host = (urlsplit(url or "").netloc or "").lower().split(":")[0]
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def is_official_source_host(host: str) -> bool:
    """True when the host is one of the central official sources."""
    cleaned = (host or "").lower().split(":")[0]
    if cleaned.startswith("www."):
        cleaned = cleaned[4:]
    return cleaned in OFFICIAL_HOSTS


def is_state_source(url: str) -> bool:
    """True for a state government domain, e.g. maharashtra.gov.in."""
    host = host_of(url)
    if not host:
        return False
    if host in OFFICIAL_HOSTS:
        return False
    return any(host.endswith(suffix) for suffix in STATE_SOURCE_SUFFIXES)


def topic_for(text: str) -> str:
    """The topic a clause is about, from its own words."""
    lowered = (text or "").lower()
    for topic, keywords in TOPIC_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return topic
    return GENERAL


def is_state_question(text: str) -> bool:
    lowered = (text or "").lower()
    return any(keyword in lowered for keyword in STATE_KEYWORDS)


def policy_for(text: str) -> SourcePolicy:
    """The sources that may be read for a clause."""
    topic = topic_for(text)
    hosts = frozenset(TOPIC_SOURCES.get(topic, TOPIC_SOURCES[GENERAL])["hosts"])
    allow_state = topic in STATE_ALLOWED_TOPICS and is_state_question(text)
    return SourcePolicy(hosts=hosts, allow_state_sources=allow_state, topic=topic)


def allows(url: str, policy: SourcePolicy) -> bool:
    """True when a URL may be read under a policy."""
    host = host_of(url)
    if not host:
        return False
    if host in OFFICIAL_HOSTS:
        return host in policy.hosts or policy.topic == GENERAL
    if policy.allow_state_sources and is_state_source(url):
        return True
    return False


def source_class(url: str) -> str:
    """How we describe a source to the user."""
    host = host_of(url)
    if host in OFFICIAL_HOSTS:
        return "central_official"
    if is_state_source(url):
        return "state_official"
    return "not_official"


# Which instrument actually governs a clause. The first match is the one we
# search for, so the agent looks for the right Act instead of the general
# topic.
INSTRUMENT_BY_KEYWORD: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("code on wages 2019", ("wage", "wages", "minimum wage", "equal remuneration", "overtime", "working hours", "leave")),
    ("code on bonus 2019", ("bonus",)),
    ("code on social security 2020", ("epf", "provident", "pf ", "esi", "employee state insurance", "gratuity", "pension", "social security")),
    ("occupational safety health working conditions code 2020", ("safety", "accident", "occupational", "health and working", "workmen compensation", "factory")),
    ("code on industrial relations 2020", ("blacklist", "debar", "debarred", "industrial relation", "trade union", "strike", " retrenchment")),
    ("contract labour regulation and abolition act 1970", ("contract labour", "contractor registration", "principal employer")),
    ("mgnrega 2005", ("mgnrega",)),
    ("cgst act 2017", ("gst", "goods and services tax", "input tax credit", "cgst", "sgst", "igst")),
    ("income tax act 1961", ("income tax", "tds", "tax deduction")),
    ("msmed act 2006", ("msme", "udyam", "micro small medium")),
    ("general financial rules 2017", ("general financial rules", "gfr", "gec", "gem")),
    ("public works department contractor registration", ("contractor classification", "contractor registration", "engineer in charge", "executive engineer")),
    ("environment protection act 1986", ("environment", "environmental", "eia", "consent to establish", "pollution")),
    ("companies act 2013", ("companies act", "memorandum of association", "articles of association")),
    ("bureau of indian standards", ("as per is", "is code", "is standard", "national standard")),
)


def instrument_for(text: str) -> str | None:
    """The instrument that governs a clause, from the clause's own words."""
    lowered = (text or "").lower()
    for instrument, keywords in INSTRUMENT_BY_KEYWORD:
        if any(keyword in lowered for keyword in keywords):
            return instrument
    return None


def search_terms_for(text: str, limit: int = 2) -> list[str]:
    """The instrument names to search for, for the clause's topic."""
    instrument = instrument_for(text)
    if instrument:
        return [instrument]
    topic = topic_for(text)
    terms = TOPIC_SOURCES.get(topic, TOPIC_SOURCES[GENERAL])["terms"]
    return list(terms[:limit])


def start_urls_for(text: str) -> list[str]:
    """Where to start when the search returns nothing usable."""
    topic = topic_for(text)
    return list(TOPIC_SOURCES.get(topic, TOPIC_SOURCES[GENERAL])["start"])
