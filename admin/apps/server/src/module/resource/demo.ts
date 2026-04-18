export type DemoRole = {
  id: number;
  slug: string;
};

export type DemoResourceTypeName = "document" | "guide" | "video" | "template";

export type DemoResourceTypeOption = {
  value: DemoResourceTypeName;
  label: string;
};

export type DemoUploader = {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
};

export type DemoResourceRow = {
  id: number;
  uploader_user_id: number;
  track_id: number | null;
  visibility_scope: string;
  uploaded_at: string;
  deleted_at: string | null;
  resource_kind: "file" | "page";
  resource_name: string;
  resource_description: string | null;
  resource_type: DemoResourceTypeName | null;
  content_html: string | null;
  file_name: string | null;
  file_mime_type: string | null;
  file_size: number | null;
  storage_key: string;
};

export type DemoResourceAudienceRow = {
  id: number;
  resource_id: number;
  role_id: number | null;
  track_id: number | null;
};

export const demoRoles: DemoRole[] = [
  { id: 1, slug: "student" },
  { id: 2, slug: "mentor" },
  { id: 3, slug: "admin" },
  { id: 4, slug: "supervisor" },
];

export const demoResourceTypes: DemoResourceTypeOption[] = [
  { value: "document", label: "Document" },
  { value: "guide", label: "Guide" },
  { value: "video", label: "Video" },
  { value: "template", label: "Template" },
];

export const demoUploaders: DemoUploader[] = [
  { id: 101, first_name: "Amy", last_name: "Wong", email: "amy.wong@example.com" },
  { id: 102, first_name: "Lucas", last_name: "Chan", email: "lucas.chan@example.com" },
  { id: 103, first_name: "Priya", last_name: "Shah", email: "priya.shah@example.com" },
  { id: 104, first_name: "Noah", last_name: "Lin", email: "noah.lin@example.com" },
  { id: 105, first_name: "Mia", last_name: "Patel", email: "mia.patel@example.com" },
  { id: 106, first_name: "Ethan", last_name: "Nguyen", email: "ethan.nguyen@example.com" },
];

const demoTrackIds = [1, 2, 3, 4, 5, 6] as const;
const demoTypeCycle: DemoResourceTypeName[] = ["document", "guide", "video", "template"];
const demoTitles = [
  "Peer Review Checklist",
  "Weekly Reflection Template",
  "Mentor Session Notes",
  "Lab Safety Orientation",
  "Biotech Ethics Guide",
  "Student Research Pitch Deck",
  "Experiment Log Sheet",
  "Onboarding Handbook",
  "Presentation Rubric",
  "Track Welcome Pack",
  "Literature Review Starter",
  "Meeting Agenda Template",
  "Poster Submission Guide",
  "Project Planning Worksheet",
  "Team Contract Template",
  "Data Collection Form",
  "Research Methods Overview",
  "Progress Update Example",
  "Peer Feedback Samples",
  "Academic Writing Guide",
  "Assessment Timeline",
  "Report Cover Page Template",
  "Mentor Q and A Notes",
  "Workshop Recording",
  "Citation Quick Reference",
  "Problem Statement Worksheet",
  "Risk Management Checklist",
  "Final Presentation Guide",
  "Collaboration Best Practices",
  "Capstone Submission Pack",
];

const demoMimeByType: Record<DemoResourceTypeName, string> = {
  document: "application/pdf",
  guide: "application/pdf",
  video: "video/mp4",
  template: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
};

const demoExtByType: Record<DemoResourceTypeName, string> = {
  document: "pdf",
  guide: "pdf",
  video: "mp4",
  template: "docx",
};

export const demoResources: DemoResourceRow[] = demoTitles.map((title, index) => {
  const id = index + 1;
  const resourceType = demoTypeCycle[index % demoTypeCycle.length];
  const resourceKind: "file" | "page" = index % 5 === 0 ? "page" : "file";
  const trackId = demoTrackIds[index % demoTrackIds.length];
  const uploader = demoUploaders[index % demoUploaders.length];
  const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const ext = demoExtByType[resourceType];
  const baseDate = new Date("2026-04-10T10:00:00.000Z").getTime();
  const uploadedAt = new Date(baseDate - index * 86400000).toISOString();

  return {
    id,
    uploader_user_id: uploader.id,
    track_id: trackId,
    visibility_scope: "role_based",
    uploaded_at: uploadedAt,
    deleted_at: null,
    resource_kind: resourceKind,
    resource_name: title,
    resource_description: `${title} for track-based mentoring and student support.`,
    resource_type: resourceType,
    content_html:
      resourceKind === "page"
        ? `<h2>${title}</h2><p>This is a rich content page for track-based guidance.</p><p><strong>Track:</strong> ${trackId}</p>`
        : null,
    file_name: resourceKind === "page" ? null : `${slug}.${ext}`,
    file_mime_type: resourceKind === "page" ? null : demoMimeByType[resourceType],
    file_size:
      resourceKind === "page"
        ? null
        : resourceType === "video"
          ? 25000000 + id * 10000
          : 70000 + id * 900,
    storage_key:
      resourceKind === "page"
        ? `resources/pages/${slug}.html`
        : `resources/${slug}.${ext}`,
  };
});

export const demoResourceAudience: DemoResourceAudienceRow[] = (() => {
  let audienceId = 1;

  return demoResources.flatMap((resource, index) => {
    const roleSet =
      index % 7 === 0
        ? [1, 3]
        : index % 7 === 1
          ? [2, 3]
          : index % 7 === 2
            ? [4, 3]
            : index % 7 === 3
              ? [1, 2, 3]
              : index % 7 === 4
                ? [1, 4, 3]
                : index % 7 === 5
                  ? [2, 4, 3]
                  : [1, 2, 4, 3];

    return roleSet.map((roleId) => ({
      id: audienceId++,
      resource_id: resource.id,
      role_id: roleId,
      track_id: resource.track_id,
    }));
  });
})();

export function useResourceDemoData(): boolean {
  return (
    process.env.RESOURCE_USE_DEMO_DATA === "true" ||
    process.env.MATCH_USE_DEMO_DATA === "true"
  );
}
