export type UserRole = "student" | "mentor" | "supervisor" | "admin";
export type ServerUserRole = UserRole;
export type UserStatus = "active" | "inactive";
export type UserSource = "server" | "local";

export type StateOption = {
  id: number;
  stateName: string;
  countryName: string | null;
};

export type StatesResponse = {
  msg: string;
  data: StateOption[];
};

export type UserAccount = {
  id: string;
  name: string;
  firstName: string;
  lastName: string;
  email: string;
  role: UserRole;
  state: StateOption | null;
  groupId: string | null;
  groupName: string | null;
  age: number | null;
  schoolName: string | null;
  mentorBackground: string | null;
  mentorInstitution: string | null;
  mentorReason: string | null;
  mentorMaxGroupCount: number | null;
  interests: string[];
  isAdmin: boolean;
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
  stateId: number | null;
  schoolName: string;
  supervisorSchoolName: string;
  mentorBackground: string;
  mentorInstitution: string;
  mentorReason: string;
  mentorMaxGroupCount: number | null;
  yearLevel: number | null;
  interests: string[];
  active: boolean;
  supervisorEmail: string;
};

export type CsvUserRow = Omit<UserFormValues, "stateId"> & {
  id: string;
  state: string | null;
};

export type UserOverride = Partial<
  Pick<
    UserAccount,
    "name" | "email" | "role" | "state" | "active" | "updatedAt"
  >
>;

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
  state: StateOption | null;
  isActive: boolean;
  accountStatus: string;
  schoolName: string | null;
  yearLevel: number | null;
  joinpermResponseId: string | null;
  groupId: number | null;
  groupName: string | null;
  interests: string[];
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

export function getUserStatus(user: Pick<UserAccount, "active">): UserStatus {
  return user.active ? "active" : "inactive";
}

export function labelizeUserRole(role: UserRole) {
  return role?.charAt(0).toUpperCase() + role?.slice(1);
}

export function labelizeState(state: StateOption | null) {
  return state?.stateName ?? "Unassigned";
}
