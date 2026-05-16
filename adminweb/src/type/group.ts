// Group type definitions

export type Track = string;

export type MentorStatusFilter = "matched" | "unmatched";

export type GroupMember = {
  id: string;
  name: string;
  email: string;
  role: "student" | "mentor";
  membershipId?: number;
};

export type Group = {
  id: string;
  name: string;
  track: Track;
  members: GroupMember[];
  mentor: GroupMember | null;
  createdAt: string;
  updatedAt: string;
  deletedAt: string | null;
};

export type MessageAttachment = {
  id: number;
  filename: string;
  mime_type: string;
  size: number;
  download_url: string;
};

export type MessageGif = {
  gif_url: string;
  preview_url: string;
  title: string;
};

export type GroupMessage = {
  id: string;
  group_id: string;
  sender: {
    id: string;
    name: string;
    email: string;
    role: "student" | "mentor" | null;
  };
  message_type: "text" | "gif" | "attachment" | "resource" | "system";
  text: string | null;
  attachments: MessageAttachment[];
  gif: MessageGif | null;
  sent_at: string;
  edited_at: string | null;
  deleted_at: string | null;
  deleted_by: string | null;
  deleted_by_name: string;
  deleted_by_is_admin: boolean;
};

export type PaginatedResponse<T> = {
  msg: string;
  data: {
    items: T[];
    total: number;
    page: number;
    limit: number;
    has_more: boolean;
  };
};
