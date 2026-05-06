export function buildUrl(host: string, ...paths: string[]) {
  const path = paths
    .map((p) => p.replace(/^\/+|\/+$/g, "")) // strip leading/trailing slashes
    .join("/");
  return new URL(path, host.replace(/\/+$/, "")).toString();
}
