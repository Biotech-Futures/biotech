export type UserTrack = string;
export type UserRole = "student" | "mentor" | "supervisor" | "admin";
export type ServerUserRole = UserRole;
export type UserStatus = "active" | "inactive";
export type UserSource = "server" | "local";

export type UserAccount = {
  id: string;
  name: string;
  firstName: string;
  lastName: string;
  email: string;
  role: UserRole;
  track: UserTrack | null;
  groupId: string | null;
  groupName: string | null;
  age: number | null;
  schoolName: string | null;
  mentorBackground: string | null;
  mentorInstitution: string | null;
  mentorReason: string | null;
  mentorMaxGroupCount: number | null;
  joinPermissionReceived: boolean;
  interests: string[];
  adminTracks: string[];
  adminIsGlobal: boolean;
  createdAt: string;
  updatedAt: string;
  active: boolean;
  source: UserSource;
  supervisorName: string | null;
  supervisorEmail: string | null;
  supervisees: { name: string; email: string }[];
};

export type ServerUser = Omit<UserAccount, "source">;

export type UserPaginatedResponse = {
  msg: string;
  data: {
    items: UserAccount[];
    total: number;
    page: number;
    limit: number;
    hasMore: boolean;
  };
};

export type UserFormValues = {
  firstName: string;
  lastName: string;
  email: string;
  role: UserRole;
  track: UserTrack | null;
  adminTracks: UserTrack[];
  adminIsGlobal: boolean;
  schoolName: string;
  supervisorSchoolName: string;
  mentorBackground: string;
  mentorInstitution: string;
  mentorReason: string;
  mentorMaxGroupCount: number | null;
  yearLevel: number | null;
  interests: string[];
  joinPermissionReceived: boolean;
  active: boolean;
  supervisorEmail: string;
};

export type CsvUserRow = UserFormValues & {
  id: string;
};

export type UserOverride = Partial<
  Pick<
    UserAccount,
    "name" | "email" | "role" | "track" | "active" | "updatedAt"
  >
>;

export const USER_TRACKS: UserTrack[] = [];

export const USER_ROLES: UserRole[] = [
  "student",
  "mentor",
  "supervisor",
  "admin",
];

export const SERVER_USER_ROLES: ServerUserRole[] = [
  "student",
  "mentor",
  "supervisor",
  "admin",
];

export type StudentTrack = string;

export type TrackOption = {
  id: number;
  trackName: string;
};

export type TracksResponse = {
  msg: string;
  data: TrackOption[];
};

export type StudentInterest = {
  id: number;
  description: string;
};

export type StudentUser = {
  id: number;
  firstName: string;
  lastName: string;
  email: string;
  role: "student";
  track: StudentTrack | null;
  isActive: boolean;
  accountStatus: string;
  schoolName: string | null;
  yearLevel: number | null;
  hasJoinPermission: boolean;
  joinpermResponseId: string | null;
  groupId: number | null;
  groupName: string | null;
  interests: StudentInterest[];
};

export type StudentPaginatedResponse = {
  msg: string;
  data: {
    items: StudentUser[];
    total: number;
    page: number;
    limit: number;
    hasMore: boolean;
  };
};
export const STUDENT_TRACKS: StudentTrack[] = USER_TRACKS;

export function getUserStatus(user: Pick<UserAccount, "active">): UserStatus {
  return user.active ? "active" : "inactive";
}

export function labelizeUserRole(role: UserRole) {
  return role?.charAt(0).toUpperCase() + role?.slice(1);
}

export function labelizeTrack(track: UserTrack | null) {
  return track ?? "Unassigned";
}
