import type {
  QueryResourcesInput,
  CreateResourceInput,
  UpdateResourceInput,
} from "./schema.js";

export type Role = {
  id: string;
  role_name: string;
};

export type ResourceType = {
  id: string;
  type_name: "document" | "guide" | "video" | "template";
  type_description: string;
};

export type ResourceUploader = {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
};

export type Resource = {
  id: string;
  resource_name: string;
  resource_description: string;
  resource_type_detail: ResourceType | null;
  upload_datetime: string;
  uploader: ResourceUploader;
  visible_roles: Role[];
  deleted_flag: boolean;
  deleted_datetime: string | null;
};

const roles: Role[] = [
  { id: "role-student", role_name: "Student" },
  { id: "role-mentor", role_name: "Mentor" },
  { id: "role-admin", role_name: "Admin" },
];

const ADMIN_ROLE_ID = "role-admin";

const resourceTypes: ResourceType[] = [
  {
    id: "type-1",
    type_name: "document",
    type_description: "Document resources such as PDFs and written materials",
  },
  {
    id: "type-2",
    type_name: "guide",
    type_description: "Step-by-step guides and tutorials",
  },
  {
    id: "type-3",
    type_name: "video",
    type_description: "Video recordings and presentations",
  },
  {
    id: "type-4",
    type_name: "template",
    type_description: "Templates and boilerplate files",
  },
];

const uploaders: ResourceUploader[] = [
  {
    id: "u-1",
    first_name: "Amy",
    last_name: "Wong",
    email: "amy.wong@example.com",
  },
  {
    id: "u-2",
    first_name: "Lucas",
    last_name: "Chan",
    email: "lucas.chan@example.com",
  },
  {
    id: "u-3",
    first_name: "Priya",
    last_name: "Shah",
    email: "priya.shah@example.com",
  },
];

function getRolesByIds(roleIds: string[] = []): Role[] {
  return roles.filter((role) => roleIds.includes(role.id));
}

function normalizeVisibleRoles(roleIds: string[] = []): Role[] {
  const uniqueRoleIds = Array.from(new Set([...roleIds, ADMIN_ROLE_ID]));
  return getRolesByIds(uniqueRoleIds);
}

function getResourceTypeById(resourceTypeId?: string | null): ResourceType | null {
  if (!resourceTypeId) return null;
  return resourceTypes.find((type) => type.id === resourceTypeId) ?? null;
}

const typeSpecificTitles: Record<ResourceType["type_name"], string[]> = {
  document: [
    "Research Summary",
    "Policy Brief",
    "Assessment Rubric",
    "Program Handbook",
    "Reference Notes",
  ],
  guide: [
    "Peer Review Guide",
    "Onboarding Guide",
    "Submission Guide",
    "Mentor Communication Guide",
    "Workshop Preparation Guide",
  ],
  video: [
    "Workshop Recording",
    "Demo Walkthrough",
    "Q&A Session Recording",
    "Orientation Video",
    "Case Study Presentation",
  ],
  template: [
    "Project Proposal Template",
    "Weekly Report Template",
    "Retrospective Template",
    "Presentation Deck Template",
    "Mentor Feedback Template",
  ],
};

function buildTitle(typeName: ResourceType["type_name"], index: number): string {
  const labels = typeSpecificTitles[typeName];
  return `${labels[index % labels.length]} ${index + 1}`;
}

function buildDescription(typeName: ResourceType["type_name"], index: number): string {
  if (typeName === "guide") {
    return `Step-by-step guidance content (${index + 1}).`;
  }
  if (typeName === "document") {
    return `Reference document for program operations (${index + 1}).`;
  }
  if (typeName === "video") {
    return `Recorded session or walkthrough material (${index + 1}).`;
  }
  return `Reusable template for recurring tasks (${index + 1}).`;
}

function generateMockResources(): Resource[] {
  const items: Resource[] = [];
  const studentRoleId = roles.find((role) => role.role_name === "Student")?.id;
  const mentorRoleId = roles.find((role) => role.role_name === "Mentor")?.id;
  const visibilitySets: string[][] =
    studentRoleId && mentorRoleId
      ? [
          [studentRoleId, mentorRoleId, ADMIN_ROLE_ID],
          [studentRoleId, ADMIN_ROLE_ID],
          [mentorRoleId, ADMIN_ROLE_ID],
        ]
      : [[ADMIN_ROLE_ID]];

  const randomInt = (max: number) => Math.floor(Math.random() * max);

  let previousTypeName: ResourceType["type_name"] | null = null;

  for (let i = 0; i < 48; i++) {
    let type = resourceTypes[randomInt(resourceTypes.length)];
    if (previousTypeName === type.type_name && resourceTypes.length > 1) {
      type = resourceTypes[(resourceTypes.indexOf(type) + 1 + randomInt(resourceTypes.length - 1)) % resourceTypes.length];
    }
    previousTypeName = type.type_name;

    const uploader = uploaders[randomInt(uploaders.length)];
    const daysAgo = randomInt(360);
    const created = new Date(Date.now() - daysAgo * 24 * 60 * 60 * 1000);
    created.setHours(8 + randomInt(11), randomInt(60), 0, 0);
    const visibleRoleIds = visibilitySets[randomInt(visibilitySets.length)];

    items.push({
      id: `res-${i + 1}`,
      resource_name: buildTitle(type.type_name, i + randomInt(24)),
      resource_description: buildDescription(type.type_name, i + randomInt(24)),
      resource_type_detail: type,
      upload_datetime: created.toISOString(),
      uploader,
      visible_roles: normalizeVisibleRoles(visibleRoleIds),
      deleted_flag: false,
      deleted_datetime: null,
    });
  }

  return items;
}

let mockResources: Resource[] = generateMockResources();

export function queryResources(params: QueryResourcesInput) {
  const { page, limit, search, uploader, type, role, order } = params;
  const offset = (page - 1) * limit;

  let filtered = mockResources.filter((resource) => !resource.deleted_flag);

  if (search) {
    const keyword = search.toLowerCase();
    filtered = filtered.filter(
      (resource) =>
        resource.resource_name.toLowerCase().includes(keyword) ||
        resource.resource_description.toLowerCase().includes(keyword),
    );
  }

  if (uploader) {
    const uploaderKeyword = uploader.toLowerCase();
    filtered = filtered.filter((resource) => {
      const fullName = `${resource.uploader.first_name} ${resource.uploader.last_name}`.toLowerCase();
      return (
        fullName.includes(uploaderKeyword) ||
        resource.uploader.email.toLowerCase().includes(uploaderKeyword)
      );
    });
  }

  if (type) {
    const typeKeyword = type.toLowerCase();
    filtered = filtered.filter(
      (resource) => resource.resource_type_detail?.type_name.toLowerCase() === typeKeyword,
    );
  }

  if (role) {
    const roleKeyword = role.toLowerCase();
    filtered = filtered.filter((resource) =>
      resource.visible_roles.some((resourceRole) =>
        resourceRole.role_name.toLowerCase().includes(roleKeyword),
      ),
    );
  }

  if (order === "oldest") {
    filtered = filtered.sort(
      (a, b) => new Date(a.upload_datetime).getTime() - new Date(b.upload_datetime).getTime(),
    );
  } else if (order === "name") {
    filtered = filtered.sort((a, b) => a.resource_name.localeCompare(b.resource_name));
  } else {
    filtered = filtered.sort(
      (a, b) => new Date(b.upload_datetime).getTime() - new Date(a.upload_datetime).getTime(),
    );
  }

  const total = filtered.length;
  const items = filtered.slice(offset, offset + limit);

  return {
    msg: "Resources retrieved successfully",
    data: {
      items,
      total,
      page,
      limit,
      hasMore: offset + limit < total,
    },
  };
}

export function queryResourceById(id: string) {
  const resource = mockResources.find((item) => item.id === id && !item.deleted_flag) ?? null;

  if (!resource) {
    return {
      msg: "Resource not found",
      data: null,
    };
  }

  return {
    msg: "Resource retrieved successfully",
    data: resource,
  };
}

export function createResource(payload: CreateResourceInput) {
  const nextId = `res-${mockResources.length + 1}`;

  const newResource: Resource = {
    id: nextId,
    resource_name: payload.resource_name,
    resource_description: payload.resource_description,
    resource_type_detail: getResourceTypeById(payload.resource_type_id),
    upload_datetime: new Date().toISOString(),
    uploader: uploaders[0],
    visible_roles: normalizeVisibleRoles(payload.role_ids),
    deleted_flag: false,
    deleted_datetime: null,
  };

  mockResources = [newResource, ...mockResources];

  return {
    msg: "Resource created successfully",
    data: newResource,
  };
}

export function updateResource(id: string, updates: UpdateResourceInput) {
  const index = mockResources.findIndex((item) => item.id === id && !item.deleted_flag);

  if (index === -1) {
    return {
      msg: "Resource not found",
      data: null,
    };
  }

  const current = mockResources[index];

  const updated: Resource = {
    ...current,
    resource_name: updates.resource_name ?? current.resource_name,
    resource_description: updates.resource_description ?? current.resource_description,
    resource_type_detail:
      updates.resource_type_id === undefined
        ? current.resource_type_detail
        : getResourceTypeById(updates.resource_type_id),
    visible_roles: updates.role_ids ? normalizeVisibleRoles(updates.role_ids) : current.visible_roles,
  };

  mockResources[index] = updated;

  return {
    msg: "Resource updated successfully",
    data: updated,
  };
}

export function deleteResource(id: string) {
  const index = mockResources.findIndex((item) => item.id === id && !item.deleted_flag);

  if (index === -1) {
    return {
      msg: "Resource not found",
      data: null,
    };
  }

  mockResources[index] = {
    ...mockResources[index],
    deleted_flag: true,
    deleted_datetime: new Date().toISOString(),
  };

  return {
    msg: "Resource deleted successfully",
    data: null,
  };
}

export function assignRoleToResource(id: string, roleId: string) {
  const index = mockResources.findIndex((item) => item.id === id && !item.deleted_flag);

  if (index === -1) {
    return {
      msg: "Resource not found",
      data: null,
    };
  }

  const role = roles.find((item) => item.id === roleId);
  if (!role) {
    return {
      msg: "Role not found",
      data: null,
    };
  }

  const hasRole = mockResources[index].visible_roles.some((item) => item.id === roleId);
  if (!hasRole) {
    mockResources[index] = {
      ...mockResources[index],
      visible_roles: [...mockResources[index].visible_roles, role],
    };
  }

  return {
    msg: "Role assigned successfully",
    data: mockResources[index],
  };
}

export function removeRoleFromResource(id: string, roleId: string) {
  const index = mockResources.findIndex((item) => item.id === id && !item.deleted_flag);

  if (index === -1) {
    return {
      msg: "Resource not found",
      data: null,
    };
  }

  if (roleId === ADMIN_ROLE_ID) {
    return {
      msg: "Admin visibility is required and cannot be removed",
      data: mockResources[index],
    };
  }

  mockResources[index] = {
    ...mockResources[index],
    visible_roles: normalizeVisibleRoles(
      mockResources[index].visible_roles
        .filter((item) => item.id !== roleId)
        .map((item) => item.id),
    ),
  };

  return {
    msg: "Role removed successfully",
    data: mockResources[index],
  };
}

export function listResourceRoles() {
  return {
    msg: "Roles retrieved successfully",
    data: roles,
  };
}

export function listResourceTypes() {
  return {
    msg: "Resource types retrieved successfully",
    data: resourceTypes,
  };
}
