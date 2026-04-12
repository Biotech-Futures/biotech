export type Role = "student" | "mentor" | "admin";
export type Track = "frontend" | "backend" | "fullstack" | "data";

export type User = {
  id: string;
  name: string;
  email: string;
  role: Role;
  track: Track | null;
  groupId: string | null;
  groupName: string | null;
  createdAt: string;
  updatedAt: string;
};

export type PaginatedResponse<T> = {
  msg: string;
  data: {
    items: T[];
    total: number;
    page: number;
    limit: number;
    hasMore: boolean;
  };
};

export const ROLES: Role[] = ["student", "mentor", "admin"];
export const TRACKS: Track[] = ["frontend", "backend", "fullstack", "data"];
