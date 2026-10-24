import { describe, expect, it } from 'vitest'

import {
  hideModerationDeletionFromViewer,
  isModerationRemoval,
} from '@/utils/chatModeration'

describe('isModerationRemoval', () => {
  it('recognises a screened message deleted by a support agent', () => {
    expect(
      isModerationRemoval({
        isDeleted: true,
        isSuppressed: true,
        deletedByIsAdmin: false,
        deletedByName: 'Sana Reid',
      }),
    ).toBe(true)
  })

  it('does not treat a message still awaiting review as removed', () => {
    expect(isModerationRemoval({ isDeleted: false, isSuppressed: true })).toBe(false)
  })

  it('does not change ordinary message deletion', () => {
    expect(isModerationRemoval({ is_deleted: true, is_suppressed: false })).toBe(false)
  })
})

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
