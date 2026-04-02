import type { StudentGroupRecommendation } from "@/algorithm/student.js";

type DemoIndividualStudent = {
  userId: number;
  firstName: string;
  lastName: string;
  trackId: number;
  trackCode: string;
  yearLevel: number | null;
  countryName: string;
};

export const demoIndividualStudents: DemoIndividualStudent[] = [
  {
    userId: 1001,
    firstName: "Mia",
    lastName: "Johnson",
    trackId: 11,
    trackCode: "AUS-NSW",
    yearLevel: 10,
    countryName: "Australia",
  },
  {
    userId: 1002,
    firstName: "Noah",
    lastName: "Lee",
    trackId: 11,
    trackCode: "AUS-NSW",
    yearLevel: 11,
    countryName: "Australia",
  },
  {
    userId: 1003,
    firstName: "Sofia",
    lastName: "Silva",
    trackId: 51,
    trackCode: "GLOBAL",
    yearLevel: 12,
    countryName: "Brazil",
  },
  {
    userId: 1004,
    firstName: "Ethan",
    lastName: "Miller",
    trackId: 51,
    trackCode: "GLOBAL",
    yearLevel: 12,
    countryName: "United States",
  },
];

export const demoMatchRecommendations: StudentGroupRecommendation[] = [
  {
    student: {
      id: 1001,
      name: "Mia Johnson",
      trackId: "AUS-NSW",
      country: "Australia",
      timezoneOffsetHours: 10,
      yearLevel: 10,
      interests: ["biology", "genetics", "medicine"],
    },
    recommendGroup: {
      id: 201,
      groupName: "NSW Bio Group A",
      trackId: "AUS-NSW",
      tutor: {
        id: 501,
        name: "Dr Alice Carter",
      },
      maxSize: 5,
      groupStudent: [
        {
          id: 3003,
          name: "Ivy Wong",
          trackId: "AUS-NSW",
          country: "Australia",
          timezoneOffsetHours: 10,
          yearLevel: 10,
          interests: ["biology", "genetics"],
        },
        {
          id: 3002,
          name: "Liam Patel",
          trackId: "AUS-NSW",
          country: "Australia",
          timezoneOffsetHours: 10,
          yearLevel: 11,
          interests: ["medicine", "biology"],
        },
      ],
    },
    reason:
      "Shares interest 'biology' with the group and has a close year level match.",
    score: 92,
    scoreBreakdown: {
      baseScore: 100,
      yearPenalty: 8,
      countryPenalty: 0,
      timezonePenalty: 0,
      sizeBonus: 3,
      totalPenalty: 8,
      objectiveScore: 95,
    },
  },
  {
    student: {
      id: 1002,
      name: "Noah Lee",
      trackId: "AUS-NSW",
      country: "Australia",
      timezoneOffsetHours: 10,
      yearLevel: 11,
      interests: ["chemistry", "genetics"],
    },
    recommendGroup: {
      id: 202,
      groupName: "NSW Chem Group B",
      trackId: "AUS-NSW",
      tutor: {
        id: 502,
        name: "Dr Ben Harper",
      },
      maxSize: 4,
      groupStudent: [
        {
          id: 3003,
          name: "Ava Tan",
          trackId: "AUS-NSW",
          country: "Australia",
          timezoneOffsetHours: 10,
          yearLevel: 11,
          interests: ["chemistry", "genetics"],
        },
        {
          id: 3004,
          name: "James Li",
          trackId: "AUS-NSW",
          country: "Australia",
          timezoneOffsetHours: 10,
          yearLevel: 11,
          interests: ["chemistry", "data science"],
        },
        {
          id: 3005,
          name: "Chloe Singh",
          trackId: "AUS-NSW",
          country: "Australia",
          timezoneOffsetHours: 10,
          yearLevel: 10,
          interests: ["genetics", "chemistry"],
        },
      ],
    },
    reason:
      "Shares interest 'chemistry' with the group and has a close year level match.",
    score: 94,
    scoreBreakdown: {
      baseScore: 100,
      yearPenalty: 6,
      countryPenalty: 0,
      timezonePenalty: 0,
      sizeBonus: 0,
      totalPenalty: 6,
      objectiveScore: 94,
    },
  },
  {
    student: {
      id: 1003,
      name: "Sofia Silva",
      trackId: "GLOBAL",
      country: "Brazil",
      timezoneOffsetHours: -3,
      yearLevel: 12,
      interests: ["oncology", "immunology"],
    },
    recommendGroup: {
      id: 301,
      groupName: "Global Health Group",
      trackId: "GLOBAL",
      tutor: {
        id: 503,
        name: "Prof Elena Rossi",
      },
      maxSize: 5,
      groupStudent: [
        {
          id: 3101,
          name: "Olivia Moore",
          trackId: "GLOBAL",
          country: "Brazil",
          timezoneOffsetHours: -3,
          yearLevel: 12,
          interests: ["oncology", "public health"],
        },
        {
          id: 3102,
          name: "Lucas Pereira",
          trackId: "GLOBAL",
          country: "Brazil",
          timezoneOffsetHours: -3,
          yearLevel: 11,
          interests: ["immunology", "oncology"],
        },
      ],
    },
    reason:
      "Shares interest 'oncology' with the group and matches the same country.",
    score: 96,
    scoreBreakdown: {
      baseScore: 100,
      yearPenalty: 4,
      countryPenalty: 0,
      timezonePenalty: 0,
      sizeBonus: 3,
      totalPenalty: 4,
      objectiveScore: 99,
    },
  },
  {
    student: {
      id: 1004,
      name: "Ethan Miller",
      trackId: "GLOBAL",
      country: "United States",
      timezoneOffsetHours: -7,
      yearLevel: 12,
      interests: ["robotics", "ai"],
    },
    recommendGroup: null,
    reason:
      "No existing non-full group in this track shares a common interest with the student.",
    score: 0,
    scoreBreakdown: {
      baseScore: 100,
      yearPenalty: 0,
      countryPenalty: 0,
      timezonePenalty: 0,
      sizeBonus: 0,
      totalPenalty: 100,
      objectiveScore: 0,
    },
  },
];

export function useMatchDemoData(): boolean {
  return process.env.MATCH_USE_DEMO_DATA === "true";
}
