import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const auth = { user: { name: "Ada", isAdmin: true, isSupport: true } as
  | { name: string; isAdmin: boolean; isSupport: boolean }
  | null };

// TanStack Router's Link needs a router in context, and nothing here is about
// routing. Same stub as AdminHomePage.test.tsx.
vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children }: { to: string; children: React.ReactNode }) => (
    <a href={to}>{children}</a>
  ),
}));

vi.mock("@/provider/AuthProvider", () => ({
  useAuthContext: () => auth,
}));

const roster = { data: undefined as unknown, isLoading: false, isError: false };
const revoke = { mutate: vi.fn(), isPending: false };
const grant = {
  mutate: vi.fn(),
  isPending: false,
  isError: false,
  error: undefined as unknown,
};

vi.mock("@/query/ticket", () => ({
  useSupportRoster: () => roster,
  useGrantSupport: () => grant,
  useRevokeSupport: () => revoke,
}));

const candidates = { data: undefined as unknown, isLoading: false };

vi.mock("@/query/user", () => ({
  useQueryUsers: () => candidates,
}));

import { SupportAgentsPage } from "./SupportAgentsPage";

const AGENT = {
  id: 4,
  name: "Sam Reid",
  email: "sam@example.com",
  openTickets: 3,
  accountStatus: "active",
};

/** A 400 the way this endpoint sends one.
 *
 *  The support-scope refusals answer {msg, data} directly rather than raising
 *  through config/exception_handler.py, so the sentence is in msg and not in
 *  the {error, code} envelope the ticket write path uses. */
function refusal(msg: string) {
  return Object.assign(new Error("Request failed with status code 400"), {
    isAxiosError: true,
    response: { status: 400, data: { msg, data: null } },
  });
}

describe("SupportAgentsPage", () => {
  beforeEach(() => {
    auth.user = { name: "Ada", isAdmin: true, isSupport: true };
    roster.data = [AGENT];
    candidates.data = undefined;
    revoke.mutate.mockClear();
    grant.isError = false;
    grant.error = undefined;
  });

  it("answers a support agent who reaches the URL instead of failing to load", () => {
    /**
     * The route only checks that somebody is signed in, so an agent who is
     * not an admin can type this address. The server refuses them either way;
     * without this branch they would sit in front of a table that never
     * loads and read it as the page being broken.
     */
    auth.user = { name: "Sam", isAdmin: false, isSupport: true };
    render(<SupportAgentsPage />);

    expect(
      screen.getByText(/Only administrators can change who works the support queue/),
    ).toBeTruthy();
  });

  it("shows how much work a person is carrying before you remove them", () => {
    render(<SupportAgentsPage />);
    expect(screen.getByText("Sam Reid")).toBeTruthy();
    expect(screen.getByText("3")).toBeTruthy();
  });

  it("warns that revoking leaves their tickets in their name", async () => {
    // The consequence an admin would not guess: revoking access does not
    // hand the work to anybody. Saying nothing here is how three tickets end
    // up owned by someone who can no longer open them.
    render(<SupportAgentsPage />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
    });

    expect(screen.getByText(/still own 3 tickets/)).toBeTruthy();
    expect(screen.getByText(/stay in this person's name/)).toBeTruthy();
  });

  it("does not warn about work when there is none", async () => {
    roster.data = [{ ...AGENT, openTickets: 0 }];
    render(<SupportAgentsPage />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
    });

    expect(screen.queryByText(/still own/)).toBeNull();
    expect(screen.getByText(/Nothing else about their account changes/)).toBeTruthy();
  });

  it("asks before it revokes, and only revokes on confirmation", async () => {
    render(<SupportAgentsPage />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
    });
    // Opening the dialog must not be the action itself.
    expect(revoke.mutate).not.toHaveBeenCalled();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Revoke access" }));
    });
    expect(revoke.mutate).toHaveBeenCalledWith(4);
  });
});

describe("SupportAgentsPage create entry point", () => {
  beforeEach(() => {
    auth.user = { name: "Ada", isAdmin: true, isSupport: true };
    candidates.data = undefined;
  });

  // The client's answer on 2026-09-04 was that an admin creates a NEW account
  // for a support agent, not only that they grant the role to an existing one.
  // Both routes exist; this is the one that has to be findable from the screen
  // somebody lands on when they think "how do I add a support person?".

  it("offers a way to create a support agent, not only to grant access", () => {
    roster.data = [];
    render(<SupportAgentsPage />);
    expect(screen.getByText(/create a support agent/i)).toBeTruthy();
  });

  it("sends the admin to the People page already filtered to support", () => {
    roster.data = [];
    render(<SupportAgentsPage />);
    const link = screen
      .getByText(/create a support agent/i)
      .closest("a") as HTMLAnchorElement | null;
    expect(link).not.toBeNull();
    expect(link!.getAttribute("href")).toBe("/people");
  });

  it("says where the button goes, because it goes somewhere and does not create", () => {
    // The control is an anchor to a filtered list. It opens no form, and the
    // Add User form waiting on the other side opens on Student, so a label
    // reading only "Create a support agent" promised a step it does not take.
    roster.data = [];
    render(<SupportAgentsPage />);
    expect(
      screen.getByText(/create a support agent/i).textContent,
    ).toBe("Create a support agent on the People page");
  });

  it("says the new account still needs Support picked as its role", () => {
    // The one thing an admin has to do that nothing on the way there tells
    // them. Miss it and the form asks for a school and a year level.
    roster.data = [];
    render(<SupportAgentsPage />);
    expect(
      screen.getByText(/needs Support picked as its role/i),
    ).toBeTruthy();
  });

  it("says plainly which of the two things each route does", () => {
    // "Adding" and "creating" are different actions with different results,
    // and the difference is the whole point of the role. A screen that offers
    // both without saying so invites an admin to make a second account for
    // somebody who already has one.
    roster.data = [];
    render(<SupportAgentsPage />);
    expect(
      screen.getByText(/gives an existing account access to the queue/i),
    ).toBeTruthy();
    expect(
      screen.getByText(/makes a new account that has queue access/i),
    ).toBeTruthy();
  });

  it("does not offer it to a support agent who is not an admin", () => {
    auth.user = { name: "Sana", isAdmin: false, isSupport: true };
    roster.data = [];
    render(<SupportAgentsPage />);
    expect(screen.queryByText(/create a support agent/i)).toBeNull();
  });
});


describe("what queue access is, and what it is not", () => {
  beforeEach(() => {
    auth.user = { name: "Ada", isAdmin: true, isSupport: true };
    roster.data = [AGENT];
    candidates.data = undefined;
    revoke.mutate.mockClear();
  });

  it("says the People page's Role column is not queue access", () => {
    // The two screens disagree by design and neither is catching up with the
    // other: revoking never touches the role, and somebody listed as Mentor
    // can be on this page working the queue. An admin comparing them needs
    // to be told which question each one answers.
    render(<SupportAgentsPage />);

    expect(
      screen.getByText(/records what an account is, not whether it can open the queue/i),
    ).toBeTruthy();
    expect(
      screen.getByText(/only place that shows queue access/i),
    ).toBeTruthy();
  });

  it("does not claim to list the administrators, who are not on it", () => {
    // ⚠️ The assertion above passes with or without the clause, so on its
    // own it locked in the contradiction. The heading says administrators
    // work the queue without being listed here, and services/queue.py counts
    // them as queue-capable, so "the only place that shows queue access"
    // read flat would hide every administrator from anyone taking stock.
    render(<SupportAgentsPage />);

    expect(
      screen.getByText(
        /apart from administrators, this page is the only place that shows queue access/i,
      ),
    ).toBeTruthy();
  });

  it("warns before revoking that the People page will still say Support", async () => {
    // Said at the moment of the action, because checking your work on the
    // People page afterwards is the natural next move, and editing that row
    // to fix it is a silent no-op.
    roster.data = [{ ...AGENT, openTickets: 0 }];
    render(<SupportAgentsPage />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
    });

    expect(
      screen.getByText(/role listed for them on the People page does not change/i),
    ).toBeTruthy();
  });

  it("warns about the role even when there are tickets to strand", async () => {
    // The other branch of the same dialog. The stranded-ticket wording
    // replaced the general sentence, so a warning written into one branch
    // only is a warning half the admins never see.
    render(<SupportAgentsPage />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
    });

    expect(screen.getByText(/still own 3 tickets/)).toBeTruthy();
    expect(
      screen.getByText(/role listed for them on the People page does not change/i),
    ).toBeTruthy();
  });
});

describe("granting access to an account that is switched off", () => {
  const LIVE = { id: "8", name: "Rae Wills", email: "rae@example.com", active: true };
  const DEAD = { id: "9", name: "Ola Nunes", email: "ola@example.com", active: false };

  beforeEach(() => {
    auth.user = { name: "Ada", isAdmin: true, isSupport: true };
    roster.data = [];
    grant.mutate.mockClear();
    grant.isError = false;
    grant.error = undefined;
    candidates.data = { data: { items: [LIVE, DEAD] } };
  });

  function search() {
    fireEvent.change(
      screen.getByLabelText("Search for a person to grant support access"),
      { target: { value: "a" } },
    );
  }

  it("marks the candidate whose account is not active", () => {
    // Which of two similar names is the live account. The mark used to read
    // "Deactivated", and this list has only is_active to go on: that is false
    // for an invited or a pending account too, and the server grants both of
    // those, so the word named a decision nobody had made.
    render(<SupportAgentsPage />);
    search();

    const row = screen.getByText("Ola Nunes").closest("li") as HTMLElement;
    expect(row.textContent).toContain("Not an active account");
    expect(row.textContent).not.toContain("Deactivated");
  });

  it("does not put that mark on an account that is fine", () => {
    // ⚠️ Load-bearing. Rendering the mark unconditionally satisfies the
    // assertion above on its own, and would label every candidate on the
    // page.
    render(<SupportAgentsPage />);
    search();

    const row = screen.getByText("Rae Wills").closest("li") as HTMLElement;
    expect(row.textContent).not.toContain("Not an active account");
  });

  it("still sends the grant rather than guessing the answer here", () => {
    // The screen has is_active and nothing else, and is_active is false for
    // an invited account the server is happy to grant. Refusing here would
    // block that ordinary case on a signal that does not decide it. The
    // server owns the rule — views_admin._grant_refusal reads account_status,
    // which this endpoint does not send — and the refusal below shows what it
    // said.
    render(<SupportAgentsPage />);
    search();

    const row = screen.getByText("Ola Nunes").closest("li") as HTMLElement;
    const button = row.querySelector("button") as HTMLButtonElement;
    expect(button.disabled).toBe(false);

    fireEvent.click(button);
    expect(grant.mutate).toHaveBeenCalledWith(9, expect.anything());
  });

  it("shows what the server said when it refused the grant", () => {
    // Without this the press did nothing visible at all: the roster did not
    // change, the button stayed enabled, and the admin pressed it again. The
    // refusal is a sentence written for them and it says what to do next.
    grant.isError = true;
    grant.error = refusal(
      "This account is switched off, so it cannot work the queue. " +
        "Reactivate it first, then grant support access.",
    );
    render(<SupportAgentsPage />);
    search();

    expect(
      screen.getByRole("alert").textContent,
    ).toContain("Reactivate it first, then grant support access.");
  });

  it("says something even when the failure carried no sentence", () => {
    // ⚠️ Load-bearing. A network fault has no msg, and rendering only
    // serverMessage would print an empty alert for it.
    grant.isError = true;
    grant.error = new Error("Network Error");
    render(<SupportAgentsPage />);
    search();

    expect(screen.getByRole("alert").textContent).toBe(
      "That person was not added to the queue.",
    );
  });

  it("stays quiet while nothing has been refused", () => {
    render(<SupportAgentsPage />);
    search();

    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("an agent whose account was switched off after they were added", () => {
  // Granting and revoking never touch the account, and switching an account
  // off never touches the roster. That is deliberate, and it leaves rows on
  // this table that nobody can sign into. The endpoint has sent accountStatus
  // since the grant guard went in and nothing read it, so the row looked
  // exactly like an agent picking up tickets.

  beforeEach(() => {
    auth.user = { name: "Ada", isAdmin: true, isSupport: true };
    candidates.data = undefined;
    grant.isError = false;
    grant.error = undefined;
  });

  it("says so beside the name", () => {
    roster.data = [{ ...AGENT, accountStatus: "deactivated" }];
    render(<SupportAgentsPage />);

    const cell = screen.getByText("Sam Reid").closest("td") as HTMLElement;
    expect(cell.textContent).toContain("Deactivated");
    expect(cell.textContent).toContain("cannot work the queue");
  });

  it("uses the account's own word, because the two are acted on differently", () => {
    roster.data = [{ ...AGENT, accountStatus: "suspended" }];
    render(<SupportAgentsPage />);

    const cell = screen.getByText("Sam Reid").closest("td") as HTMLElement;
    expect(cell.textContent).toContain("Suspended");
  });

  it("leaves an agent who is working today unmarked", () => {
    // ⚠️ Load-bearing. A mark rendered on every row satisfies the two above
    // and tells the reader nothing.
    roster.data = [AGENT];
    render(<SupportAgentsPage />);

    const cell = screen.getByText("Sam Reid").closest("td") as HTMLElement;
    expect(cell.textContent).not.toContain("cannot work the queue");
  });

  it("leaves an invited colleague unmarked, because they can sign in", () => {
    // is_active is false for them as well. INACTIVE_LOGIN_STATUSES leaves
    // invited out and the grant endpoint accepts it, so a mark here would
    // contradict the server about an ordinary case.
    roster.data = [{ ...AGENT, accountStatus: "invited" }];
    render(<SupportAgentsPage />);

    const cell = screen.getByText("Sam Reid").closest("td") as HTMLElement;
    expect(cell.textContent).not.toContain("cannot work the queue");
  });
});
