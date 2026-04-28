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
  type CreateEventInput,
  type UpdateEvent,
  type UpdateEventInput,
  type CreateEventRsvp,
  type CreateEventRsvpInput,
} from "@/schema/event";
import {
  useCreateEvent,
  useDeleteEvent,
  useQueryEvents,
  useUpdateEvent,
  useQueryEventRsvps,
  useCreateEventRsvp,
} from "@/query/event";
import { useQueryUsers } from "@/query/user";
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
import { Controller, useForm } from "react-hook-form";
import { useEffect, useState } from "react";

export const Route = createFileRoute("/_auth/event")({
  component: EventPage,
});

function EventPage() {
  const [page, setPage] = useState(1);
  const [upcoming, setUpcoming] = useState(true);
  const [editingEvent, setEditingEvent] = useState<Event | null>(null);
  const [rsvpEventId, setRsvpEventId] = useState<number | null>(null);

  const { data: sessionData } = authClient.useSession();

  const { data, isPending } = useQueryEvents({ page, limit: 10, upcoming });
  const { data: usersData } = useQueryUsers();

  const { mutate: createEvent, isPending: isCreating } = useCreateEvent();
  const { mutate: deleteEvent, isPending: isDeleting } = useDeleteEvent();
  const { mutate: updateEvent, isPending: isUpdating } = useUpdateEvent();
  const { data: rsvpData, isPending: isRsvpLoading } =
    useQueryEventRsvps(rsvpEventId);
  const { mutate: createRsvp, isPending: isCreatingRsvp } =
    useCreateEventRsvp();

  const allUsers = usersData?.data.items ?? [];
  const studentUsers = allUsers.filter((u) => u.role === "student");

  const currentAdminEmail = sessionData?.user?.email ?? "";
  const currentUserRecord = allUsers.find((u) => u.email === currentAdminEmail);
  const currentUserId = currentUserRecord ? Number(currentUserRecord.id) : null;

  // Create form
  const {
    control,
    handleSubmit,
    reset,
    register,
    formState: { errors },
  } = useForm<CreateEventInput, undefined, CreateEvent>({
    defaultValues: {
      hostUserId: null,
      eventName: "",
      description: null,
      location: null,
      humanitixLink: "",
      isVirtual: false,
      startAt: "",
      endsAt: "",
    },
    resolver: zodResolver(createEventSchema),
  });

  useEffect(() => {
    if (currentUserId) {
      reset((prev) => ({ ...prev, hostUserId: currentUserId }));
    }
  }, [currentUserId, reset]);

  // Edit form
  const {
    control: editControl,
    handleSubmit: handleEditSubmit,
    reset: resetEdit,
    register: registerEdit,
    formState: { errors: editErrors },
  } = useForm<UpdateEventInput, undefined, UpdateEvent>({
    resolver: zodResolver(updateEventSchema),
  });

  // RSVP form
  const {
    control: rsvpControl,
    handleSubmit: handleRsvpSubmit,
    reset: resetRsvp,
    formState: { errors: rsvpErrors },
  } = useForm<CreateEventRsvpInput, undefined, CreateEventRsvp>({
    resolver: zodResolver(createEventRsvpSchema),
  });

  useEffect(() => {
    setPage(1);
  }, [upcoming]);

  useEffect(() => {
    if (editingEvent) {
      resetEdit({
        hostUserId: editingEvent.hostUserId,
        eventName: editingEvent.eventName,
        description: editingEvent.description,
        location: editingEvent.location,
        isVirtual: editingEvent.isVirtual,
        startAt: toDatetimeLocal(editingEvent.startDatetime),
        endsAt: toDatetimeLocal(editingEvent.endsDatetime),
      });
    }
  }, [editingEvent, resetEdit]);

  const eventsList = data?.data.items ?? [];
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
            eventName: "",
            description: null,
            location: null,
            humanitixLink: "",
            isVirtual: false,
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
      { onSuccess: () => resetRsvp() },
    );
  };

  const handleDelete = (event: Event) => {
    const shouldDelete = window.confirm(
      `Delete event "${event.eventName}"? All RSVPs will also be deleted.`,
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
            className="grid gap-4 lg:grid-cols-3"
            onSubmit={handleSubmit(onSubmit)}
          >
            {/* Host User ID — auto-filled */}
            <div className="space-y-1.5">
              <Label>Host User ID</Label>
              <Input
                value={currentUserId ?? "—"}
                readOnly
                disabled
                className="bg-muted text-muted-foreground cursor-not-allowed"
              />
            </div>

            {/* Event Name */}
            <div className="space-y-1.5">
              <Label>Event Name</Label>
              <Input placeholder="Event name" {...register("eventName")} />
              {errors.eventName && (
                <p className="text-sm text-destructive">
                  {errors.eventName.message}
                </p>
              )}
            </div>

            {/* Description */}
            <div className="space-y-1.5">
              <Label>Description</Label>
              <Input placeholder="Optional" {...register("description")} />
            </div>

            {/* Location */}
            <div className="space-y-1.5">
              <Label>Location</Label>
              <Input placeholder="Optional" {...register("location")} />
            </div>

            {/* Humanitix Link */}
            <div className="space-y-1.5">
              <Label>Humanitix Link</Label>
              <Input placeholder="https://..." {...register("humanitixLink")} />
            </div>

            {/* Is Virtual */}
            <Controller
              control={control}
              name="isVirtual"
              render={({ field }) => (
                <div className="space-y-1.5">
                  <Label>Virtual Event?</Label>
                  <Select
                    value={field.value ? "true" : "false"}
                    onValueChange={(val) => field.onChange(val === "true")}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="false">No (In-person)</SelectItem>
                      <SelectItem value="true">Yes (Virtual)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
            />

            {/* Start */}
            <Controller
              control={control}
              name="startAt"
              render={({ field }) => (
                <div className="space-y-1.5">
                  <Label>Start</Label>
                  <Input type="datetime-local" {...field} />
                  {errors.startAt && (
                    <p className="text-sm text-destructive">
                      {errors.startAt.message}
                    </p>
                  )}
                </div>
              )}
            />

            {/* End */}
            <Controller
              control={control}
              name="endsAt"
              render={({ field }) => (
                <div className="space-y-1.5">
                  <Label>End</Label>
                  <Input type="datetime-local" {...field} />
                  {errors.endsAt && (
                    <p className="text-sm text-destructive">
                      {errors.endsAt.message}
                    </p>
                  )}
                </div>
              )}
            />

            <div className="lg:col-span-3">
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
                      value={
                        field.value === true
                          ? "true"
                          : field.value === false
                            ? "false"
                            : ""
                      }
                      onValueChange={(val) => field.onChange(val === "true")}
                    >
                      <SelectTrigger className="w-36">
                        <SelectValue placeholder="Status" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="true">Attending</SelectItem>
                        <SelectItem value="false">Declined</SelectItem>
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

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>RSVP ID</TableHead>
                  <TableHead>Student</TableHead>
                  <TableHead>RSVP Status</TableHead>
                  <TableHead>Attended</TableHead>
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
                          <Badge
                            variant={rsvp.rsvpStatus ? "default" : "outline"}
                          >
                            {rsvp.rsvpStatus ? "Attending" : "Declined"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              rsvp.attendanceStatus ? "default" : "outline"
                            }
                          >
                            {rsvp.attendanceStatus ? "Yes" : "No"}
                          </Badge>
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
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <div className="flex gap-3 rounded-md border p-4 items-end">
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
              <TableHead>Event Name</TableHead>
              <TableHead>Host</TableHead>
              <TableHead>Virtual</TableHead>
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
                  <TableCell>{event.hostUserId ?? "Unassigned"}</TableCell>
                  <TableCell>
                    <Badge variant={event.isVirtual ? "default" : "outline"}>
                      {event.isVirtual ? "Virtual" : "In-person"}
                    </Badge>
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

      {/* Edit Event — Right Slide-in Sheet */}
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
            {/* Host User ID — read-only */}
            <div className="space-y-1.5">
              <Label>Host User ID</Label>
              <Input
                value={editingEvent?.hostUserId ?? currentUserId ?? "—"}
                readOnly
                disabled
                className="bg-muted text-muted-foreground cursor-not-allowed"
              />
            </div>

            {/* Event Name */}
            <div className="space-y-1.5">
              <Label>Event Name</Label>
              <Input {...registerEdit("eventName")} />
              {editErrors.eventName && (
                <p className="text-sm text-destructive">
                  {editErrors.eventName.message}
                </p>
              )}
            </div>

            {/* Description */}
            <div className="space-y-1.5">
              <Label>Description</Label>
              <Input {...registerEdit("description")} />
            </div>

            {/* Location */}
            <div className="space-y-1.5">
              <Label>Location</Label>
              <Input {...registerEdit("location")} />
            </div>

            {/* Is Virtual */}
            <Controller
              control={editControl}
              name="isVirtual"
              render={({ field }) => (
                <div className="space-y-1.5">
                  <Label>Virtual Event?</Label>
                  <Select
                    value={field.value ? "true" : "false"}
                    onValueChange={(val) => field.onChange(val === "true")}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="false">No (In-person)</SelectItem>
                      <SelectItem value="true">Yes (Virtual)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
            />

            {/* Start */}
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

            {/* End */}
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
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Australia/Sydney",
  }).format(new Date(value));
}

function toDatetimeLocal(value: string) {
  const date = new Date(value);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
