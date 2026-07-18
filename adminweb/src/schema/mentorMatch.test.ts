import { describe, expect, it } from "vitest";
import {
  matchedGroupsResponseSchema,
  mentorListResponseSchema,
  unmatchedGroupsResponseSchema,
} from "./mentorMatch";

// The backend derives a group's country from its students' states (_modal_country) and
// returns null when none are known — an empty group, or students with no state set.
// A non-nullable countryName here fails the whole array and silently empties the tab.

describe("mentorMatch schemas tolerate a null countryName", () => {
  it("accepts unmatched groups with no known country", () => {
    const parsed = unmatchedGroupsResponseSchema.parse({
      data: [
        {
          groupId: 1,
          groupName: "BTF_C7f3a9b2c1d4e5f6a7b8c9d0e1f2a3b4c",
          countryName: null,
          studentInterests: [],
          studentCount: 0,
        },
        {
          groupId: 2,
          groupName: "Group with a country",
          countryName: "Australia",
          studentInterests: ["Genomics"],
          studentCount: 3,
        },
      ],
    });

    expect(parsed.data).toHaveLength(2);
    expect(parsed.data[0].countryName).toBeNull();
  });

  it("accepts a mentor with no known country", () => {
    const parsed = mentorListResponseSchema.parse({
      data: [
        {
          mentorId: 10,
          name: "Steph Yee",
          countryName: null,
          institution: "Publicis CoLab",
          interests: [],
          maxGroupCount: 2,
          currentAssignedCount: 0,
          remainingCapacity: 2,
        },
      ],
    });

    expect(parsed.data[0].countryName).toBeNull();
  });

  it("accepts matched groups where neither group nor mentor has a country", () => {
    const parsed = matchedGroupsResponseSchema.parse({
      data: [
        {
          membershipId: 5,
          groupId: 1,
          groupName: "Matched group",
          countryName: null,
          studentCount: 4,
          students: [],
          mentor: {
            mentorId: 10,
            name: "Yuan Chen",
            isActive: true,
            countryName: null,
            institution: null,
          },
        },
      ],
    });

    expect(parsed.data[0].countryName).toBeNull();
    expect(parsed.data[0].mentor.countryName).toBeNull();
  });
});
