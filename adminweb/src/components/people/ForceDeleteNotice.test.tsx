import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ForceDeleteNotice } from "./ForceDeleteNotice";

/**
 * The sentence an admin reads before destroying somebody's content, pinned
 * word for word.
 *
 * It is written out here rather than imported from the component, because
 * comparing the component against itself would pass whatever it said. What
 * this guards is not the wording as such — it is that the wording keeps
 * naming support tickets. It stopped doing that once already: tickets were
 * added to the purge and all seven copies of this list stayed as they were,
 * so the checkbox promised to delete four things and deleted five.
 */
describe("the force delete notice", () => {
  it("names support tickets, which the purge destroys", () => {
    render(<ForceDeleteNotice subject="user" />);

    const notice = screen.getByText(/Force delete/).textContent ?? "";
    expect(notice).toContain("any support ticket they raised");
    // Not just the ticket: an agent's replies and internal notes go with it,
    // and those belong to work somebody else is doing.
    expect(notice).toContain("internal notes support staff wrote on it");
  });

  it("still names everything it named before tickets were added", () => {
    render(<ForceDeleteNotice subject="user" />);

    const notice = screen.getByText(/Force delete/).textContent ?? "";
    for (const item of [
      "chat messages",
      "uploaded resources",
      "workshops",
      "match runs",
    ]) {
      expect(notice).toContain(item);
    }
  });

  it("says whose content it is, on each of the three pages that use it", () => {
    // Three People pages share this sentence and each names its own subject.
    // A single hardcoded noun would have read "each user's" on the students
    // page, which is where most tickets come from.
    for (const subject of ["user", "supervisor", "student"] as const) {
      const { unmount } = render(<ForceDeleteNotice subject={subject} />);
      expect(screen.getByText(/Force delete/).textContent).toContain(
        `each ${subject}'s`,
      );
      unmount();
    }
  });
});
