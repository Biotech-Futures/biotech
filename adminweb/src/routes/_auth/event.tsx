import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import {
  SortableTableHead,
  useSortableRows,
  type SortState,
} from "@/components/ui/sortable-table";
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
  useQueryTracks,
  useQueryEventTargets,
} from "@/query/event";
import { useQueryUsers } from "@/query/user";
import type { Event, EventRsvp } from "@/type/event";
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
} from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";

export const Route = createFileRoute("/_auth/event")({
  component: EventPage,
});

const RSVP_STATUS_LABELS: Record<
  string,
  { label: string; variant: "default" | "outline" | "secondary" }
> = {
  going: { label: "Going", variant: "default" },
  maybe: { label: "Maybe", variant: "secondary" },
  declined: { label: "Declined", variant: "outline" },
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
  isVirtual: boolean;
  currentHostName: string;
  groups: { id: number; groupName: string; trackId: number | null; trackName: string | null }[];
  roles: { id: number; roleName: string }[];
  tracks: { id: number; trackName: string }[];
  watchedGroupIds: number[];
  watchedRoleIds: number[];
  watchedTrackIds: number[];
  onToggleGroup: (id: number) => void;
  onToggleRole: (id: number) => void;
  onToggleTrack: (id: number) => void;
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
  isVirtual,
  currentHostName,
  groups,
  roles,
  tracks,
  watchedGroupIds,
  watchedRoleIds,
  watchedTrackIds,
  onToggleGroup,
  onToggleRole,
  onToggleTrack,
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
        name="isVirtual"
        render={({ field }) => (
          <EventFormRow label="Event Type">
            <Select
              value={field.value ? "true" : "false"}
              onValueChange={(val) => field.onChange(val === "true")}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="false">In-person</SelectItem>
                <SelectItem value="true">Virtual</SelectItem>
              </SelectContent>
            </Select>
          </EventFormRow>
        )}
      />

      {!isVirtual && (
        <EventFormRow label="Location">
          <Input
            placeholder="Venue address or room"
            {...register("location")}
          />
        </EventFormRow>
      )}

      <EventFormRow label={isVirtual ? "Meeting Link" : "Google Map Link"}>
        <Input
          placeholder={
            isVirtual ? "https://zoom.us/..." : "https://maps.google.com/..."
          }
          {...register("locationLink")}
        />
      </EventFormRow>

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
          <div className="space-y-3">
            {Object.entries(
              groups.reduce<Record<string, typeof groups>>((acc, g) => {
                const key = g.trackName ?? "No Track";
                if (!acc[key]) acc[key] = [];
                acc[key].push(g);
                return acc;
              }, {})
            ).map(([trackName, trackGroups]) => (
              <div key={trackName}>
                <p className="text-xs font-medium text-muted-foreground mb-1">{trackName}</p>
                <div className="grid grid-cols-2 gap-2">
                  {trackGroups.map((g) => (
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
              </div>
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

      {tracks.length > 0 && (
        <EventFormRow label="Target Tracks">
          <div className="grid grid-cols-2 gap-2">
            {tracks.map((t) => (
              <label
                key={t.id}
                className="flex items-center gap-2 text-sm cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={watchedTrackIds.includes(t.id)}
                  onChange={() => onToggleTrack(t.id)}
                />
                {t.trackName}
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
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement | null>(null);

  const openPicker = () => {
    const input = inputRef.current;
    if (!input) return;
    input.focus();
    try {
      input.showPicker?.();
    } catch {
      // ignore
    }
  };

  return (
    <div className="flex h-10 w-full overflow-hidden rounded-md border border-input bg-background ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2">
      <input
        id={inputId}
        type="datetime-local"
        className="min-w-0 flex-1 bg-transparent px-3 py-2 text-sm outline-none"
        name={field.name}
        onBlur={field.onBlur}
        onChange={field.onChange}
        onClick={openPicker}
        ref={(element) => {
          field.ref(element);
          inputRef.current = element;
        }}
        value={field.value ?? ""}
      />
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function EventPage() {
  const [page, setPage] = useState(1);
  const [upcoming, setUpcoming] = useState(true);
  const [createEventOpen, setCreateEventOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<Event | null>(null);
  const [rsvpEventId, setRsvpEventId] = useState<number | null>(null);
  const [eventSortState, setEventSortState] =
    useState<SortState<EventSortKey>>(initialEventSort);
  const [viewingEvent, setViewingEvent] = useState<Event | null>(null);

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
    limit: 10,
    upcoming,
    sortBy: eventSortState.key,
    sortOrder: eventSortState.direction,
  });
  const { data: usersData } = useQueryUsers();
  const { data: groupsData } = useQueryGroups();
  const { data: rolesData } = useQueryRoles();
  const { data: tracksData } = useQueryTracks();
  const { data: eventTargetsData } = useQueryEventTargets(
    editingEvent?.id ?? null,
  );
  const { data: viewTargetsData } = useQueryEventTargets(
    viewingEvent?.id ?? null,
  );

  const { mutate: createEvent, isPending: isCreating } = useCreateEvent();
  const { mutate: deleteEvent, isPending: isDeleting } = useDeleteEvent();
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
  const tracks = tracksData?.data ?? [];

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
      isVirtual: false,
      startAt: "",
      endsAt: "",
      targetGroupIds: [],
      targetRoleIds: [],
      targetTrackIds: [],
    },
    resolver: zodResolver(createEventSchema),
  });

  const createIsVirtual = watch("isVirtual");
  const createGroupIds = watch("targetGroupIds") ?? [];
  const createRoleIds = watch("targetRoleIds") ?? [];
  const createTrackIds = watch("targetTrackIds") ?? [];

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

  const editIsVirtual = watchEdit("isVirtual");
  const editGroupIds = watchEdit("targetGroupIds") ?? [];
  const editRoleIds = watchEdit("targetRoleIds") ?? [];
  const editTrackIds = watchEdit("targetTrackIds") ?? [];

  useEffect(() => {
    setPage(1);
  }, [upcoming]);

  useEffect(() => {
    if (editingEvent) {
      const targets = eventTargetsData?.data;
      resetEdit({
        hostUserId: editingEvent.hostUserId,
        eventName: editingEvent.eventName,
        description: editingEvent.description,
        eventImage: editingEvent.eventImage ?? null,
        location: editingEvent.location,
        locationLink: editingEvent.locationLink,
        isVirtual: editingEvent.isVirtual,
        startAt: toDatetimeLocal(editingEvent.startDatetime),
        endsAt: toDatetimeLocal(editingEvent.endsDatetime),
        targetGroupIds: targets?.groupIds ?? [],
        targetRoleIds: targets?.roleIds ?? [],
        targetTrackIds: targets?.trackIds ?? [],
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

  const eventsList = data?.data.items ?? [];
  const total = data?.data.total ?? 0;
  const limit = data?.data.limit ?? 10;
  const totalPages = Math.max(1, Math.ceil(total / limit));
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
            isVirtual: false,
            startAt: "",
            endsAt: "",
            targetGroupIds: [],
            targetRoleIds: [],
            targetTrackIds: [],
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
        <Button
          type="button"
          variant={upcoming ? "default" : "outline"}
          onClick={() => setUpcoming((v) => !v)}
        >
          {upcoming ? "Upcoming Only" : "All Events"}
        </Button>
        <Button type="button" onClick={() => setCreateEventOpen(true)}>
          <CalendarIcon className="size-4" />
          Create Event
        </Button>
      </div>

      <div className="min-w-0 overflow-hidden rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
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
              eventsList.map((event) => (
                <TableRow key={event.id}>
                  <TableCell>{event.eventName}</TableCell>
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
              ))
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

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Page {page} of {totalPages}
        </p>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={page <= 1 || isPending}
            onClick={() => setPage((v) => Math.max(1, v - 1))}
          >
            Previous
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={page >= totalPages || isPending}
            onClick={() => setPage((v) => v + 1)}
          >
            Next
          </Button>
        </div>
      </div>

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
              <p>{viewingEvent?.isVirtual ? "Virtual" : "In-person"}</p>
            </EventDetailRow>
            {!viewingEvent?.isVirtual && (
              <EventDetailRow label="Location">
                <p>{viewingEvent?.location || "---"}</p>
              </EventDetailRow>
            )}
            {viewingEvent?.locationLink && (
              <EventDetailRow
                label={
                  viewingEvent.isVirtual ? "Meeting Link" : "Google Map Link"
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
                  ? formatDateTime(viewingEvent.startDatetime)
                  : "---"}
              </p>
            </EventDetailRow>
            <EventDetailRow label="End">
              <p>
                {viewingEvent
                  ? formatDateTime(viewingEvent.endsDatetime)
                  : "---"}
              </p>
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
            {(viewTargetsData?.data?.trackIds?.length ?? 0) > 0 && (
              <EventDetailRow label="Target Tracks">
                <div className="flex flex-wrap gap-1.5">
                  {viewTargetsData!.data!.trackIds.map((id) => {
                    const t = tracks.find((x) => x.id === id);
                    return t ? (
                      <Badge key={id} variant="secondary">
                        {t.trackName}
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
              isVirtual: false,
              startAt: "",
              endsAt: "",
              targetGroupIds: [],
              targetRoleIds: [],
              targetTrackIds: [],
            });
          }
        }}
      >
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Create Event</DialogTitle>
            <DialogDescription>
              Add an event to the BIOTech Futures program calendar.
            </DialogDescription>
          </DialogHeader>
          <EventForm
            formId="create-event-form"
            control={control}
            register={register}
            errors={errors}
            isVirtual={!!createIsVirtual}
            currentHostName={currentHostName}
            groups={groups}
            roles={roles}
            tracks={tracks}
            watchedGroupIds={createGroupIds}
            watchedRoleIds={createRoleIds}
            watchedTrackIds={createTrackIds}
            onToggleGroup={(id) =>
              toggleId(createGroupIds, id, (v) => setValue("targetGroupIds", v))
            }
            onToggleRole={(id) =>
              toggleId(createRoleIds, id, (v) => setValue("targetRoleIds", v))
            }
            onToggleTrack={(id) =>
              toggleId(createTrackIds, id, (v) => setValue("targetTrackIds", v))
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
            isVirtual={!!editIsVirtual}
            currentHostName={
              editingEvent
                ? formatEventHost(editingEvent, usersById)
                : currentHostName
            }
            groups={groups}
            roles={roles}
            tracks={tracks}
            watchedGroupIds={editGroupIds}
            watchedRoleIds={editRoleIds}
            watchedTrackIds={editTrackIds}
            onToggleGroup={(id) =>
              toggleId(editGroupIds, id, (v) =>
                setEditValue("targetGroupIds", v),
              )
            }
            onToggleRole={(id) =>
              toggleId(editRoleIds, id, (v) => setEditValue("targetRoleIds", v))
            }
            onToggleTrack={(id) =>
              toggleId(editTrackIds, id, (v) =>
                setEditValue("targetTrackIds", v),
              )
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

function toDatetimeLocal(value: string) {
  const date = new Date(value);
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    date.getFullYear() +
    "-" +
    pad(date.getMonth() + 1) +
    "-" +
    pad(date.getDate()) +
    "T" +
    pad(date.getHours()) +
    ":" +
    pad(date.getMinutes())
  );
}
