export type AnnouncementAudience = {
  id: number;
  roleId: number | null;
  trackId: number | null;
  roleName: string | null;
};

export type Announcement = {
  id: number;
  title: string;
  body: string;
  visibilityScope: "global" | "track_based" | "role_based";
  publishedAt: string;
  archivedAt: string | null;
  authorUserId: number;
  trackId: number | null;
  trackName: string | null;
  audiences: AnnouncementAudience[];
};

export type AnnouncementListItem = Omit<Announcement, "body">;

export type PaginatedAnnouncements = {
  items: AnnouncementListItem[];
  total: number;
  page: number;
  limit: number;
  hasMore: boolean;
};

export type TrackOption = { id: number; name: string };
export type RoleOption = { id: number; name: string };
