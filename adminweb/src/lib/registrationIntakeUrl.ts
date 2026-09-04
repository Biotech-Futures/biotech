export type RegistrationIntakeUrlResult =
  | { status: "configured"; url: string }
  | { status: "unconfigured" }
  | { status: "invalid" };

export function resolveRegistrationIntakeUrl(
  configuredValue: string | undefined,
): RegistrationIntakeUrlResult {
  const value = configuredValue?.trim();
  if (!value) {
    return { status: "unconfigured" };
  }

  try {
    const url = new URL(value);
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return { status: "invalid" };
    }

    return { status: "configured", url: url.toString() };
  } catch {
    return { status: "invalid" };
  }
}
