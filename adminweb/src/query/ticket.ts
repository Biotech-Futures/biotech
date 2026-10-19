import { myFetch } from "@/lib/myFetch";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  supportAgentSchema,
  ticketAnalyticsSchema,
  ticketAuditPageSchema,
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

function buildParams(
  page: number,
  limit: number,
  filters: TicketFilters,
  walk?: { asOf: string; after: string },
) {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) });
  // Falsy means "no filter" — the backend reads them the same way, so an
  // empty select does not have to be special-cased on either side.
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  // Both halves or neither. A cursor without its snapshot is refused with a
  // 400, and a snapshot without a cursor is ignored: the server will not page
  // by offset inside a frozen set, because a frozen set can still shrink and
  // that is the defect the cursor exists to close.
  //
  // URLSearchParams percent-encodes on toString(), which matters here more
  // than anywhere else on this page: an un-encoded "+" in a timestamp arrives
  // as a space and the server cannot read it. Both values carry timestamps.
  if (walk) {
    params.set("asOf", walk.asOf);
    params.set("after", walk.after);
  }
  return params;
}

export function useTicketsQuery(
  page: number,
  limit: number,
  filters: TicketFilters,
  walk?: { asOf: string; after: string },
) {
  return useQuery({
    queryKey: ["tickets", page, limit, filters, walk?.asOf, walk?.after],
    // Overrides the app-wide default, for this query only. An agent works
    // with the queue open and comes back to it expecting to see what arrived
    // while they were away; every other list on the platform is something you
    // navigate to on purpose, which is why the global default stays off and
    // the other nine admin pages are untouched.
    refetchOnWindowFocus: true,
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: unknown }>(
        `${BASE}?${buildParams(page, limit, filters, walk)}`,
      );
      return ticketQueueSchema.parse(res.data.data);
    },
  });
}

export function useTicketSummary() {
  return useQuery({
    queryKey: ["ticket-summary"],
    // Same reason as the queue: the counters sit above it and disagreeing
    // with the rows underneath is worse than either being stale alone.
    refetchOnWindowFocus: true,
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
  // Re-filing a mis-categorised ticket. Like priority, it is a triage field:
  // the backend audits the change and deliberately writes no timeline message,
  // so the requester's list does not reorder and no email goes out.
  category?: string;
  // null hands the ticket back to the pool. axios keeps a JSON null intact, so
  // it arrives as null rather than being dropped from the body.
  assignee?: number | null;
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
      moveToPending,
    }: {
      id: number;
      messageType: "support_reply" | "internal_note";
      body: string;
      files?: File[];
      moveToPending?: boolean;
    }) => {
      const form = new FormData();
      form.set("messageType", messageType);
      form.set("body", body);
      // Only sent when ticked. FormData carries strings, so an unticked box
      // would otherwise post "false" — which the serializer does read
      // correctly, but leaving the key out keeps the request identical to
      // what it was before this option existed.
      if (moveToPending) form.set("moveToPending", "true");
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

export function useDeleteTicket() {
  const invalidate = useTicketInvalidation();
  return useMutation({
    mutationFn: async (id: number) => {
      await myFetch.delete(`${BASE}/${id}/delete`);
      return id;
    },
    // No id passed on: the ticket is gone, so refreshing its own detail query
    // would only fetch a 404.
    onSuccess: () => invalidate(),
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
      // null hands the whole batch back to the pool, the same way the
      // single-ticket PATCH above does it. The serializer takes null and
      // refuses the key being absent, so it is null or a primary key here and
      // never undefined.
      assigneeId: number | null;
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


// --- The support roster. Admin-only on the server; the screen is admin-only
// --- too, so a support agent never sees a control that would 403.

const ROSTER = `${BASE}/support-scope`;

export function useSupportRoster() {
  return useQuery({
    queryKey: ["ticket-roster"],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: unknown }>(ROSTER);
      return z.array(supportAgentSchema).parse(res.data.data);
    },
  });
}

export function useGrantSupport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (userId: number) => {
      await myFetch.post(ROSTER, { userId });
    },
    // The assignee dropdowns are built from who can work the queue, so they
    // go stale the moment the roster changes.
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["ticket-roster"] });
      client.invalidateQueries({ queryKey: ["ticket-assignees"] });
    },
  });
}

export function useRevokeSupport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (userId: number) => {
      await myFetch.delete(`${ROSTER}/${userId}`);
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["ticket-roster"] });
      client.invalidateQueries({ queryKey: ["ticket-assignees"] });
    },
  });
}


export type TicketAuditFilters = { action?: string; actor?: string };

export function useTicketAudit(
  page: number,
  limit: number,
  filters: TicketAuditFilters,
) {
  return useQuery({
    queryKey: ["ticket-audit", page, limit, filters],
    queryFn: async () => {
      const params = new URLSearchParams({
        page: String(page),
        limit: String(limit),
      });
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      const res = await myFetch.get<{ msg: string; data: unknown }>(
        `${BASE}/audit?${params}`,
      );
      return ticketAuditPageSchema.parse(res.data.data);
    },
  });
}


export type AnalyticsParams = { from?: string; to?: string; dimension?: string };

export function useTicketAnalytics(params: AnalyticsParams) {
  return useQuery({
    queryKey: ["ticket-analytics", params],
    queryFn: async () => {
      const search = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value) search.set(key, value);
      });
      const res = await myFetch.get<{ msg: string; data: unknown }>(
        `${BASE}/analytics?${search}`,
      );
      return ticketAnalyticsSchema.parse(res.data.data);
    },
  });
}
