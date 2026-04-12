import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type {
  CreateResourceInput,
  QueryResourcesInput,
  UpdateResourceInput,
} from "./schema.js";

type ResourceRole = {
  id: string;
  role_name: string;
};

type ResourceTypeName = "document" | "guide" | "video" | "template";

type ResourceType = {
  id: string;
  type_name: ResourceTypeName;
  type_description: string;
};

type Resource = {
  id: string;
  resource_name: string;
  resource_description: string;
  resource_type_detail: ResourceType | null;
  upload_datetime: string;
  uploader: {
    id: string;
    first_name: string;
    last_name: string;
    email: string;
  };
  visible_roles: ResourceRole[];
  deleted_flag: boolean;
  deleted_datetime: string | null;
};

type ResourceStore = {
  items: Resource[];
  nextId: number;
};

const moduleDir = dirname(fileURLToPath(import.meta.url));
const resourceStoreFile = resolve(moduleDir, "../../../.mock/resource-store.json");

const resourceRoles: ResourceRole[] = [
  { id: "role-student", role_name: "student" },
  { id: "role-mentor", role_name: "mentor" },
  { id: "role-admin", role_name: "admin" },
];

const resourceTypes: ResourceType[] = [
  {
    id: "type-1",
    type_name: "document",
    type_description: "Reference document and written material",
  },
  {
    id: "type-2",
    type_name: "guide",
    type_description: "How-to guide and onboarding instructions",
  },
  {
    id: "type-3",
    type_name: "video",
    type_description: "Recorded walkthrough and session materials",
  },
  {
    id: "type-4",
    type_name: "template",
    type_description: "Reusable worksheet and checklist",
  },
];

function resolveType(typeId?: string | null) {
  if (!typeId) {
    return null;
  }

  return resourceTypes.find((item) => item.id === typeId) ?? null;
}

function resolveRoles(roleIds?: string[]) {
  if (!roleIds || roleIds.length === 0) {
    return [];
  }

  return resourceRoles.filter((role) => roleIds.includes(role.id));
}

function createMockResources(): Resource[] {
  return [
    {
      id: "res-1",
      resource_name: "Mentor Onboarding Guide",
      resource_description:
        "A short orientation pack for new mentors covering cadence, expectations, and escalation paths.",
      resource_type_detail: resourceTypes[1],
      upload_datetime: "2026-03-21T10:00:00.000Z",
      uploader: {
        id: "u-admin-1",
        first_name: "Nina",
        last_name: "Taylor",
        email: "nina.taylor@example.com",
      },
      visible_roles: [resourceRoles[1], resourceRoles[2]],
      deleted_flag: false,
      deleted_datetime: null,
    },
    {
      id: "res-2",
      resource_name: "Student Pitch Template",
      resource_description:
        "A slide starter for student teams preparing their biotech problem statement and proposed solution.",
      resource_type_detail: resourceTypes[3],
      upload_datetime: "2026-03-29T06:30:00.000Z",
      uploader: {
        id: "u-admin-2",
        first_name: "Liam",
        last_name: "Wong",
        email: "liam.wong@example.com",
      },
      visible_roles: [resourceRoles[0], resourceRoles[2]],
      deleted_flag: false,
      deleted_datetime: null,
    },
    {
      id: "res-3",
      resource_name: "Lab Safety Basics",
      resource_description:
        "Introductory lab safety checklist for teams running in-person prototyping activities.",
      resource_type_detail: resourceTypes[0],
      upload_datetime: "2026-04-02T12:45:00.000Z",
      uploader: {
        id: "u-admin-3",
        first_name: "Aria",
        last_name: "Singh",
        email: "aria.singh@example.com",
      },
      visible_roles: [resourceRoles[0], resourceRoles[1], resourceRoles[2]],
      deleted_flag: false,
      deleted_datetime: null,
    },
    {
      id: "res-4",
      resource_name: "Program Walkthrough Recording",
      resource_description:
        "A video recap of the first admin orientation, including workflow demos for matching and resources.",
      resource_type_detail: resourceTypes[2],
      upload_datetime: "2026-04-06T08:15:00.000Z",
      uploader: {
        id: "u-admin-1",
        first_name: "Nina",
        last_name: "Taylor",
        email: "nina.taylor@example.com",
      },
      visible_roles: [resourceRoles[2]],
      deleted_flag: false,
      deleted_datetime: null,
    },
    {
      id: "res-5",
      resource_name: "Weekly Check-in Worksheet",
      resource_description:
        "Template for coordinators to track mentor response rates, flagged groups, and follow-up actions.",
      resource_type_detail: resourceTypes[3],
      upload_datetime: "2026-04-09T04:20:00.000Z",
      uploader: {
        id: "u-admin-4",
        first_name: "Grace",
        last_name: "Morris",
        email: "grace.morris@example.com",
      },
      visible_roles: [resourceRoles[2]],
      deleted_flag: false,
      deleted_datetime: null,
    },
  ];
}

function createInitialStore(): ResourceStore {
  const items = createMockResources();
  return {
    items,
    nextId: items.length + 1,
  };
}

function readStore(): ResourceStore {
  if (!existsSync(resourceStoreFile)) {
    const initialStore = createInitialStore();
    mkdirSync(dirname(resourceStoreFile), { recursive: true });
    writeFileSync(resourceStoreFile, JSON.stringify(initialStore, null, 2), "utf8");
    return initialStore;
  }

  return JSON.parse(readFileSync(resourceStoreFile, "utf8")) as ResourceStore;
}

function writeStore(store: ResourceStore) {
  mkdirSync(dirname(resourceStoreFile), { recursive: true });
  writeFileSync(resourceStoreFile, JSON.stringify(store, null, 2), "utf8");
}

export function queryResources(params: QueryResourcesInput) {
  const { page, limit, search, type } = params;
  const normalizedSearch = search?.trim().toLowerCase();
  const store = readStore();

  const filtered = store.items.filter((resource) => {
    if (type && resource.resource_type_detail?.type_name !== type) {
      return false;
    }

    if (!normalizedSearch) {
      return true;
    }

    return (
      resource.resource_name.toLowerCase().includes(normalizedSearch) ||
      resource.resource_description.toLowerCase().includes(normalizedSearch) ||
      resource.uploader.email.toLowerCase().includes(normalizedSearch)
    );
  });

  const offset = (page - 1) * limit;
  const items = filtered.slice(offset, offset + limit);

  return {
    msg: "Resources retrieved successfully",
    data: {
      items,
      total: filtered.length,
      page,
      limit,
      hasMore: offset + items.length < filtered.length,
    },
  };
}

export function queryResourceById(id: string) {
  const store = readStore();
  const resource = store.items.find((item) => item.id === id) ?? null;
  return {
    msg: resource ? "Resource retrieved successfully" : "Resource not found",
    data: resource,
  };
}

export function queryResourceRoles() {
  return {
    msg: "Resource roles retrieved successfully",
    data: resourceRoles,
  };
}

export function queryResourceTypes() {
  return {
    msg: "Resource types retrieved successfully",
    data: resourceTypes,
  };
}

export function createResource(input: CreateResourceInput) {
  const store = readStore();
  const now = new Date().toISOString();
  const resource: Resource = {
    id: `res-${store.nextId++}`,
    resource_name: input.resource_name,
    resource_description: input.resource_description,
    resource_type_detail: resolveType(input.resource_type_id),
    upload_datetime: now,
    uploader: {
      id: "u-admin-demo",
      first_name: "Demo",
      last_name: "Coordinator",
      email: "demo.coordinator@example.com",
    },
    visible_roles: resolveRoles(input.role_ids),
    deleted_flag: false,
    deleted_datetime: null,
  };

  store.items = [resource, ...store.items];
  writeStore(store);

  return {
    msg: "Resource created successfully",
    data: resource,
  };
}

export function updateResource(id: string, input: UpdateResourceInput) {
  const store = readStore();
  const index = store.items.findIndex((item) => item.id === id);
  if (index === -1) {
    return { msg: "Resource not found", data: null };
  }

  const current = store.items[index];
  const updated: Resource = {
    ...current,
    resource_name: input.resource_name ?? current.resource_name,
    resource_description:
      input.resource_description ?? current.resource_description,
    resource_type_detail:
      input.resource_type_id !== undefined
        ? resolveType(input.resource_type_id)
        : current.resource_type_detail,
    visible_roles:
      input.role_ids !== undefined ? resolveRoles(input.role_ids) : current.visible_roles,
  };

  store.items[index] = updated;
  writeStore(store);

  return {
    msg: "Resource updated successfully",
    data: updated,
  };
}

export function deleteResource(id: string) {
  const store = readStore();
  const exists = store.items.some((item) => item.id === id);
  if (!exists) {
    return { msg: "Resource not found", data: null };
  }

  store.items = store.items.filter((item) => item.id !== id);
  writeStore(store);
  return {
    msg: "Resource deleted successfully",
    data: null,
  };
}
