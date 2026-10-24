// The year's other dates, for keeping a Management date in order, as the
// server does (apps.management.services.date_order): registration opens
// before the challenge starts, and submissions close after both the
// challenge start and registration's close. Each picker greys out what it
// can't be; the server refuses anything else, saying why.
import { computed, ref } from 'vue'

import { toSydneyDateTimeInput } from '@/utils/date'
import { fetchChallengeStart, fetchRegistrationOpen, fetchSubmissionDeadline } from '@/utils/managementAPI'

/** The minute after (1) or before (-1) an instant, in Sydney's time as
 *  Management's dates are: a picker's earliest or latest for "later than"
 *  or "earlier than" it. */
export const minuteBeside = (value: string | null | undefined, side: 1 | -1): string =>
  value ? toSydneyDateTimeInput(new Date(Date.parse(value) + side * 60_000).toISOString()) : ''

// Read on its own: one that can't be read just leaves its limit off.
const quietly = async (read: () => Promise<void>) => {
  try {
    await read()
  } catch {
    // No limit from it.
  }
}

export function useDateOrder() {
  const registrationOpens = ref<string | null>(null)
  const registrationCloses = ref<string | null>(null)
  const challengeStart = ref<string | null>(null)
  const deadline = ref<string | null>(null)

  // Registration's dates are this calendar year's, so a deadline counts
  // against them only when it's this year's too.
  const deadlineThisYear = computed(() =>
    deadline.value && new Date(deadline.value).getUTCFullYear() === new Date().getUTCFullYear() ? deadline.value : null
  )

  // The deadline only where it isn't the page's own (Submission Deadline reads it itself).
  const load = ({ withDeadline = true } = {}) =>
    Promise.all([
      quietly(async () => {
        const registration = await fetchRegistrationOpen()
        registrationOpens.value = registration.opens_at
        registrationCloses.value = registration.closes_at
      }),
      quietly(async () => {
        challengeStart.value = (await fetchChallengeStart()).starts_at
      }),
      withDeadline &&
        quietly(async () => {
          deadline.value = (await fetchSubmissionDeadline()).deadline?.closes_at ?? null
        })
    ])

  return { registrationOpens, registrationCloses, challengeStart, deadline, deadlineThisYear, load }
}
