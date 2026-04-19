import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
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
  createEventRsvpSchema,
  type CreateEvent,
  type UpdateEvent,
  type CreateEventRsvp,
} from "@/schema/event";
import {
  useCreateEvent,
  useDeleteEvent,
  useQueryEvents,
  useUpdateEvent,
  useQueryEventRsvps,
  useCreateEventRsvp,
} from "@/query/event";
import { useQueryUsers, useQueryTracks } from "@/query/user";
import type { Event, EventRsvp } from "@/type/event";
import { authClient } from "@/lib/authClient";
import { zodResolver } from "@hookform/resolvers/zod";
import { createFileRoute } from "@tanstack/react-router";
import {
  CalendarIcon,
  Trash2Icon,
  PencilIcon,
  UsersIcon,
  XIcon,
} from "lucide-react";
import { Controller, type Control, useForm } from "react-hook-form";
import { useEffect, useState } from "react";

export const Route = createFileRoute("/_auth/event")({
  component: EventPage,
});

const EVENT_TYPES = ["Workshop", "Tutorial", "Lecture"] as const;
const RSVP_STATUSES = ["attending", "declined"] as const;

function EventPage() {
  const [page, setPage] = useState(1);
  const [filterEventType, setFilterEventType] = useState("");
  const [filterTrackId, setFilterTrackId] = useState("");
  const [upcoming, setUpcoming] = useState(true);

  // Edit sidebar state
  const [editingEvent, setEditingEvent] = useState<Event | null>(null);

  // RSVP panel state
  const [rsvpEventId, setRsvpEventId] = useState<number | null>(null);

  // Get current logged-in admin user
  const { data: sessionData } = authClient.useSession();

  // Data queries
  const { data, isPending } = useQueryEvents({
    page,
    limit: 10,
    eventType: filterEventType || undefined,
    trackId: filterTrackId ? Number(filterTrackId) : undefined,
    upcoming,
  });
  const { data: usersData } = useQueryUsers();
  const { data: tracksData } = useQueryTracks();

  const { mutate: createEvent, isPending: isCreating } = useCreateEvent();
  const { mutate: deleteEvent, isPending: isDeleting } = useDeleteEvent();
  const { mutate: updateEvent, isPending: isUpdating } = useUpdateEvent();
  const { data: rsvpData, isPending: isRsvpLoading } =
    useQueryEventRsvps(rsvpEventId);
  const { mutate: createRsvp, isPending: isCreatingRsvp } =
    useCreateEventRsvp();

  // Derive lists
  const allUsers = usersData?.data.items ?? [];
  const studentUsers = allUsers.filter((u) => u.role === "student");
  const tracks = tracksData?.data ?? [];

  // Find current admin's numeric user id by matching email
  const currentAdminEmail = sessionData?.user?.email ?? "";
  const currentUserRecord = allUsers.find(
    (u) => u.email === currentAdminEmail,
  );
  const currentUserId = currentUserRecord ? Number(currentUserRecord.id) : null;

  // Create form
  const {
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateEvent>({
    defaultValues: {
      hostUserId: null,
      trackId: null,
      eventType: null,
      startAt: "",
      endsAt: "",
    },
    resolver: zodResolver(createEventSchema),
  });

  // Set hostUserId default once we know current user
  useEffect(() => {
    if (currentUserId) {
      reset((prev) => ({
        ...prev,
        hostUserId: currentUserId,
      }));
    }
  }, [currentUserId, reset]);

  // Edit form
  const {
    control: editControl,
    handleSubmit: handleEditSubmit,
    reset: resetEdit,
    formState: { errors: editErrors },
  } = useForm<UpdateEvent>({
    resolver: zodResolver(updateEventSchema),
  });

  // RSVP form
  const {
    control: rsvpControl,
    handleSubmit: handleRsvpSubmit,
    reset: resetRsvp,
    formState: { errors: rsvpErrors },
  } = useForm<CreateEventRsvp>({
    resolver: zodResolver(createEventRsvpSchema),
  });

  useEffect(() => {
    setPage(1);
  }, [filterEventType, filterTrackId, upcoming]);

  // Populate edit form when editing event changes
  useEffect(() => {
    if (editingEvent) {
      resetEdit({
        hostUserId: editingEvent.hostUserId,
        trackId: editingEvent.trackId,
        eventType: editingEvent.eventType,
        startAt: toDatetimeLocal(editingEvent.startAt),
        endsAt: toDatetimeLocal(editingEvent.endsAt),
      });
    }
  }, [editingEvent, resetEdit]);

  const events = data?.data.items ?? [];
  const total = data?.data.total ?? 0;
  const limit = data?.data.limit ?? 10;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const rsvps: EventRsvp[] = rsvpData?.data ?? [];

  const onSubmit = (formData: CreateEvent) => {
    createEvent(formData, {
      onSuccess: (result) => {
        if (result.data) {
          reset({
            hostUserId: currentUserId,
            trackId: null,
            eventType: null,
            startAt: "",
            endsAt: "",
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

  const onRsvpSubmit = (formData: CreateEventRsvp) => {
    if (!rsvpEventId) return;
    createRsvp(
      { eventId: rsvpEventId, data: formData },
      {
        onSuccess: () => {
          resetRsvp();
        },
      },
    );
  };

  const handleDelete = (event: Event) => {
    const shouldDelete = window.confirm(`Delete event #${event.id}? All RSVPs for this event will also be deleted.`);
    if (!shouldDelete) return;
    deleteEvent(event.id, {
    onSuccess: () => {
      if (rsvpEventId === event.id) setRsvpEventId(null);
    },
  });
};

  // Helper: get track label by id
  const getTrackLabel = (trackId: number | null) => {
    if (!trackId) return "Any";
    const found = tracks.find((t: { id: number; trackCode: string }) => t.id === trackId);
    return found ? found.trackCode : String(trackId);
  };

  return (
    <div className="p-4 space-y-4">
      {/* Create Event Form */}
      <Card>
        <CardHeader>
          <CardTitle>Create Event</CardTitle>
          <CardDescription>
            Add an event to the BIOTech Futures program calendar
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4 lg:grid-cols-5"
            onSubmit={handleSubmit(onSubmit)}
          >
            {/* Host User ID — auto-filled, read-only display */}
            <div className="space-y-1.5">
              <Label>Host User ID</Label>
              <Input
                value={currentUserId ?? "—"}
                readOnly
                disabled
                className="bg-muted text-muted-foreground cursor-not-allowed"
              />
            </div>

            {/* Track ID — dropdown */}
            <Controller
              control={control}
              name="trackId"
              render={({ field }) => (
                <div className="space-y-1.5">
                  <Label>Track</Label>
                  <Select
                    value={field.value ? String(field.value) : "none"}
                    onValueChange={(val) =>
                      field.onChange(val === "none" ? null : Number(val))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="All Tracks" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">All Tracks</SelectItem>
                      {tracks.map((t: { id: number; trackCode: string }) => (
                        <SelectItem key={t.id} value={String(t.id)}>
                          {t.trackCode}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {errors.trackId && (
                    <p className="text-sm text-destructive">
                      {errors.trackId.message}
                    </p>
                  )}
                </div>
              )}
            />

            {/* Event Type — dropdown */}
            <Controller
              control={control}
              name="eventType"
              render={({ field }) => (
                <div className="space-y-1.5">
                  <Label>Event Type</Label>
                  <Select
                    value={field.value ?? "none"}
                    onValueChange={(val) =>
                      field.onChange(val === "none" ? null : val)
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">— None —</SelectItem>
                      {EVENT_TYPES.map((t) => (
                        <SelectItem key={t} value={t}>
                          {t}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {errors.eventType && (
                    <p className="text-sm text-destructive">
                      {errors.eventType.message}
                    </p>
                  )}
                </div>
              )}
            />

            {/* Start datetime */}
            <Controller
              control={control}
              name="startAt"
              render={({ field }) => (
                <div className="space-y-1.5">
                  <Label htmlFor="start-at">Start</Label>
                  <Input id="start-at" type="datetime-local" {...field} />
                  {errors.startAt && (
                    <p className="text-sm text-destructive">
                      {errors.startAt.message}
                    </p>
                  )}
                </div>
              )}
            />

            {/* End datetime */}
            <Controller
              control={control}
              name="endsAt"
              render={({ field }) => (
                <div className="space-y-1.5">
                  <Label htmlFor="ends-at">End</Label>
                  <Input id="ends-at" type="datetime-local" {...field} />
                  {errors.endsAt && (
                    <p className="text-sm text-destructive">
                      {errors.endsAt.message}
                    </p>
                  )}
                </div>
              )}
            />

            <div className="lg:col-span-5">
              <Button type="submit" disabled={isCreating}>
                <CalendarIcon className="size-4" />
                {isCreating ? "Creating..." : "Create Event"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* RSVP Panel */}
      {rsvpEventId && (
        <Card className="border-green-300">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>RSVP List — Event #{rsvpEventId}</CardTitle>
                <CardDescription>
                  View and add RSVPs for this event
                </CardDescription>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setRsvpEventId(null)}
              >
                <XIcon className="size-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Add RSVP form */}
            <form
              className="flex gap-3 items-end"
              onSubmit={handleRsvpSubmit(onRsvpSubmit)}
            >
              {/* Student dropdown */}
              <Controller
                control={rsvpControl}
                name="userId"
                render={({ field }) => (
                  <div className="space-y-1.5">
                    <Label>Student</Label>
                    <Select
                      value={field.value ? String(field.value) : ""}
                      onValueChange={(val) => field.onChange(Number(val))}
                    >
                      <SelectTrigger className="w-56">
                        <SelectValue placeholder="Select student" />
                      </SelectTrigger>
                      <SelectContent>
                        {studentUsers.length === 0 ? (
                          <SelectItem value="__empty" disabled>
                            No students found
                          </SelectItem>
                        ) : (
                          studentUsers.map((u) => (
                            <SelectItem key={u.id} value={u.id}>
                              {u.name} ({u.email})
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                    {rsvpErrors.userId && (
                      <p className="text-sm text-destructive">
                        {rsvpErrors.userId.message}
                      </p>
                    )}
                  </div>
                )}
              />

              {/* RSVP Status dropdown */}
              <Controller
                control={rsvpControl}
                name="rsvpStatus"
                render={({ field }) => (
                  <div className="space-y-1.5">
                    <Label>RSVP Status</Label>
                    <Select
                      value={field.value ?? ""}
                      onValueChange={field.onChange}
                    >
                      <SelectTrigger className="w-36">
                        <SelectValue placeholder="Status" />
                      </SelectTrigger>
                      <SelectContent>
                        {RSVP_STATUSES.map((s) => (
                          <SelectItem key={s} value={s}>
                            {s}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {rsvpErrors.rsvpStatus && (
                      <p className="text-sm text-destructive">
                        {rsvpErrors.rsvpStatus.message}
                      </p>
                    )}
                  </div>
                )}
              />

              <Button type="submit" disabled={isCreatingRsvp}>
                {isCreatingRsvp ? "Adding..." : "Add RSVP"}
              </Button>
            </form>

            {/* RSVP Table */}
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>RSVP ID</TableHead>
                  <TableHead>Student</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isRsvpLoading ? (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center">
                      Loading...
                    </TableCell>
                  </TableRow>
                ) : rsvps.length > 0 ? (
                  rsvps.map((rsvp) => {
                    const student = allUsers.find(
                      (u) => Number(u.id) === rsvp.userId,
                    );
                    return (
                      <TableRow key={rsvp.id}>
                        <TableCell>{rsvp.id}</TableCell>
                        <TableCell>
                          {student
                            ? `${student.name} (${student.email})`
                            : `User #${rsvp.userId}`}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{rsvp.rsvpStatus}</Badge>
                        </TableCell>
                      </TableRow>
                    );
                  })
                ) : (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center">
                      No RSVPs yet.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <div className="flex flex-col gap-3 rounded-md border p-4 lg:flex-row lg:items-end">
        {/* Event Type filter */}
        <div className="space-y-1.5">
          <Label>Event Type</Label>
          <Select
            value={filterEventType || "all"}
            onValueChange={(val) =>
              setFilterEventType(val === "all" ? "" : val)
            }
          >
            <SelectTrigger className="w-40">
              <SelectValue placeholder="All Types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              {EVENT_TYPES.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Track filter */}
        <div className="space-y-1.5">
          <Label>Track</Label>
          <Select
            value={filterTrackId || "all"}
            onValueChange={(val) =>
              setFilterTrackId(val === "all" ? "" : val)
            }
          >
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Any" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Any</SelectItem>
              {tracks.map((t: { id: number; trackCode: string }) => (
                <SelectItem key={t.id} value={String(t.id)}>
                  {t.trackCode}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Button
          type="button"
          variant={upcoming ? "default" : "outline"}
          onClick={() => setUpcoming((v) => !v)}
        >
          {upcoming ? "Upcoming Only" : "All Events"}
        </Button>
      </div>

      {/* Events Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Track</TableHead>
              <TableHead>Host</TableHead>
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
            ) : events.length > 0 ? (
              events.map((event) => (
                <TableRow key={event.id}>
                  <TableCell>{event.id}</TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {event.eventType ?? "General"}
                    </Badge>
                  </TableCell>
                  <TableCell>{getTrackLabel(event.trackId)}</TableCell>
                  <TableCell>{event.hostUserId ?? "Unassigned"}</TableCell>
                  <TableCell>{formatDateTime(event.startAt)}</TableCell>
                  <TableCell>{formatDateTime(event.endsAt)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
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

      {/* Pagination */}
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

      {/* ✅ Edit Event — Right Slide-in Sheet */}
      <Sheet
        open={!!editingEvent}
        onOpenChange={(open) => {
          if (!open) setEditingEvent(null);
        }}
      >
        <SheetContent className="w-[420px] sm:w-[480px] overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Edit Event #{editingEvent?.id}</SheetTitle>
            <SheetDescription>Update the event details</SheetDescription>
          </SheetHeader>

          <form
            className="mt-6 grid gap-5"
            onSubmit={handleEditSubmit(onEditSubmit)}
          >
            {/* Host User ID — auto-filled, read-only */}
            <div className="space-y-1.5">
              <Label>Host User ID</Label>
              <Input
                value={editingEvent?.hostUserId ?? currentUserId ?? "—"}
                readOnly
                disabled
                className="bg-muted text-muted-foreground cursor-not-allowed"
              />
            </div>

            {/* Track — dropdown */}
            <Controller
              control={editControl}
              name="trackId"
              render={({ field }) => (
                <div className="space-y-1.5">
                  <Label>Track</Label>
                  <Select
                    value={field.value ? String(field.value) : "none"}
                    onValueChange={(val) =>
                      field.onChange(val === "none" ? null : Number(val))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="All Tracks" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">All Tracks</SelectItem>
                      {tracks.map((t: { id: number; trackCode: string }) => (
                        <SelectItem key={t.id} value={String(t.id)}>
                          {t.trackCode}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {editErrors.trackId && (
                    <p className="text-sm text-destructive">
                      {editErrors.trackId.message}
                    </p>
                  )}
                </div>
              )}
            />

            {/* Event Type — dropdown */}
            <Controller
              control={editControl}
              name="eventType"
              render={({ field }) => (
                <div className="space-y-1.5">
                  <Label>Event Type</Label>
                  <Select
                    value={field.value ?? "none"}
                    onValueChange={(val) =>
                      field.onChange(val === "none" ? null : val)
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">— None —</SelectItem>
                      {EVENT_TYPES.map((t) => (
                        <SelectItem key={t} value={t}>
                          {t}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {editErrors.eventType && (
                    <p className="text-sm text-destructive">
                      {editErrors.eventType.message}
                    </p>
                  )}
                </div>
              )}
            />

            {/* Start datetime */}
            <Controller
              control={editControl}
              name="startAt"
              render={({ field }) => (
                <div className="space-y-1.5">
                  <Label>Start</Label>
                  <Input
                    type="datetime-local"
                    {...field}
                    value={field.value ?? ""}
                  />
                  {editErrors.startAt && (
                    <p className="text-sm text-destructive">
                      {editErrors.startAt.message}
                    </p>
                  )}
                </div>
              )}
            />

            {/* End datetime */}
            <Controller
              control={editControl}
              name="endsAt"
              render={({ field }) => (
                <div className="space-y-1.5">
                  <Label>End</Label>
                  <Input
                    type="datetime-local"
                    {...field}
                    value={field.value ?? ""}
                  />
                  {editErrors.endsAt && (
                    <p className="text-sm text-destructive">
                      {editErrors.endsAt.message}
                    </p>
                  )}
                </div>
              )}
            />

            <div className="flex gap-2 pt-2">
              <Button type="submit" disabled={isUpdating}>
                {isUpdating ? "Saving..." : "Save Changes"}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditingEvent(null)}
              >
                Cancel
              </Button>
            </div>
          </form>
        </SheetContent>
      </Sheet>
    </div>
  );
}

function formatDateTime(value: string) {
  const isoValue = value.replace(" ", "T") + "Z";
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(isoValue));
}

function toDatetimeLocal(value: string) {
  const date = new Date(value);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
