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

export interface CursorMessage {
  id?: number | string
  isOwn?: boolean
  senderId?: number
  readBy?: number[]
  deliveredTo?: number[]
  readCount?: number
  deliveredCount?: number
}

/**
 * Apply one `message.read_updated` / `message.delivered_updated` cursor frame
 * to a single message, returning the updated message (or the original when the
 * frame doesn't apply).
 *
 * `recipientIds` is the same set the server filters `read_by_ids` against.
 * Adding a reader outside it — a supervisor or an admin opening the board —
 * is what pushed the ticks to "read by everyone" while students who had never
 * received the message were still listed as pending.
 */
export function applyCursorToMessage(
  message: CursorMessage,
  options: {
    userId: number
    upToId: number
    field: 'read' | 'delivered'
    recipientIds: ReadonlySet<number> | number[]
    currentUserId: number
  },
): CursorMessage {
  const { userId, upToId, field, currentUserId } = options
  const recipients =
    options.recipientIds instanceof Set ? options.recipientIds : new Set(options.recipientIds)

  const messageId = Number(message?.id)
  if (!Number.isFinite(messageId) || messageId > upToId) return message

  // A sender never has a status row for their own message. `senderId` is 0 on
  // list-loaded messages (the public payload omits it by design), so `isOwn` is
  // the only guard that holds for my own history.
  if (Number(message.senderId || 0) === userId) return message
  if (message.isOwn && userId === currentUserId) return message

  // Only recipients count, matching the server-side filter exactly.
  if (!recipients.has(userId)) return message

  const deliveredTo = Array.from(new Set([...(message.deliveredTo || []), userId]))
  if (field === 'delivered') {
    return { ...message, deliveredTo, deliveredCount: deliveredTo.length }
  }

  // A read implies delivery — the backend stamps delivered_at alongside read_at.
  const readBy = Array.from(new Set([...(message.readBy || []), userId]))
  return { ...message, readBy, deliveredTo, readCount: readBy.length, deliveredCount: deliveredTo.length }
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
