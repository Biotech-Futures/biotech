import { myFetch } from "@/lib/myFetch";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  assigneeOptionSchema,
  bulkAssignResultSchema,
  regionOptionSchema,
  ticketDetailSchema,
  ticketHistoryEntrySchema,
  ticketQueueSchema,
  ticketSummarySchema,
  type TicketFilters,
} from "@/schema/ticket";
import { z } from "zod";

const BASE = "/tickets";

function buildParams(page: number, limit: number, filters: TicketFilters) {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) });
  // Falsy means "no filter" — the backend reads them the same way, so an
  // empty select does not have to be special-cased on either side.
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  return params;
}

export function useTicketsQuery(page: number, limit: number, filters: TicketFilters) {
  return useQuery({
    queryKey: ["tickets", page, limit, filters],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: unknown }>(
        `${BASE}?${buildParams(page, limit, filters)}`,
      );
      return ticketQueueSchema.parse(res.data.data);
    },
  });
}

export function useTicketSummary() {
  return useQuery({
    queryKey: ["ticket-summary"],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: unknown }>(`${BASE}/summary`);
      return ticketSummarySchema.parse(res.data.data);
    },
  });
}

export function useTicketDetail(id: number | null) {
  return useQuery({
    queryKey: ["ticket", id],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: unknown }>(`${BASE}/${id}`);
      return ticketDetailSchema.parse(res.data.data);
    },
    enabled: id !== null,
  });
}

export function useTicketHistory(id: number | null) {
  return useQuery({
    queryKey: ["ticket-history", id],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: unknown }>(
        `${BASE}/${id}/history`,
      );
      return z.array(ticketHistoryEntrySchema).parse(res.data.data);
    },
    enabled: id !== null,
  });
}

export function useAssignees() {
  return useQuery({
    queryKey: ["ticket-assignees"],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: unknown }>(`${BASE}/assignees`);
      return z.array(assigneeOptionSchema).parse(res.data.data);
    },
  });
}

export function useTicketRegions() {
  return useQuery({
    queryKey: ["ticket-regions"],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: unknown }>(`${BASE}/regions`);
      return z.array(regionOptionSchema).parse(res.data.data);
    },
  });
}

// Anything that changes a ticket invalidates the queue and the counters as
// well as the ticket itself: a status change moves it between counter cards
// and can move it in the sort order.
function useTicketInvalidation() {
  const client = useQueryClient();
  return (id?: number) => {
    client.invalidateQueries({ queryKey: ["tickets"] });
    client.invalidateQueries({ queryKey: ["ticket-summary"] });
    if (id !== undefined) {
      client.invalidateQueries({ queryKey: ["ticket", id] });
      client.invalidateQueries({ queryKey: ["ticket-history", id] });
    }
  };
}

export type TicketPatch = {
  status?: string;
  priority?: string;
  assignee?: number;
};

export function useUpdateTicket() {
  const invalidate = useTicketInvalidation();
  return useMutation({
    // status and assignee are mutually exclusive — the backend answers 400 if
    // both arrive together, because each one drives a different transition and
    // any implied ordering produces a wrong end state.
    mutationFn: async ({ id, patch }: { id: number; patch: TicketPatch }) => {
      const res = await myFetch.patch<{ msg: string; data: unknown }>(
        `${BASE}/${id}`,
        patch,
      );
      return ticketDetailSchema.parse(res.data.data);
    },
    onSuccess: (ticket) => invalidate(ticket.id),
  });
}

export function useReplyTicket() {
  const invalidate = useTicketInvalidation();
  return useMutation({
    mutationFn: async ({
      id,
      messageType,
      body,
      files,
    }: {
      id: number;
      messageType: "support_reply" | "internal_note";
      body: string;
      files?: File[];
    }) => {
      const form = new FormData();
      form.set("messageType", messageType);
      form.set("body", body);
      // Repeated under one key: the backend reads request.FILES.getlist.
      (files ?? []).forEach((file) => form.append("files", file));
      const res = await myFetch.post<{ msg: string; data: unknown }>(
        `${BASE}/${id}/messages`,
        form,
      );
      return ticketDetailSchema.parse(res.data.data);
    },
    onSuccess: (ticket) => invalidate(ticket.id),
  });
}

export function useBulkAssign() {
  const invalidate = useTicketInvalidation();
  return useMutation({
    mutationFn: async ({
      ticketIds,
      assigneeId,
    }: {
      ticketIds: number[];
      assigneeId: number;
    }) => {
      const res = await myFetch.post<{ msg: string; data: unknown }>(
        `${BASE}/bulk-assign`,
        { ticketIds, assigneeId },
      );
      // Per-ticket results: one bad id does not undo the rest of the batch,
      // so the caller has to be able to report which ones failed.
      return bulkAssignResultSchema.parse(res.data.data);
    },
    onSuccess: () => invalidate(),
  });
}

export function ticketAttachmentUrl(ticketId: number, attachmentId: number) {
  return `${myFetch.defaults.baseURL}${BASE}/${ticketId}/attachments/${attachmentId}/`;
}
