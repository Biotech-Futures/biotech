export function getTimelineStatusClass(status: string): string {
  if (status === 'completed') return 'is-completed'
  if (status === 'current') return 'is-current'
  return 'is-upcoming'
}

export function getAccentClass(accent: string): string {
  return accent ? `accent-${accent}` : 'accent-blue'
}