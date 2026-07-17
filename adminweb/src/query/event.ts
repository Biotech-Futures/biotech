import { myFetch } from "@/lib/myFetch";
import type { CreateEvent, UpdateEvent } from "@/schema/event";
import type {
  ApiResponse,
  Event,
  EventRsvp,
  PaginatedResponse,
  QueryEventsParams,
} from "@/type/event";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export function useQueryEvents(params: QueryEventsParams) {
  return useQuery({
    queryKey: ["events", params],
    queryFn: async (): Promise<PaginatedResponse<Event>> => {
      const res = await myFetch.get<PaginatedResponse<Event>>("/event", {
        params,
      });
      return res.data;
    },
  });
}

export function useCreateEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (
      data: CreateEvent,
    ): Promise<ApiResponse<Event | null>> => {
      const payload = toApiEventPayload(data);
      const res = await myFetch.post<ApiResponse<Event | null>>(
        "/event",
        payload,
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });
}

export function useUpdateEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: number;
      data: UpdateEvent;
    }): Promise<ApiResponse<Event | null>> => {
      const payload = toApiEventPayload(data);
      const res = await myFetch.put<ApiResponse<Event | null>>(
        `/event/${id}`,
        payload,
      );
      return res.data;
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
      queryClient.invalidateQueries({ queryKey: ["event", String(id)] });
      queryClient.invalidateQueries({ queryKey: ["event-targets", id] });
    },
  });
}

export function useDeleteEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number): Promise<ApiResponse<Event | null>> => {
      const res = await myFetch.delete<ApiResponse<Event | null>>(
        `/event/${id}`,
      );
      return res.data;
    },
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
      queryClient.invalidateQueries({ queryKey: ["event-rsvps", deletedId] });
    },
  });
}

export function useUploadEventImage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      eventId,
      file,
    }: {
      eventId: number;
      file: File;
    }): Promise<ApiResponse<Event | null>> => {
      const formData = new FormData();
      formData.append("image", file);
      const res = await myFetch.post<ApiResponse<Event | null>>(
        `/event/${eventId}/upload-image`,
        formData,
      );
      return res.data;
    },
   onSuccess: (_result: ApiResponse<Event | null>, variables: { eventId: number; file: File }) => {
  queryClient.invalidateQueries({ queryKey: ["events"] });
  queryClient.invalidateQueries({ queryKey: ["event", String(variables.eventId)] });
    },
  });
}

export function useQueryEventRsvps(eventId: number | null) {
  return useQuery({
    queryKey: ["event-rsvps", eventId],
    queryFn: async (): Promise<ApiResponse<EventRsvp[] | null>> => {
      const res = await myFetch.get<ApiResponse<EventRsvp[] | null>>(
        `/event/${eventId}/rsvp`,
      );
      return res.data;
    },
    enabled: eventId !== null,
  });
}

// ── Reference data ────────────────────────────────────────────────────────────

export function useQueryGroups() {
  return useQuery({
    queryKey: ["event-meta-groups"],
    queryFn: async (): Promise<ApiResponse<{ id: number; groupName: string }[]>> => {
      const res = await myFetch.get<ApiResponse<{ id: number; groupName: string }[]>>(
        "/event/meta/groups",
      );
      return res.data;
    },
  });
}

export function useQueryRoles() {
  return useQuery({
    queryKey: ["event-meta-roles"],
    queryFn: async (): Promise<ApiResponse<{ id: number; roleName: string }[]>> => {
      const res = await myFetch.get<ApiResponse<{ id: number; roleName: string }[]>>(
        "/event/meta/roles",
      );
      return res.data;
    },
  });
}

export function useQueryEventTargets(eventId: number | null) {
  return useQuery({
    queryKey: ["event-targets", eventId],
    queryFn: async (): Promise<ApiResponse<{ groupIds: number[]; roleIds: number[] }>> => {
      const res = await myFetch.get<ApiResponse<{ groupIds: number[]; roleIds: number[] }>>(
        `/event/${eventId}/targets`,
      );
      return res.data;
    },
    enabled: eventId !== null,
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function toApiEventPayload(data: CreateEvent | UpdateEvent) {
  const tz = data.eventTimezone || Intl.DateTimeFormat().resolvedOptions().timeZone;
  return {
    ...data,
    hostUserId: data.hostUserId ?? null,
    startAt: localInTzToUtcIso(data.startAt, tz),
    endsAt: localInTzToUtcIso(data.endsAt, tz),
    location_link: data.locationLink ?? null,
    locationLink: undefined,
    eventImage: data.eventImage ?? null,
  };
}

/**
 * Converts a datetime-local string (e.g. "2024-01-15T14:30") interpreted in
 * the given IANA timezone to a UTC ISO string.
 *
 * Algorithm: treat input as naive UTC, find what it shows as in the target TZ,
 * then apply the inverse offset: T_utc = 2*naive - shown.
 */
function localInTzToUtcIso(value: string | undefined, timeZone: string): string | undefined {
  if (!value) return undefined;
  const naive = new Date(value + ":00Z");
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
    hour12: false,
  }).formatToParts(naive);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "00";
  const h = get("hour") === "24" ? "00" : get("hour");
  const shown = new Date(`${get("year")}-${get("month")}-${get("day")}T${h}:${get("minute")}:${get("second")}Z`);
  return new Date(2 * naive.getTime() - shown.getTime()).toISOString();
}
