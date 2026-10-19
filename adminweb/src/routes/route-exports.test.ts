import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { describe, expect, it } from "vitest";

// import.meta.url is not a file: URL under the jsdom environment, so derive
// the directory from Vitest's own notion of the file path instead.
const ROUTES_DIR = dirname(__filename);

function routeFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) return routeFiles(full);
    if (!entry.name.endsWith(".tsx")) return [];
    if (entry.name.includes(".test.") || entry.name.includes(".spec.")) return [];
    return [full];
  });
}

/**
 * A route file may export the Route and nothing else.
 *
 * Any extra export switches off TanStack Router's autoCodeSplitting for that
 * route. This is not hypothetical: exporting two page components from their
 * route files (both times so a test could import them) grew the main chunk
 * from 526 kB to 697 kB, and nothing said so — the build succeeds, the app
 * works, and every visitor pays 170 kB. The fix each time was moving the
 * component to its own file; this test is what makes the third time a red
 * test instead of a silent regression. Same shape as the urlconf test that
 * guards permission_classes: the rule is mechanical, so a machine holds it.
 */
describe("route files", () => {
  it("export the Route and nothing else", () => {
    const offenders: string[] = [];
    for (const file of routeFiles(ROUTES_DIR)) {
      const source = readFileSync(file, "utf8");
      for (const line of source.split("\n")) {
        const isExport = /^export\s/.test(line);
        const isTheRoute = /^export const Route\b/.test(line);
        const isTypeOnly = /^export type\s/.test(line);
        if (isExport && !isTheRoute && !isTypeOnly) {
          offenders.push(`${relative(ROUTES_DIR, file)}: ${line.trim().slice(0, 60)}`);
        }
      }
    }
    expect(
      offenders,
      "OFFENDER: an extra export in a route file disables code splitting " +
        "for that route (measured at 170 kB). Move it to a component file. " +
        offenders.join("; "),
    ).toEqual([]);
  });
});
