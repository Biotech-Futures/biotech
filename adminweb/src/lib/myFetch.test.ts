import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * The replay guard on the stale-CSRF retry.
 *
 * Both front ends talk to the same backend origin and therefore share one
 * cookie jar. Signing in on the student portal in another tab rotates the CSRF
 * token, so every write in this tab fails with a 403 whose body mentions CSRF.
 * The interceptor refreshes the token and replays the request once, which is
 * the right behaviour when the session still belongs to the same person.
 *
 * When it does not, replaying files the write under whoever owns the session
 * now. `routes/setup-password.tsx` posts through this instance, so a replayed
 * set-password puts the password one person typed onto another person's
 * account.
 *
 * That guard had no test at all. Two mutations were run against the suite
 * before these were written — deleting the check outright, and neutering it to
 * `if (false && ...)` so the types stayed clean — and 61 tests plus typecheck
 * passed both times. These are the assertions that would have failed.
 */


function csrfRefused() {
  return {
    status: 403,
    data: { error: "CSRF token missing or incorrect" },
  };
}

/** Who the browser reports as signed in, and how the write is answered. */
async function attemptWrite({
  knownUser,
  sessionUser,
}: {
  knownUser: number | null;
  sessionUser: number | null;
}) {
  vi.resetModules();

  const rememberedGetter = vi.fn(() => knownUser);
  vi.doMock("@/util/csrf", () => ({
    knownSessionUser: rememberedGetter,
    rememberSessionUser: vi.fn(),
    resetCsrfToken: vi.fn(),
    ensureCsrfToken: vi.fn(async () => "fresh-token"),
    csrfInterceptor: (config: unknown) => config,
  }));

  // The identity check deliberately uses a bare fetch rather than one of the
  // axios instances, because going through them would re-enter the very
  // interceptor under test.
  const fetchMock = vi.fn(async () =>
    sessionUser === null
      ? ({ ok: false, json: async () => ({}) } as unknown as Response)
      : ({ ok: true, json: async () => ({ id: sessionUser }) } as unknown as Response),
  );
  vi.stubGlobal("fetch", fetchMock);

  const { myFetch } = await import("./myFetch");

  let attempts = 0;
  myFetch.defaults.adapter = async (config) => {
    attempts += 1;
    // Always refuse, so a replay shows up as a second attempt rather than as
    // a success that could be mistaken for the first one.
    return Promise.reject(
      Object.assign(new Error("csrf"), {
        config,
        response: { ...csrfRefused(), config, headers: {}, statusText: "" },
        isAxiosError: true,
      }),
    );
  };

  const result = await myFetch
    .post("/tickets/1/messages/", { body: "hello" })
    .then(() => "resolved" as const)
    .catch(() => "rejected" as const);

  return { attempts, result, identityChecked: fetchMock.mock.calls.length > 0 };
}

describe("the stale-CSRF replay guard", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
    vi.doUnmock("@/util/csrf");
  });

  it("replays a write when the session still belongs to the same person", async () => {
    const { attempts, identityChecked } = await attemptWrite({
      knownUser: 7,
      sessionUser: 7,
    });

    expect(identityChecked).toBe(true);
    expect(attempts).toBe(2);
  });

  it("does not replay a write once somebody else owns the session", async () => {
    // The case the comment names: a replayed set-password would put the
    // password this person typed onto the other person's account.
    const { attempts, result } = await attemptWrite({
      knownUser: 7,
      sessionUser: 9,
    });

    expect(attempts).toBe(1);
    expect(result).toBe("rejected");
  });

  it("does not replay when it cannot tell who owns the session", async () => {
    // Unknown is not the same as matching. A /users/me/ that fails to answer
    // must not be read as confirmation.
    const { attempts, result } = await attemptWrite({
      knownUser: 7,
      sessionUser: null,
    });

    expect(attempts).toBe(1);
    expect(result).toBe("rejected");
  });

  it("does not replay when this tab never learned who it is", async () => {
    const { attempts } = await attemptWrite({ knownUser: null, sessionUser: 7 });

    expect(attempts).toBe(1);
  });
});
