// A mentor's details, weekly times and application, as registering asks for
// them (apps.users.mentor_registration): shared by the user panel's mentor
// parts and Add user's mentor form.
import type { Directive } from 'vue'
import type { AppSelectOption } from '@/components/AppSelect.vue'

export const MENTOR_BACKGROUNDS: AppSelectOption[] = [
  { value: 'undergraduate', label: 'University Student - Undergraduate' },
  { value: 'postgraduate', label: 'University Student - Postgraduate' },
  { value: 'hdr', label: 'University Student - HDR' },
  { value: 'academic', label: 'Academic / research staff' },
  { value: 'industry', label: 'Industry' }
]
export const STUDY_YEAR_OPTIONS: AppSelectOption[] = [
  { value: '1', label: 'Year 1' },
  { value: '2', label: 'Year 2' },
  { value: '3', label: 'Year 3' },
  { value: '4', label: 'Year 4' },
  { value: '5+', label: 'Year 5 or later' }
]
/** University students give their year of study. */
export const isStudyingBackground = (background: AppSelectOption['value'] | undefined) =>
  background === 'undergraduate' || background === 'postgraduate'

// Hours a week they can give, as registering asks: 1 to 40.
export const MAX_WEEKLY_HOURS = 40

export const capacityLabel = (count: number | null | undefined) =>
  count == null ? '—' : `${count} ${count === 1 ? 'group' : 'groups'}`

// A weekly time they're free (Monday is 0), each end as its hour and its
// minutes, put back together as "HH:MM" to save.
export interface MentorSlot {
  weekday: AppSelectOption['value']
  startHour: AppSelectOption['value']
  startMinute: AppSelectOption['value']
  endHour: AppSelectOption['value']
  endMinute: AppSelectOption['value']
}
export const blankSlot = (): MentorSlot => ({
  weekday: null,
  startHour: null,
  startMinute: null,
  endHour: null,
  endMinute: null
})
export const splitSlot = (slot: { weekday: number; start: string; end: string }): MentorSlot => ({
  weekday: slot.weekday,
  startHour: slot.start.slice(0, 2),
  startMinute: slot.start.slice(3, 5),
  endHour: slot.end.slice(0, 2),
  endMinute: slot.end.slice(3, 5)
})

const twoDigits = (count: number) => String(count).padStart(2, '0')
export const HOUR_OPTIONS: AppSelectOption[] = Array.from({ length: 24 }, (_, hour) => ({
  value: twoDigits(hour),
  label: twoDigits(hour)
}))
// 00 to 55 in 5-minute steps; minutes saved between them stay a choice.
const FIVE_MINUTES: AppSelectOption[] = Array.from({ length: 12 }, (_, step) => ({
  value: twoDigits(step * 5),
  label: twoDigits(step * 5)
}))
export const minuteOptions = (current: AppSelectOption['value']): AppSelectOption[] =>
  typeof current === 'string' && current && !FIVE_MINUTES.some((option) => option.value === current)
    ? [...FIVE_MINUTES, { value: current, label: current }].sort((a, b) => a.label.localeCompare(b.label))
    : FIVE_MINUTES

// An hour picked first takes :00 until its minutes are picked.
export const pickHour = (slot: MentorSlot, end: 'start' | 'end', hour: AppSelectOption['value']) => {
  if (end === 'start') {
    slot.startHour = hour
    slot.startMinute ??= '00'
  } else {
    slot.endHour = hour
    slot.endMinute ??= '00'
  }
}
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
    const parts = [slot.weekday, slot.startHour, slot.startMinute, slot.endHour, slot.endMinute]
    if (parts.every((part) => part === null)) continue
    if (parts.some((part) => part === null)) return 'Give each weekly time a day and both times.'
    const start = `${slot.startHour}:${slot.startMinute}`
    const end = `${slot.endHour}:${slot.endMinute}`
    if (end <= start) return 'Each weekly time must end after it starts.'
    availability.push({ weekday: slot.weekday, start, end })
  }
  return availability
}

// The three questions registering asks, 150 words each at most.
export const MAX_ANSWER_WORDS = 150
export const APPLICATION_QUESTIONS = [
  { key: 'mentorRelevantBackground', field: 'mentorRelevantBackground', label: 'Relevant background' },
  { key: 'mentorReason', field: 'mentorReason', label: 'Why would you like to mentor?' },
  { key: 'mentorMentoringApproach', field: 'mentorMentoringApproach', label: 'How would you mentor BIOTech groups?' }
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
