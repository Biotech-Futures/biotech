import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * The admin's attachment download helper.
 *
 * ⚠️ This file exists because the helper had NO coverage at all. Measured on
 * 2026-09-14: deleting the entire body of `downloadTicketAttachment` — the
 * request, the blob, the object URL, the `download` attribute, the click and
 * the revoke — left `pnpm test` at `Test Files 18 passed / Tests 238 passed`,
 * exit 0. TicketDetailPanel.test.tsx mocks this function out, so it proves the
 * panel CALLS it and nothing proves it does anything. The portal's equivalent
 * in frontend/src/utils/__tests__/supportAPI.spec.ts has five such assertions;
 * this is the admin half of that pair.
 *
 * What is pinned is the part that would fail silently in production: asking
 * for a blob (without `responseType` axios parses the bytes and
 * `createObjectURL` gets a string), saving under the name the panel shows, and
 * not leaking the object URL or the anchor.
 */

const get = vi.fn();
vi.mock("@/lib/myFetch", () => ({
  myFetch: { get: (...args: unknown[]) => get(...args) },
}));

const { downloadTicketAttachment, attachmentErrorMessage } = await import("./ticket");

describe("downloading a ticket attachment from the admin app", () => {
  let created: string[] = [];
  let revoked: string[] = [];
  let clicked: HTMLAnchorElement[] = [];

  beforeEach(() => {
    get.mockReset();
    created = [];
    revoked = [];
    clicked = [];
    window.URL.createObjectURL = vi.fn(() => {
      const url = `blob:mock/${created.length}`;
      created.push(url);
      return url;
    }) as unknown as typeof window.URL.createObjectURL;
    window.URL.revokeObjectURL = vi.fn((url: string) => {
      revoked.push(url);
    }) as unknown as typeof window.URL.revokeObjectURL;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked.push(this);
    });
    get.mockResolvedValue({ data: new Blob(["%PDF-1.4"], { type: "application/pdf" }) });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("asks for the bytes as a blob, or createObjectURL gets a parsed string", async () => {
    await downloadTicketAttachment(7, 9, "gone.png");

    expect(get).toHaveBeenCalledTimes(1);
    expect(get.mock.calls[0][1]).toMatchObject({ responseType: "blob" });
  });

  it("asks the endpoint the panel's ticket and attachment name", async () => {
    await downloadTicketAttachment(7, 9, "gone.png");

    expect(get.mock.calls[0][0]).toBe("/tickets/7/attachments/9");
  });

  it("saves it under the name the panel is showing", async () => {
    // Not the name in Content-Disposition: reading that header cross-origin
    // needs Access-Control-Expose-Headers, which this endpoint does not send.
    await downloadTicketAttachment(7, 9, "gone.png");

    expect(clicked).toHaveLength(1);
    expect(clicked[0].download).toBe("gone.png");
    expect(clicked[0].getAttribute("href")).toBe(created[0]);
  });

  it("leaves neither the object URL nor the anchor behind", async () => {
    await downloadTicketAttachment(7, 9, "gone.png");

    expect(revoked).toEqual(created);
    expect(document.querySelectorAll("a[download]")).toHaveLength(0);
  });

  it("lets the refusal out, instead of saving an error page as the file", async () => {
    get.mockRejectedValue(Object.assign(new Error("Request failed"), {
      isAxiosError: true,
      response: { status: 404, data: new Blob(["{}"]) },
    }));

    await expect(downloadTicketAttachment(7, 9, "gone.png")).rejects.toThrow();
    expect(clicked).toHaveLength(0);
    expect(created).toEqual([]);
  });

  it("reads the status off an axios error even when the body is a Blob", async () => {
    // responseType: "blob" makes an error body a Blob too, so anything that
    // tried to read `.error` off it would get undefined. The message is keyed
    // on the status for exactly that reason.
    const blobBodied = Object.assign(new Error("Request failed"), {
      isAxiosError: true,
      response: { status: 403, data: new Blob(["{}"]) },
    });
    expect(attachmentErrorMessage(blobBodied)).toBe(
      "Your session has expired. Reload this page and sign in again to open this file.",
    );
  });
});
