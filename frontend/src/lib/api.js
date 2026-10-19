const API_URL = (import.meta.env.VITE_API_URL || "/api").replace(/\/$/, "");
const TOKEN_KEY = "bidkaro_token";

export class ApiError extends Error {
  constructor(message, status = 0, details = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

function messageFromDetail(detail, fallback) {
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item?.msg === "string" ? item.msg : String(item)))
      .join(" ");
  }
  return fallback;
}

async function request(path, { method = "GET", body, headers = {}, raw = false } = {}) {
  const token = getToken();
  const finalHeaders = { ...headers };
  if (token) finalHeaders.Authorization = `Bearer ${token}`;
  let payload = body;
  if (body && !(body instanceof FormData) && typeof body !== "string") {
    finalHeaders["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers: finalHeaders,
      body: payload,
    });
  } catch (error) {
    throw new ApiError("NETWORK_ERROR", 0, error);
  }

  if (response.status === 401) {
    setToken(null);
    window.dispatchEvent(new CustomEvent("bidkaro:auth-expired"));
  }

  if (!response.ok) {
    let detail = null;
    try {
      const data = await response.json();
      detail = data?.detail;
    } catch {
      // Non-JSON error body.
    }
    throw new ApiError(
      messageFromDetail(detail, `Request failed (${response.status}).`),
      response.status,
      detail,
    );
  }

  if (raw) return response;
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json();
  return response.text();
}

export const api = {
  get: (path) => request(path),
  post: (path, body, options = {}) => request(path, { ...options, method: "POST", body }),
  patch: (path, body) => request(path, { method: "PATCH", body }),
  delete: (path) => request(path, { method: "DELETE" }),
  postForm: (path, formData) => request(path, { method: "POST", body: formData }),
  async download(path, filename) {
    const response = await request(path, { raw: true });
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename || "document";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  },
};

export { API_URL };
