// User service with mock data
import type { QueryUsersInput, CreateUserInput, BulkCreateUsersInput, UpdateUserInput } from "./schema.js";

export type Role = "student" | "mentor" | "admin";
export type Track = "frontend" | "backend" | "fullstack" | "data";

export type User = {
  id: string;
  name: string;
  email: string;
  role: Role;
  track: Track | null;
  groupId: string | null;
  groupName: string | null;
  createdAt: string;
  updatedAt: string;
};

// Mock group name lookup
const groupNames: Record<string, string> = Object.fromEntries(
  Array.from({ length: 50 }, (_, i) => [`g${i + 1}`, `Group ${i + 1}`]),
);

const tracks: Track[] = ["frontend", "backend", "fullstack", "data"];
const roles: Role[] = ["student", "mentor", "admin"];

const firstNames = ["Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Henry", "Iris", "Jack"];
const lastNames = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Wilson", "Moore"];

function generateMockUsers(): User[] {
  const users: User[] = [];
  let id = 1;

  for (let i = 0; i < 60; i++) {
    const role = i < 40 ? "student" : i < 55 ? "mentor" : "admin";
    const track = role !== "admin" ? tracks[i % 4] : null;
    const groupId = role === "student" ? `g${(i % 20) + 1}` : null;

    const firstName = firstNames[i % firstNames.length];
    const lastName = lastNames[Math.floor(i / firstNames.length) % lastNames.length];

    users.push({
      id: `u${id++}`,
      name: `${firstName} ${lastName}`,
      email: `${firstName.toLowerCase()}.${lastName.toLowerCase()}${i}@example.com`,
      role,
      track,
      groupId,
      groupName: groupId ? groupNames[groupId] : null,
      createdAt: new Date(2024, 0, 1 + (i % 30)).toISOString(),
      updatedAt: new Date(2024, 0, 1 + (i % 30)).toISOString(),
    });
  }

  return users;
}

let mockUsers: User[] = generateMockUsers();
let nextId = mockUsers.length + 1;

export function queryUsers(params: QueryUsersInput) {
  const { page, limit, search, role, track } = params;
  const offset = (page - 1) * limit;

  let filtered = mockUsers.filter((u) => {
    if (role && u.role !== role) return false;
    if (track && u.track !== track) return false;
    if (search) {
      const s = search.toLowerCase();
      if (!u.name.toLowerCase().includes(s) && !u.email.toLowerCase().includes(s)) return false;
    }
    return true;
  });

  const total = filtered.length;
  const items = filtered.slice(offset, offset + limit);

  return {
    msg: "Users retrieved successfully",
    data: { items, total, page, limit, hasMore: offset + items.length < total },
  };
}

export function queryUserById(id: string) {
  const u = mockUsers.find((u) => u.id === id);
  if (!u) return { msg: "User not found", data: null };
  return { msg: "User retrieved successfully", data: u };
}

export function createUser(input: CreateUserInput) {
  const existing = mockUsers.find((u) => u.email === input.email);
  if (existing) return { msg: "Email already exists", data: null };

  const now = new Date().toISOString();
  const newUser: User = {
    id: `u${nextId++}`,
    name: input.name,
    email: input.email,
    role: input.role,
    track: input.track ?? null,
    groupId: input.groupId ?? null,
    groupName: input.groupId ? (groupNames[input.groupId] ?? null) : null,
    createdAt: now,
    updatedAt: now,
  };

  mockUsers.push(newUser);
  return { msg: "User created successfully", data: newUser };
}

export function bulkCreateUsers(input: BulkCreateUsersInput) {
  const created: User[] = [];
  const skipped: string[] = [];
  const now = new Date().toISOString();

  for (const u of input.users) {
    if (mockUsers.find((existing) => existing.email === u.email)) {
      skipped.push(u.email);
      continue;
    }
    const newUser: User = {
      id: `u${nextId++}`,
      name: u.name,
      email: u.email,
      role: u.role,
      track: u.track ?? null,
      groupId: u.groupId ?? null,
      groupName: u.groupId ? (groupNames[u.groupId] ?? null) : null,
      createdAt: now,
      updatedAt: now,
    };
    mockUsers.push(newUser);
    created.push(newUser);
  }

  return {
    msg: `Bulk import complete: ${created.length} created, ${skipped.length} skipped`,
    data: { created, skipped },
  };
}

export function updateUser(id: string, input: UpdateUserInput) {
  const index = mockUsers.findIndex((u) => u.id === id);
  if (index === -1) return { msg: "User not found", data: null };

  const groupId = input.groupId !== undefined ? input.groupId : mockUsers[index].groupId;

  mockUsers[index] = {
    ...mockUsers[index],
    ...input,
    groupId,
    groupName: groupId ? (groupNames[groupId] ?? null) : null,
    updatedAt: new Date().toISOString(),
  };

  return { msg: "User updated successfully", data: mockUsers[index] };
}

export function deleteUser(id: string) {
  const index = mockUsers.findIndex((u) => u.id === id);
  if (index === -1) return { msg: "User not found", data: null };

  mockUsers.splice(index, 1);
  return { msg: "User deleted successfully", data: null };
}
