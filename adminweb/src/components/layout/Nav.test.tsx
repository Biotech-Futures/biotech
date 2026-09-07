import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// The sidebar primitives need a SidebarProvider and measure the viewport;
// none of that is what these tests are about, so they become plain wrappers.
vi.mock("@/components/ui/sidebar", () => {
  const passthrough =
    (Tag: "div" | "ul" | "li") =>
    ({ children }: { children?: React.ReactNode }) => <Tag>{children}</Tag>;
  return {
    SidebarGroup: passthrough("div"),
    SidebarGroupContent: passthrough("div"),
    SidebarGroupLabel: ({ children }: { children?: React.ReactNode }) => (
      <h2>{children}</h2>
    ),
    SidebarMenu: passthrough("ul"),
    SidebarMenuItem: passthrough("li"),
    SidebarMenuButton: ({ children }: { children?: React.ReactNode }) => (
      <span>{children}</span>
    ),
  };
});

vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children }: { to: string; children: React.ReactNode }) => (
    <a href={to}>{children}</a>
  ),
}));

const useAuthContext = vi.fn();
vi.mock("@/provider/AuthProvider", () => ({
  useAuthContext: () => useAuthContext(),
}));

const { NavMain, NAV_SECTIONS } = await import("./Nav");
const { NAV_SECTIONS: HOME_SECTIONS } = await import(
  "@/components/home/AdminHomePage"
);

const ALL_LABELS = ["Overview", "People", "Groups & Matching", "Content", "Support"];

function sidebarAs(user: Record<string, unknown>) {
  useAuthContext.mockReturnValue({ user });
  render(<NavMain />);
}

/**
 * The home page grid got these tests first and the sidebar got none, which
 * was exactly backwards as a precedent: the sidebar is the copy that was
 * right all along, and nothing would have noticed it going wrong.
 */
describe("sidebar visibility", () => {
  it("shows an admin every section", () => {
    sidebarAs({ isAdmin: true });
    for (const label of ALL_LABELS) {
      expect(screen.getByRole("heading", { name: label })).toBeTruthy();
    }
  });

  it("shows a support agent Overview and Support and nothing else", () => {
    sidebarAs({ isSupport: true });
    expect(screen.getByRole("heading", { name: "Overview" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Support" })).toBeTruthy();
    for (const label of ["People", "Groups & Matching", "Content"]) {
      expect(
        screen.queryByRole("heading", { name: label }),
        `${label} was shown to a support agent`,
      ).toBeNull();
    }
  });

  it("shows somebody with neither role only the way back to the dashboard", () => {
    sidebarAs({});
    expect(screen.getByRole("heading", { name: "Overview" })).toBeTruthy();
    for (const label of ["People", "Groups & Matching", "Content", "Support"]) {
      expect(
        screen.queryByRole("heading", { name: label }),
        `${label} was shown to a user with no role`,
      ).toBeNull();
    }
  });
});

/**
 * Two files each hold a copy of "who sees what" — different copy, same rule.
 * The agreement lived in a comment ("`support` is spelled the same way in
 * both"), and a comment is what allowed the home page to filter for an
 * "Overview" section it does not have and ship a blank page. This is the
 * comment, promoted to a test.
 */
describe("the two NAV_SECTIONS copies", () => {
  it("agree on the support flag for every label they share", () => {
    const sidebarFlags = new Map(
      NAV_SECTIONS.map((s) => [s.label, Boolean(s.support)]),
    );
    for (const section of HOME_SECTIONS) {
      expect(
        sidebarFlags.has(section.label),
        `home section "${section.label}" does not exist in the sidebar`,
      ).toBe(true);
      expect(
        Boolean((section as { support?: boolean }).support),
        `"${section.label}": home and sidebar disagree about who sees it`,
      ).toBe(sidebarFlags.get(section.label));
    }
  });

  it("mark Support, and for the home grid only Support, as support-visible", () => {
    const homeSupport = HOME_SECTIONS.filter(
      (s) => (s as { support?: boolean }).support,
    ).map((s) => s.label);
    expect(homeSupport).toEqual(["Support"]);
    // The sidebar adds Overview on purpose: "/" is where signing in lands
    // an agent, and a sidebar without it strands them.
    const sidebarSupport = NAV_SECTIONS.filter((s) => s.support).map((s) => s.label);
    expect(sidebarSupport).toEqual(["Overview", "Support"]);
  });
});

/**
 * Every page must be reachable from both lists.
 *
 * The three screens added on 2026-09-02 — the support roster, the ticket
 * audit and the p52 dashboard — could have their links deleted from the
 * sidebar *and* the home grid with the whole suite green and typecheck clean.
 * Nobody had opened them in a browser either, so a dropped entry would have
 * left three finished pages that no one could reach and nothing would report.
 *
 * The consistency test above compares labels and the support flag; it does
 * not look inside `items` or `cards`, which is the gap this closes.
 */
describe("every destination is reachable from both lists", () => {
  const REQUIRED = [
    "/tickets",
    "/tickets/audit",
    "/tickets/analytics",
    "/people/support-agents",
  ];

  const sidebarUrls = NAV_SECTIONS.flatMap((s) => s.items.map((i) => i.url));
  const homeUrls = HOME_SECTIONS.flatMap((s) => s.cards.map((c) => c.url));

  it.each(REQUIRED)("the sidebar links to %s", (url) => {
    expect(sidebarUrls).toContain(url);
  });

  it.each(REQUIRED)("the home grid links to %s", (url) => {
    expect(homeUrls).toContain(url);
  });

  it("puts the roster under People, not Support", () => {
    // A support agent must not be offered the screen that grants the role:
    // the Support section carries support: true and is shown to them.
    const support = NAV_SECTIONS.find((s) => s.label === "Support");
    expect(support?.items.map((i) => i.url)).not.toContain("/people/support-agents");
  });

  it("keeps the queue and its two sub-pages in the Support section", () => {
    const support = NAV_SECTIONS.find((s) => s.label === "Support");
    expect(support?.items.map((i) => i.url)).toEqual([
      "/tickets",
      "/tickets/audit",
      "/tickets/analytics",
    ]);
  });
});
