import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
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
} from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import { useEffect, useId, useMemo, useRef, useState } from "react";

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

interface EventFormProps {
  formId: string;
  control: any;
  register: any;
  errors: any;
  isVirtual: boolean;
  currentHostName: string;
  groups: { id: number; groupName: string }[];
  roles: { id: number; roleName: string }[];
  tracks: { id: number; trackName: string }[];
  watchedGroupIds: number[];
  watchedRoleIds: number[];
  watchedTrackIds: number[];
  onToggleGroup: (id: number) => void;
  onToggleRole: (id: number) => void;
  onToggleTrack: (id: number) => void;
  onSubmit: (e: React.FormEvent) => void;
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
}: EventFormProps) {
  return (
    <form id={formId} className="grid gap-5 px-4 pb-4" onSubmit={onSubmit}>
      <div className="space-y-1.5">
        <Label>Host</Label>
        <Input
          value={currentHostName}
          readOnly
          disabled
          className="bg-muted text-muted-foreground cursor-not-allowed"
        />
      </div>

      <div className="space-y-1.5">
        <Label>Event Name</Label>
        <Input placeholder="Event name" {...register("eventName")} />
        {errors.eventName && (
          <p className="text-sm text-destructive">{errors.eventName.message}</p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label>Description</Label>
        <Input placeholder="Optional" {...register("description")} />
      </div>

      <Controller
        control={control}
        name="isVirtual"
        render={({ field }) => (
          <div className="space-y-1.5">
            <Label>Event Type</Label>
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
          </div>
        )}
      />

      {!isVirtual && (
        <div className="space-y-1.5">
          <Label>Location</Label>
          <Input
            placeholder="Venue address or room"
            {...register("location")}
          />
        </div>
      )}

      <div className="space-y-1.5">
        <Label>{isVirtual ? "Meeting Link" : "Google Map Link"}</Label>
        <Input
          placeholder={isVirtual ? "https://zoom.us/..." : "https://maps.google.com/..."}
          {...register("locationLink")}
        />
      </div>

      <Controller
        control={control}
        name="startAt"
        render={({ field }) => (
          <div className="space-y-1.5">
            <Label>Start</Label>
            <DateTimeLocalInput field={field} />
            {errors.startAt && (
              <p className="text-sm text-destructive">
                {errors.startAt.message}
              </p>
            )}
          </div>
        )}
      />

      <Controller
        control={control}
        name="endsAt"
        render={({ field }) => (
          <div className="space-y-1.5">
            <Label>End</Label>
            <DateTimeLocalInput field={field} />
            {errors.endsAt && (
              <p className="text-sm text-destructive">
                {errors.endsAt.message}
              </p>
            )}
          </div>
        )}
      />

      {groups.length > 0 && (
        <div className="space-y-2">
          <Label>Target Groups</Label>
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
        </div>
      )}

      {roles.length > 0 && (
        <div className="space-y-2">
          <Label>Target Roles</Label>
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
        </div>
      )}

      {tracks.length > 0 && (
        <div className="space-y-2">
          <Label>Target Tracks</Label>
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
        </div>
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

function EventPage() {
  const [page, setPage] = useState(1);
  const [upcoming, setUpcoming] = useState(true);
  const [createEventOpen, setCreateEventOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<Event | null>(null);
  const [rsvpEventId, setRsvpEventId] = useState<number | null>(null);
  const [viewingEvent, setViewingEvent] = useState<Event | null>(null);

  const { user: currentUser } = useAuthContext();
  const { data, isPending } = useQueryEvents({ page, limit: 10, upcoming });
  const { data: usersData } = useQueryUsers();
  const { data: groupsData } = useQueryGroups();
  const { data: rolesData } = useQueryRoles();
  const { data: tracksData } = useQueryTracks();
  const { data: eventTargetsData } = useQueryEventTargets(editingEvent?.id ?? null);
  const { data: viewTargetsData } = useQueryEventTargets(viewingEvent?.id ?? null);

  const { mutate: createEvent, isPending: isCreating } = useCreateEvent();
  const { mutate: deleteEvent, isPending: isDeleting } = useDeleteEvent();
  const { mutate: updateEvent, isPending: isUpdating } = useUpdateEvent();
  const { data: rsvpData, isPending: isRsvpLoading } = useQueryEventRsvps(rsvpEventId);

  const allUsers = usersData?.data.items ?? [];
  const usersById = useMemo(
    () => new Map(allUsers.map((user) => [Number(user.id), user])),
    [allUsers],
  );
  const groups = groupsData?.data ?? [];
  const roles = rolesData?.data ?? [];
  const tracks = tracksData?.data ?? [];

  const currentAdminEmail = currentUser?.email ?? "";
  const currentUserRecord = allUsers.find((u) => u.email === currentAdminEmail);
  const currentUserId = currentUserRecord ? Number(currentUserRecord.id) : null;
  const currentHostName = currentUserId
    ? formatHostName(currentUserId, usersById)
    : "---";

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
        location: editingEvent.location,
        locationLink: editingEvent.locationLink,
        isVirtual: editingEvent.isVirtual,
        startAt: toDatetimeLocal(editingEvent.startDatetime),
        endsAt: toDatetimeLocal(editingEvent.endsDatetime),
        targetGroupIds: targets?.groupIds ?? [],
        targetRoleIds: targets?.roleIds ?? [],
        targetTrackIds: targets?.trackIds ?? [],
      });
    }
  }, [editingEvent, eventTargetsData, resetEdit]);

  const eventsList = data?.data.items ?? [];
  const total = data?.data.total ?? 0;
  const limit = data?.data.limit ?? 10;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const rsvps: EventRsvp[] = rsvpData?.data ?? [];
  const rsvpEvent = eventsList.find((event) => event.id === rsvpEventId);

  const toggleId = (
    ids: number[],
    id: number,
    setter: (val: number[]) => void,
  ) => {
    setter(ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]);
  };

  const onSubmit = (formData: CreateEvent) => {
    createEvent(formData, {
      onSuccess: (result) => {
        if (result.data) {
          setCreateEventOpen(false);
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
      },
    });
  };

  const onEditSubmit = (formData: UpdateEvent) => {
    if (!editingEvent) return;
    updateEvent(
      { id: editingEvent.id, data: formData },
      {
        onSuccess: () => {
          setEditingEvent(null);
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
    <div className="p-4 space-y-4">
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

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Event Name</TableHead>
              <TableHead>Host</TableHead>
              <TableHead>Location / Link</TableHead>
              <TableHead>Start</TableHead>
              <TableHead>End</TableHead>
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
                  <TableCell>{event.id}</TableCell>
                  <TableCell>{event.eventName}</TableCell>
                  <TableCell>
                    {event.hostUserId
                      ? formatHostName(event.hostUserId, usersById)
                      : "Unassigned"}
                  </TableCell>
                  <TableCell>
                    {event.location
                      ? event.location
                      : event.locationLink
                        ? (
                          <a
                            href={event.locationLink}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-500 underline"
                          >
                            Link
                          </a>
                        )
                        : "---"}
                  </TableCell>
                  <TableCell>{formatDateTime(event.startDatetime)}</TableCell>
                  <TableCell>{formatDateTime(event.endsDatetime)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          setViewingEvent(
                            viewingEvent?.id === event.id ? null : event,
                          )
                        }
                      >
                        <EyeIcon className="size-4" />
                        View
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          setRsvpEventId(
                            rsvpEventId === event.id ? null : event.id,
                          )
                        }
                      >
                        <UsersIcon className="size-4" />
                        RSVP
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          setEditingEvent(
                            editingEvent?.id === event.id ? null : event,
                          )
                        }
                      >
                        <PencilIcon className="size-4" />
                        Edit
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={isDeleting}
                        onClick={() => handleDelete(event)}
                      >
                        <Trash2Icon className="size-4" />
                        Delete
                      </Button>
                    </div>
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

      <Drawer
        direction="right"
        open={!!viewingEvent}
        onOpenChange={(open) => {
          if (!open) setViewingEvent(null);
        }}
      >
        <DrawerContent className="overflow-y-auto sm:max-w-xl">
          <DrawerHeader>
            <DrawerTitle>
              {viewingEvent?.eventName ?? "Event Details"}
            </DrawerTitle>
            <DrawerDescription>Event #{viewingEvent?.id}</DrawerDescription>
          </DrawerHeader>
          <div className="grid gap-5 px-4 pb-4">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground uppercase">Host</Label>
              <p className="text-sm">
                {viewingEvent?.hostUserId
                  ? formatHostName(viewingEvent.hostUserId, usersById)
                  : "---"}
              </p>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground uppercase">Description</Label>
              <p className="text-sm">{viewingEvent?.description || "---"}</p>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground uppercase">Event Type</Label>
              <p className="text-sm">
                {viewingEvent?.isVirtual ? "Virtual" : "In-person"}
              </p>
            </div>
            {!viewingEvent?.isVirtual && (
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground uppercase">Location</Label>
                <p className="text-sm">{viewingEvent?.location || "---"}</p>
              </div>
            )}
            {viewingEvent?.locationLink && (
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground uppercase">
                  {viewingEvent.isVirtual ? "Meeting Link" : "Google Map Link"}
                </Label>
                <p className="text-sm">
                  <a
                    href={viewingEvent.locationLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 underline"
                  >
                    {viewingEvent.locationLink}
                  </a>
                </p>
              </div>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground uppercase">Start</Label>
                <p className="text-sm">
                  {viewingEvent ? formatDateTime(viewingEvent.startDatetime) : "---"}
                </p>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground uppercase">End</Label>
                <p className="text-sm">
                  {viewingEvent ? formatDateTime(viewingEvent.endsDatetime) : "---"}
                </p>
              </div>
            </div>
            {(viewTargetsData?.data?.groupIds?.length ?? 0) > 0 && (
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground uppercase">Target Groups</Label>
                <div className="flex flex-wrap gap-1.5">
                  {viewTargetsData!.data!.groupIds.map((id) => {
                    const g = groups.find((x) => x.id === id);
                    return g ? (
                      <Badge key={id} variant="secondary">{g.groupName}</Badge>
                    ) : null;
                  })}
                </div>
              </div>
            )}
            {(viewTargetsData?.data?.roleIds?.length ?? 0) > 0 && (
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground uppercase">Target Roles</Label>
                <div className="flex flex-wrap gap-1.5">
                  {viewTargetsData!.data!.roleIds.map((id) => {
                    const r = roles.find((x) => x.id === id);
                    return r ? (
                      <Badge key={id} variant="secondary">{r.roleName}</Badge>
                    ) : null;
                  })}
                </div>
              </div>
            )}
            {(viewTargetsData?.data?.trackIds?.length ?? 0) > 0 && (
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground uppercase">Target Tracks</Label>
                <div className="flex flex-wrap gap-1.5">
                  {viewTargetsData!.data!.trackIds.map((id) => {
                    const t = tracks.find((x) => x.id === id);
                    return t ? (
                      <Badge key={id} variant="secondary">{t.trackName}</Badge>
                    ) : null;
                  })}
                </div>
              </div>
            )}
          </div>
          <DrawerFooter>
            <Button type="button" variant="outline" onClick={() => setViewingEvent(null)}>
              Close
            </Button>
          </DrawerFooter>
        </DrawerContent>
      </Drawer>

      <Drawer
        direction="right"
        open={createEventOpen}
        onOpenChange={(open) => {
          setCreateEventOpen(open);
          if (!open) {
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
        <DrawerContent className="overflow-y-auto sm:max-w-xl">
          <DrawerHeader>
            <DrawerTitle>Create Event</DrawerTitle>
            <DrawerDescription>
              Add an event to the BIOTech Futures program calendar.
            </DrawerDescription>
          </DrawerHeader>
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
          />
          <DrawerFooter>
            <Button form="create-event-form" type="submit" disabled={isCreating}>
              <CalendarIcon className="size-4" />
              {isCreating ? "Creating..." : "Create Event"}
            </Button>
            <Button type="button" variant="outline" onClick={() => setCreateEventOpen(false)}>
              Cancel
            </Button>
          </DrawerFooter>
        </DrawerContent>
      </Drawer>

      <Drawer
        direction="right"
        open={rsvpEventId !== null}
        onOpenChange={(open) => {
          if (!open) setRsvpEventId(null);
        }}
      >
        <DrawerContent className="overflow-y-auto sm:max-w-3xl">
          <DrawerHeader>
            <DrawerTitle>
              RSVP List {rsvpEvent ? "- " + rsvpEvent.eventName : ""}
            </DrawerTitle>
            <DrawerDescription>
              Event #{rsvpEventId} has {rsvps.length} RSVP
              {rsvps.length === 1 ? "" : "s"}.
            </DrawerDescription>
          </DrawerHeader>
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
                      <TableHead>RSVP ID</TableHead>
                      <TableHead>Student</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Responded At</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {isRsvpLoading ? (
                      <TableRow>
                        <TableCell colSpan={4} className="text-center">Loading...</TableCell>
                      </TableRow>
                    ) : rsvps.length > 0 ? (
                      rsvps.map((rsvp) => {
                        const student = allUsers.find(
                          (u) => Number(u.id) === rsvp.userId,
                        );
                        const statusInfo = RSVP_STATUS_LABELS[rsvp.rsvpStatus] ?? {
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
                        <TableCell colSpan={4} className="text-center">No RSVPs yet.</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </div>
          </div>
          <DrawerFooter>
            <Button type="button" variant="outline" onClick={() => setRsvpEventId(null)}>
              Close
            </Button>
          </DrawerFooter>
        </DrawerContent>
      </Drawer>

      <Drawer
        direction="right"
        open={!!editingEvent}
        onOpenChange={(open) => {
          if (!open) setEditingEvent(null);
        }}
      >
        <DrawerContent className="overflow-y-auto sm:max-w-xl">
          <DrawerHeader>
            <DrawerTitle>Edit Event #{editingEvent?.id}</DrawerTitle>
            <DrawerDescription>Update the event details.</DrawerDescription>
          </DrawerHeader>
          <EventForm
            formId="edit-event-form"
            control={editControl}
            register={registerEdit}
            errors={editErrors}
            isVirtual={!!editIsVirtual}
            currentHostName={
              editingEvent?.hostUserId
                ? formatHostName(editingEvent.hostUserId, usersById)
                : currentHostName
            }
            groups={groups}
            roles={roles}
            tracks={tracks}
            watchedGroupIds={editGroupIds}
            watchedRoleIds={editRoleIds}
            watchedTrackIds={editTrackIds}
            onToggleGroup={(id) =>
              toggleId(editGroupIds, id, (v) => setEditValue("targetGroupIds", v))
            }
            onToggleRole={(id) =>
              toggleId(editRoleIds, id, (v) => setEditValue("targetRoleIds", v))
            }
            onToggleTrack={(id) =>
              toggleId(editTrackIds, id, (v) => setEditValue("targetTrackIds", v))
            }
            onSubmit={handleEditSubmit(onEditSubmit)}
          />
          <DrawerFooter>
            <Button form="edit-event-form" type="submit" disabled={isUpdating}>
              {isUpdating ? "Saving..." : "Save Changes"}
            </Button>
            <Button type="button" variant="outline" onClick={() => setEditingEvent(null)}>
              Cancel
            </Button>
          </DrawerFooter>
        </DrawerContent>
      </Drawer>
    </div>
  );
}

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

function toDatetimeLocal(value: string) {
  const date = new Date(value);
  const pad = (n: number) => String(n).padStart(2, "0");
  return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate()) + "T" + pad(date.getHours()) + ":" + pad(date.getMinutes());
}
