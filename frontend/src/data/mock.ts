export interface MockUser {
  id: number
  name: string
  email: string
  role: 'mentor' | 'student' | 'admin' | 'supervisor'
  track: string
  status: string
  region?: string
}

export interface MockGroup {
  id: string
  name: string
  members: number
  status: string
  mentor: string
  track?: string
  category?: string
}

export interface MockResource {
  id: number
  title: string
  type: 'document' | 'video' | 'link' | 'pdf' | 'article'
  updated: string
  role: 'all' | 'mentor' | 'student' | 'supervisor' | 'admin'
  category?: string
}

export interface MockEvent {
  id: number
  title: string
  date: string
  time: string
  location: string
  mode: string
}

export interface MockAnnouncement {
  id: number
  title: string
  date: string
  author: string
  summary: string
  audience: 'all' | 'mentor' | 'student' | 'supervisor' | 'admin'
  link?: string
  route?: string | null
}

export const mockUsers: MockUser[] = [
  {
    id: 1,
    name: 'Anita Pickard',
    email: 'anita.pickard@email.com',
    role: 'mentor',
    track: 'AUS-NSW',
    status: 'active',
    region: 'Australia'
  },
  {
    id: 2,
    name: 'Yilin Guo',
    email: 'yilin.guo@email.com',
    role: 'student',
    track: 'AUS-NSW',
    status: 'active',
    region: 'Australia'
  },
  {
    id: 3,
    name: 'Claudia Zhang',
    email: 'claudia.zhang@email.com',
    role: 'student',
    track: 'AUS-NSW',
    status: 'active',
    region: 'Australia'
  },
  {
    id: 4,
    name: 'Zhujin Wang',
    email: 'zhujin.wang@email.com',
    role: 'student',
    track: 'AUS-NSW',
    status: 'active',
    region: 'Australia'
  },
  {
    id: 5,
    name: 'William Nixon',
    email: 'william.nixon@biotech.com',
    role: 'admin',
    track: 'Global',
    status: 'active',
    region: 'Global'
  }
]

export const mockGroups: MockGroup[] = [
  {
    id: 'BTF046',
    name: 'BTF046',
    members: 4,
    status: 'active',
    mentor: 'Anita Pickard',
    track: 'NSW'
  },
  {
    id: 'BTF001',
    name: 'BTF001',
    members: 5,
    status: 'active',
    mentor: 'Anita Pickard',
    track: 'NSW'
  },
  {
    id: 'BTF112',
    name: 'BTF112',
    members: 6,
    status: 'active',
    mentor: 'William Nixon',
    track: 'GL'
  }
]

export const mockResources: MockResource[] = [
  {
    id: 1,
    title: '2025 Challenge Guidebook',
    type: 'document',
    updated: '5 hours ago',
    role: 'all',
    category: 'Guide'
  },
  {
    id: 2,
    title: 'Frequently Asked Questions',
    type: 'document',
    updated: '1 day ago',
    role: 'all',
    category: 'FAQ'
  },
  {
    id: 3,
    title: 'Mentor Handbook',
    type: 'pdf',
    updated: '3 days ago',
    role: 'mentor',
    category: 'Handbook'
  },
  {
    id: 4,
    title: 'Conversation Starters',
    type: 'document',
    updated: '1 week ago',
    role: 'all',
    category: 'Template'
  },
  {
    id: 5,
    title: 'Marking Rubrics and Submission Details',
    type: 'pdf',
    updated: '2 weeks ago',
    role: 'mentor',
    category: 'Assessment'
  },
  {
    id: 6,
    title: 'Mentor Info Session Recording and Slides',
    type: 'video',
    updated: '1 month ago',
    role: 'mentor',
    category: 'Recording'
  },
  {
    id: 7,
    title: 'Student Workshop Templates',
    type: 'document',
    updated: '3 days ago',
    role: 'student',
    category: 'Template'
  },
  {
    id: 8,
    title: 'Supervisor Assessment Guide',
    type: 'article',
    updated: '1 week ago',
    role: 'supervisor',
    category: 'Guide'
  }
]

export const mockEvents: MockEvent[] = [
  {
    id: 101,
    title: 'Mentor Kickoff Workshop',
    date: '2026-03-25',
    time: '5:30 PM',
    location: 'Online',
    mode: 'Live session'
  },
  {
    id: 102,
    title: 'Group Check-in Session',
    date: '2026-03-28',
    time: '4:00 PM',
    location: 'Zoom',
    mode: 'Mentoring session'
  },
  {
    id: 103,
    title: 'Program Q&A',
    date: '2026-04-02',
    time: '6:00 PM',
    location: 'Online',
    mode: 'Open event'
  }
]

export const mockAnnouncements: MockAnnouncement[] = [
  {
    id: 101,
    title: 'Welcome to the 2025 BIOTech Futures Challenge',
    date: '2025-09-01T09:00:00+10:00',
    author: 'Program Team',
    summary: 'Kickoff details, timelines, and how to get started with your mentor group.',
    audience: 'all'
  },
  {
    id: 102,
    title: 'Mentor Info Session Slides Available',
    date: '2025-09-03T18:00:00+10:00',
    author: 'Mentor Coordination',
    summary: 'Download the slides and recording from our first mentor info session.',
    link: 'https://example.org/mentor-info-slides',
    audience: 'mentor'
  },
  {
    id: 103,
    title: 'Submission Rubrics Updated',
    date: '2025-09-04T10:30:00+10:00',
    author: 'Academic Committee',
    summary: 'We have refined scoring criteria. Please review before planning your events.',
    route: null,
    audience: 'mentor'
  },
  {
    id: 104,
    title: 'Student Orientation Session Reminder',
    date: '2025-09-05T14:00:00+10:00',
    author: 'Student Services',
    summary: 'Do not forget to attend the mandatory orientation session scheduled for next week.',
    audience: 'student'
  },
  {
    id: 105,
    title: 'Supervisor Guidelines Released',
    date: '2025-09-06T11:00:00+10:00',
    author: 'Academic Committee',
    summary: 'New guidelines for supervisors have been published in the resources section.',
    audience: 'supervisor'
  }
]

export interface MockDashboardProgress {
  completionRate: number
  completedTasks: number
  totalTasks: number
  currentWeek: string
  nextMilestone: string
  nextMilestoneDate: string
}

export interface MockDashboardAction {
  key: string
  label: string
  helper: string
  type: 'route' | 'link'
  to?: string
  url?: string
}

export interface MockDashboardChecklistItem {
  key: string
  title: string
  meta: string
  to: string
}

export interface MockAdminWorkflowSummary {
  pendingMatches: number
  pendingReassignments: number
  pendingApprovals: number
  draftBulkMessages: number
}

export const mockDashboardProgress: MockDashboardProgress = {
  completionRate: 42,
  completedTasks: 3,
  totalTasks: 7,
  currentWeek: 'Week 3',
  nextMilestone: 'Check-in #1',
  nextMilestoneDate: '2026-03-28'
}

export const mockStudentActionCenter: MockDashboardAction[] = [
  {
    key: 'join-event',
    label: 'Open next event',
    helper: 'Group Check-in Session',
    type: 'route',
    to: '/events'
  },
  {
    key: 'open-group',
    label: 'Open my active group',
    helper: '3 groups available',
    type: 'route',
    to: '/groups'
  },
  {
    key: 'continue-task',
    label: 'Continue my next task',
    helper: 'Check-in #1 is coming up',
    type: 'route',
    to: '/resources'
  }
]

export const mockTeacherActionCenter: MockDashboardAction[] = [
  {
    key: 'open-session',
    label: 'Open next session',
    helper: 'Mentor Kickoff Workshop',
    type: 'route',
    to: '/events'
  },
  {
    key: 'review-groups',
    label: 'Review my groups',
    helper: '3 groups assigned',
    type: 'route',
    to: '/groups'
  },
  {
    key: 'open-mentor-resources',
    label: 'Open mentor resources',
    helper: 'Mentor materials available',
    type: 'route',
    to: '/resources'
  }
]

export const mockAdminActionCenter: MockDashboardAction[] = [
  {
    key: 'review-matches',
    label: 'Review pending matches',
    helper: '5 items waiting',
    type: 'route',
    to: '/groups'
  },
  {
    key: 'process-approvals',
    label: 'Process approvals',
    helper: '4 approvals open',
    type: 'route',
    to: '/groups'
  },
  {
    key: 'open-reassignments',
    label: 'Open reassignment queue',
    helper: '2 requests pending',
    type: 'route',
    to: '/groups'
  }
]

export const mockStudentChecklist: MockDashboardChecklistItem[] = [
  {
    key: 'event',
    title: 'Prepare for your next event',
    meta: 'Group Check-in Session · 28 Mar 2026',
    to: '/events'
  },
  {
    key: 'group',
    title: 'Check your group space',
    meta: '3 active group spaces',
    to: '/groups'
  },
  {
    key: 'resource',
    title: 'Continue your current milestone task',
    meta: 'Check-in #1 is the next milestone',
    to: '/resources'
  }
]

export const mockTeacherChecklist: MockDashboardChecklistItem[] = [
  {
    key: 'session',
    title: 'Confirm next mentoring session',
    meta: 'Mentor Kickoff Workshop · 25 Mar 2026',
    to: '/events'
  },
  {
    key: 'groups',
    title: 'Check recent group activity',
    meta: '3 groups assigned to you',
    to: '/groups'
  },
  {
    key: 'resources',
    title: 'Review support materials',
    meta: 'Mentor handbook and rubrics available',
    to: '/resources'
  }
]

export const mockAdminChecklist: MockDashboardChecklistItem[] = [
  {
    key: 'matches',
    title: 'Mentor matching queue',
    meta: '5 items need review',
    to: '/groups'
  },
  {
    key: 'approvals',
    title: 'Open approval requests',
    meta: '4 records pending',
    to: '/groups'
  },
  {
    key: 'messages',
    title: 'Broadcast communication drafts',
    meta: '1 draft ready to review',
    to: '/announcements'
  }
]

export const mockAdminWorkflowSummary: MockAdminWorkflowSummary = {
  pendingMatches: 5,
  pendingReassignments: 2,
  pendingApprovals: 4,
  draftBulkMessages: 1
}

/*
  English:
  mockDashboardTimeline is the temporary timeline dataset for the Dashboard page.
  Use this before the admin-configurable timeline API is ready.

  Future replacement:
  Replace this mock with backend data after the admin timeline management feature is implemented.
*/
export const mockDashboardTimeline = [
  {
    key: 'week-0',
    label: 'Week 0-1',
    title: 'Group onboarding and setup',
    status: 'completed'
  },
  {
    key: 'week-3',
    label: 'Week 3',
    title: 'Check-in #1',
    status: 'current'
  },
  {
    key: 'week-6',
    label: 'Week 6',
    title: 'Check-in #2',
    status: 'upcoming'
  },
  {
    key: 'week-9',
    label: 'Week 9',
    title: 'Final check-in',
    status: 'upcoming'
  },
  {
    key: 'week-10',
    label: 'Week 10',
    title: 'Project outputs and evaluation',
    status: 'upcoming'
  }
]

/*
  English:
  mockBiotechShowcaseItems is the temporary showcase dataset for the Dashboard hero card.
  Use this before the admin-editable showcase content API is ready.

  Future replacement:
  Replace this mock with backend data after the showcase management feature is implemented.
*/
export const mockBiotechShowcaseItems = [
  {
    id: 'local-1',
    title: 'Biotech innovation in modern research spaces',
    summary: 'Explore how research environments, instrumentation, and data systems support scalable biotech work.',
    image: 'https://images.unsplash.com/photo-1576086213369-97a306d36557?auto=format&fit=crop&w=1600&q=80',
    link: '/resources'
  },
  {
    id: 'local-2',
    title: 'Clinical and molecular workflows',
    summary: 'From microscopy to analytics dashboards, connected workflows help teams move faster with better visibility.',
    image: 'https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?auto=format&fit=crop&w=1600&q=80',
    link: '/announcements'
  },
  {
    id: 'local-3',
    title: 'Life science collaboration and platform operations',
    summary: 'Biotech systems often combine research tools, data pipelines, and operational platforms in one ecosystem.',
    image: 'https://images.unsplash.com/photo-1582719508461-905c673771fd?auto=format&fit=crop&w=1600&q=80',
    link: '/groups'
  }
]