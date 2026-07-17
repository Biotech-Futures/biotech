export type UserRole = "student" | "mentor" | "supervisor" | "admin";
export type UserSource = "server" | "local";

export type CountryOption = {
  id: number;
  countryName: string;
};

/** A row in the /user/states lookup. Carries its country so the picker can
 *  qualify state names that repeat across countries ("NSW · Australia"). */
export type StateOption = {
  id: number;
  stateName: string;
  countryName: string | null;
};

/** A user's own sub-national region. No countryName — read `user.country`. */
export type UserState = {
  id: number;
  stateName: string;
};

export type CountriesResponse = {
  msg: string;
  data: CountryOption[];
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
  country: CountryOption | null;
  state: UserState | null;
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
  countryId: number | null;
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

export type CsvUserRow = Omit<UserFormValues, "countryId" | "stateId"> & {
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

export type StudentUser = {
  id: number;
  firstName: string;
  lastName: string;
  email: string;
  role: "student";
  country: CountryOption | null;
  state: UserState | null;
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

export function labelizeUserRole(role: UserRole) {
  return role?.charAt(0).toUpperCase() + role?.slice(1);
}

export function labelizeCountry(country: CountryOption | null) {
  return country?.countryName ?? "Unassigned";
}

// Most non-Australian users have no state — that's expected, not a gap to flag.
export function labelizeState(state: UserState | null) {
  return state?.stateName ?? "-";
}
