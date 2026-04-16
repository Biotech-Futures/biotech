// User service with mock data
import { auth } from "@/lib/auth.js";
import type {
  QueryUsersInput,
  QueryStudentsInput,
  CreateUserInput,
  BulkCreateUsersInput,
  UpdateUserInput,
} from "./schema.js";

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
  age: number | null;
  interests: string[];
  createdAt: string;
  updatedAt: string;
};

// Mock group name lookup
const groupNames: Record<string, string> = Object.fromEntries(
  Array.from({ length: 50 }, (_, i) => [`g${i + 1}`, `Group ${i + 1}`]),
);

const tracks: Track[] = ["frontend", "backend", "fullstack", "data"];
const roles: Role[] = ["student", "mentor", "admin"];
const interestsPool = [
  "biology",
  "genetics",
  "robotics",
  "data science",
  "ai",
  "healthtech",
  "chemistry",
  "sustainability",
];

const firstNames = [
  "Alice",
  "Bob",
  "Carol",
  "David",
  "Emma",
  "Frank",
  "Grace",
  "Henry",
  "Iris",
  "Jack",
];
const lastNames = [
  "Smith",
  "Johnson",
  "Williams",
  "Brown",
  "Jones",
  "Garcia",
  "Miller",
  "Davis",
  "Wilson",
  "Moore",
];

function generateMockUsers(): User[] {
  const users: User[] = [];
  let id = 1;

  for (let i = 0; i < 60; i++) {
    const role = i < 40 ? "student" : i < 55 ? "mentor" : "admin";
    const track = role !== "admin" ? tracks[i % 4] : null;
    const groupId =
      role === "student" && i % 5 !== 0 ? `g${(i % 20) + 1}` : null;
    const age = role === "student" ? 14 + (i % 5) : null;
    const interests =
      role === "student"
        ? [
            interestsPool[i % interestsPool.length],
            interestsPool[(i + 3) % interestsPool.length],
          ]
        : [];

    const firstName = firstNames[i % firstNames.length];
    const lastName =
      lastNames[Math.floor(i / firstNames.length) % lastNames.length];

    users.push({
      id: `u${id++}`,
      name: `${firstName} ${lastName}`,
      email: `${firstName.toLowerCase()}.${lastName.toLowerCase()}${i}@example.com`,
      role,
      track,
      groupId,
      groupName: groupId ? groupNames[groupId] : null,
      age,
      interests,
      createdAt: new Date(2024, 0, 1 + (i % 30)).toISOString(),
      updatedAt: new Date(2024, 0, 1 + (i % 30)).toISOString(),
    });
  }

  return users;
}

let mockUsers: User[] = generateMockUsers();
let nextId = mockUsers.length + 1;

export function queryStudents(params: QueryStudentsInput) {
  const { page, limit, search, age, track, interest, inGroup } = params;
  const offset = (page - 1) * limit;

  let filtered = mockUsers.filter((u) => {
    if (u.role !== "student") return false;
    if (track && u.track !== track) return false;
    if (age !== undefined && u.age !== age) return false;

    if (interest) {
      const target = interest.toLowerCase();
      if (!u.interests.some((item) => item.toLowerCase().includes(target)))
        return false;
    }

    if (inGroup === "yes" && !u.groupId) return false;
    if (inGroup === "no" && !!u.groupId) return false;

    if (search) {
      const s = search.toLowerCase();
      if (
        !u.name.toLowerCase().includes(s) &&
        !u.email.toLowerCase().includes(s)
      )
        return false;
    }

    return true;
  });

  const total = filtered.length;
  const items = filtered.slice(offset, offset + limit);

  return {
    msg: "Students retrieved successfully",
    data: { items, total, page, limit, hasMore: offset + items.length < total },
  };
}

export function queryUsers(params: QueryUsersInput) {
  const { page, limit, search, role, track } = params;
  const offset = (page - 1) * limit;

  let filtered = mockUsers.filter((u) => {
    if (role && u.role !== role) return false;
    if (track && u.track !== track) return false;
    if (search) {
      const s = search.toLowerCase();
      if (
        !u.name.toLowerCase().includes(s) &&
        !u.email.toLowerCase().includes(s)
      )
        return false;
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
    age: input.role === "student" ? 16 : null,
    interests: input.role === "student" ? ["biology"] : [],
    createdAt: now,
    updatedAt: now,
  };

  mockUsers.push(newUser);
  return { msg: "User created successfully", data: newUser };
}

export async function bulkCreateUsers(input: BulkCreateUsersInput) {
  const created: User[] = [];
  const skipped: string[] = [];
  const now = new Date().toISOString();

  const { others } = await bulkCreateAdminUsers(input.users);

  for (const u of others) {
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
      age: u.role === "student" ? 16 : null,
      interests: u.role === "student" ? ["biology"] : [],
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

  const groupId =
    input.groupId !== undefined ? input.groupId : mockUsers[index].groupId;

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

async function bulkCreateAdminUsers(users: CreateUserInput[]) {
  const success = [];
  const failed = [];
  const others = [];
  for (const user of users) {
    if (user.role === "admin") {
      try {
        const newUser = await auth.api.createUser({
          body: {
            email: user.email,
            name: user.name,
          },
        });
        if (newUser) {
          success.push(user);
        } else {
          failed.push(user);
        }
      } catch (error) {
        failed.push(user);
      }
    } else {
      others.push(user);
    }
  }

  return {
    success,
    failed,
    others,
  };
}
