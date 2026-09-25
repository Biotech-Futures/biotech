/** Formatting helpers for the submission portal. */

/** Splits on whitespace, matching the server's word count. */
export function countWords(text: string | null | undefined): number {
  return (text || '').split(/\s+/).filter(Boolean).length
}

export function formatFileSize(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return 'unknown size'
  if (bytes >= 1024 * 1024) {
    const mb = bytes / (1024 * 1024)
    return `${Number.isInteger(mb) ? mb : mb.toFixed(1)} MB`
  }
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`
  return `${bytes} bytes`
}

export function describeTimeRemaining(
  closesAt: string | null | undefined,
  now: number = Date.now()
): string {
  if (!closesAt) return ''
  const msLeft = new Date(closesAt).getTime() - now
  if (Number.isNaN(msLeft)) return ''
  // Empty once passed, so the unannounced grace period is never shown.
  if (msLeft <= 0) return ''

  const minutes = Math.floor(msLeft / 60000)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (days >= 1) return `${days} day${days === 1 ? '' : 's'} left`
  if (hours >= 1) return `${hours} hour${hours === 1 ? '' : 's'} left`
  return `${minutes} minute${minutes === 1 ? '' : 's'} left`
}

export function isDeadlineNear(
  closesAt: string | null | undefined,
  now: number = Date.now()
): boolean {
  if (!closesAt) return false
  const msLeft = new Date(closesAt).getTime() - now
  return !Number.isNaN(msLeft) && msLeft > 0 && msLeft < 24 * 60 * 60 * 1000
}

export function describeQuestionStep(
  answers: Record<string, string>,
  questionKeys: string[]
): string {
  if (!questionKeys.length) return 'Required'
  const answered = questionKeys.filter((key) => (answers[key] || '').trim()).length
  return `Required · ${answered} of ${questionKeys.length}`
}
