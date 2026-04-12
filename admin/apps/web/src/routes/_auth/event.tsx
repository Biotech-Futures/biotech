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
import type { Event, EventRsvp } from "@/type/event";
import { zodResolver } from "@hookform/resolvers/zod";
import { createFileRoute } from "@tanstack/react-router";
import { CalendarIcon, Trash2Icon, PencilIcon, UsersIcon, XIcon } from "lucide-react";
import { Controller, type Control, useForm } from "react-hook-form";
import { useEffect, useState } from "react";

export const Route = createFileRoute("/_auth/event")({
  component: EventPage,
});

function EventPage() {
  const [page, setPage] = useState(1);
  const [eventType, setEventType] = useState("");
  const [trackId, setTrackId] = useState("");
  const [upcoming, setUpcoming] = useState(true);

  // Edit state
  const [editingEvent, setEditingEvent] = useState<Event | null>(null);

  // RSVP state
  const [rsvpEventId, setRsvpEventId] = useState<number | null>(null);

  const { data, isPending } = useQueryEvents({
    page,
    limit: 10,
    eventType: eventType || undefined,
    trackId: trackId ? Number(trackId) : undefined,
    upcoming,
  });
  const { mutate: createEvent, isPending: isCreating } = useCreateEvent();
  const { mutate: deleteEvent, isPending: isDeleting } = useDeleteEvent();
  const { mutate: updateEvent, isPending: isUpdating } = useUpdateEvent();
  const { data: rsvpData, isPending: isRsvpLoading } = useQueryEventRsvps(rsvpEventId);
  const { mutate: createRsvp, isPending: isCreatingRsvp } = useCreateEventRsvp();

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
    register: registerRsvp,
    handleSubmit: handleRsvpSubmit,
    reset: resetRsvp,
    formState: { errors: rsvpErrors },
  } = useForm<CreateEventRsvp>({
    resolver: zodResolver(createEventRsvpSchema),
  });

  useEffect(() => {
    setPage(1);
  }, [eventType, trackId, upcoming]);

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
          reset();
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
      }
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
      }
    );
  };

  const handleDelete = (event: Event) => {
    const shouldDelete = window.confirm(`Delete event #${event.id}?`);
    if (!shouldDelete) return;
    deleteEvent(event.id);
  };

  return (
    <div className="p-4 space-y-4">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Event Management</h1>
          <p className="text-muted-foreground">
            Create events, review schedules, and maintain event records
          </p>
        </div>
      </div>

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
            <NumberField control={control} name="hostUserId" label="Host User ID" placeholder="Optional" />
            <NumberField control={control} name="trackId" label="Track ID" placeholder="Optional" />
            <Controller
              control={control}
              name="eventType"
              render={({ field }) => (
                <div className="space-y-1.5">
                  <Label htmlFor="event-type">Event Type</Label>
                  <Input
                    id="event-type"
                    placeholder="Workshop"
                    value={field.value ?? ""}
                    onChange={(e) => field.onChange(e.target.value || null)}
                  />
                  {errors.eventType && <p className="text-sm text-destructive">{errors.eventType.message}</p>}
                </div>
              )}
            />
            <Controller
              control={control}
              name="startAt"
              render={({ field }) => (
                <div className="space-y-1.5">
                  <Label htmlFor="start-at">Start</Label>
                  <Input id="start-at" type="datetime-local" {...field} />
                  {errors.startAt && <p className="text-sm text-destructive">{errors.startAt.message}</p>}
                </div>
              )}
            />
            <Controller
              control={control}
              name="endsAt"
              render={({ field }) => (
                <div className="space-y-1.5">
                  <Label htmlFor="ends-at">End</Label>
                  <Input id="ends-at" type="datetime-local" {...field} />
                  {errors.endsAt && <p className="text-sm text-destructive">{errors.endsAt.message}</p>}
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

      {/* Edit Event Form */}
      {editingEvent && (
        <Card className="border-blue-300">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Edit Event #{editingEvent.id}</CardTitle>
                <CardDescription>Update the event details</CardDescription>
              </div>
              <Button type="button" variant="ghost" size="sm" onClick={() => setEditingEvent(null)}>
                <XIcon className="size-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <form
              className="grid gap-4 lg:grid-cols-5"
              onSubmit={handleEditSubmit(onEditSubmit)}
            >
              <EditNumberField control={editControl} name="hostUserId" label="Host User ID" placeholder="Optional" />
              <EditNumberField control={editControl} name="trackId" label="Track ID" placeholder="Optional" />
              <Controller
                control={editControl}
                name="eventType"
                render={({ field }) => (
                  <div className="space-y-1.5">
                    <Label>Event Type</Label>
                    <Input
                      placeholder="Workshop"
                      value={field.value ?? ""}
                      onChange={(e) => field.onChange(e.target.value || null)}
                    />
                    {editErrors.eventType && <p className="text-sm text-destructive">{editErrors.eventType.message}</p>}
                  </div>
                )}
              />
              <Controller
                control={editControl}
                name="startAt"
                render={({ field }) => (
                  <div className="space-y-1.5">
                    <Label>Start</Label>
                    <Input type="datetime-local" {...field} value={field.value ?? ""} />
                    {editErrors.startAt && <p className="text-sm text-destructive">{editErrors.startAt.message}</p>}
                  </div>
                )}
              />
              <Controller
                control={editControl}
                name="endsAt"
                render={({ field }) => (
                  <div className="space-y-1.5">
                    <Label>End</Label>
                    <Input type="datetime-local" {...field} value={field.value ?? ""} />
                    {editErrors.endsAt && <p className="text-sm text-destructive">{editErrors.endsAt.message}</p>}
                  </div>
                )}
              />
              <div className="lg:col-span-5 flex gap-2">
                <Button type="submit" disabled={isUpdating}>
                  {isUpdating ? "Saving..." : "Save Changes"}
                </Button>
                <Button type="button" variant="outline" onClick={() => setEditingEvent(null)}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* RSVP Panel */}
      {rsvpEventId && (
        <Card className="border-green-300">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>RSVP List — Event #{rsvpEventId}</CardTitle>
                <CardDescription>View and add RSVPs for this event</CardDescription>
              </div>
              <Button type="button" variant="ghost" size="sm" onClick={() => setRsvpEventId(null)}>
                <XIcon className="size-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Add RSVP form */}
            <form className="flex gap-3 items-end" onSubmit={handleRsvpSubmit(onRsvpSubmit)}>
              <div className="space-y-1.5">
                <Label>User ID</Label>
                <Input type="number" min={1} placeholder="User ID" {...registerRsvp("userId", { valueAsNumber: true })} />
                {rsvpErrors.userId && <p className="text-sm text-destructive">{rsvpErrors.userId.message}</p>}
              </div>
              <div className="space-y-1.5">
                <Label>RSVP Status</Label>
                <Input placeholder="attending / declined" {...registerRsvp("rsvpStatus")} />
                {rsvpErrors.rsvpStatus && <p className="text-sm text-destructive">{rsvpErrors.rsvpStatus.message}</p>}
              </div>
              <Button type="submit" disabled={isCreatingRsvp}>
                {isCreatingRsvp ? "Adding..." : "Add RSVP"}
              </Button>
            </form>

            {/* RSVP Table */}
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>RSVP ID</TableHead>
                  <TableHead>User ID</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isRsvpLoading ? (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center">Loading...</TableCell>
                  </TableRow>
                ) : rsvps.length > 0 ? (
                  rsvps.map((rsvp) => (
                    <TableRow key={rsvp.id}>
                      <TableCell>{rsvp.id}</TableCell>
                      <TableCell>{rsvp.userId}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{rsvp.rsvpStatus}</Badge>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center">No RSVPs yet.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <div className="flex flex-col gap-3 rounded-md border p-4 lg:flex-row lg:items-end">
        <div className="space-y-1.5">
          <Label htmlFor="filter-event-type">Event Type</Label>
          <Input
            id="filter-event-type"
            placeholder="Workshop"
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="filter-track-id">Track ID</Label>
          <Input
            id="filter-track-id"
            type="number"
            min={1}
            placeholder="Any"
            value={trackId}
            onChange={(e) => setTrackId(e.target.value)}
          />
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
                <TableCell colSpan={7} className="h-24 text-center">Loading events...</TableCell>
              </TableRow>
            ) : events.length > 0 ? (
              events.map((event) => (
                <TableRow key={event.id}>
                  <TableCell>{event.id}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{event.eventType ?? "General"}</Badge>
                  </TableCell>
                  <TableCell>{event.trackId ?? "Any"}</TableCell>
                  <TableCell>{event.hostUserId ?? "Unassigned"}</TableCell>
                  <TableCell>{formatDateTime(event.startAt)}</TableCell>
                  <TableCell>{formatDateTime(event.endsAt)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setRsvpEventId(rsvpEventId === event.id ? null : event.id)}
                      >
                        <UsersIcon className="size-4" />
                        RSVP
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setEditingEvent(editingEvent?.id === event.id ? null : event)}
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
                <TableCell colSpan={7} className="h-24 text-center">No events found.</TableCell>
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
    </div>
  );
}

function NumberField({
  control,
  name,
  label,
  placeholder,
}: {
  control: Control<CreateEvent>;
  name: "hostUserId" | "trackId";
  label: string;
  placeholder: string;
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <div className="space-y-1.5">
          <Label htmlFor={name}>{label}</Label>
          <Input
            id={name}
            type="number"
            min={1}
            placeholder={placeholder}
            value={field.value ?? ""}
            onChange={(e) => {
              const value = e.target.value;
              field.onChange(value ? Number(value) : null);
            }}
          />
          {fieldState.error && <p className="text-sm text-destructive">{fieldState.error.message}</p>}
        </div>
      )}
    />
  );
}

function EditNumberField({
  control,
  name,
  label,
  placeholder,
}: {
  control: Control<UpdateEvent>;
  name: "hostUserId" | "trackId";
  label: string;
  placeholder: string;
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <div className="space-y-1.5">
          <Label>{label}</Label>
          <Input
            type="number"
            min={1}
            placeholder={placeholder}
            value={field.value ?? ""}
            onChange={(e) => {
              const value = e.target.value;
              field.onChange(value ? Number(value) : null);
            }}
          />
          {fieldState.error && <p className="text-sm text-destructive">{fieldState.error.message}</p>}
        </div>
      )}
    />
  );
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function toDatetimeLocal(value: string) {
  const date = new Date(value);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
