import { describe, it, expect } from "vitest";
import {
  assignTrack,
  buildGroups,
  scoreGroup,
  type StudentInput,
} from "./student.js";

function student(overrides: Partial<StudentInput> & { id: string }): StudentInput {
  return {
    id: overrides.id,
    region: overrides.region ?? "AUS-NSW",
    country: overrides.country ?? "AU",
    timezoneOffsetHours: overrides.timezoneOffsetHours ?? 10,
    yearLevel: overrides.yearLevel ?? 10,
    interests: overrides.interests ?? ["math"],
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
