import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// TanStack Router's Link needs a router in context; nothing here is about
// navigation, so it becomes a plain anchor.
vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children }: { to: string; children: React.ReactNode }) => (
    <a href={to}>{children}</a>
  ),
}));

const useAuthContext = vi.fn();
vi.mock("@/provider/AuthProvider", () => ({
  useAuthContext: () => useAuthContext(),
}));

const { AdminHomePage } = await import("./AdminHomePage");

function signedInAs(user: Record<string, unknown>) {
  useAuthContext.mockReturnValue({ user });
  render(<AdminHomePage />);
}

describe("admin home page", () => {
  it("shows an admin every section", () => {
    signedInAs({ name: "Ada Lin", email: "admin@example.com", isAdmin: true });

    for (const heading of ["People", "Groups & Matching", "Content", "Support"]) {
      expect(screen.getByRole("heading", { name: heading })).toBeTruthy();
    }
  });

  it("shows a support agent the support section and nothing else", () => {
    signedInAs({ name: "Sam Reid", email: "agent@example.com", isSupport: true });

    expect(screen.getByRole("heading", { name: "Support" })).toBeTruthy();
    // Every admin section by name, not a hand-picked sample. The first
    // version listed People and Content and skipped Groups & Matching, so
    // marking that one section support:true opened it to agents with 39
    // green — "nothing else" enforced on two thirds of the list. A review
    // pass caught it with exactly that mutation.
    for (const section of ["People", "Groups & Matching", "Content"]) {
      expect(
        screen.queryByRole("heading", { name: section }),
        `${section} was shown to a support agent`,
      ).toBeNull();
    }
  });

  it("tells somebody with neither role why the page is empty", () => {
    // This is the regression that shipped. The branch was copied from the
    // sidebar, which keeps an "Overview" section for exactly this case — and
    // this page has no such section, so the filter matched nothing and the
    // page rendered a name and then blank space. A blank admin page reads as
    // broken software, not as "this is not for you".
    //
    // ⚠️ Measured, because the obvious reading of that story is wrong: on a
    // list with no "Overview" the copied filter and a plain `[]` produce the
    // same sections, so swapping one for the other is an equivalent mutation
    // and this test stays green. The expression was changed for clarity. What
    // actually fixes the blank page is the paragraph below it, and deleting
    // *that* is what turns this test red.
    signedInAs({ name: "Mia Thompson", email: "student@example.com" });

    expect(screen.getByText(/does not have access to any of it/i)).toBeTruthy();
  });

  it("offers no ticket queue card to somebody with neither role", () => {
    // And the regression before that one: with only two branches, everybody
    // who was not an admin fell into the support branch and got a card that
    // answers 403.
    signedInAs({ name: "Mia Thompson", email: "student@example.com" });

    expect(screen.queryByText("Ticket queue")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Support" })).toBeNull();
  });
});
