import { isAxiosError } from "axios";

/** Whether a failed query was a refusal rather than a fault.
 *
 *  Both of these routes are gated on being signed in and nothing more, so a
 *  support agent or a student who types the address reaches the page and the
 *  server answers 403. Reporting that as "could not be loaded" tells them the
 *  product is broken when in fact it is working exactly as intended, and it
 *  sends them to look for a fault that is not there.
 */
export function wasRefused(error: unknown): boolean {
  return isAxiosError(error) && error.response?.status === 403;
}

/** The server's own explanation of a refusal, when it gave one.
 *
 *  Every endpoint on this app answers `{msg, data}` and returns 400 with a
 *  useful `msg` when it declines a write — "Country cannot be cleared",
 *  "Email already exists". axios rejects on 4xx, so a caller that reads
 *  `response.msg` on the success path and falls back to a generic string in
 *  its `catch` shows the generic string for every one of those, and the
 *  person editing is told "Unable to update the user right now" when the
 *  server has already said exactly what is wrong.
 */
export function serverMessage(error: unknown): string | undefined {
  if (!isAxiosError(error)) return undefined;
  const data = error.response?.data as { msg?: unknown } | undefined;
  return typeof data?.msg === "string" && data.msg.trim() !== ""
    ? data.msg
    : undefined;
}
