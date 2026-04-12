export type Event = {
  id: number;
  hostUserId: number | null;
  trackId: number | null;
  eventType: string | null;
  startAt: string;
  endsAt: string;
};

export type EventRsvp = {
  id: number;
  eventId: number;
  userId: number;
  rsvpStatus: string;
  respondedAt: string | null;
};

export type ApiResponse<T> = {
  msg: string;
  data: T;
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

export type QueryEventsParams = {
  page: number;
  limit?: number;
  hostUserId?: number;
  trackId?: number;
  eventType?: string;
  upcoming?: boolean;
};
