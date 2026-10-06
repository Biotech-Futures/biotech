import type { AdminMentorAvailability, AdminMentorDetail } from '@/utils/adminAPI'

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

/** Whole days since a date, or null when the value is missing/invalid. */
export const daysSince = (dateStr: string | null): number | null => {
  if (!dateStr) return null
  const diff = Date.now() - new Date(dateStr).getTime()
  return Math.floor(diff / (1000 * 60 * 60 * 24))
}

export const isEffectivelyInactive = (mentor: AdminMentorDetail, inactiveDaysValue: number): boolean => {
  if (!mentor.isActive) return true
  const days = daysSince(mentor.lastMessageAt)
  if (days === null) return true // never sent a message
  return days >= inactiveDaysValue
}

export const lastMessageDays = (dateStr: string): number => daysSince(dateStr) ?? 0

export const relativeDays = (dateStr: string): string => {
  const days = daysSince(dateStr) ?? 0
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  return `${days} days ago`
}

export const formatLogin = (dateStr: string): string => new Date(dateStr).toLocaleString()

export const loginDate = (dateStr: string): string => new Date(dateStr).toLocaleDateString()

export const sortedAvailability = (availability: AdminMentorAvailability[]) =>
  [...availability].sort((a, b) => a.weekday - b.weekday)