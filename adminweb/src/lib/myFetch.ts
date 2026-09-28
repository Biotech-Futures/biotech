import { buildUrl } from "@/util/url";
import {
  csrfInterceptor,
  ensureCsrfToken,
  knownSessionUser,
  resetCsrfToken,
} from "@/util/csrf";
import axios, { type AxiosError, type AxiosInstance } from "axios";

// Standard API fetcher for old things or non-admin things
const API_BASE_URL =
  import.meta.env.VITE_PUBLIC_API_URL || "http://localhost:8000";

export const apiFetch = axios.create({
  baseURL: buildUrl(API_BASE_URL, "api", "v1"),
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

myFetch.interceptors.request.use(csrfInterceptor);
apiFetch.interceptors.request.use(csrfInterceptor);

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

/**
 * Recover from a CSRF token that went stale under us.
 *
 * Django rotates the CSRF token on every login, and util/csrf.ts caches the
 * token in module scope with nothing to invalidate it. Both front ends talk to
 * the same backend origin and therefore share one cookie jar, so signing in on
 * the student portal in another tab silently kills every write in this one —
 * with a 403 whose message says "CSRF token ... incorrect", which reads like a
 * bug in the page rather than "reload me".
 *
 * On that specific 403: drop the cached token, fetch a fresh one and replay the
 * request once — but for a write, only after confirming the session still
 * belongs to the same person.
 *
 * 🔴 That confirmation is not optional. An earlier version of this comment
 * argued a replay was safe because a caller who is not support-capable gets
 * refused by IsSupportScoped. That reasoning only covers a student taking over
 * the session. It does not cover another ADMIN taking it over, and the actor
 * recorded is whoever owns the session at replay time, not whoever typed. The
 * concrete case: routes/setup-password.tsx posts through this instance, so a
 * replayed set-password could put the password you typed on somebody else's
 * account.
 */
function looksLikeStaleCsrf(error: AxiosError): boolean {
  if (error.response?.status !== 403) return false;
  const data = error.response.data as { error?: string; msg?: string } | string;
  const text = typeof data === "string" ? data : (data?.error ?? data?.msg ?? "");
  return text.toLowerCase().includes("csrf");
}

const SAFE_METHODS = ["get", "head", "options"];

/** Whether the browser's session still belongs to the person this tab knows.
 *
 *  Uses a bare fetch rather than one of the axios instances: going through
 *  them would re-enter this very interceptor. */
async function sessionUnchanged(): Promise<boolean> {
  const expected = knownSessionUser();
  if (expected === null) return false; // unknown is not the same as matching
  try {
    const response = await fetch(
      new URL("/api/v1/users/me/", API_BASE_URL).toString(),
      { credentials: "include" },
    );
    if (!response.ok) return false;
    const me = (await response.json()) as { id?: number };
    return me?.id === expected;
  } catch {
    return false;
  }
}

function retryOnceOnStaleCsrf(client: AxiosInstance) {
  client.interceptors.response.use(undefined, async (error: AxiosError) => {
    const config = error.config as
      | (NonNullable<AxiosError["config"]> & { _csrfRetried?: boolean })
      | undefined;
    if (!config || config._csrfRetried || !looksLikeStaleCsrf(error)) {
      return Promise.reject(error);
    }
    const method = (config.method || "get").toLowerCase();
    if (!SAFE_METHODS.includes(method) && !(await sessionUnchanged())) {
      // Somebody else is signed in now, or we cannot tell. Refresh the token
      // anyway so the next request works, but do not replay this one under
      // their name.
      resetCsrfToken();
      await ensureCsrfToken();
      return Promise.reject(error);
    }
    config._csrfRetried = true;
    resetCsrfToken();
    const token = await ensureCsrfToken();
    if (!token) return Promise.reject(error);
    return client.request(config);
  });
}

retryOnceOnStaleCsrf(myFetch);
retryOnceOnStaleCsrf(apiFetch);
