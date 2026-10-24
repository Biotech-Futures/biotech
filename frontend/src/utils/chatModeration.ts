type MessageLike = Record<string, unknown> | null | undefined

function numericId(...values: unknown[]): number {
  for (const value of values) {
    const id = Number(value || 0)
    if (Number.isFinite(id) && id > 0) return id
  }
  return 0
}

/**
 * A deleted message that is still marked as suppressed was removed through
 * the screening review flow. The reviewer may be an administrator or a
 * support agent, so the review state—not the reviewer's role—determines the
 * sender-facing status and wording.
 */
export function isModerationRemoval(message: MessageLike): boolean {
  const isDeleted = Boolean(
    message?.is_deleted || message?.isDeleted || message?.deleted_at || message?.deletedAt,
  )
  const isSuppressed = Boolean(message?.is_suppressed || message?.isSuppressed)
  return isDeleted && isSuppressed
}

/**
 * A screening rejection is still broadcast to the whole group so every open
 * board can remove its stale copy. Only the original sender gets the deletion
 * tombstone; peers must not learn that a hidden message was removed.
 */
export function hideModerationDeletionFromViewer(
  message: MessageLike,
  payload: MessageLike,
  viewerId: unknown,
): boolean {
  const wasSuppressed = Boolean(
    message?.is_suppressed ||
      message?.isSuppressed ||
      payload?.is_suppressed ||
      payload?.isSuppressed,
  )
  if (!wasSuppressed) return false

  const senderId = numericId(
    message?.sender_user,
    message?.sender_id,
    message?.sender_user_id,
    message?.senderId,
    payload?.sender_user_id,
    payload?.sender_user,
  )
  return senderId === 0 || senderId !== numericId(viewerId)
}
