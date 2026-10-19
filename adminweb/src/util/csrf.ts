import { AxiosHeaders, type InternalAxiosRequestConfig } from "axios";

const API_BASE_URL =
  import.meta.env.VITE_PUBLIC_API_URL || "http://localhost:8000";

let cachedCsrfToken: string | null = null;

function getCsrfEndpoint() {
  return new URL("/services/csrf/", API_BASE_URL).toString();
}

export function resetCsrfToken() {
  cachedCsrfToken = null;
}

export async function ensureCsrfToken() {
  if (cachedCsrfToken) {
    return cachedCsrfToken;
  }

  try {
    const response = await fetch(getCsrfEndpoint(), {
      method: "GET",
      credentials: "include",
    });

    if (!response.ok) {
      return null;
    }

    const data = (await response.json()) as { csrfToken?: string };
    cachedCsrfToken = data.csrfToken ?? null;
  } catch (error) {
    console.error("Failed to fetch CSRF token:", error);
  }

  return cachedCsrfToken;
}

export async function csrfInterceptor(config: InternalAxiosRequestConfig) {
  const method = (config.method || "get").toUpperCase();

  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = await ensureCsrfToken();

    if (token) {
      const headers = AxiosHeaders.from(config.headers);
      headers.set("X-CSRFToken", token);
      config.headers = headers;
    }
  }

  return config;
}
