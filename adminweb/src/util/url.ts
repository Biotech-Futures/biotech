export function buildUrl(host: string, ...paths: string[]) {
  const path = paths
    .map((p) => p.replace(/^\/+|\/+$/g, "")) // strip leading/trailing slashes
    .join("/");
  return new URL(path, host.replace(/\/+$/, "")).toString();
}

/** Resolve backend-relative media URLs for display in the admin frontend. */
export function resolvePublicUrl(value?: string | null): string {
  if (!value) return "";
  if (/^(https?:|data:|blob:)/i.test(value)) return value;

  const apiOrigin = import.meta.env.VITE_PUBLIC_API_URL || "http://localhost:8000";
  return new URL(value, `${apiOrigin.replace(/\/+$/, "")}/`).toString();
}
