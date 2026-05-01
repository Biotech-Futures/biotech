import type { CreateUserInput } from "./schema.js";

export type User = {
  id: number;
  firstName: string;
  lastName: string;
  email: string;
  role: string | null;
  track: string | null;
  groupName: string | null;
  schoolName: string | null;
  mentorBackground: string | null;
  mentorInstitution: string | null;
  mentorReason: string | null;
  mentorMaxGroupCount: number | null;
  yearLevel: number | null;
  joinPermissionReceived: boolean;
  interests: string[];
  adminTracks: string[] | null;
  isActive: boolean;
  accountStatus: string;
  invitedAt: string | null;
  activatedAt: string | null;
};

export type TrackOption = {
  id: number;
  trackName: string;
};

export type AddUsersByRoleResult = {
  input: CreateUserInput;
  data: User | null;
  msg: string;
};
