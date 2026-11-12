// Static production exports use the authenticated, same-origin reverse proxy.
// No API password or token belongs in NEXT_PUBLIC_* variables.
export const BACKEND_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : "/backend")
).replace(/\/$/, "");

export const backendUrl = (path) => `${BACKEND_URL}/${path.replace(/^\//, "")}`;
