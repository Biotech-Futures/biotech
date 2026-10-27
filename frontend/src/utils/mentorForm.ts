// A mentor's details, weekly times and application, as registering asks for
// them (apps.users.mentor_registration): shared by the user panel's mentor
// parts and Add user's mentor form.
import type { Directive } from 'vue'
import type { AppSelectOption } from '@/components/AppSelect.vue'
import { MENTOR_BACKGROUND_OPTIONS } from '@/utils/userOptions'

// The five categories live in one place (AM2). Re-exported in the shape the
// pickers want, so this module and userOptions can never name them
// differently.
export const MENTOR_BACKGROUNDS: AppSelectOption[] = MENTOR_BACKGROUND_OPTIONS.map(
  ({ value, label }) => ({ value, label })
)
export const STUDY_YEAR_OPTIONS: AppSelectOption[] = [
  { value: '1', label: 'Year 1' },
  { value: '2', label: 'Year 2' },
  { value: '3', label: 'Year 3' },
  { value: '4', label: 'Year 4' },
  { value: '5+', label: 'Year 5 or later' }
]
/** A background typed before there was a list, read as the list's choice
 * where it's clear ("Undergraduate Student" is undergraduate); anything else
 * stays as written. */
export const mentorBackgroundCode = (background: AppSelectOption['value'] | undefined): AppSelectOption['value'] => {
  if (typeof background !== 'string' || !background) return background ?? null
  if (MENTOR_BACKGROUNDS.some((option) => option.value === background)) return background
  const text = background.toLowerCase()
  if (text.includes('industry')) return 'industry'
  if (text.includes('undergrad')) return 'undergraduate'
  if (text.includes('postgrad')) return 'postgraduate'
  if (text.includes('hdr') || text.includes('phd')) return 'hdr'
  if (text.includes('academic') || text.includes('research staff')) return 'academic'
  return background
}

/** University students give their year of study. */
export const isStudyingBackground = (background: AppSelectOption['value'] | undefined) =>
  background === 'undergraduate' || background === 'postgraduate'

export const capacityLabel = (count: number | null | undefined) =>
  count == null ? '—' : `${count} ${count === 1 ? 'group' : 'groups'}`

// A weekly time they're free (Monday is 0), from and to as "HH:MM", each
// picked with a time picker (AppTimePicker) in 5-minute steps; empty until
// picked.
export interface MentorSlot {
  weekday: AppSelectOption['value']
  start: string
  end: string
}
export const blankSlot = (): MentorSlot => ({ weekday: null, start: '', end: '' })
/** A saved weekly time as the form edits it. */
export const draftSlot = (slot: { weekday: number; start: string; end: string }): MentorSlot => ({
  weekday: slot.weekday,
  start: slot.start.slice(0, 5),
  end: slot.end.slice(0, 5)
})
export const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
export const WEEKDAY_OPTIONS: AppSelectOption[] = WEEKDAYS.map((day, index) => ({ value: index, label: day }))
/** As many weekly times as a mentor can give. */
export const MAX_SLOTS = 21

/** The weekly times to save, or what's wrong with them: each given in full
 * and ending after it starts; a row left empty is dropped. */
export const availabilityTimes = (
  slots: MentorSlot[]
): { weekday: AppSelectOption['value']; start: string; end: string }[] | string => {
  const availability = []
  for (const slot of slots) {
    const parts = [slot.weekday, slot.start || null, slot.end || null]
    if (parts.every((part) => part === null)) continue
    if (parts.some((part) => part === null)) return 'Give each weekly time a day and both times.'
    if (slot.end <= slot.start) return 'Each weekly time must end after it starts.'
    availability.push({ weekday: slot.weekday, start: slot.start, end: slot.end })
  }
  return availability
}

// The question registering asks, 150 words at most.
export const MAX_ANSWER_WORDS = 150
export const APPLICATION_QUESTIONS = [
  { key: 'mentorReason', field: 'mentorReason', label: 'Why would you like to mentor?' }
] as const

export const wordCount = (text: string) => (text.trim() ? text.trim().split(/\s+/).length : 0)

// An answer's box grows with what's written, from its 9 rows, rather than
// scrolling.
const growToFit = (box: HTMLTextAreaElement) => {
  box.style.height = ''
  if (box.scrollHeight > box.clientHeight) {
    box.style.height = `${box.scrollHeight + box.offsetHeight - box.clientHeight}px`
  }
}
export const vAutoGrow: Directive<HTMLTextAreaElement> = { mounted: growToFit, updated: growToFit }
