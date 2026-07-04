import { myFetch } from "@/lib/myFetch";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  Announcement,
  PaginatedAnnouncements,
  RoleOption,
  TrackOption,
} from "@/type/announcement";
import type { SortState } from "@/components/ui/sortable-table";

const BASE = "/announcement";

export function useListAnnouncements(
  page: number,
  search: string,
  archived?: boolean,
  sort?: SortState<"title" | "audience" | "published" | "status">,
) {
  return useQuery({
    queryKey: ["announcements", page, search, archived, sort?.key, sort?.direction],
    queryFn: async () => {
      const params = new URLSearchParams({
        page: String(page),
        limit: "10",
      });
      if (search) params.set("search", search);
      if (archived === true) params.set("archived", "true");
      if (archived === false) params.set("archived", "false");
      if (sort) {
        params.set("sortBy", sort.key);
        params.set("sortOrder", sort.direction);
      }
      const res = await myFetch.get<{ msg: string; data: PaginatedAnnouncements }>(
        `${BASE}?${params}`,
      );
      return res.data.data;
    },
  });
}

export function useGetAnnouncement(id: number | null) {
  return useQuery({
    queryKey: ["announcement", id],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: Announcement }>(
        `${BASE}/${id}`,
      );
      return res.data.data;
    },
    enabled: id !== null,
  });
}

export function useAnnouncementTracks() {
  return useQuery({
    queryKey: ["announcement-tracks"],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: TrackOption[] }>(
        `${BASE}/tracks`,
      );
      return res.data.data;
    },
  });
}

export function useAnnouncementRoles() {
  return useQuery({
    queryKey: ["announcement-roles"],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: RoleOption[] }>(
        `${BASE}/roles`,
      );
      return res.data.data;
    },
  });
}

export function useCreateAnnouncement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      title: string;
      body: string;
      track_ids?: number[];
      role_ids?: number[];
      send_email: boolean;
    }) => {
      const res = await myFetch.post<{ msg: string; data: Announcement }>(
        BASE,
        data,
      );
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["announcements"] }),
  });
}

export function useUpdateAnnouncement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: number;
      data: {
        title?: string;
        body?: string;
        track_ids?: number[];
        role_ids?: number[];
        send_email?: boolean;
      };
    }) => {
      const res = await myFetch.put<{ msg: string; data: Announcement }>(
        `${BASE}/${id}`,
        data,
      );
      return res.data;
    },
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ["announcements"] });
      qc.invalidateQueries({ queryKey: ["announcement", id] });
    },
  });
}

export function useArchiveAnnouncement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await myFetch.post<{ msg: string; data: Announcement }>(
        `${BASE}/${id}/archive`,
      );
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["announcements"] }),
  });
}

export function useDeleteAnnouncement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await myFetch.delete<{ msg: string; data: Announcement }>(
        `${BASE}/${id}`,
      );
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["announcements"] }),
  });
}

export function useSendAnnouncementEmail() {
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await myFetch.post<{ msg: string; sent: number }>(
        `${BASE}/${id}/notify`,
      );
      return res.data;
    },
  });
}
