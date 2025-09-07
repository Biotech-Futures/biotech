// src/data/mock.js
export const mockUsers = [
  { id: 1, name: 'Anita Pickard', email: 'anita.pickard@email.com', role: 'mentor', track: 'AUS-NSW', status: 'active' },
  { id: 2, name: 'Yilin Guo', email: 'yilin.guo@email.com', role: 'student', track: 'AUS-NSW', status: 'active' },
  { id: 3, name: 'Claudia Zhang', email: 'claudia.zhang@email.com', role: 'student', track: 'AUS-NSW', status: 'active' },
  { id: 4, name: 'Zhujin Wang', email: 'zhujin.wang@email.com', role: 'student', track: 'AUS-NSW', status: 'active' },
  { id: 5, name: 'William Nixon', email: 'william.nixon@biotech.com', role: 'admin', track: 'Global', status: 'active' }
];

export const mockGroups = [
  { id: 'BTF046', name: 'BTF046', members: 4, status: 'Schedule Workshop', mentor: 'Anita Pickard' },
  { id: 'BTF001', name: 'BTF001', members: 5, status: 'Schedule Workshop', mentor: 'Anita Pickard' }
];

export const mockResources = [
  { id: 1, title: '2025 Challenge Guidebook', type: 'document', updated: '5 hours ago', role: 'all' },
  { id: 2, title: 'Frequently Asked Questions', type: 'document', updated: '1 day ago', role: 'all' },
  { id: 3, title: 'Mentor Handbook', type: 'document', updated: '3 days ago', role: 'mentor' },
  { id: 4, title: 'Conversation Starters', type: 'document', updated: '1 week ago', role: 'all' },
  { id: 5, title: 'Marking rubrics and submission details', type: 'document', updated: '2 weeks ago', role: 'mentor' },
  { id: 6, title: 'Mentor Info Session Recording and Slides', type: 'video', updated: '1 month ago', role: 'mentor' }
];

// ★ 补充这个：
export const mockEvents = [
  { id: 1, title: 'Program Kickoff',            date: '2025-09-15', time: '10:00 AM', location: 'Sydney University', type: 'in-person' },
  { id: 2, title: 'Mentor Training Workshop',   date: '2025-09-20', time: '2:00 PM',  location: 'Online',            type: 'virtual'   },
  { id: 3, title: 'Student Orientation',        date: '2025-09-22', time: '3:00 PM',  location: 'Online',            type: 'virtual'   },
  { id: 4, title: 'Mid-Program Check-in',       date: '2025-10-15', time: '4:00 PM',  location: 'Online',            type: 'virtual'   },
  { id: 5, title: 'Final Presentations',        date: '2025-11-20', time: '9:00 AM',  location: 'Sydney University', type: 'in-person' }
];


export const mockAnnouncements = [
  {
    id: 101,
    title: 'Welcome to the 2025 BIOTech Futures Challenge',
    date: '2025-09-01T09:00:00+10:00',
    author: 'Program Team',
    summary: 'Kickoff details, timelines, and how to get started with your mentor group.'
  },
  {
    id: 102,
    title: 'Mentor Info Session Slides Available',
    date: '2025-09-03T18:00:00+10:00',
    author: 'Mentor Coordination',
    summary: 'Download the slides and recording from our first mentor info session.',
    link: 'https://example.org/mentor-info-slides' // 外链示例
  },
  {
    id: 103,
    title: 'Submission Rubrics Updated',
    date: '2025-09-04T10:30:00+10:00',
    author: 'Academic Committee',
    summary: 'We have refined scoring criteria. Please review before planning your workshops.',
    route: null // 预留：若将来有内部详情页，可填 '/announcements/103'
  }
]
 