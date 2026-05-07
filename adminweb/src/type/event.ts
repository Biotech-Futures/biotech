export type Event = {
  id: number;
  eventName: string;
  description: string | null;
  startDatetime: string;
  endsDatetime: string;
  location: string | null;
  location_link: string | null;
  deletedFlag: boolean;
  deletedDatetime: string | null;
  "eventImage(img)": string | null;
  isVirtual: boolean;
  hostUserId: number | null;
};

export type EventRsvp = {
  id: number;
  eventId: number;
  userId: number;
  rsvpStatus: "going" | "maybe" | "declined";
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
  upcoming?: boolean;
};
