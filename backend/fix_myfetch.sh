#!/bin/bash
FRONTEND_DIR="../admin/apps/web/src/lib"

cat << 'INNER_EOF' > $FRONTEND_DIR/myFetch.ts
import { buildUrl } from "@/util/url";
import axios from "axios";

// Standard API fetcher for old things or non-admin things
export const apiFetch = axios.create({
  baseURL: buildUrl(
    import.meta.env.VITE_PUBLIC_API_URL || "http://localhost:8000",
    "api",
    "v1",
  ),
  withCredentials: true,
});

// Admin API fetcher for the new endpoints using /api/v1/admin/
export const myFetch = axios.create({
  baseURL: buildUrl(
    import.meta.env.VITE_PUBLIC_API_URL || "http://localhost:8000",
    "api",
    "v1",
    "admin"
  ),
  withCredentials: true,
});

const ensureTrailingSlash = (config: any) => {
  if (config.url) {
    const URL_PARTS = config.url.split('?');
    let path = URL_PARTS[0];
    const query = URL_PARTS[1];
    if (!path.endsWith('/')) {
      path += '/';
    }
    config.url = query ? `${path}?${query}` : path;
  }
  return config;
};

// Axios interceptors to ensure trailing slashes which Django requires for POST/PUT/DELETE
myFetch.interceptors.request.use(ensureTrailingSlash);
apiFetch.interceptors.request.use(ensureTrailingSlash);

INNER_EOF
echo "Updated myFetch.ts with safe trailing slashes"
