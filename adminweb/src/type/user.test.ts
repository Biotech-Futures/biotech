import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import {
  ROLES_WITHOUT_GEOGRAPHY,
  USER_ROLES,
  roleHasGeography,
} from "./user";

/**
 * The role lists this app shares with the backend.
 *
 * Two of them are the same rule written twice, once per language, and there
 * is no type system spanning the gap. That is exactly how the last defect
 * here happened: "support" was added to the create path's exemption in
 * apps/admin/services/user.py and not to the update path's, so an admin could
 * make a support agent and then never save one again — the editor sent
 * `countryId: null` and the server answered "Country cannot be cleared".
 *
 * The backend was then consolidated onto one constant,
 * `ROLES_WITHOUT_GEOGRAPHY`, and pinned by a test. This file is the other
 * half. Without it, adding a role to the list below passes every React test
 * and typecheck while every save of that role 400s in production — the same
 * defect, one language along.
 *
 * The backend file is read as text rather than reimplemented. A hand-copied
 * expectation would be a third copy of the rule, and a third copy is a third
 * thing to drift.
 */
const backendSource = readFileSync(
  resolve(__dirname, "../../../backend/apps/admin/services/user.py"),
  "utf8",
);

function backendList(name: string): string[] {
  // ROLES_WITHOUT_GEOGRAPHY = ("admin", "support")
  const match = backendSource.match(
    new RegExp(`^${name}\\s*=\\s*[\\(\\[]([^\\)\\]]*)[\\)\\]]`, "m"),
  );
  if (!match) {
    throw new Error(
      `${name} was not found in backend/apps/admin/services/user.py. If it ` +
        "was renamed or moved, this test has to follow it rather than be " +
        "deleted — it is the only thing keeping the two languages in step.",
    );
  }
  return [...match[1].matchAll(/["']([^"']+)["']/g)].map((m) => m[1]);
}

describe("the roles that carry no geography", () => {
  it("is the same list the backend exempts", () => {
    expect([...ROLES_WITHOUT_GEOGRAPHY].sort()).toEqual(
      backendList("ROLES_WITHOUT_GEOGRAPHY").sort(),
    );
  });

  it("exempts admin and support, and nobody else", () => {
    // Spelled out as well as compared, so a change that edits both files at
    // once still has to be a deliberate one.
    expect([...ROLES_WITHOUT_GEOGRAPHY].sort()).toEqual(["admin", "support"]);
  });

  it("roleHasGeography is the inverse of that list", () => {
    for (const role of USER_ROLES) {
      expect(roleHasGeography(role)).toBe(
        !ROLES_WITHOUT_GEOGRAPHY.includes(role),
      );
    }
  });

  it("every role the editor offers is one the backend knows", () => {
    // ROLES is the backend's list of every role the platform has. It was
    // missing "support" for two months after the role shipped, and this test
    // used to paper over that by appending the word itself — which made the
    // assertion true whatever ROLES said. Read as it is now.
    const backendRoles = backendList("ROLES");
    for (const role of USER_ROLES) {
      expect(backendRoles).toContain(role);
    }
  });

  it("the roles a spreadsheet may create are fewer than the roles that exist", () => {
    /* The one a bulk upload must not reach. Both endpoints that import users
     * meet in add_users_by_role, and the list they are held to is this one —
     * a CSV that could set role=support would hand queue access, on a platform
     * whose users are minors, to as many accounts as it had rows.
     *
     * Written out rather than derived, and asserted against the backend
     * source, so that widening either side has to be done in both places. */
    const importable = backendList("BULK_IMPORTABLE_ROLES");
    expect(importable.sort()).toEqual(["mentor", "student", "supervisor"]);
    expect(importable).not.toContain("support");
    expect(importable).not.toContain("admin");
  });
});
