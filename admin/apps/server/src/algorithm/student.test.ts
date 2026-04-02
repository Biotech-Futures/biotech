import { describe, it, expect } from "vitest";
import {
  assignTrack,
  buildGroups,
  formatRecommendationInput,
  recommendGroupsByTrack,
  scoreGroup,
  type ExistingGroupInput,
  type ExistingGroupMemberInput,
  type GroupStudentSource,
  type IndividualStudentSource,
  type RecommendationInputByTrack,
  type StudentInput,
} from "./student.js";

function student(overrides: Partial<StudentInput> & { id: string }): StudentInput {
  return {
    id: overrides.id,
    name: overrides.name ?? overrides.id,
    region: overrides.region ?? "AUS-NSW",
    trackId: overrides.trackId,
    country: overrides.country ?? "AU",
    timezoneOffsetHours: overrides.timezoneOffsetHours ?? 10,
    yearLevel: overrides.yearLevel ?? 10,
    interests: overrides.interests ?? ["math"],
  };
}

function member(
  overrides: Partial<ExistingGroupMemberInput> & { id: string },
): ExistingGroupMemberInput {
  return {
    id: overrides.id,
    name: overrides.name ?? overrides.id,
    trackId: overrides.trackId,
    country: overrides.country ?? "AU",
    timezoneOffsetHours: overrides.timezoneOffsetHours ?? 10,
    yearLevel: overrides.yearLevel ?? 10,
    interests: overrides.interests ?? ["math"],
  };
}

function group(
  overrides: Partial<ExistingGroupInput> & {
    id: string | number;
    trackId: ExistingGroupInput["trackId"];
    groupStudent: ExistingGroupMemberInput[];
  },
): ExistingGroupInput {
  return {
    id: overrides.id,
    groupName: overrides.groupName ?? String(overrides.id),
    trackId: overrides.trackId,
    groupStudent: overrides.groupStudent,
    maxSize: overrides.maxSize,
  };
}

describe("assignTrack", () => {
  it("maps known region tracks and defaults others to GLOBAL", () => {
    expect(assignTrack("AUS-NSW")).toBe("AUS-NSW");
    expect(assignTrack("AUS-QLD")).toBe("AUS-QLD");
    expect(assignTrack("AUS-VIC")).toBe("AUS-VIC");
    expect(assignTrack("AUS-WA")).toBe("AUS-WA");
    expect(assignTrack("BRA")).toBe("BRA");
    expect(assignTrack("USA-CA")).toBe("GLOBAL");
  });
});

describe("buildGroups", () => {
  it("does not cross tracks", () => {
    const input: StudentInput[] = [
      student({ id: "a1", region: "AUS-NSW", interests: ["math"] }),
      student({ id: "a2", region: "AUS-NSW", interests: ["math"] }),
      student({
        id: "g1",
        region: "USA-CA",
        country: "US",
        timezoneOffsetHours: -8,
        interests: ["math"],
      }),
      student({
        id: "g2",
        region: "USA-NY",
        country: "US",
        timezoneOffsetHours: -5,
        interests: ["math"],
      }),
    ];

    const result = buildGroups(input);
    expect(result.groups).toHaveLength(2);
    expect(result.groups.map((group) => group.track).sort()).toEqual([
      "AUS-NSW",
      "GLOBAL",
    ]);
  });

  it("keeps students unmatched when mandatory overlap cannot be satisfied", () => {
    const input: StudentInput[] = [
      student({ id: "s1", interests: ["math"] }),
      student({ id: "s2", interests: ["science"] }),
      student({ id: "s3", interests: ["history"] }),
    ];

    const result = buildGroups(input);
    expect(result.groups).toHaveLength(0);
    expect(result.unmatchedStudentIds).toEqual(["s1", "s2", "s3"]);
    expect(result.unmatchedStudentReasons).toHaveLength(3);
    expect(
      result.unmatchedStudentReasons.every(
        (item) => item.reasonCode === "NO_SHARED_INTEREST_IN_TRACK",
      ),
    ).toBe(true);
    expect(
      result.unmatchedStudentReasons.every((item) => item.score === 0),
    ).toBe(true);
  });

  it("region tracks prioritize lower year spread", () => {
    const input: StudentInput[] = [
      student({ id: "s1", interests: ["math"], yearLevel: 7 }),
      student({ id: "s2", interests: ["math"], yearLevel: 8 }),
      student({ id: "s3", interests: ["math"], yearLevel: 12 }),
    ];

    const result = buildGroups(input);
    expect(result.groups).toHaveLength(1);
    expect(result.groups[0].studentIds).toEqual(["s1", "s2"]);
    expect(result.unmatchedStudentIds).toEqual(["s3"]);
  });

  it("global scoring prefers same country, then timezone, then year", () => {
    const nearTimeDiffCountry = scoreGroup(
      [
        student({
          id: "g1",
          region: "USA-CA",
          country: "US",
          timezoneOffsetHours: -8,
          yearLevel: 10,
          interests: ["math"],
        }),
        student({
          id: "g2",
          region: "MEX",
          country: "MX",
          timezoneOffsetHours: -7,
          yearLevel: 10,
          interests: ["math"],
        }),
      ],
      "GLOBAL",
    );

    const sameCountryLargeTimezone = scoreGroup(
      [
        student({
          id: "g3",
          region: "USA-CA",
          country: "US",
          timezoneOffsetHours: -8,
          yearLevel: 10,
          interests: ["math"],
        }),
        student({
          id: "g4",
          region: "USA-NY",
          country: "US",
          timezoneOffsetHours: -5,
          yearLevel: 10,
          interests: ["math"],
        }),
      ],
      "GLOBAL",
    );

    expect(nearTimeDiffCountry).not.toBeNull();
    expect(sameCountryLargeTimezone).not.toBeNull();
    expect(sameCountryLargeTimezone!.qualityScore).toBeGreaterThan(
      nearTimeDiffCountry!.qualityScore,
    );
  });

  it("prefers larger valid groups when quality is close", () => {
    const input: StudentInput[] = [
      student({ id: "s1", interests: ["math"], yearLevel: 10 }),
      student({ id: "s2", interests: ["math"], yearLevel: 10 }),
      student({ id: "s3", interests: ["math"], yearLevel: 10 }),
      student({ id: "s4", interests: ["math"], yearLevel: 10 }),
    ];

    const result = buildGroups(input);
    expect(result.groups).toHaveLength(1);
    expect(result.groups[0].groupSize).toBe(4);
    expect(result.groups[0].studentIds).toEqual(["s1", "s2", "s3", "s4"]);
  });

  it("does not prefer larger groups when quality degradation is high", () => {
    const input: StudentInput[] = [
      student({ id: "s1", interests: ["math"], yearLevel: 10 }),
      student({ id: "s2", interests: ["math"], yearLevel: 10 }),
      student({ id: "s3", interests: ["math"], yearLevel: 10 }),
      student({ id: "s4", interests: ["math"], yearLevel: 12 }),
      student({ id: "s5", interests: ["math"], yearLevel: 12 }),
    ];

    const result = buildGroups(input);
    expect(result.groups.length).toBeGreaterThan(0);

    const bestGroup = result.groups[0];
    expect(bestGroup.groupSize).toBeLessThan(5);
  });

  it("returns deterministic output for equal-score candidates", () => {
    const input: StudentInput[] = [
      student({ id: "s1", interests: ["math"], yearLevel: 10 }),
      student({ id: "s2", interests: ["math"], yearLevel: 10 }),
      student({ id: "s3", interests: ["math"], yearLevel: 10 }),
      student({ id: "s4", interests: ["math"], yearLevel: 10 }),
    ];

    const run1 = buildGroups(input);
    const run2 = buildGroups(input);
    expect(run1).toEqual(run2);
  });

  it("marks leftover single student as unmatched", () => {
    const input: StudentInput[] = [
      student({ id: "s1", interests: ["math"] }),
      student({ id: "s2", interests: ["math"] }),
      student({ id: "s3", interests: ["history"] }),
    ];

    const result = buildGroups(input);
    expect(result.groups).toHaveLength(1);
    expect(result.unmatchedStudentIds).toEqual(["s3"]);
    expect(result.unmatchedStudentReasons).toHaveLength(1);
    expect(result.unmatchedStudentReasons[0].studentId).toBe("s3");
    expect(result.unmatchedStudentReasons[0].reasonCode).toBe(
      "NO_SHARED_INTEREST_IN_TRACK",
    );
    expect(result.unmatchedStudentReasons[0].scoreBreakdown.baseScore).toBe(100);
    expect(result.unmatchedStudentReasons[0].scoreBreakdown.totalPenalty).toBe(100);
  });

  it("assigns all students when valid groups exist for all of them", () => {
    const input: StudentInput[] = [
      student({ id: "a1", interests: ["math"], region: "AUS-NSW" }),
      student({ id: "a2", interests: ["math"], region: "AUS-NSW" }),
      student({ id: "a3", interests: ["math"], region: "AUS-NSW" }),
      student({
        id: "g1",
        interests: ["robotics"],
        region: "USA-CA",
        country: "US",
        timezoneOffsetHours: -8,
      }),
      student({
        id: "g2",
        interests: ["robotics"],
        region: "USA-NY",
        country: "US",
        timezoneOffsetHours: -5,
      }),
    ];

    const result = buildGroups(input);
    const groupedIds = new Set(result.groups.flatMap((group) => group.studentIds));

    expect(result.unmatchedStudentIds).toEqual([]);
    expect(result.unmatchedStudentReasons).toEqual([]);
    expect(groupedIds).toEqual(new Set(input.map((s) => s.id)));
  });

  it("returns per-student score entries for grouped students", () => {
    const input: StudentInput[] = [
      student({ id: "s1", interests: ["math"], yearLevel: 10 }),
      student({ id: "s2", interests: ["math"], yearLevel: 11 }),
    ];

    const result = buildGroups(input);
    expect(result.groups).toHaveLength(1);
    expect(result.studentScores).toHaveLength(2);
    expect(result.studentScores.map((s) => s.studentId).sort()).toEqual([
      "s1",
      "s2",
    ]);
  });
});

describe("recommendGroupsByTrack", () => {
  it("only recommends groups in the same track", () => {
    const input: RecommendationInputByTrack = {
      "AUS-NSW": {
        students: [student({ id: "s1", region: "AUS-NSW", interests: ["math"] })],
        groups: [
          group({
            id: "nsw-1",
            trackId: "AUS-NSW",
            groupStudent: [member({ id: "m1", interests: ["math"], yearLevel: 10 })],
          }),
          group({
            id: "global-1",
            trackId: "GLOBAL",
            groupStudent: [member({ id: "m2", country: "US", interests: ["math"] })],
          }),
        ],
      },
    };

    const result = recommendGroupsByTrack(input);
    expect(result).toHaveLength(1);
    expect(result[0].recommendGroup?.id).toBe("nsw-1");
  });

  it("rejects groups with no shared interest overlap", () => {
    const input: RecommendationInputByTrack = {
      "AUS-NSW": {
        students: [student({ id: "s1", region: "AUS-NSW", interests: ["biology"] })],
        groups: [
          group({
            id: "nsw-1",
            trackId: "AUS-NSW",
            groupStudent: [member({ id: "m1", interests: ["math"] })],
          }),
        ],
      },
    };

    const result = recommendGroupsByTrack(input);
    expect(result[0].recommendGroup).toBeNull();
    expect(result[0].score).toBe(0);
    expect(result[0].reason).toContain("common interest");
  });

  it("prefers closer year level within a region track", () => {
    const input: RecommendationInputByTrack = {
      "AUS-NSW": {
        students: [student({ id: "s1", region: "AUS-NSW", yearLevel: 10 })],
        groups: [
          group({
            id: "near-year",
            trackId: "AUS-NSW",
            groupStudent: [member({ id: "m1", interests: ["math"], yearLevel: 10 })],
          }),
          group({
            id: "far-year",
            trackId: "AUS-NSW",
            groupStudent: [member({ id: "m2", interests: ["math"], yearLevel: 12 })],
          }),
        ],
      },
    };

    const result = recommendGroupsByTrack(input);
    expect(result[0].recommendGroup?.id).toBe("near-year");
  });

  it("prefers same country over cross-country in global track", () => {
    const input: RecommendationInputByTrack = {
      GLOBAL: {
        students: [
          student({
            id: "s1",
            region: "USA-CA",
            country: "US",
            timezoneOffsetHours: -8,
            interests: ["math"],
          }),
        ],
        groups: [
          group({
            id: "same-country",
            trackId: "GLOBAL",
            groupStudent: [
              member({
                id: "m1",
                country: "US",
                timezoneOffsetHours: -5,
                interests: ["math"],
              }),
            ],
          }),
          group({
            id: "cross-country",
            trackId: "GLOBAL",
            groupStudent: [
              member({
                id: "m2",
                country: "MX",
                timezoneOffsetHours: -7,
                interests: ["math"],
              }),
            ],
          }),
        ],
      },
    };

    const result = recommendGroupsByTrack(input);
    expect(result[0].recommendGroup?.id).toBe("same-country");
  });

  it("prefers smaller timezone gap when countries differ in global track", () => {
    const input: RecommendationInputByTrack = {
      GLOBAL: {
        students: [
          student({
            id: "s1",
            region: "USA-CA",
            country: "US",
            timezoneOffsetHours: -8,
            interests: ["robotics"],
          }),
        ],
        groups: [
          group({
            id: "near-timezone",
            trackId: "GLOBAL",
            groupStudent: [
              member({
                id: "m1",
                country: "CA",
                timezoneOffsetHours: -7,
                interests: ["robotics"],
              }),
            ],
          }),
          group({
            id: "far-timezone",
            trackId: "GLOBAL",
            groupStudent: [
              member({
                id: "m2",
                country: "BR",
                timezoneOffsetHours: -3,
                interests: ["robotics"],
              }),
            ],
          }),
        ],
      },
    };

    const result = recommendGroupsByTrack(input);
    expect(result[0].recommendGroup?.id).toBe("near-timezone");
  });

  it("adds a size bonus for larger non-full groups when quality is close", () => {
    const input: RecommendationInputByTrack = {
      "AUS-NSW": {
        students: [student({ id: "s1", region: "AUS-NSW", yearLevel: 10 })],
        groups: [
          group({
            id: "small",
            trackId: "AUS-NSW",
            groupStudent: [member({ id: "m1", yearLevel: 10, interests: ["math"] })],
          }),
          group({
            id: "large",
            trackId: "AUS-NSW",
            groupStudent: [
              member({ id: "m2", yearLevel: 10, interests: ["math"] }),
              member({ id: "m3", yearLevel: 10, interests: ["math"] }),
              member({ id: "m4", yearLevel: 10, interests: ["math"] }),
            ],
          }),
        ],
      },
    };

    const result = recommendGroupsByTrack(input);
    expect(result[0].recommendGroup?.id).toBe("large");
    expect(result[0].scoreBreakdown.sizeBonus).toBe(5);
  });

  it("does not prefer larger groups when quality is materially worse", () => {
    const input: RecommendationInputByTrack = {
      "AUS-NSW": {
        students: [student({ id: "s1", region: "AUS-NSW", yearLevel: 10 })],
        groups: [
          group({
            id: "small-close",
            trackId: "AUS-NSW",
            groupStudent: [member({ id: "m1", yearLevel: 10, interests: ["math"] })],
          }),
          group({
            id: "large-far",
            trackId: "AUS-NSW",
            groupStudent: [
              member({ id: "m2", yearLevel: 12, interests: ["math"] }),
              member({ id: "m3", yearLevel: 12, interests: ["math"] }),
              member({ id: "m4", yearLevel: 12, interests: ["math"] }),
            ],
          }),
        ],
      },
    };

    const result = recommendGroupsByTrack(input);
    expect(result[0].recommendGroup?.id).toBe("small-close");
  });

  it("ignores full groups", () => {
    const input: RecommendationInputByTrack = {
      "AUS-NSW": {
        students: [student({ id: "s1", region: "AUS-NSW", interests: ["math"] })],
        groups: [
          group({
            id: "full-group",
            trackId: "AUS-NSW",
            groupStudent: [
              member({ id: "m1" }),
              member({ id: "m2" }),
              member({ id: "m3" }),
              member({ id: "m4" }),
              member({ id: "m5" }),
            ],
          }),
        ],
      },
    };

    const result = recommendGroupsByTrack(input);
    expect(result[0].recommendGroup).toBeNull();
    expect(result[0].reason).toContain("full");
  });

  it("returns null recommendation with clear reason when no valid group exists", () => {
    const input: RecommendationInputByTrack = {
      "AUS-NSW": {
        students: [student({ id: "s1", region: "AUS-NSW", interests: ["history"] })],
        groups: [
          group({
            id: "nsw-1",
            trackId: "AUS-NSW",
            groupStudent: [member({ id: "m1", interests: ["math"] })],
          }),
        ],
      },
    };

    const result = recommendGroupsByTrack(input);
    expect(result[0]).toMatchObject({
      recommendGroup: null,
      score: 0,
    });
    expect(result[0].reason).toContain("common interest");
  });

  it("returns deterministic output for equal-score candidates", () => {
    const input: RecommendationInputByTrack = {
      "AUS-NSW": {
        students: [student({ id: "s1", region: "AUS-NSW", yearLevel: 10 })],
        groups: [
          group({
            id: "a-group",
            trackId: "AUS-NSW",
            groupStudent: [member({ id: "m1", yearLevel: 10, interests: ["math"] })],
          }),
          group({
            id: "b-group",
            trackId: "AUS-NSW",
            groupStudent: [member({ id: "m2", yearLevel: 10, interests: ["math"] })],
          }),
        ],
      },
    };

    const run1 = recommendGroupsByTrack(input);
    const run2 = recommendGroupsByTrack(input);
    expect(run1).toEqual(run2);
    expect(run1[0].recommendGroup?.id).toBe("a-group");
  });

  it("returns score breakdown with expected penalties and objective score", () => {
    const input: RecommendationInputByTrack = {
      GLOBAL: {
        students: [
          student({
            id: "s1",
            region: "USA-CA",
            country: "US",
            timezoneOffsetHours: -8,
            yearLevel: 10,
            interests: ["math"],
          }),
        ],
        groups: [
          group({
            id: "g1",
            trackId: "GLOBAL",
            groupStudent: [
              member({
                id: "m1",
                country: "MX",
                timezoneOffsetHours: -5,
                yearLevel: 12,
                interests: ["math"],
              }),
            ],
          }),
        ],
      },
    };

    const result = recommendGroupsByTrack(input);
    expect(result[0].scoreBreakdown).toEqual({
      baseScore: 100,
      yearPenalty: 12,
      countryPenalty: 12,
      timezonePenalty: 6,
      sizeBonus: 0,
      totalPenalty: 30,
      objectiveScore: 70,
    });
    expect(result[0].score).toBe(70);
  });
});

describe("formatRecommendationInput", () => {
  it("formats raw groupStudents and individualStudents into recommendation input", () => {
    const groupStudents: GroupStudentSource[] = [
      {
        groupId: 101,
        groupName: "NSW Alpha",
        groupTrackCode: "AUS-NSW",
        userId: 1,
        firstName: "Ann",
        lastName: "Lee",
        yearLevel: 10,
        countryName: "AU",
        timezoneOffsetHours: 10,
        interests: ["math", { interestDesc: "biology" }],
      },
      {
        groupId: 101,
        groupName: "NSW Alpha",
        groupTrackCode: "AUS-NSW",
        userId: 2,
        firstName: "Ben",
        lastName: "Ng",
        yearLevel: 10,
        countryName: "AU",
        timezoneOffsetHours: 10,
        interests: [{ interestDesc: "math" }],
      },
      {
        groupId: 202,
        groupName: "Global Beta",
        groupTrackCode: "GLOBAL",
        userId: 3,
        firstName: "Cara",
        lastName: "Diaz",
        yearLevel: 11,
        countryName: "US",
        timezoneOffsetHours: -8,
        interests: ["robotics"],
      },
    ];

    const individualStudents: IndividualStudentSource[] = [
      {
        userId: 11,
        firstName: "Dana",
        lastName: "Wu",
        trackCode: "AUS-NSW",
        yearLevel: 10,
        countryName: "AU",
        timezoneOffsetHours: 10,
        interests: [{ interestDesc: "math" }],
      },
      {
        userId: 12,
        firstName: "Eli",
        lastName: "Brown",
        region: "USA-CA",
        yearLevel: 11,
        countryName: "US",
        timezoneOffsetHours: -8,
        interests: ["robotics"],
      },
    ];

    const result = formatRecommendationInput(groupStudents, individualStudents);

    expect(Object.keys(result).sort()).toEqual(["AUS-NSW", "GLOBAL"]);
    expect(result["AUS-NSW"]?.groups).toHaveLength(1);
    expect(result["AUS-NSW"]?.groups[0]).toMatchObject({
      id: 101,
      groupName: "NSW Alpha",
      trackId: "AUS-NSW",
    });
    expect(result["AUS-NSW"]?.groups[0].groupStudent).toHaveLength(2);
    expect(result["AUS-NSW"]?.students[0]).toMatchObject({
      id: 11,
      name: "Dana Wu",
      trackId: "AUS-NSW",
      interests: ["math"],
    });
    expect(result.GLOBAL?.groups).toHaveLength(1);
    expect(result.GLOBAL?.students[0]).toMatchObject({
      id: 12,
      name: "Eli Brown",
      interests: ["robotics"],
    });
  });
});
