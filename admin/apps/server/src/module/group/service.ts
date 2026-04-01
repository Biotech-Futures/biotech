// Group service with mock data
import type { QueryGroupsInput, UpdateGroupInput } from "./schema.js";

// Types
export type Track = "frontend" | "backend" | "fullstack" | "data";

export type GroupMember = {
  id: string;
  name: string;
  email: string;
  role: "student" | "mentor";
};

export type Group = {
  id: string;
  name: string;
  track: Track;
  members: GroupMember[];
  mentor: GroupMember | null;
  createdAt: string;
  updatedAt: string;
};

// Mock data storage
const mentors: GroupMember[] = [
  { id: "m1", name: "Alice Johnson", email: "alice@example.com", role: "mentor" },
  { id: "m2", name: "Bob Smith", email: "bob@example.com", role: "mentor" },
  { id: "m3", name: "Carol White", email: "carol@example.com", role: "mentor" },
  { id: "m4", name: "David Brown", email: "david@example.com", role: "mentor" },
  { id: "m5", name: "Emma Davis", email: "emma@example.com", role: "mentor" },
];

const studentNames = [
  "John Doe", "Jane Smith", "Mike Johnson", "Sarah Williams", "Tom Brown",
  "Lisa Anderson", "Chris Taylor", "Amy Martinez", "Kevin Garcia", "Rachel Lee",
  "Steve Clark", "Michelle Rodriguez", "Brian Wilson", "Emily Moore", "Jason Taylor",
  "Ashley Thomas", "Matthew Jackson", "Samantha White", "Daniel Harris", "Jessica Martin",
  "Andrew Thompson", "Nicole Robinson", "Joshua Lewis", "Amanda Walker", "Ryan Hall",
  "Stephanie Allen", "Brandon Young", "Jennifer King", "Justin Wright", "Melissa Scott",
];

const tracks: Track[] = ["frontend", "backend", "fullstack", "data"];

// Generate mock groups
function generateMockGroups(): Group[] {
  const groups: Group[] = [];
  let studentId = 1;

  for (let i = 1; i <= 50; i++) {
    const track = tracks[(i - 1) % 4];
    const mentorIndex = (i - 1) % mentors.length;

    // Generate 3-5 members per group
    const memberCount = 3 + (i % 3);
    const members: GroupMember[] = [];

    for (let j = 0; j < memberCount; j++) {
      const studentNameIndex = (studentId - 1) % studentNames.length;
      members.push({
        id: `s${studentId}`,
        name: studentNames[studentNameIndex],
        email: `student${studentId}@example.com`,
        role: "student",
      });
      studentId++;
    }

    groups.push({
      id: `g${i}`,
      name: `Group ${i}`,
      track,
      members,
      mentor: mentors[mentorIndex],
      createdAt: new Date(2024, 0, 1 + (i % 30)).toISOString(),
      updatedAt: new Date(2024, 0, 1 + (i % 30)).toISOString(),
    });
  }

  return groups;
}

// Initialize mock data
let mockGroups: Group[] = generateMockGroups();

// Query groups with pagination and filters
export function queryGroups(params: QueryGroupsInput) {
  const { page, limit, searchName, searchGroup, track } = params;
  const offset = (page - 1) * limit;

  // Filter groups
  let filtered = mockGroups.filter((group) => {
    // Filter by track
    if (track && group.track !== track) {
      return false;
    }

    // Filter by group name
    if (searchGroup) {
      const searchLower = searchGroup.toLowerCase();
      if (!group.name.toLowerCase().includes(searchLower)) {
        return false;
      }
    }

    // Filter by member name
    if (searchName) {
      const searchLower = searchName.toLowerCase();
      const hasMatchingMember = group.members.some(
        (member) => member.name.toLowerCase().includes(searchLower)
      );
      if (!hasMatchingMember) {
        return false;
      }
    }

    return true;
  });

  const total = filtered.length;
  const hasMore = offset + limit < total;
  const items = filtered.slice(offset, offset + limit);

  return {
    msg: "Groups retrieved successfully",
    data: {
      items,
      total,
      page,
      limit,
      hasMore,
    },
  };
}

// Get single group by ID
export function queryGroupById(id: string) {
  const group = mockGroups.find((g) => g.id === id);

  if (!group) {
    return {
      msg: "Group not found",
      data: null,
    };
  }

  return {
    msg: "Group retrieved successfully",
    data: group,
  };
}

// Update group
export function updateGroup(id: string, updates: UpdateGroupInput) {
  const index = mockGroups.findIndex((g) => g.id === id);

  if (index === -1) {
    return {
      msg: "Group not found",
      data: null,
    };
  }

  mockGroups[index] = {
    ...mockGroups[index],
    ...updates,
    updatedAt: new Date().toISOString(),
  };

  return {
    msg: "Group updated successfully",
    data: mockGroups[index],
  };
}