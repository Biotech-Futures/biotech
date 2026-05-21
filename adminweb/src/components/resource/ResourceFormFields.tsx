import { RichEditor } from "@/components/announcement/RichEditor";
import type { ReactNode } from "react";
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
import { Textarea } from "@/components/ui/textarea";
import type {
  ResourceKind,
  ResourceRole,
  ResourceTrackOption,
  ResourceTypeName,
  ResourceTypeOption,
  VisibilityScope,
} from "@/type/resource";
import { ResourceRoleSelector } from "./ResourceRoleSelector";

export interface ResourceFormData {
  name: string;
  description: string;
  kind: ResourceKind;
  visibilityScope: VisibilityScope;
  trackId: number | null;
  typeName: ResourceTypeName | null;
  contentHtml: string;
  roleIds: number[];
  labelInput: string;
}

interface ResourceFormFieldsProps {
  value: ResourceFormData;
  onChange: (value: ResourceFormData) => void;
  roles: ResourceRole[];
  tracks: ResourceTrackOption[];
  types: ResourceTypeOption[];
  file: File | null;
  onFileChange: (file: File | null) => void;
  fileLabel: string;
  fileHelpText?: string;
  editorKey?: string | number;
  showAttachmentKind?: boolean;
  canChangeKind?: boolean;
}

function formatFileSize(file: File | null) {
  if (!file) return "";
  const kb = file.size / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

interface ResourceFieldRowProps {
  label: string;
  htmlFor?: string;
  required?: boolean;
  children: ReactNode;
}

function ResourceFieldRow({
  label,
  htmlFor,
  required,
  children,
}: ResourceFieldRowProps) {
  return (
    <div className="grid gap-2 sm:grid-cols-[9rem_minmax(0,1fr)] sm:items-start">
      <Label
        htmlFor={htmlFor}
        className="pt-2 text-sm font-medium text-muted-foreground"
        requiredMarker={required}
      >
        {label}
      </Label>
      <div className="min-w-0 space-y-1.5">{children}</div>
    </div>
  );
}

export function ResourceFormFields({
  value,
  onChange,
  roles,
  tracks,
  types,
  file,
  onFileChange,
  fileLabel,
  fileHelpText,
  editorKey,
  showAttachmentKind = true,
  canChangeKind = true,
}: ResourceFormFieldsProps) {
  const updateValue = (updates: Partial<ResourceFormData>) => {
    onChange({ ...value, ...updates });
  };

  return (
    <div className="space-y-4">
      <ResourceFieldRow label="Resource Kind" htmlFor="resource-kind">
        <Select
          value={value.kind}
          disabled={!canChangeKind}
          onValueChange={(nextValue) =>
            updateValue({ kind: nextValue as ResourceKind })
          }
        >
          <SelectTrigger id="resource-kind">
            <SelectValue placeholder="Select resource mode" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="file">File Upload</SelectItem>
            {showAttachmentKind ? (
              <SelectItem value="attachment">Attachment</SelectItem>
            ) : null}
            <SelectItem value="page">Rich Content Page</SelectItem>
          </SelectContent>
        </Select>
      </ResourceFieldRow>

      <ResourceFieldRow label="Resource Name" htmlFor="resource-name" required>
        <Input
          id="resource-name"
          value={value.name}
          onChange={(event) => updateValue({ name: event.target.value })}
          placeholder="e.g. Mentor Handbook 2026"
        />
      </ResourceFieldRow>

      <ResourceFieldRow label="Description" htmlFor="resource-description" required>
        <Textarea
          id="resource-description"
          value={value.description}
          onChange={(event) => updateValue({ description: event.target.value })}
          placeholder="Short description for admins and users."
        />
      </ResourceFieldRow>

      <ResourceFieldRow label="Visibility" htmlFor="resource-visibility-mode">
        <Select
          value={value.visibilityScope}
          onValueChange={(nextValue) =>
            updateValue({ visibilityScope: nextValue as VisibilityScope })
          }
        >
          <SelectTrigger id="resource-visibility-mode">
            <SelectValue placeholder="Select visibility mode" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="track_based">Track-based</SelectItem>
            <SelectItem value="role_based">Role-based</SelectItem>
          </SelectContent>
        </Select>
      </ResourceFieldRow>

      {value.visibilityScope === "track_based" ? (
        <ResourceFieldRow label="Track" htmlFor="resource-track" required>
          <Select
            value={value.trackId === null ? "none" : String(value.trackId)}
            onValueChange={(nextValue) =>
              updateValue({
                trackId: nextValue === "none" ? null : Number(nextValue),
              })
            }
          >
            <SelectTrigger id="resource-track">
              <SelectValue placeholder="Select track" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">Unassigned</SelectItem>
              {tracks.map((track) => (
                <SelectItem key={track.id} value={String(track.id)}>
                  {track.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </ResourceFieldRow>
      ) : null}

      {value.visibilityScope === "role_based" ? (
        <ResourceFieldRow label="Visible Roles" required>
          <ResourceRoleSelector
            mode="edit"
            roles={roles}
            selectedRoleIds={value.roleIds}
            onSelectedRoleIdsChange={(roleIds) => updateValue({ roleIds })}
          />
        </ResourceFieldRow>
      ) : null}

      <ResourceFieldRow label="Resource Labels" htmlFor="resource-labels">
        <Input
          id="resource-labels"
          value={value.labelInput}
          onChange={(event) => updateValue({ labelInput: event.target.value })}
        />
        <p className="text-xs text-muted-foreground">
          Enter comma separated labels (e.g. Do&apos;s and Don&apos;ts, Group tips)
        </p>
      </ResourceFieldRow>

      <ResourceFieldRow label="Type" htmlFor="resource-type">
        <Select
          value={value.typeName ?? "none"}
          onValueChange={(nextValue) =>
            updateValue({
              typeName:
                nextValue === "none" ? null : (nextValue as ResourceTypeName),
            })
          }
        >
          <SelectTrigger id="resource-type">
            <SelectValue placeholder="Select type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">Uncategorized</SelectItem>
            {types.map((typeItem) => (
              <SelectItem key={typeItem.value} value={typeItem.value}>
                {typeItem.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </ResourceFieldRow>

      {value.kind === "page" ? (
        <ResourceFieldRow label="Page Content" required>
          <div className="flex flex-wrap items-center gap-2">
            {/* <Button
              type="button"
              variant="default"
              size="sm"
              onClick={() => openHtmlPreviewPage(value.contentHtml)}
            >
              Open Preview Page
            </Button> */}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => updateValue({ contentHtml: "" })}
            >
              Clear
            </Button>
          </div>
          <RichEditor
            key={editorKey}
            value={value.contentHtml}
            onChange={(contentHtml) => updateValue({ contentHtml })}
            placeholder="Write resource page content..."
          />
        </ResourceFieldRow>
      ) : (
        <ResourceFieldRow label={fileLabel} htmlFor="resource-file">
          <Input
            id="resource-file"
            type="file"
            onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
          />
          {file ? (
            <p className="text-xs text-muted-foreground">
              {file.name} ({formatFileSize(file)})
            </p>
          ) : fileHelpText ? (
            <p className="text-xs text-muted-foreground">{fileHelpText}</p>
          ) : null}
        </ResourceFieldRow>
      )}
    </div>
  );
}
