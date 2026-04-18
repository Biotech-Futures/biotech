// Group type definitions

export type Track = string;

export type MentorStatusFilter = "matched" | "unmatched";

export type GroupMember = {
  id: string;
  name: string;
  email: string;
  role: "student" | "mentor";
};

export type Group = {
  id: string;
  name: string;
  track: Track;
  members: GroupMember[];
  mentor: GroupMember | null;
  createdAt: string;
  updatedAt: string;
};

export type GroupMessage = {
  id: string;
  groupId: string;
  sender: {
    id: string;
    name: string;
    email: string;
    role: "student" | "mentor" | null;
  };
  text: string;
  sentAt: string;
  editedAt: string | null;
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
