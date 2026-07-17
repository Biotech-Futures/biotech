import { type ReactNode, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
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
  type CountryOption,
  type StateOption,
  type UserAccount,
  type UserFormValues,
  type UserRole,
} from "@/type/user";
import { toast } from "sonner";

interface UserEditorSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  user: UserAccount | null;
  countries?: CountryOption[];
  states?: StateOption[];
  supervisors?: Array<{ id: string; name: string; email: string }>;
  /** Role to preselect when creating (e.g. "supervisor" on the Supervisors tab). */
  defaultRole?: UserRole;
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
  countryId: null,
  stateId: null,
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
  countries,
  states,
  supervisors,
  defaultRole,
  onSubmit,
  onDelete,
  isPending,
  isDeleting,
}: UserEditorSheetProps) {
  const [values, setValues] = useState<UserFormValues>(initialValues);
  const currentCountry = user?.country ?? null;
  const countryOptions = countries ?? [];
  const availableCountries =
    currentCountry && !countryOptions.some((item) => item.id === currentCountry.id)
      ? [...countryOptions, currentCountry]
      : countryOptions;

  const currentState = user?.state ?? null;
  const stateOptions = states ?? [];
  // The user's own state carries no country (that's `user.country`), so pair it back
  // up before merging it into the lookup-shaped list the country filter below reads.
  const currentStateOption: StateOption | null = currentState
    ? { ...currentState, countryName: currentCountry?.countryName ?? null }
    : null;
  const allStates =
    currentStateOption && !stateOptions.some((item) => item.id === currentStateOption.id)
      ? [...stateOptions, currentStateOption]
      : stateOptions;
  // A state belongs to a country, so only the selected country's states are valid.
  const selectedCountryName =
    availableCountries.find((item) => item.id === values.countryId)?.countryName ??
    null;
  const availableStates = selectedCountryName
    ? allStates.filter((item) => item.countryName === selectedCountryName)
    : [];

  useEffect(() => {
    if (!open) return;

    if (mode === "edit" && user) {
      setValues({
        firstName: user.firstName,
        lastName: user.lastName,
        email: user.email,
        role: user.role,
        countryId: user.country?.id ?? null,
        stateId: user.state?.id ?? null,
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

    setValues(
      defaultRole ? { ...initialValues, role: defaultRole } : initialValues,
    );
  }, [mode, open, user, defaultRole]);

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
    // State stays optional — only Australian registrations carry one.
    if (values.role !== "admin" && values.countryId == null) {
      toast.error("Country is required for non-admin users.");
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
            Manage role, state, and account status without touching other modules.
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
                  countryId: value === "admin" ? null : current.countryId,
                  stateId: value === "admin" ? null : current.stateId,
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

          {values.role !== "admin" ? (
            <>
              <UserFormRow label="Country" htmlFor="user-country-select" required>
                <Select
                  value={values.countryId != null ? String(values.countryId) : "none"}
                  onValueChange={(value) =>
                    setValues((current) => ({
                      ...current,
                      countryId: value === "none" ? null : Number(value),
                      stateId: null, // states belong to a country; the old pick can't survive
                    }))
                  }
                >
                  <SelectTrigger id="user-country-select">
                    <SelectValue placeholder="Select a country" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Unassigned</SelectItem>
                    {availableCountries.map((country) => (
                      <SelectItem key={country.id} value={String(country.id)}>
                        {country.countryName}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </UserFormRow>

              {availableStates.length ? (
                <UserFormRow label="State" htmlFor="user-state-select">
                  <Select
                    value={values.stateId != null ? String(values.stateId) : "none"}
                    onValueChange={(value) =>
                      setValues((current) => ({
                        ...current,
                        stateId: value === "none" ? null : Number(value),
                      }))
                    }
                  >
                    <SelectTrigger id="user-state-select">
                      <SelectValue placeholder="Select a state" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None</SelectItem>
                      {availableStates.map((state) => (
                        <SelectItem key={state.id} value={String(state.id)}>
                          {state.stateName}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </UserFormRow>
              ) : null}
            </>
          ) : null}

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
            <UserFormRow label="School (optional)" htmlFor="user-supervisor-school-name">
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
