import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  USER_ROLES,
  type TrackOption,
  type UserAccount,
  type UserFormValues,
  type UserRole,
  type UserTrack,
} from "@/type/user";

interface UserEditorSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  user: UserAccount | null;
  tracks?: TrackOption[];
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
  schoolName: "",
  yearLevel: null,
  interests: [],
  joinPermissionReceived: false,
  active: true,
};

function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function UserEditorSheet({
  open,
  onOpenChange,
  mode,
  user,
  tracks,
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
        schoolName: user.schoolName ?? "",
        yearLevel: user.age,
        interests: user.interests,
        joinPermissionReceived: user.joinPermissionReceived,
        active: user.active,
      });
      return;
    }

    setValues(initialValues);
  }, [mode, open, user]);

  const handleSubmit = async () => {
    if (!values.firstName.trim()) {
      window.alert("First name is required.");
      return;
    }
    if (!values.lastName.trim()) {
      window.alert("Last name is required.");
      return;
    }
    if (!values.email.trim()) {
      window.alert("Email is required.");
      return;
    }
    if (!isValidEmail(values.email.trim())) {
      window.alert("Invalid email format.");
      return;
    }
    if (values.role !== "admin" && !values.track) {
      window.alert("Track is required for non-admin users.");
      return;
    }
    if (values.role === "student") {
      if (!values.schoolName.trim()) {
        window.alert("School is required for student users.");
        return;
      }
      if (!values.yearLevel || values.yearLevel < 9 || values.yearLevel > 12) {
        window.alert("Year level must be between 9 and 12.");
        return;
      }
      if (!values.interests.length) {
        window.alert("At least one interest is required for student users.");
        return;
      }
    }

    await onSubmit({
      ...values,
      firstName: values.firstName.trim(),
      lastName: values.lastName.trim(),
      email: values.email.trim(),
      schoolName: values.schoolName.trim(),
    });
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{mode === "create" ? "Add User" : "Edit User"}</SheetTitle>
          <SheetDescription>
            Manage role, track, and account status without touching other modules.
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-4 px-4">
          <div className="space-y-1.5">
            <Label htmlFor="user-first-name">First Name</Label>
            <Input
              id="user-first-name"
              value={values.firstName}
              onChange={(event) =>
                setValues((current) => ({ ...current, firstName: event.target.value }))
              }
              placeholder="Jane"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="user-last-name">Last Name</Label>
            <Input
              id="user-last-name"
              value={values.lastName}
              onChange={(event) =>
                setValues((current) => ({ ...current, lastName: event.target.value }))
              }
              placeholder="Doe"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="user-email">Email</Label>
            <Input
              id="user-email"
              type="email"
              value={values.email}
              onChange={(event) =>
                setValues((current) => ({ ...current, email: event.target.value }))
              }
              placeholder="jane@example.com"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="user-role-select">Role</Label>
            <Select
              value={values.role}
              onValueChange={(value) =>
                setValues((current) => ({ ...current, role: value as UserRole }))
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
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="user-track-select">Track</Label>
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
          </div>

          {values.role === "student" ? (
            <>
              <div className="space-y-1.5">
                <Label htmlFor="user-school-name">School</Label>
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
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="user-year-level">Year Level</Label>
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
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="user-interests">Interests</Label>
                <Textarea
                  id="user-interests"
                  value={values.interests.join(", ")}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      interests: event.target.value
                        .split(",")
                        .map((item) => item.trim())
                        .filter(Boolean),
                    }))
                  }
                  placeholder="biology, genetics, ai"
                />
              </div>

              <div className="space-y-2">
                <Label>Join Permission Received</Label>
                <div className="flex gap-2">
                  <Button
                    variant={values.joinPermissionReceived ? "default" : "outline"}
                    size="sm"
                    onClick={() =>
                      setValues((current) => ({
                        ...current,
                        joinPermissionReceived: true,
                      }))
                    }
                  >
                    Yes
                  </Button>
                  <Button
                    variant={!values.joinPermissionReceived ? "default" : "outline"}
                    size="sm"
                    onClick={() =>
                      setValues((current) => ({
                        ...current,
                        joinPermissionReceived: false,
                      }))
                    }
                  >
                    No
                  </Button>
                </div>
              </div>
            </>
          ) : null}

          <div className="space-y-2">
            <Label>Account Status</Label>
            <div className="flex gap-2">
              <Button
                variant={values.active ? "default" : "outline"}
                size="sm"
                onClick={() => setValues((current) => ({ ...current, active: true }))}
              >
                Active
              </Button>
              <Button
                variant={!values.active ? "default" : "outline"}
                size="sm"
                onClick={() => setValues((current) => ({ ...current, active: false }))}
              >
                Inactive
              </Button>
            </div>
          </div>
        </div>

        <SheetFooter>
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
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
