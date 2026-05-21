import { type ReactNode, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MultiSelect } from "@/components/ui/multi-select";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  USER_ROLES,
  type TrackOption,
  type UserAccount,
  type UserFormValues,
  type UserRole,
  type UserTrack,
} from "@/type/user";
import { toast } from "sonner";

interface UserEditorSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  user: UserAccount | null;
  tracks?: TrackOption[];
  supervisors?: Array<{ id: string; name: string; email: string }>;
  onSubmit: (values: UserFormValues) => Promise<void> | void;
  onDelete?: (user: UserAccount) => Promise<void> | void;
  isPending?: boolean;
  isDeleting?: boolean;
}

const initialValues: UserFormValues = {
  firstName: "",
  lastName: "",
  email: "",
  role: "student",
  track: null,
  adminTracks: [],
  adminIsGlobal: false,
  schoolName: "",
  supervisorSchoolName: "",
  mentorBackground: "",
  mentorInstitution: "",
  mentorReason: "",
  mentorMaxGroupCount: 2,
  yearLevel: null,
  interests: [],
  active: true,
  supervisorEmail: "",
};

const AREA_OF_INTEREST_OPTIONS = [
  "Biomedical Innovations",
  "Environmental Sustainability & Climate Tech",
  "Space & Astrobiology",
  "AI & Robotics and Smart Systems",
  "Nanotechnology & Materials Science",
  "Food & Agriculture Technology",
  "Neuroscience & Mental Health Tech",
  "Water & Energy Tech",
  "Ethical & Societal Impacts of Emerging Tech",
];

const AREA_OF_INTEREST_SELECT_OPTIONS = AREA_OF_INTEREST_OPTIONS.map((interest) => ({
  label: interest,
  value: interest,
}));

function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function roleUsesInterests(role: UserRole) {
  return role === "student" || role === "mentor";
}

function normalizeInterestSelections(interests: string[]) {
  return interests.filter((interest) =>
    AREA_OF_INTEREST_OPTIONS.includes(interest),
  );
}

function UserFormRow({
  label,
  htmlFor,
  required,
  children,
}: {
  label: string;
  htmlFor?: string;
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-1.5 sm:grid-cols-[140px_minmax(0,1fr)] sm:items-start sm:gap-4">
      <Label
        htmlFor={htmlFor}
        className="pt-2 sm:justify-end sm:text-right"
        requiredMarker={required}
      >
        {label}
      </Label>
      <div className="min-w-0 space-y-1.5">{children}</div>
    </div>
  );
}

export function UserEditorSheet({
  open,
  onOpenChange,
  mode,
  user,
  tracks,
  supervisors,
  onSubmit,
  onDelete,
  isPending,
  isDeleting,
}: UserEditorSheetProps) {
  const [values, setValues] = useState<UserFormValues>(initialValues);
  const availableTracks = Array.from(
    new Set([
      ...(tracks ?? []).map((item) => item.trackName),
      ...(user?.track ? [user.track] : []),
      ...(user?.adminTracks ?? []),
    ]),
  );

  useEffect(() => {
    if (!open) return;

    if (mode === "edit" && user) {
      setValues({
        firstName: user.firstName,
        lastName: user.lastName,
        email: user.email,
        role: user.role,
        track: user.track,
        adminTracks: user.role === "admin" ? (user.adminTracks ?? []) : [],
        adminIsGlobal: user.role === "admin" ? user.adminIsGlobal : false,
        schoolName: user.role === "student" ? (user.schoolName ?? "") : "",
        supervisorSchoolName:
          user.role === "supervisor" ? (user.schoolName ?? "") : "",
        mentorBackground: user.role === "mentor" ? (user.mentorBackground ?? "") : "",
        mentorInstitution:
          user.role === "mentor" ? (user.mentorInstitution ?? "") : "",
        mentorReason: user.role === "mentor" ? (user.mentorReason ?? "") : "",
        mentorMaxGroupCount:
          user.role === "mentor" ? (user.mentorMaxGroupCount ?? 2) : 2,
        yearLevel: user.age,
        interests: normalizeInterestSelections(user.interests),
        active: user.active,
        supervisorEmail: user.role === "student" ? (user.supervisorEmail ?? "") : "",
      });
      return;
    }

    setValues(initialValues);
  }, [mode, open, user]);

  const handleSubmit = async () => {
    if (!values.firstName.trim()) {
      toast.error("First name is required.");
      return;
    }
    if (!values.lastName.trim()) {
      toast.error("Last name is required.");
      return;
    }
    if (!values.email.trim()) {
      toast.error("Email is required.");
      return;
    }
    if (!isValidEmail(values.email.trim())) {
      toast.error("Invalid email format.");
      return;
    }
    if (values.role !== "admin" && !values.track) {
      toast.error("Track is required for non-admin users.");
      return;
    }
    if (
      values.role === "admin" &&
      !values.adminIsGlobal &&
      !values.adminTracks.length
    ) {
      toast.error("Select global admin or at least one admin track.");
      return;
    }
    if (values.role === "student") {
      if (!values.schoolName.trim()) {
        toast.error("School is required for student users.");
        return;
      }
      if (!values.yearLevel || values.yearLevel < 9 || values.yearLevel > 12) {
        toast.error("Year level must be between 9 and 12.");
        return;
      }
    }
    if (values.role === "supervisor" && !values.supervisorSchoolName.trim()) {
      toast.error("School is required for supervisor users.");
      return;
    }
    if (values.role === "mentor") {
      if (!values.mentorInstitution.trim()) {
        toast.error("Institution is required for mentor users.");
        return;
      }
      if (!values.mentorReason.trim()) {
        toast.error("Mentor reason is required for mentor users.");
        return;
      }
      if (
        values.mentorMaxGroupCount === null ||
        values.mentorMaxGroupCount < 0
      ) {
        toast.error("Max group count must be 0 or greater.");
        return;
      }
    }
    if (roleUsesInterests(values.role) && !values.interests.length) {
      toast.error(`At least one interest is required for ${values.role} users.`);
      return;
    }

    await onSubmit({
      ...values,
      firstName: values.firstName.trim(),
      lastName: values.lastName.trim(),
      email: values.email.trim(),
      schoolName: values.schoolName.trim(),
      supervisorSchoolName: values.supervisorSchoolName.trim(),
      mentorBackground: values.mentorBackground.trim(),
      mentorInstitution: values.mentorInstitution.trim(),
      mentorReason: values.mentorReason.trim(),
      interests: normalizeInterestSelections(values.interests),
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[92vh] flex-col overflow-hidden sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{mode === "create" ? "Add User" : "Edit User"}</DialogTitle>
          <DialogDescription>
            Manage role, track, and account status without touching other modules.
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 pb-4">
          <UserFormRow label="First Name" htmlFor="user-first-name" required>
            <Input
              id="user-first-name"
              value={values.firstName}
              onChange={(event) =>
                setValues((current) => ({ ...current, firstName: event.target.value }))
              }
              placeholder="Jane"
            />
          </UserFormRow>

          <UserFormRow label="Last Name" htmlFor="user-last-name" required>
            <Input
              id="user-last-name"
              value={values.lastName}
              onChange={(event) =>
                setValues((current) => ({ ...current, lastName: event.target.value }))
              }
              placeholder="Doe"
            />
          </UserFormRow>

          <UserFormRow label="Email" htmlFor="user-email" required>
            <Input
              id="user-email"
              type="email"
              value={values.email}
              onChange={(event) => {
                if (mode === "edit") return;
                setValues((current) => ({ ...current, email: event.target.value }));
              }}
              readOnly={mode === "edit"}
              disabled={mode === "edit"}
              placeholder="jane@example.com"
            />
          </UserFormRow>

          <UserFormRow label="Role" htmlFor="user-role-select" required>
            <Select
              value={values.role}
              onValueChange={(value) =>
                setValues((current) => ({
                  ...current,
                  role: value as UserRole,
                  track: value === "admin" ? null : current.track,
                  adminTracks: value === "admin" ? current.adminTracks : [],
                  adminIsGlobal: value === "admin" ? current.adminIsGlobal : false,
                }))
              }
            >
              <SelectTrigger id="user-role-select">
                <SelectValue placeholder="Select a role" />
              </SelectTrigger>
              <SelectContent>
                {USER_ROLES.map((role) => (
                  <SelectItem key={role} value={role}>
                    {role}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </UserFormRow>

          {values.role === "admin" ? (
            <UserFormRow label="Admin Scope" required>
              <div className="space-y-3">
                <label className="flex cursor-pointer items-center gap-2 rounded-md border p-3 text-sm">
                  <Checkbox
                    checked={values.adminIsGlobal}
                    onCheckedChange={(checked) =>
                      setValues((current) => ({
                        ...current,
                        adminIsGlobal: checked === true,
                      }))
                    }
                  />
                  <span className="font-medium">Global admin</span>
                </label>

                <Label>Admin Tracks</Label>
                <div className="max-h-40 overflow-auto rounded-md border p-3">
                  {availableTracks.length ? (
                    <div className="space-y-2">
                      {availableTracks.map((track) => {
                        const checked = values.adminTracks.includes(track);

                        return (
                          <label
                            key={track}
                            className="flex cursor-pointer items-center gap-2 text-sm"
                          >
                            <input
                              type="checkbox"
                              className="size-4 rounded border-border"
                              checked={checked}
                              disabled={values.adminIsGlobal}
                              onChange={() =>
                                setValues((current) => ({
                                  ...current,
                                  adminTracks: checked
                                    ? current.adminTracks.filter(
                                        (item) => item !== track,
                                      )
                                    : [...current.adminTracks, track],
                                }))
                              }
                            />
                            <span>{track}</span>
                          </label>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      No tracks are available.
                    </p>
                  )}
                </div>
              </div>
            </UserFormRow>
          ) : (
            <UserFormRow label="Track" htmlFor="user-track-select" required>
              <Select
                value={values.track ?? "none"}
                onValueChange={(value) =>
                  setValues((current) => ({
                    ...current,
                    track: value === "none" ? null : (value as UserTrack),
                  }))
                }
              >
                <SelectTrigger id="user-track-select">
                  <SelectValue placeholder="Select a track" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Unassigned</SelectItem>
                  {availableTracks.map((track) => (
                    <SelectItem key={track} value={track}>
                      {track}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </UserFormRow>
          )}

          {values.role === "student" ? (
            <>
              <UserFormRow label="School" htmlFor="user-school-name" required>
                <Input
                  id="user-school-name"
                  value={values.schoolName}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      schoolName: event.target.value,
                    }))
                  }
                  placeholder="Sydney High School"
                />
              </UserFormRow>

              <UserFormRow label="Year Level" htmlFor="user-year-level" required>
                <Input
                  id="user-year-level"
                  type="number"
                  min={10}
                  max={30}
                  value={values.yearLevel ?? ""}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      yearLevel: event.target.value
                        ? Number(event.target.value)
                        : null,
                    }))
                  }
                  placeholder="10"
                />
              </UserFormRow>

              <UserFormRow label="Supervisor" htmlFor="user-supervisor-email">
                <Input
                  id="user-supervisor-email"
                  list="user-supervisor-datalist"
                  value={values.supervisorEmail}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      supervisorEmail: event.target.value,
                    }))
                  }
                  placeholder="Search by name or email (optional)"
                />
                {supervisors && supervisors.length > 0 && (
                  <datalist id="user-supervisor-datalist">
                    {supervisors.map((sup) => (
                      <option key={sup.id} value={sup.email} label={sup.name} />
                    ))}
                  </datalist>
                )}
                {values.supervisorEmail && supervisors && (
                  <p className="text-xs text-muted-foreground">
                    {supervisors.find((s) => s.email === values.supervisorEmail)?.name ?? ""}
                  </p>
                )}
              </UserFormRow>
            </>
          ) : null}

          {values.role === "supervisor" ? (
            <UserFormRow label="School" htmlFor="user-supervisor-school-name" required>
              <Input
                id="user-supervisor-school-name"
                value={values.supervisorSchoolName}
                onChange={(event) =>
                  setValues((current) => ({
                    ...current,
                    supervisorSchoolName: event.target.value,
                  }))
                }
                placeholder="Sydney High School"
              />
            </UserFormRow>
          ) : null}

          {values.role === "mentor" ? (
            <>
              <UserFormRow label="Institution" htmlFor="user-mentor-institution" required>
                <Input
                  id="user-mentor-institution"
                  value={values.mentorInstitution}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      mentorInstitution: event.target.value,
                    }))
                  }
                  placeholder="University of Sydney"
                />
              </UserFormRow>

              <UserFormRow label="Background" htmlFor="user-mentor-background">
                <Input
                  id="user-mentor-background"
                  value={values.mentorBackground}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      mentorBackground: event.target.value,
                    }))
                  }
                  placeholder="Research"
                />
              </UserFormRow>

              <UserFormRow label="Mentor Reason" htmlFor="user-mentor-reason" required>
                <Textarea
                  id="user-mentor-reason"
                  value={values.mentorReason}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      mentorReason: event.target.value,
                    }))
                  }
                  placeholder="Interested in supporting student research projects."
                />
              </UserFormRow>

              <UserFormRow
                label="Max Groups"
                htmlFor="user-mentor-max-group-count"
                required
              >
                <Input
                  id="user-mentor-max-group-count"
                  type="number"
                  min={0}
                  value={values.mentorMaxGroupCount ?? ""}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      mentorMaxGroupCount: event.target.value
                        ? Number(event.target.value)
                        : null,
                    }))
                  }
                  placeholder="2"
                />
              </UserFormRow>
            </>
          ) : null}

          {roleUsesInterests(values.role) ? (
            <UserFormRow
              label={
                values.role === "mentor" ? "Interests / Expertise" : "Interests"
              }
              htmlFor="user-interests"
              required
            >
              <MultiSelect
                id="user-interests"
                options={AREA_OF_INTEREST_SELECT_OPTIONS}
                value={values.interests}
                onValueChange={(interests) =>
                  setValues((current) => ({
                    ...current,
                    interests: normalizeInterestSelections(interests),
                  }))
                }
                placeholder="Select areas of interest"
                searchPlaceholder="Search areas..."
              />
            </UserFormRow>
          ) : null}

        </div>

        <DialogFooter className="shrink-0 border-t">
          {mode === "edit" && user && onDelete ? (
            <Button
              variant="destructive"
              onClick={() => onDelete(user)}
              loading={isDeleting}
            >
              Delete User
            </Button>
          ) : null}
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} loading={isPending}>
            {mode === "create" ? "Create User" : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
