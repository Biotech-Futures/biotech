// Path data for TicketIcon.vue, on a 24 by 24 grid, stroked at 2.
// A circle is drawn as two half arcs; a rounded box as lines and corner arcs.

const box3to21 = 'M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z'

export const TICKET_ICON_PATHS = {
  key: [
    'M15.5 7.5l2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4',
    'M21 2l-9.6 9.6',
    'M2 15.5a5.5 5.5 0 1 0 11 0a5.5 5.5 0 1 0-11 0',
  ],
  'user-plus': [
    'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2',
    'M5 7a4 4 0 1 0 8 0a4 4 0 1 0-8 0',
    'M19 8v6',
    'M22 11h-6',
  ],
  award: ['M6 8a6 6 0 1 0 12 0a6 6 0 1 0-12 0', 'M15.48 12.89L17 22l-5-3-5 3 1.52-9.11'],
  message: ['M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z', 'M13 8H7', 'M17 12H7'],
  search: ['M3 11a8 8 0 1 0 16 0a8 8 0 1 0-16 0', 'M21 21l-4.3-4.3'],
  paperclip: [
    'M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48',
  ],
  file: [
    'M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z',
    'M14 2v4a2 2 0 0 0 2 2h4',
    'M10 9H8',
    'M16 13H8',
    'M16 17H8',
  ],
  image: [box3to21, 'M7 9a2 2 0 1 0 4 0a2 2 0 1 0-4 0', 'M21 15l-3.09-3.09a2 2 0 0 0-2.82 0L6 21'],
  alert: ['M2 12a10 10 0 1 0 20 0a10 10 0 1 0-20 0', 'M12 8v4', 'M12 16h.01'],
  reply: ['M9 17l-5-5 5-5', 'M20 18v-2a4 4 0 0 0-4-4H4'],
  lock: [
    'M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z',
    'M7 11V7a5 5 0 0 1 10 0v4',
  ],
  sheet: [box3to21, 'M3 9h18', 'M3 15h18', 'M12 9v12'],
  x: ['M18 6L6 18', 'M6 6l12 12'],
} as const satisfies Record<string, readonly string[]>

export type TicketIconName = keyof typeof TICKET_ICON_PATHS
