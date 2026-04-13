export type StudentTrack = "frontend" | "backend" | "fullstack" | "data";

export type StudentUser = {
  id: string;
  name: string;
  email: string;
  role: "student";
  track: StudentTrack | null;
  groupId: string | null;
  groupName: string | null;
  age: number | null;
  interests: string[];
  createdAt: string;
  updatedAt: string;
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

export const STUDENT_TRACKS: StudentTrack[] = ["frontend", "backend", "fullstack", "data"];
