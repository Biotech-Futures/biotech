export type UserTrack = string;
export type UserRole = "student" | "mentor" | "supervisor" | "admin";
export type ServerUserRole = UserRole;
export type UserStatus = "active" | "inactive";
export type UserSource = "server" | "local";

export type UserAccount = {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  track: UserTrack | null;
  groupId: string | null;
  groupName: string | null;
  age: number | null;
  schoolName: string | null;
  joinPermissionReceived: boolean;
  interests: string[];
  createdAt: string;
  updatedAt: string;
  active: boolean;
  source: UserSource;
};

export type ServerUser = Omit<UserAccount, "source">;

export type UserPaginatedResponse = {
  msg: string;
  data: {
    items: Omit<UserAccount, "source">[];
    total: number;
    page: number;
    limit: number;
    hasMore: boolean;
  };
};

export type UserFormValues = {
  name: string;
  email: string;
  role: UserRole;
  track: UserTrack | null;
  schoolName: string;
  yearLevel: number | null;
  interests: string[];
  joinPermissionReceived: boolean;
  active: boolean;
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
  trackCode: string;
};

export type TracksResponse = {
  msg: string;
  data: TrackOption[];
};

export type StudentInterest = {
  id: number;
  description: string;
};

export type StudentGroupInfo = {
  id: number;
  name: string;
  membershipId: number;
  membershipRole: string | null;
  joinedAt: string;
};

export type StudentUser = {
  id: number;
  name: string;
  firstName: string;
  lastName: string;
  email: string;
  role: "student";
  track: StudentTrack | null;
  isActive: boolean;
  accountStatus: string;
  invitedAt: string | null;
  activatedAt: string | null;
  basicInfo: {
    id: number;
    name: string;
    firstName: string;
    lastName: string;
    email: string;
    track: StudentTrack | null;
    isActive: boolean;
    accountStatus: string;
  };
  studentInfo: {
    schoolName: string | null;
    yearLevel: number | null;
    joinPermissionReceived: boolean;
    joinPermissionResponseId: string | null;
  };
  groupInfo: StudentGroupInfo | null;
  groupId: string | null;
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
