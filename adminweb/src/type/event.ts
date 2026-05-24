export const EVENT_FORMATS = ["in_person", "virtual", "hybrid"] as const;
export type EventFormat = (typeof EVENT_FORMATS)[number];

export const EVENT_FORMAT_LABELS: Record<EventFormat, string> = {
  in_person: "In-person",
  virtual: "Virtual",
  hybrid: "Hybrid",
};

export type Event = {
  id: number;
  eventName: string;
  description: string | null;
  startDatetime: string;
  endsDatetime: string;
  location: string | null;
  locationLink: string | null;
  deletedFlag: boolean;
  deletedDatetime: string | null;
  eventImage: string | null;
  eventFormat: EventFormat;
  eventTimezone: string;
  hostUserId: number | null;
  hostName: string | null;
  hostEmail: string | null;
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
  sortBy?: "id" | "name" | "host" | "location" | "start" | "end";
  sortOrder?: "asc" | "desc";
};
