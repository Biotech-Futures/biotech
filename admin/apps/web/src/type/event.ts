export type Event = {
  id: number;
  eventName: string;
  description: string | null;
  startDatetime: string;
  endsDatetime: string;
  location: string | null;
  humanitixLink: string;
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
  sentDatetime: string;
  attendanceStatus: boolean;
  rsvpStatus: boolean;
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
