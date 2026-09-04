import { describe, expect, it } from "vitest";
import { resolveRegistrationIntakeUrl } from "./registrationIntakeUrl";
import { PEOPLE_TABS } from "@/routes/_auth/people/-peopleTabs";

describe("resolveRegistrationIntakeUrl", () => {
  it("normalizes configured HTTP and HTTPS URLs", () => {
    expect(
      resolveRegistrationIntakeUrl(
        " http://127.0.0.1:5174/#/supervisor/registration/embed ",
      ),
    ).toEqual({
      status: "configured",
      url: "http://127.0.0.1:5174/#/supervisor/registration/embed",
    });
    expect(
      resolveRegistrationIntakeUrl(
        "https://registration.example.org/supervisor/embed",
      ),
    ).toEqual({
      status: "configured",
      url: "https://registration.example.org/supervisor/embed",
    });
  });

  it("reports blank configuration separately", () => {
    expect(resolveRegistrationIntakeUrl(undefined)).toEqual({
      status: "unconfigured",
    });
    expect(resolveRegistrationIntakeUrl("   ")).toEqual({
      status: "unconfigured",
    });
  });

  it("rejects invalid and non-web protocols", () => {
    expect(resolveRegistrationIntakeUrl("not a URL")).toEqual({
      status: "invalid",
    });
    expect(resolveRegistrationIntakeUrl("javascript:alert(1)")).toEqual({
      status: "invalid",
    });
    expect(resolveRegistrationIntakeUrl("ftp://example.org/intake")).toEqual({
      status: "invalid",
    });
  });
});

describe("People registration navigation", () => {
  it("exposes registration as a route-backed People tab", () => {
    expect(PEOPLE_TABS).toContainEqual({
      label: "Registration",
      to: "/people/registration",
    });
  });
});
