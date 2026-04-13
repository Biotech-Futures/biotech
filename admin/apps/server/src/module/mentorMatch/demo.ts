import type { GroupSource, MentorSource } from "@/algorithm/mentor.js";

/**
 * Demo data for MATCH_USE_DEMO_DATA=true.
 *
 * Mode differences visible in the UI:
 *
 * Strict    – 4 matched / 3 unmatched.
 *             G4 (AUS-QLD), G6 (AUS-VIC), G7 (AUS-SA) have no same-track mentor.
 *             M4 (GLOBAL, capacity=1) can only absorb one of them — G5 wins
 *             because its data-science interests best match M4.
 *             G4, G6, G7 are left with "No suitable mentor."
 *
 * Balanced  – All 7 matched via single-pass Gale-Shapley.
 *             G4 → M1 (cross-track, genetics overlap, score ~96)
 *             G6 → M1 (cross-track, medicine overlap, score ~76)
 *             G7 → M3 (cross-track, zero interest overlap, score ~58) ← "basically unmatched"
 *
 * Coverage  – All 7 matched via two-phase algorithm (same result as Balanced
 *             with these weights; phase-2 fallback explicitly covers G4/G6/G7).
 *             G7 again ends up with M3 at score ~58, illustrating that coverage
 *             forces a match even when no good option exists.
 *
 * Note: Balanced and Coverage produce the same final assignments because the
 * track-mismatch penalty (40 pts) always exceeds the max interest bonus (30 pts),
 * so same-track groups naturally win their same-track mentors in both modes.
 * The conceptual difference is the two-phase prioritisation in Coverage.
 */

export const demoMentors: MentorSource[] = [
  {
    mentorId: 101,
    firstName: "Alice",
    lastName: "Chen",
    trackCode: "AUS-NSW",
    institution: "UNSW",
    interests: ["genetics", "biology", "medicine"],
    maxGroupCount: 3,
    currentAcceptedCount: 0,
  },
  {
    mentorId: 102,
    firstName: "Ben",
    lastName: "Torres",
    trackCode: "AUS-NSW",
    institution: "University of Sydney",
    interests: ["chemistry", "pharmacology"],
    maxGroupCount: 2,
    currentAcceptedCount: 0,
  },
  {
    mentorId: 103,
    firstName: "Carla",
    lastName: "Souza",
    trackCode: "BRA",
    institution: "USP São Paulo",
    interests: ["oncology", "immunology", "genetics"],
    maxGroupCount: 2,
    currentAcceptedCount: 0,
  },
  {
    // GLOBAL mentor with limited capacity — core differentiator across modes.
    // G5 (data science) wins this slot in all modes; G4/G6/G7 must go cross-track
    // in Balanced/Coverage, or remain unmatched in Strict.
    mentorId: 104,
    firstName: "David",
    lastName: "Kim",
    trackCode: "GLOBAL",
    institution: "MIT",
    interests: ["data science", "AI", "bioinformatics"],
    maxGroupCount: 1,
    currentAcceptedCount: 0,
  },
];

export const demoGroups: GroupSource[] = [
  {
    groupId: 201,
    groupName: "NSW Bio Lab A",
    trackCode: "AUS-NSW",
    studentInterests: ["genetics", "biology", "medicine"],
    studentCount: 4,
    students: [
      { name: "Mia Johnson", interests: ["genetics", "biology"] },
      { name: "Noah Lee", interests: ["biology", "medicine"] },
      { name: "Zoe Chen", interests: ["genetics", "medicine"] },
      { name: "Liam Park", interests: ["biology"] },
    ],
  },
  {
    groupId: 202,
    groupName: "NSW Chem Team",
    trackCode: "AUS-NSW",
    studentInterests: ["chemistry", "pharmacology", "biology"],
    studentCount: 3,
    students: [
      { name: "Ava Williams", interests: ["chemistry", "pharmacology"] },
      { name: "James Liu", interests: ["chemistry", "biology"] },
      { name: "Chloe Singh", interests: ["pharmacology"] },
    ],
  },
  {
    groupId: 203,
    groupName: "São Paulo Oncology",
    trackCode: "BRA",
    studentInterests: ["oncology", "immunology"],
    studentCount: 5,
    students: [
      { name: "Lucas Pereira", interests: ["oncology", "immunology"] },
      { name: "Olivia Martins", interests: ["oncology"] },
      { name: "Gabriel Costa", interests: ["immunology"] },
      { name: "Isabella Ferreira", interests: ["oncology", "immunology"] },
      { name: "Mateus Alves", interests: ["oncology"] },
    ],
  },
  {
    // No AUS-QLD mentor.
    // Strict: unmatched.
    // Balanced/Coverage: → M1 (cross-track, genetics overlap, score ~96).
    groupId: 204,
    groupName: "Queensland Genetics",
    trackCode: "AUS-QLD",
    studentInterests: ["genetics", "biology"],
    studentCount: 4,
    students: [
      { name: "Ethan Brown", interests: ["genetics", "biology"] },
      { name: "Sophie Taylor", interests: ["genetics"] },
      { name: "Riley Anderson", interests: ["biology", "genetics"] },
      { name: "Jack Thomas", interests: ["biology"] },
    ],
  },
  {
    // No AUS-WA mentor. Best match is M4 (GLOBAL, data science).
    // Wins M4's single slot in all modes.
    groupId: 205,
    groupName: "Perth Data Science",
    trackCode: "AUS-WA",
    studentInterests: ["data science", "AI"],
    studentCount: 3,
    students: [
      { name: "Harper Robinson", interests: ["data science", "AI"] },
      { name: "Mason Scott", interests: ["data science"] },
      { name: "Lily Harris", interests: ["AI"] },
    ],
  },
  {
    // No AUS-VIC mentor.
    // Strict: unmatched (M4 already taken by G5).
    // Balanced/Coverage: → M1 (cross-track, medicine overlap, score ~76).
    groupId: 206,
    groupName: "Victoria Med Group",
    trackCode: "AUS-VIC",
    studentInterests: ["medicine", "immunology", "oncology"],
    studentCount: 4,
    students: [
      { name: "Isla Martin", interests: ["medicine", "immunology"] },
      { name: "Oscar Thompson", interests: ["medicine", "oncology"] },
      { name: "Charlotte White", interests: ["immunology"] },
      { name: "Henry Jackson", interests: ["medicine", "oncology"] },
    ],
  },
  {
    // No AUS-SA mentor, and no mentor has neuroscience/neurology interests.
    // AUS-SA is not in the timezone map → treated as UTC+0 → 10-hour gap from
    // AUS-NSW/QLD/VIC → large timezone penalty on top of track-mismatch penalty.
    //
    // Strict: unmatched (M4 taken, no same-track mentor).
    // Balanced/Coverage: → M3 (BRA) with score ~58 — zero interest overlap,
    //   cross-track penalty, partial timezone penalty. This is the "basically
    //   unmatched" case that demonstrates Coverage's forced-match behaviour.
    groupId: 207,
    groupName: "SA Neuroscience Research",
    trackCode: "AUS-SA",
    studentInterests: ["neuroscience", "neurology", "cognitive science"],
    studentCount: 3,
    students: [
      { name: "Emma Wilson", interests: ["neuroscience", "neurology"] },
      { name: "Jack Brown", interests: ["neuroscience", "cognitive science"] },
      { name: "Ruby Taylor", interests: ["neurology"] },
    ],
  },
];
