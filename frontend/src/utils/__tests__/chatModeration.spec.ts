import { describe, expect, it } from 'vitest'

import { hideModerationDeletionFromViewer } from '@/utils/chatModeration'

describe('hideModerationDeletionFromViewer', () => {
  const deletedSuppressedMessage = {
    id: 41,
    sender_user: 7,
    is_deleted: true,
    is_suppressed: true,
  }

  it('keeps the deletion tombstone for the original sender', () => {
    expect(hideModerationDeletionFromViewer(deletedSuppressedMessage, {}, 7)).toBe(false)
  })

  it('hides the deletion tombstone from every other group member', () => {
    expect(hideModerationDeletionFromViewer(deletedSuppressedMessage, {}, 9)).toBe(true)
  })

  it('does not change the existing behaviour for ordinary message deletion', () => {
    expect(
      hideModerationDeletionFromViewer(
        { ...deletedSuppressedMessage, is_suppressed: false },
        {},
        9,
      ),
    ).toBe(false)
  })
})
