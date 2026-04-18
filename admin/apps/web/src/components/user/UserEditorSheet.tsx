import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
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
  isPending?: boolean;
}

const initialValues: UserFormValues = {
  name: "",
  email: "",
  role: "student",
  track: null,
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
  isPending,
}: UserEditorSheetProps) {
  const [values, setValues] = useState<UserFormValues>(initialValues);
  const availableTracks = Array.from(
    new Set([
      ...(tracks ?? []).map((item) => item.trackCode),
      ...(user?.track ? [user.track] : []),
    ]),
  );

  useEffect(() => {
    if (!open) return;

    if (mode === "edit" && user) {
      setValues({
        name: user.name,
        email: user.email,
        role: user.role,
        track: user.track,
        active: user.active,
      });
      return;
    }

    setValues(initialValues);
  }, [mode, open, user]);

  const handleSubmit = async () => {
    if (!values.name.trim()) {
      window.alert("Name is required.");
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

    await onSubmit({
      ...values,
      name: values.name.trim(),
      email: values.email.trim(),
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
            <Label htmlFor="user-name">Name</Label>
            <Input
              id="user-name"
              value={values.name}
              onChange={(event) =>
                setValues((current) => ({ ...current, name: event.target.value }))
              }
              placeholder="Jane Doe"
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
