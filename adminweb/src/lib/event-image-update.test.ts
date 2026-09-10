import { describe, expect, it } from "vitest";

import { buildEventUpdateWithImageIntent } from "./event-image-update";

describe("buildEventUpdateWithImageIntent", () => {
  it("omits a null image value when the image was not removed", () => {
    const result = buildEventUpdateWithImageIntent(
      { eventName: "Renamed event", eventImage: null },
      false,
    );

    expect(result).toEqual({ eventName: "Renamed event" });
    expect(result).not.toHaveProperty("eventImage");
  });

  it("sends null only after an explicit remove action", () => {
    const result = buildEventUpdateWithImageIntent(
      { eventName: "Renamed event" },
      true,
    );

    expect(result).toEqual({
      eventName: "Renamed event",
      eventImage: null,
    });
  });

  it("omits the image field while a replacement upload is pending", () => {
    const result = buildEventUpdateWithImageIntent(
      { eventName: "Renamed event", eventImage: null },
      false,
    );

    expect(result).not.toHaveProperty("eventImage");
  });
});
