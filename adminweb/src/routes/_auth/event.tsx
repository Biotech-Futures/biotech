import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandInput,
  CommandItem,
  CommandList,
  CommandEmpty,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import { BulkActionsBar } from "@/components/ui/bulk-actions-bar";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  SortableTableHead,
  useSortableRows,
  type SortState,
} from "@/components/ui/sortable-table";
import { TablePaginationBar } from "@/components/ui/table-pagination";
import {
  createEventSchema,
  updateEventSchema,
  type CreateEvent,
  type CreateEventInput,
  type UpdateEvent,
  type UpdateEventInput,
} from "@/schema/event";
import {
  useCreateEvent,
  useDeleteEvent,
  useQueryEvents,
  useUpdateEvent,
  useUploadEventImage,
  useQueryEventRsvps,
  useQueryGroups,
  useQueryRoles,
  useQueryEventTargets,
} from "@/query/event";
import { useQueryUsers } from "@/query/user";
import type { Event, EventFormat, EventRsvp } from "@/type/event";
import { EVENT_FORMAT_LABELS } from "@/type/event";
import { BRAND_NAME } from "@/lib/brand";
import { useAuthContext } from "@/provider/AuthProvider";
import { zodResolver } from "@hookform/resolvers/zod";
import { createFileRoute } from "@tanstack/react-router";
import {
  CalendarIcon,
  Trash2Icon,
  PencilIcon,
  UsersIcon,
  EyeIcon,
  MoreHorizontalIcon,
  ImageIcon,
  XIcon,
  ChevronsUpDownIcon,
} from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";

const DEFAULT_PAGE_SIZE = 25;

export const Route = createFileRoute("/_auth/event")({
  component: EventPage,
});

const RSVP_STATUS_LABELS: Record<
  string,
  { label: string; variant: "default" | "outline" | "secondary" }
> = {
  pending: { label: "Pending", variant: "secondary" },
  accepted: { label: "Accepted", variant: "default" },
  tentative: { label: "Tentative", variant: "secondary" },
  declined: { label: "Declined", variant: "outline" },
  waitlisted: { label: "Waitlisted", variant: "outline" },
};

type EventSortKey = "id" | "name" | "host" | "location" | "start" | "end";
type RsvpSortKey = "id" | "student" | "status" | "responded";

const initialEventSort: SortState<EventSortKey> = {
  key: "start",
  direction: "asc",
};

const initialRsvpSort: SortState<RsvpSortKey> = {
  key: "responded",
  direction: "desc",
};

// ── Image upload sub-component ────────────────────────────────────────────────

interface ImageUploadFieldProps {
  /** Existing URL from the event record (edit mode). Null in create mode. */
  existingUrl?: string | null;
  /** Called with the selected File so the form can hold it for submission. */
  onFileSelected: (file: File | null) => void;
  /** Preview URL derived from the selected file (object URL). */
  previewUrl: string | null;
}

function ImageUploadField({
  existingUrl,
  onFileSelected,
  previewUrl,
}: ImageUploadFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const displayUrl = previewUrl ?? existingUrl ?? null;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    onFileSelected(file);
  };

  const handleClear = () => {
    onFileSelected(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => inputRef.current?.click()}
        >
          <ImageIcon className="size-4" />
          {displayUrl ? "Change Image" : "Upload Image"}
        </Button>
        {displayUrl && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleClear}
            className="text-muted-foreground"
          >
            <XIcon className="size-4" />
            Remove
          </Button>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp"
          className="hidden"
          onChange={handleChange}
        />
      </div>
      {displayUrl && (
        <div className="relative inline-block">
          <img
            src={displayUrl}
            alt="Event image preview"
            className="h-32 w-auto rounded-md border object-cover"
          />
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        Accepted: JPG, PNG, GIF, WEBP · Max 5 MB
      </p>
    </div>
  );
}

// ── Form row helpers ───────────────────────────────────────────────────────────

interface EventFormProps {
  formId: string;
  control: any;
  register: any;
  errors: any;
  eventFormat: EventFormat;
  currentHostName: string;
  groups: { id: number; groupName: string }[];
  roles: { id: number; roleName: string }[];
  watchedGroupIds: number[];
  watchedRoleIds: number[];
  onToggleGroup: (id: number) => void;
  onToggleRole: (id: number) => void;
  onSubmit: (e: React.FormEvent) => void;
  // image props
  existingImageUrl?: string | null;
  imagePreviewUrl: string | null;
  onImageFileSelected: (file: File | null) => void;
}

function EventFormRow({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-1.5 sm:grid-cols-[140px_minmax(0,1fr)] sm:items-start sm:gap-4">
      <Label
        className="pt-2 sm:justify-end sm:text-right"
        requiredMarker={required}
      >
        {label}
      </Label>
      <div className="min-w-0 space-y-1.5">{children}</div>
    </div>
  );
}

function EventDetailRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-1.5 sm:grid-cols-[140px_minmax(0,1fr)] sm:items-start sm:gap-4">
      <Label className="text-xs uppercase text-muted-foreground sm:text-right">
        {label}
      </Label>
      <div className="min-w-0 text-sm">{children}</div>
    </div>
  );
}

function EventForm({
  formId,
  control,
  register,
  errors,
  eventFormat,
  currentHostName,
  groups,
  roles,
  watchedGroupIds,
  watchedRoleIds,
  onToggleGroup,
  onToggleRole,
  onSubmit,
  existingImageUrl,
  imagePreviewUrl,
  onImageFileSelected,
}: EventFormProps) {
  return (
    <form id={formId} className="grid gap-5 px-4 pb-4" onSubmit={onSubmit}>
      <EventFormRow label="Host">
        <Input
          value={currentHostName}
          readOnly
          disabled
          className="bg-muted text-muted-foreground cursor-not-allowed"
        />
      </EventFormRow>

      <EventFormRow label="Event Name" required>
        <Input placeholder="Event name" {...register("eventName")} />
        {errors.eventName && (
          <p className="text-sm text-destructive">{errors.eventName.message}</p>
        )}
      </EventFormRow>

      <EventFormRow label="Description">
        <Input placeholder="Optional" {...register("description")} />
      </EventFormRow>

      <EventFormRow label="Image URL">
        <Input
          placeholder="https://example.com/image.jpg"
          {...register("eventImage")}
        />
        {errors.eventImage && (
          <p className="text-sm text-destructive">
            {errors.eventImage.message}
          </p>
        )}
      </EventFormRow>

      <Controller
        control={control}
        name="eventFormat"
        render={({ field }) => (
          <EventFormRow label="Event Type">
            <Select
              value={field.value ?? "in_person"}
              onValueChange={(val) => field.onChange(val as EventFormat)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="in_person">{EVENT_FORMAT_LABELS.in_person}</SelectItem>
                <SelectItem value="virtual">{EVENT_FORMAT_LABELS.virtual}</SelectItem>
                <SelectItem value="hybrid">{EVENT_FORMAT_LABELS.hybrid}</SelectItem>
              </SelectContent>
            </Select>
          </EventFormRow>
        )}
      />

      {eventFormat !== "virtual" && (
        <EventFormRow label="Location">
          <Input
            placeholder="Venue address or room"
            {...register("location")}
          />
        </EventFormRow>
      )}

      <EventFormRow
        label={eventFormat !== "virtual" ? "Google Map Link" : "Meeting Link"}
      >
        <Input
          placeholder={
            eventFormat !== "virtual"
              ? "https://maps.google.com/..."
              : "https://zoom.us/..."
          }
          {...register("locationLink")}
        />
      </EventFormRow>

      <Controller
        control={control}
        name="eventTimezone"
        render={({ field }) => (
          <EventFormRow label="Timezone">
            <TimezoneCombobox
              value={field.value ?? BROWSER_TZ}
              onChange={field.onChange}
            />
            <p className="text-xs text-muted-foreground">
              Start and end times will be saved in this timezone.
            </p>
          </EventFormRow>
        )}
      />

      <Controller
        control={control}
        name="startAt"
        render={({ field }) => (
          <EventFormRow label="Start" required>
            <DateTimeLocalInput field={field} />
            {errors.startAt && (
              <p className="text-sm text-destructive">
                {errors.startAt.message}
              </p>
            )}
          </EventFormRow>
        )}
      />

      <Controller
        control={control}
        name="endsAt"
        render={({ field }) => (
          <EventFormRow label="End" required>
            <DateTimeLocalInput field={field} />
            {errors.endsAt && (
              <p className="text-sm text-destructive">
                {errors.endsAt.message}
              </p>
            )}
          </EventFormRow>
        )}
      />

      <EventFormRow label="Event Image">
        <ImageUploadField
          existingUrl={existingImageUrl}
          onFileSelected={onImageFileSelected}
          previewUrl={imagePreviewUrl}
        />
      </EventFormRow>

      {groups.length > 0 && (
        <EventFormRow label="Target Groups">
          <div className="grid grid-cols-2 gap-2">
            {groups.map((g) => (
              <label
                key={g.id}
                className="flex items-center gap-2 text-sm cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={watchedGroupIds.includes(g.id)}
                  onChange={() => onToggleGroup(g.id)}
                />
                {g.groupName}
              </label>
            ))}
          </div>
        </EventFormRow>
      )}

      {roles.length > 0 && (
        <EventFormRow label="Target Roles">
          <div className="grid grid-cols-2 gap-2">
            {roles.map((r) => (
              <label
                key={r.id}
                className="flex items-center gap-2 text-sm cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={watchedRoleIds.includes(r.id)}
                  onChange={() => onToggleRole(r.id)}
                />
                {r.roleName}
              </label>
            ))}
          </div>
        </EventFormRow>
      )}
    </form>
  );
}

function DateTimeLocalInput({
  field,
}: {
  field: {
    name: string;
    value?: string;
    onBlur: () => void;
    onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
    ref: (instance: HTMLInputElement | null) => void;
  };
}) {
  const dateId = useId();
  const timeId = useId();

  const [datePart, setDatePart] = useState(field.value ? field.value.slice(0, 10) : "");
  const [hourPart, setHourPart] = useState(field.value ? field.value.slice(11, 13) : "");
  const [minutePart, setMinutePart] = useState(field.value ? field.value.slice(14, 16) : "");

  useEffect(() => {
    if (field.value) {
      setDatePart(field.value.slice(0, 10));
      setHourPart(field.value.slice(11, 13));
      setMinutePart(field.value.slice(14, 16));
    }
  }, [field.value]);

  const emit = (date: string, hour: string, minute: string) => {
    if (date && hour !== "" && minute !== "") {
      const combined = `${date}T${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;
      field.onChange({ target: { value: combined } } as React.ChangeEvent<HTMLInputElement>);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <input
        id={dateId}
        type="date"
        className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
        value={datePart}
        onBlur={field.onBlur}
        ref={field.ref}
        onChange={(e) => {
          setDatePart(e.target.value);
          emit(e.target.value, hourPart, minutePart);
        }}
      />
      <div className="flex items-center gap-1">
        <input
          id={timeId}
          type="number"
          min={0}
          max={23}
          placeholder="HH"
          className="flex h-10 w-14 rounded-md border border-input bg-background px-2 py-2 text-sm text-center ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
          value={hourPart}
          onBlur={field.onBlur}
          onChange={(e) => {
            const v = String(Math.min(23, Math.max(0, Number(e.target.value))));
            setHourPart(v);
            emit(datePart, v, minutePart);
          }}
        />
        <span className="text-sm font-medium">:</span>
        <input
          type="number"
          min={0}
          max={59}
          placeholder="MM"
          className="flex h-10 w-14 rounded-md border border-input bg-background px-2 py-2 text-sm text-center ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
          value={minutePart}
          onBlur={field.onBlur}
          onChange={(e) => {
            const v = String(Math.min(59, Math.max(0, Number(e.target.value))));
            setMinutePart(v);
            emit(datePart, hourPart, v);
          }}
        />
        <span className="text-xs text-muted-foreground">24h</span>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function EventPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [upcoming, setUpcoming] = useState(true);
  const [createEventOpen, setCreateEventOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<Event | null>(null);
  const [rsvpEventId, setRsvpEventId] = useState<number | null>(null);
  const [eventSortState, setEventSortState] =
    useState<SortState<EventSortKey>>(initialEventSort);
  const [viewingEvent, setViewingEvent] = useState<Event | null>(null);
  // Selected events, keyed by id, so the selection persists across pages and
  // we keep each event snapshot for the bulk delete action.
  const [selected, setSelected] = useState<Map<number, Event>>(new Map());
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  // image state for create dialog
  const [createImageFile, setCreateImageFile] = useState<File | null>(null);
  const [createImagePreviewUrl, setCreateImagePreviewUrl] = useState<
    string | null
  >(null);

  // image state for edit dialog
  const [editImageFile, setEditImageFile] = useState<File | null>(null);
  const [editImagePreviewUrl, setEditImagePreviewUrl] = useState<string | null>(
    null,
  );

  const { user: currentUser } = useAuthContext();
  const { data, isPending } = useQueryEvents({
    page,
    limit: pageSize,
    upcoming,
    sortBy: eventSortState.key,
    sortOrder: eventSortState.direction,
  });

  const handlePageSizeChange = (size: number) => {
    setPageSize(size);
    setPage(1);
  };
  const { data: usersData } = useQueryUsers();
  const { data: groupsData } = useQueryGroups();
  const { data: rolesData } = useQueryRoles();
  const { data: eventTargetsData } = useQueryEventTargets(
    editingEvent?.id ?? null,
  );
  const { data: viewTargetsData } = useQueryEventTargets(
    viewingEvent?.id ?? null,
  );

  const { mutate: createEvent, isPending: isCreating } = useCreateEvent();
  const {
    mutate: deleteEvent,
    mutateAsync: deleteEventAsync,
    isPending: isDeleting,
  } = useDeleteEvent();
  const { mutate: updateEvent, isPending: isUpdating } = useUpdateEvent();
  const { mutateAsync: uploadEventImage, isPending: isUploading } =
    useUploadEventImage();
  const { data: rsvpData, isPending: isRsvpLoading } =
    useQueryEventRsvps(rsvpEventId);

  const allUsers = usersData?.data.items ?? [];
  const usersById = useMemo(
    () => new Map(allUsers.map((user) => [Number(user.id), user])),
    [allUsers],
  );
  const groups = groupsData?.data ?? [];
  const roles = rolesData?.data ?? [];

  const authUserId = Number(currentUser?.id);
  const currentAdminEmail = currentUser?.email ?? "";
  const currentUserRecord = allUsers.find((u) => u.email === currentAdminEmail);
  const currentUserId = Number.isFinite(authUserId)
    ? authUserId
    : currentUserRecord
      ? Number(currentUserRecord.id)
      : null;
  const currentHostName =
    currentUserId && usersById.has(currentUserId)
      ? formatHostName(currentUserId, usersById)
      : getAuthUserName(currentUser) || "---";

  const {
    control,
    handleSubmit,
    reset,
    register,
    watch,
    setValue,
    formState: { errors },
  } = useForm<CreateEventInput, undefined, CreateEvent>({
    defaultValues: {
      hostUserId: null,
      eventName: "",
      description: null,
      eventImage: null,
      location: null,
      locationLink: null,
      eventFormat: "in_person",
      eventTimezone: BROWSER_TZ,
      startAt: "",
      endsAt: "",
      targetGroupIds: [],
      targetRoleIds: [],
    },
    resolver: zodResolver(createEventSchema),
  });

  const createEventFormat = (watch("eventFormat") ?? "in_person") as EventFormat;
  const createGroupIds = watch("targetGroupIds") ?? [];
  const createRoleIds = watch("targetRoleIds") ?? [];

  useEffect(() => {
    if (currentUserId) {
      reset((prev) => ({ ...prev, hostUserId: currentUserId }));
    }
  }, [currentUserId, reset]);

  const {
    control: editControl,
    handleSubmit: handleEditSubmit,
    reset: resetEdit,
    register: registerEdit,
    watch: watchEdit,
    setValue: setEditValue,
    formState: { errors: editErrors },
  } = useForm<UpdateEventInput, undefined, UpdateEvent>({
    resolver: zodResolver(updateEventSchema),
  });

  const editEventFormat = (watchEdit("eventFormat") ?? "in_person") as EventFormat;
  const editGroupIds = watchEdit("targetGroupIds") ?? [];
  const editRoleIds = watchEdit("targetRoleIds") ?? [];

  // The upcoming/all toggle changes the matching set, so drop the selection.
  useEffect(() => {
    setPage(1);
    setSelected(new Map());
  }, [upcoming]);

  useEffect(() => {
    if (editingEvent) {
      const targets = eventTargetsData?.data;
      const tz = editingEvent.eventTimezone || BROWSER_TZ;
      resetEdit({
        hostUserId: editingEvent.hostUserId,
        eventName: editingEvent.eventName,
        description: editingEvent.description,
        eventImage: editingEvent.eventImage ?? null,
        location: editingEvent.location,
        locationLink: editingEvent.locationLink,
        eventFormat: editingEvent.eventFormat,
        eventTimezone: tz,
        startAt: toDatetimeLocalInTz(editingEvent.startDatetime, tz),
        endsAt: toDatetimeLocalInTz(editingEvent.endsDatetime, tz),
        targetGroupIds: targets?.groupIds ?? [],
        targetRoleIds: targets?.roleIds ?? [],
      });
      // Reset image state when switching events
      setEditImageFile(null);
      setEditImagePreviewUrl(null);
    }
  }, [editingEvent, eventTargetsData, resetEdit]);

  // Revoke object URLs on unmount / change to avoid memory leaks
  useEffect(() => {
    return () => {
      if (createImagePreviewUrl) URL.revokeObjectURL(createImagePreviewUrl);
    };
  }, [createImagePreviewUrl]);

  useEffect(() => {
    return () => {
      if (editImagePreviewUrl) URL.revokeObjectURL(editImagePreviewUrl);
    };
  }, [editImagePreviewUrl]);

  const handleCreateImageSelected = (file: File | null) => {
    if (createImagePreviewUrl) URL.revokeObjectURL(createImagePreviewUrl);
    setCreateImageFile(file);
    setCreateImagePreviewUrl(file ? URL.createObjectURL(file) : null);
  };

  const handleEditImageSelected = (file: File | null) => {
    if (editImagePreviewUrl) URL.revokeObjectURL(editImagePreviewUrl);
    setEditImageFile(file);
    setEditImagePreviewUrl(file ? URL.createObjectURL(file) : null);
  };

  const eventsList = useMemo(
    () => data?.data.items ?? [],
    [data?.data.items],
  );
  const total = data?.data.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  // Keep selected snapshots in sync with refetched page data so per-row edits
  // are reflected in the bulk-action selection.
  useEffect(() => {
    setSelected((prev) => {
      if (prev.size === 0) return prev;
      let changed = false;
      const next = new Map(prev);
      for (const event of eventsList) {
        if (next.has(event.id) && next.get(event.id) !== event) {
          next.set(event.id, event);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [eventsList]);

  const clearSelection = useCallback(() => setSelected(new Map()), []);

  const toggleRow = useCallback((event: Event) => {
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(event.id)) next.delete(event.id);
      else next.set(event.id, event);
      return next;
    });
  }, []);

  const toggleAllOnPage = useCallback(() => {
    setSelected((prev) => {
      const next = new Map(prev);
      const allSelected =
        eventsList.length > 0 && eventsList.every((e) => next.has(e.id));
      if (allSelected) {
        eventsList.forEach((e) => next.delete(e.id));
      } else {
        eventsList.forEach((e) => next.set(e.id, e));
      }
      return next;
    });
  }, [eventsList]);

  const selectedOnPage = eventsList.filter((event) => selected.has(event.id));
  const headerState: boolean | "indeterminate" =
    eventsList.length > 0 && selectedOnPage.length === eventsList.length
      ? true
      : selectedOnPage.length > 0
        ? "indeterminate"
        : false;

  const handleBulkDelete = async () => {
    const targets = [...selected.values()];
    if (!targets.length) {
      setDeleteConfirmOpen(false);
      return;
    }
    // Settle every delete independently so one failure doesn't strand the rest.
    const outcomes = await Promise.allSettled(
      targets.map((event) => deleteEventAsync(event.id).then(() => event.id)),
    );
    const deletedIds = outcomes
      .filter(
        (o): o is PromiseFulfilledResult<number> => o.status === "fulfilled",
      )
      .map((o) => o.value);
    const failed = targets.length - deletedIds.length;

    if (deletedIds.length) {
      // Drop only the events we actually deleted; keep other selections.
      setSelected((prev) => {
        const next = new Map(prev);
        deletedIds.forEach((id) => next.delete(id));
        return next;
      });
      if (rsvpEventId !== null && deletedIds.includes(rsvpEventId)) {
        setRsvpEventId(null);
      }
    }

    if (failed === 0) {
      toast.success(
        `Deleted ${deletedIds.length} event${deletedIds.length === 1 ? "" : "s"}.`,
      );
    } else if (deletedIds.length) {
      toast.error(
        `Deleted ${deletedIds.length}, but ${failed} could not be deleted.`,
      );
    } else {
      toast.error("Unable to delete the selected events.");
    }
    setDeleteConfirmOpen(false);
  };
  const rsvps: EventRsvp[] = rsvpData?.data ?? [];
  const rsvpEvent = eventsList.find((event) => event.id === rsvpEventId);
  const getRsvpSortValue = useCallback(
    (rsvp: EventRsvp, key: RsvpSortKey) => {
      const student = usersById.get(rsvp.userId);
      switch (key) {
        case "id":
          return rsvp.id;
        case "student":
          return student
            ? `${student.name} ${student.email}`
            : `User #${rsvp.userId}`;
        case "status":
          return RSVP_STATUS_LABELS[rsvp.rsvpStatus]?.label ?? rsvp.rsvpStatus;
        case "responded":
          return rsvp.respondedAt ?? "";
      }
    },
    [usersById],
  );
  const {
    sortState: rsvpSortState,
    setSortState: setRsvpSortState,
    sortedRows: sortedRsvps,
  } = useSortableRows(rsvps, initialRsvpSort, getRsvpSortValue);

  const toggleId = (
    ids: number[],
    id: number,
    setter: (val: number[]) => void,
  ) => {
    setter(ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]);
  };

  const onSubmit = async (formData: CreateEvent) => {
    createEvent(formData, {
      onSuccess: async (result) => {
        if (result.data) {
          const newEventId = result.data.id;
          // Upload image if one was selected
          if (createImageFile && newEventId) {
            await uploadEventImage({
              eventId: newEventId,
              file: createImageFile,
            });
          }
          setCreateEventOpen(false);
          handleCreateImageSelected(null);
          reset({
            hostUserId: currentUserId,
            eventName: "",
            description: null,
            eventImage: null,
            location: null,
            locationLink: null,
            eventFormat: "in_person",
            eventTimezone: BROWSER_TZ,
            startAt: "",
            endsAt: "",
            targetGroupIds: [],
            targetRoleIds: [],
          });
        }
      },
    });
  };

  const onEditSubmit = async (formData: UpdateEvent) => {
    if (!editingEvent) return;
    updateEvent(
      { id: editingEvent.id, data: formData },
      {
        onSuccess: async () => {
          // Upload image if a new one was selected
          if (editImageFile) {
            await uploadEventImage({
              eventId: editingEvent.id,
              file: editImageFile,
            });
          }
          setEditingEvent(null);
          handleEditImageSelected(null);
          resetEdit();
        },
      },
    );
  };

  const handleDelete = (event: Event) => {
    const shouldDelete = window.confirm(
      "Delete event " + event.eventName + "? All RSVPs will also be deleted.",
    );
    if (!shouldDelete) return;
    deleteEvent(event.id, {
      onSuccess: () => {
        if (rsvpEventId === event.id) setRsvpEventId(null);
      },
    });
  };

  return (
    <div className="min-w-0 space-y-4 p-4">
      <div className="flex flex-wrap gap-3 p-4 items-end justify-between">
        <div className="inline-flex rounded-md border p-0.5">
          <Button
            type="button"
            variant={upcoming ? "default" : "ghost"}
            size="sm"
            onClick={() => setUpcoming(true)}
          >
            Upcoming
          </Button>
          <Button
            type="button"
            variant={!upcoming ? "default" : "ghost"}
            size="sm"
            onClick={() => setUpcoming(false)}
          >
            All Events
          </Button>
        </div>
        <Button type="button" onClick={() => setCreateEventOpen(true)}>
          <CalendarIcon className="size-4" />
          Create Event
        </Button>
      </div>

      {selected.size > 0 && (
        <BulkActionsBar
          count={selected.size}
          noun="event"
          onClear={clearSelection}
          disabled={isDeleting}
        >
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setDeleteConfirmOpen(true)}
            disabled={isDeleting}
          >
            <Trash2Icon className="size-4" />
            Delete
          </Button>
        </BulkActionsBar>
      )}

      <div className="min-w-0 overflow-hidden rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <Checkbox
                  checked={headerState}
                  onCheckedChange={toggleAllOnPage}
                  aria-label="Select all on this page"
                  disabled={isPending || eventsList.length === 0}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Event Name"
                  sortKey="name"
                  sortState={eventSortState}
                  onSortChange={(nextSort) => {
                    setEventSortState(nextSort);
                    setPage(1);
                  }}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Host"
                  sortKey="host"
                  sortState={eventSortState}
                  onSortChange={(nextSort) => {
                    setEventSortState(nextSort);
                    setPage(1);
                  }}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Location / Link"
                  sortKey="location"
                  sortState={eventSortState}
                  onSortChange={(nextSort) => {
                    setEventSortState(nextSort);
                    setPage(1);
                  }}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Start"
                  sortKey="start"
                  sortState={eventSortState}
                  onSortChange={(nextSort) => {
                    setEventSortState(nextSort);
                    setPage(1);
                  }}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="End"
                  sortKey="end"
                  sortState={eventSortState}
                  onSortChange={(nextSort) => {
                    setEventSortState(nextSort);
                    setPage(1);
                  }}
                />
              </TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isPending ? (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center">
                  Loading events...
                </TableCell>
              </TableRow>
            ) : eventsList.length > 0 ? (
              eventsList.map((event) => {
                const isPast = new Date(event.endsDatetime) < new Date();
                return (
                <TableRow
                  key={event.id}
                  data-state={selected.has(event.id) ? "selected" : undefined}
                  className={isPast ? "text-muted-foreground bg-muted/30" : ""}
                >
                  <TableCell
                    className="w-10"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Checkbox
                      checked={selected.has(event.id)}
                      onCheckedChange={() => toggleRow(event)}
                      aria-label={`Select ${event.eventName}`}
                    />
                  </TableCell>
                  <TableCell
                    className={`border-l-4 ${isPast ? "border-l-gray-400" : "border-l-green-500"}`}
                  >
                    {event.eventName}
                  </TableCell>
                  <TableCell>{formatEventHost(event, usersById)}</TableCell>
                  <TableCell>
                    {event.location ? (
                      event.location
                    ) : event.locationLink ? (
                      <a
                        href={event.locationLink}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-500 underline"
                      >
                        Link
                      </a>
                    ) : (
                      "---"
                    )}
                  </TableCell>
                  <TableCell>{formatDateTime(event.startDatetime)}</TableCell>
                  <TableCell>{formatDateTime(event.endsDatetime)}</TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label={`Open actions for ${event.eventName}`}
                        >
                          <MoreHorizontalIcon className="size-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={() =>
                            setViewingEvent(
                              viewingEvent?.id === event.id ? null : event,
                            )
                          }
                        >
                          <EyeIcon className="size-4" />
                          View
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() =>
                            setRsvpEventId(
                              rsvpEventId === event.id ? null : event.id,
                            )
                          }
                        >
                          <UsersIcon className="size-4" />
                          RSVP
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() =>
                            setEditingEvent(
                              editingEvent?.id === event.id ? null : event,
                            )
                          }
                        >
                          <PencilIcon className="size-4" />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          variant="destructive"
                          disabled={isDeleting}
                          onClick={() => handleDelete(event)}
                        >
                          <Trash2Icon className="size-4" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
                );
              })
            ) : (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center">
                  No events found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <TablePaginationBar
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        pageSize={pageSize}
        onPageSizeChange={handlePageSizeChange}
        disabled={isPending}
      />

      {/* ── View Dialog ──────────────────────────────────────────────────── */}
      <Dialog
        open={!!viewingEvent}
        onOpenChange={(open) => {
          if (!open) setViewingEvent(null);
        }}
      >
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {viewingEvent?.eventName ?? "Event Details"}
            </DialogTitle>
            <DialogDescription>Event #{viewingEvent?.id}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-5 px-4 pb-4">
            <EventDetailRow label="Host">
              <p>
                {viewingEvent
                  ? formatEventHost(viewingEvent, usersById)
                  : "---"}
              </p>
            </EventDetailRow>
            <EventDetailRow label="Description">
              <p>{viewingEvent?.description || "---"}</p>
            </EventDetailRow>
            {viewingEvent?.eventImage && (
              <EventDetailRow label="Image">
                <img
                  src={viewingEvent.eventImage}
                  alt={viewingEvent.eventName}
                  className="w-full rounded-md object-cover"
                  style={{ maxHeight: 220 }}
                />
              </EventDetailRow>
            )}
            <EventDetailRow label="Event Type">
              <p>
                {viewingEvent
                  ? EVENT_FORMAT_LABELS[viewingEvent.eventFormat] ?? viewingEvent.eventFormat
                  : "---"}
              </p>
            </EventDetailRow>
            {viewingEvent && viewingEvent.eventFormat !== "virtual" && (
              <EventDetailRow label="Location">
                <p>{viewingEvent.location || "---"}</p>
              </EventDetailRow>
            )}
            {viewingEvent?.locationLink && (
              <EventDetailRow
                label={
                  viewingEvent.eventFormat !== "virtual"
                    ? "Google Map Link"
                    : "Meeting Link"
                }
              >
                <p>
                  <a
                    href={viewingEvent.locationLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="break-all text-blue-500 underline"
                  >
                    {viewingEvent.locationLink}
                  </a>
                </p>
              </EventDetailRow>
            )}
            <EventDetailRow label="Start">
              <p>
                {viewingEvent
                  ? formatDateTimeInTz(viewingEvent.startDatetime, viewingEvent.eventTimezone || BROWSER_TZ)
                  : "---"}
              </p>
            </EventDetailRow>
            <EventDetailRow label="End">
              <p>
                {viewingEvent
                  ? formatDateTimeInTz(viewingEvent.endsDatetime, viewingEvent.eventTimezone || BROWSER_TZ)
                  : "---"}
              </p>
            </EventDetailRow>
            <EventDetailRow label="Timezone">
              <p>{viewingEvent?.eventTimezone || "UTC"}</p>
            </EventDetailRow>

            {/* Event Image — thumbnail + click to open full size */}
            {viewingEvent?.eventImage && (
              <EventDetailRow label="Event Image">
                <a
                  href={viewingEvent.eventImage!}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Click to open full image"
                >
                  <img
                    src={viewingEvent.eventImage!}
                    alt="Event banner"
                    className="h-20 w-auto rounded-md border object-cover transition-opacity hover:opacity-80"
                  />
                </a>
                <p className="mt-1 text-xs text-muted-foreground">
                  Click image to open full size
                </p>
              </EventDetailRow>
            )}

            {(viewTargetsData?.data?.groupIds?.length ?? 0) > 0 && (
              <EventDetailRow label="Target Groups">
                <div className="flex flex-wrap gap-1.5">
                  {viewTargetsData!.data!.groupIds.map((id) => {
                    const g = groups.find((x) => x.id === id);
                    return g ? (
                      <Badge key={id} variant="secondary">
                        {g.groupName}
                      </Badge>
                    ) : null;
                  })}
                </div>
              </EventDetailRow>
            )}
            {(viewTargetsData?.data?.roleIds?.length ?? 0) > 0 && (
              <EventDetailRow label="Target Roles">
                <div className="flex flex-wrap gap-1.5">
                  {viewTargetsData!.data!.roleIds.map((id) => {
                    const r = roles.find((x) => x.id === id);
                    return r ? (
                      <Badge key={id} variant="secondary">
                        {r.roleName}
                      </Badge>
                    ) : null;
                  })}
                </div>
              </EventDetailRow>
            )}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setViewingEvent(null)}
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Create Dialog ────────────────────────────────────────────────── */}
      <Dialog
        open={createEventOpen}
        onOpenChange={(open) => {
          setCreateEventOpen(open);
          if (!open) {
            handleCreateImageSelected(null);
            reset({
              hostUserId: currentUserId,
              eventName: "",
              description: null,
              location: null,
              locationLink: null,
              eventFormat: "in_person",
              eventTimezone: BROWSER_TZ,
              startAt: "",
              endsAt: "",
              targetGroupIds: [],
              targetRoleIds: [],
            });
          }
        }}
      >
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Create Event</DialogTitle>
            <DialogDescription>
              Add an event to the {BRAND_NAME} program calendar.
            </DialogDescription>
          </DialogHeader>
          <EventForm
            formId="create-event-form"
            control={control}
            register={register}
            errors={errors}
            eventFormat={createEventFormat}
            currentHostName={currentHostName}
            groups={groups}
            roles={roles}
            watchedGroupIds={createGroupIds}
            watchedRoleIds={createRoleIds}
            onToggleGroup={(id) =>
              toggleId(createGroupIds, id, (v) => setValue("targetGroupIds", v))
            }
            onToggleRole={(id) =>
              toggleId(createRoleIds, id, (v) => setValue("targetRoleIds", v))
            }
            onSubmit={handleSubmit(onSubmit)}
            existingImageUrl={null}
            imagePreviewUrl={createImagePreviewUrl}
            onImageFileSelected={handleCreateImageSelected}
          />
          <DialogFooter>
            <Button
              form="create-event-form"
              type="submit"
              disabled={isCreating || isUploading}
            >
              <CalendarIcon className="size-4" />
              {isCreating
                ? "Creating..."
                : isUploading
                  ? "Uploading image..."
                  : "Create Event"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => setCreateEventOpen(false)}
            >
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── RSVP Dialog ──────────────────────────────────────────────────── */}
      <Dialog
        open={rsvpEventId !== null}
        onOpenChange={(open) => {
          if (!open) setRsvpEventId(null);
        }}
      >
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle>
              RSVP List {rsvpEvent ? "- " + rsvpEvent.eventName : ""}
            </DialogTitle>
            <DialogDescription>
              Event #{rsvpEventId} has {rsvps.length} RSVP
              {rsvps.length === 1 ? "" : "s"}.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 px-4 pb-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-medium">RSVPs</h3>
                <Badge variant="outline">{rsvps.length}</Badge>
              </div>
              <div className="overflow-x-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>
                        <SortableTableHead
                          label="RSVP ID"
                          sortKey="id"
                          sortState={rsvpSortState}
                          onSortChange={setRsvpSortState}
                        />
                      </TableHead>
                      <TableHead>
                        <SortableTableHead
                          label="Student"
                          sortKey="student"
                          sortState={rsvpSortState}
                          onSortChange={setRsvpSortState}
                        />
                      </TableHead>
                      <TableHead>
                        <SortableTableHead
                          label="Status"
                          sortKey="status"
                          sortState={rsvpSortState}
                          onSortChange={setRsvpSortState}
                        />
                      </TableHead>
                      <TableHead>
                        <SortableTableHead
                          label="Responded At"
                          sortKey="responded"
                          sortState={rsvpSortState}
                          onSortChange={setRsvpSortState}
                        />
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {isRsvpLoading ? (
                      <TableRow>
                        <TableCell colSpan={4} className="text-center">
                          Loading...
                        </TableCell>
                      </TableRow>
                    ) : rsvps.length > 0 ? (
                      sortedRsvps.map((rsvp) => {
                        const student = usersById.get(rsvp.userId);
                        const statusInfo = RSVP_STATUS_LABELS[
                          rsvp.rsvpStatus
                        ] ?? {
                          label: rsvp.rsvpStatus,
                          variant: "outline" as const,
                        };
                        return (
                          <TableRow key={rsvp.id}>
                            <TableCell>{rsvp.id}</TableCell>
                            <TableCell>
                              {student
                                ? student.name + " (" + student.email + ")"
                                : "User #" + rsvp.userId}
                            </TableCell>
                            <TableCell>
                              <Badge variant={statusInfo.variant}>
                                {statusInfo.label}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              {rsvp.respondedAt
                                ? formatDateTime(rsvp.respondedAt)
                                : "---"}
                            </TableCell>
                          </TableRow>
                        );
                      })
                    ) : (
                      <TableRow>
                        <TableCell colSpan={4} className="text-center">
                          No RSVPs yet.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setRsvpEventId(null)}
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Edit Dialog ──────────────────────────────────────────────────── */}
      <Dialog
        open={!!editingEvent}
        onOpenChange={(open) => {
          if (!open) {
            setEditingEvent(null);
            handleEditImageSelected(null);
          }
        }}
      >
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Event #{editingEvent?.id}</DialogTitle>
            <DialogDescription>Update the event details.</DialogDescription>
          </DialogHeader>
          <EventForm
            formId="edit-event-form"
            control={editControl}
            register={registerEdit}
            errors={editErrors}
            eventFormat={editEventFormat}
            currentHostName={
              editingEvent
                ? formatEventHost(editingEvent, usersById)
                : currentHostName
            }
            groups={groups}
            roles={roles}
            watchedGroupIds={editGroupIds}
            watchedRoleIds={editRoleIds}
            onToggleGroup={(id) =>
              toggleId(editGroupIds, id, (v) =>
                setEditValue("targetGroupIds", v),
              )
            }
            onToggleRole={(id) =>
              toggleId(editRoleIds, id, (v) => setEditValue("targetRoleIds", v))
            }
            onSubmit={handleEditSubmit(onEditSubmit)}
            existingImageUrl={editingEvent?.eventImage ?? null}
            imagePreviewUrl={editImagePreviewUrl}
            onImageFileSelected={handleEditImageSelected}
          />
          <DialogFooter>
            <Button
              form="edit-event-form"
              type="submit"
              disabled={isUpdating || isUploading}
            >
              {isUpdating
                ? "Saving..."
                : isUploading
                  ? "Uploading image..."
                  : "Save Changes"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setEditingEvent(null);
                handleEditImageSelected(null);
              }}
            >
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Bulk Delete Confirm ──────────────────────────────────────────── */}
      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {selected.size} {selected.size === 1 ? "event" : "events"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              All RSVPs will also be deleted. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={isDeleting}
              onClick={(event) => {
                event.preventDefault();
                void handleBulkDelete();
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatHostName(
  hostUserId: number,
  usersById: Map<number, { name: string; email: string }>,
) {
  const user = usersById.get(hostUserId);
  return user?.name || user?.email || "Unassigned";
}

function formatEventHost(
  event: Event,
  usersById: Map<number, { name: string; email: string }>,
) {
  return (
    event.hostName ||
    event.hostEmail ||
    (event.hostUserId ? formatHostName(event.hostUserId, usersById) : null) ||
    "Unassigned"
  );
}

function getAuthUserName(user: any) {
  if (!user) return "";
  const firstName = typeof user.firstName === "string" ? user.firstName : "";
  const lastName = typeof user.lastName === "string" ? user.lastName : "";
  const fullName = `${firstName} ${lastName}`.trim();
  return fullName || user.name || user.email || "";
}

/** Convert a UTC ISO string to a datetime-local value displayed in the given IANA timezone. */
function toDatetimeLocalInTz(utcIso: string, timeZone: string): string {
  if (!utcIso) return "";
  const date = new Date(utcIso);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "00";
  const h = get("hour") === "24" ? "00" : get("hour");
  return `${get("year")}-${get("month")}-${get("day")}T${h}:${get("minute")}`;
}

/** Format a UTC ISO datetime for display in the given IANA timezone, with TZ abbreviation. */
function formatDateTimeInTz(utcIso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
  }).format(new Date(utcIso));
}

const BROWSER_TZ = Intl.DateTimeFormat().resolvedOptions().timeZone;

const ALL_TIMEZONES: string[] = (() => {
  try {
    return (Intl as any).supportedValuesOf("timeZone") as string[];
  } catch {
    return [BROWSER_TZ];
  }
})();

function tzOffsetLabel(tz: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    timeZoneName: "shortOffset",
  }).formatToParts(new Date());
  return parts.find((p) => p.type === "timeZoneName")?.value ?? "";
}

function TimezoneCombobox({
  value,
  onChange,
}: {
  value: string;
  onChange: (val: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!search.trim()) return ALL_TIMEZONES.slice(0, 100);
    const q = search.toLowerCase();
    return ALL_TIMEZONES.filter((tz) => tz.toLowerCase().includes(q)).slice(0, 100);
  }, [search]);

  const displayLabel = value
    ? `${value} (${tzOffsetLabel(value)})`
    : "Select timezone";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between font-normal"
        >
          <span className="truncate">{displayLabel}</span>
          <ChevronsUpDownIcon className="ml-2 size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
        <Command>
          <CommandInput
            placeholder="Search timezone..."
            value={search}
            onValueChange={setSearch}
          />
          <CommandList className="max-h-60 overflow-y-auto" onWheel={(e) => e.stopPropagation()}>
            <CommandEmpty>No timezone found.</CommandEmpty>
            {filtered.map((tz) => (
              <CommandItem
                key={tz}
                value={tz}
                onSelect={() => {
                  onChange(tz);
                  setSearch("");
                  setOpen(false);
                }}
              >
                {tz} <span className="ml-auto text-xs text-muted-foreground">{tzOffsetLabel(tz)}</span>
              </CommandItem>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
