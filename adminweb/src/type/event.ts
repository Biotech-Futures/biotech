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

// Mirrors backend EventRsvp.RsvpStatus (meeting-standard PARTSTAT wording).
export const RSVP_STATUSES = [
  "pending",
  "accepted",
  "tentative",
  "declined",
  "waitlisted",
] as const;
export type RsvpStatus = (typeof RSVP_STATUSES)[number];

export type EventRsvp = {
  id: number;
  eventId: number;
  userId: number;
  rsvpStatus: RsvpStatus;
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
    // Backend event list emits snake_case here (unlike user/resource/announcement).
    has_more: boolean;
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
