/**
 * Pure formatting and derivation used by the submission portal.
 *
 * Kept out of the page component so it can be tested directly. Three of these
 * have to agree with rules enforced on the server — a counter that disagrees
 * with the server tells a student their answer is fine and then has the save
 * rejected, which is worse than having no counter at all.
 */

/**
 * Words in an answer.
 *
 * Must match the server and the client's Qualtrics regex, both of which
 * split on whitespace. Anything cleverer would disagree with what is saved.
 */
export function countWords(text: string | null | undefined): number {
  return (text || '').split(/\s+/).filter(Boolean).length
}

/** Human-readable file size. Whole megabytes lose the decimal, so a stated
 *  limit reads "5 MB" rather than "5.0 MB". */
export function formatFileSize(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return 'unknown size'
  if (bytes >= 1024 * 1024) {
    const mb = bytes / (1024 * 1024)
    return `${Number.isInteger(mb) ? mb : mb.toFixed(1)} MB`
  }
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`
  return `${bytes} bytes`
}

/**
 * How long until a deadline, in the largest useful unit.
 *
 * Days, then hours, then minutes: three weeks out nobody needs the minute
 * count, and ten minutes out they very much do.
 */
export function describeTimeRemaining(
  closesAt: string | null | undefined,
  now: number = Date.now()
): string {
  if (!closesAt) return ''
  const msLeft = new Date(closesAt).getTime() - now
  if (Number.isNaN(msLeft)) return ''
  if (msLeft <= 0) return 'Closing now'

  const minutes = Math.floor(msLeft / 60000)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (days >= 1) return `${days} day${days === 1 ? '' : 's'} left`
  if (hours >= 1) return `${hours} hour${hours === 1 ? '' : 's'} left`
  return `${minutes} minute${minutes === 1 ? '' : 's'} left`
}

/** Inside the final day, when the time left is what a student needs to know. */
export function isDeadlineNear(
  closesAt: string | null | undefined,
  now: number = Date.now()
): boolean {
  if (!closesAt) return false
  const msLeft = new Date(closesAt).getTime() - now
  return !Number.isNaN(msLeft) && msLeft > 0 && msLeft < 24 * 60 * 60 * 1000
}

/** Short factual note for a wizard step: what it needs, and what is filled in. */
export function describeQuestionStep(
  answers: Record<string, string>,
  questionKeys: string[]
): string {
  if (!questionKeys.length) return 'Required'
  const answered = questionKeys.filter((key) => (answers[key] || '').trim()).length
  return `Required · ${answered} of ${questionKeys.length}`
}
