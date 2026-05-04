export const ROLES = ["student", "mentor", "supervisor", "admin"] as const;

export const STATUS = {
  INVITED: "invited",
  PENDING: "pending",
  ACTIVE: "active",
  SUSPENDED: "suspended",
  DEACTIVATED: "deactivated",
} as const;

export const DEFAULT_MENTOR_PROFILE = {
  background: null,
  institution: "",
  mentorReason: "",
  maxGroupCount: 2,
} as const;
