import { myFetch } from "@/lib/myFetch";
import type {
  CreateEvent,
  CreateEventRsvp,
  UpdateEvent,
  UpdateEventRsvp,
} from "@/schema/event";
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

export function useQueryEvent(id: string) {
  return useQuery({
    queryKey: ["event", id],
    queryFn: async (): Promise<ApiResponse<Event | null>> => {
      const res = await myFetch.get<ApiResponse<Event | null>>(`/event/${id}`);
      return res.data;
    },
    enabled: !!id,
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

export function useCreateEventRsvp() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      eventId,
      data,
    }: {
      eventId: number;
      data: CreateEventRsvp;
    }): Promise<ApiResponse<EventRsvp | null>> => {
      const res = await myFetch.post<ApiResponse<EventRsvp | null>>(
        `/event/${eventId}/rsvp`,
        data,
      );
      return res.data;
    },
    onSuccess: (_, { eventId }) => {
      queryClient.invalidateQueries({ queryKey: ["event-rsvps", eventId] });
    },
  });
}

export function useUpdateEventRsvp() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      rsvpId,
      data,
    }: {
      eventId: number;
      rsvpId: number;
      data: UpdateEventRsvp;
    }): Promise<ApiResponse<EventRsvp | null>> => {
      const res = await myFetch.put<ApiResponse<EventRsvp | null>>(
        `/event/rsvp/${rsvpId}`,
        data,
      );
      return res.data;
    },
    onSuccess: (_, { eventId }) => {
      queryClient.invalidateQueries({ queryKey: ["event-rsvps", eventId] });
    },
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

export function useQueryTracks() {
  return useQuery({
    queryKey: ["event-meta-tracks"],
    queryFn: async (): Promise<ApiResponse<{ id: number; trackName: string }[]>> => {
      const res = await myFetch.get<ApiResponse<{ id: number; trackName: string }[]>>(
        "/event/meta/tracks",
      );
      return res.data;
    },
  });
}

export function useQueryEventTargets(eventId: number | null) {
  return useQuery({
    queryKey: ["event-targets", eventId],
    queryFn: async (): Promise<ApiResponse<{ groupIds: number[]; roleIds: number[]; trackIds: number[] }>> => {
      const res = await myFetch.get<ApiResponse<{ groupIds: number[]; roleIds: number[]; trackIds: number[] }>>(
        `/event/${eventId}/targets`,
      );
      return res.data;
    },
    enabled: eventId !== null,
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function toApiEventPayload(data: CreateEvent | UpdateEvent) {
  return {
    ...data,
    hostUserId: data.hostUserId ?? null,
    startAt: toIsoFromDatetimeLocal(data.startAt),
    endsAt: toIsoFromDatetimeLocal(data.endsAt),
  };
}

function toIsoFromDatetimeLocal(value: string | undefined) {
  if (!value) return undefined;
  return new Date(value).toISOString();
}
