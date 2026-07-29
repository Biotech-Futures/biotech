/**
 * Read-receipt tick semantics for chat messages.
 *
 * Extracted from GroupDetailPage so the states are unit-testable: a mentor
 * once saw "Receipt details unavailable" on a message nobody had opened,
 * and nothing here was covered.
 *
 * ``recipientCount`` is the server-supplied denominator (``recipient_count``
 * on the messages list response) — active members minus the caller, minus
 * supervisors and login-blocked accounts.
 */

export type ReceiptState = 'delivered' | 'partial' | 'read'

export interface ReceiptMessage {
  readCount?: number
  deliveredCount?: number
}

/**
 * single grey  — delivered, nobody has read yet
 * double grey  — some but not all recipients have read
 * double blue  — every recipient has read
 */
export function getReceiptState(
  message: ReceiptMessage | null | undefined,
  recipientCount: number,
): ReceiptState {
  if (!message) return 'delivered'
  const reads = Number(message.readCount) || 0
  const recipients = Number(recipientCount) || 0
  if (recipients > 0 && reads >= recipients) return 'read'
  if (reads > 0) return 'partial'
  return 'delivered'
}

export function getReceiptAriaLabel(
  message: ReceiptMessage | null | undefined,
  recipientCount: number,
): string {
  const state = getReceiptState(message, recipientCount)
  const recipients = Number(recipientCount) || 0
  // The count is server-scoped to the same recipients as the denominator, but
  // clamp anyway so a lagging payload can't announce "Read by 5 of 4".
  const reads = Math.min(Number(message?.readCount) || 0, recipients || Infinity)
  if (state === 'read') return `Read by everyone (${reads})`
  // Denominator unknown (roster not loaded): state a bare count rather than
  // "Read by 2 of 2", which would contradict the grey partial tick.
  if (state === 'partial') return recipients ? `Read by ${reads} of ${recipients}` : `Read by ${reads}`
  const delivered = Number(message?.deliveredCount) || 0
  return delivered > 0 ? `Delivered to ${delivered}` : 'Delivered'
}
