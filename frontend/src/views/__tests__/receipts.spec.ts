import { describe, expect, it } from 'vitest'
import { applyCursorToMessage, getReceiptAriaLabel, getReceiptState } from '@/utils/receipts'
import type { CursorMessage } from '@/utils/receipts'

// A group of 4 students + 1 mentor + 1 supervisor: the mentor's denominator is
// the 4 students (supervisors and login-blocked accounts are excluded server-side).
const RECIPIENTS = 4

describe('getReceiptState', () => {
  it('is delivered when nobody has read yet', () => {
    expect(getReceiptState({ readCount: 0, deliveredCount: 0 }, RECIPIENTS)).toBe('delivered')
  })

  it('is partial when some but not all recipients have read', () => {
    expect(getReceiptState({ readCount: 1 }, RECIPIENTS)).toBe('partial')
    expect(getReceiptState({ readCount: 3 }, RECIPIENTS)).toBe('partial')
  })

  it('is read when every recipient has read', () => {
    expect(getReceiptState({ readCount: 4 }, RECIPIENTS)).toBe('read')
  })

  it('stays read when a supervisor read pushes the count past the denominator', () => {
    expect(getReceiptState({ readCount: 5 }, RECIPIENTS)).toBe('read')
  })

  it('never claims all-read while the denominator is unknown', () => {
    // recipient_count arrives with the messages list; before it lands, a read
    // must not be mistaken for "everyone".
    expect(getReceiptState({ readCount: 2 }, 0)).toBe('partial')
  })

  it('falls back to delivered for a missing message', () => {
    expect(getReceiptState(null, RECIPIENTS)).toBe('delivered')
    expect(getReceiptState(undefined, RECIPIENTS)).toBe('delivered')
  })
})

describe('getReceiptAriaLabel', () => {
  it('reports plain delivered when nothing has landed', () => {
    expect(getReceiptAriaLabel({ readCount: 0, deliveredCount: 0 }, RECIPIENTS)).toBe('Delivered')
  })

  it('reports the delivered count before any read', () => {
    expect(getReceiptAriaLabel({ readCount: 0, deliveredCount: 2 }, RECIPIENTS)).toBe(
      'Delivered to 2',
    )
  })

  it('reports progress against the denominator', () => {
    expect(getReceiptAriaLabel({ readCount: 1 }, RECIPIENTS)).toBe('Read by 1 of 4')
  })

  it('clamps a count that exceeds the denominator', () => {
    // Defensive: a lagging payload must never say "Read by 5 of 4".
    expect(getReceiptAriaLabel({ readCount: 5 }, RECIPIENTS)).toBe('Read by everyone (4)')
  })

  it('states a bare count when the denominator is unknown', () => {
    // Must not read "Read by 2 of 2" while the tick is still grey/partial.
    expect(getReceiptAriaLabel({ readCount: 2 }, 0)).toBe('Read by 2')
  })
})

// Group: mentor 1 (me), students 11/12/13, supervisor 14, non-member admin 99.
// The server filters read_by_ids to the students; the client must filter the
// live cursor frames to the same set or the two disagree.
const RECIPIENT_IDS = [1, 11, 12, 13]
const ME = 1

const cursor = (message: CursorMessage, userId: number, field: 'read' | 'delivered' = 'read') =>
  applyCursorToMessage(message, {
    userId,
    upToId: 100,
    field,
    recipientIds: RECIPIENT_IDS,
    currentUserId: ME,
  })

describe('applyCursorToMessage', () => {
  const myMessage = { id: 50, isOwn: true, readBy: [], deliveredTo: [] }

  it('counts a student read', () => {
    expect(cursor(myMessage, 11).readCount).toBe(1)
  })

  it('ignores a supervisor read', () => {
    // The regression this guards: a supervisor opening the board pushed the
    // ticks to "read by everyone" while students still sat in pending.
    const after = cursor({ ...myMessage, readBy: [11, 12, 13] }, 14)
    expect(after.readCount ?? 3).toBe(3)
    expect(after.readBy).toEqual([11, 12, 13])
  })

  it('ignores a non-member admin read', () => {
    expect(cursor({ ...myMessage, readBy: [11] }, 99).readBy).toEqual([11])
  })

  it('never counts me as a reader of my own message', () => {
    // senderId is absent from the public payload, so isOwn is the only guard.
    expect(cursor(myMessage, ME).readBy).toEqual([])
  })

  it('skips a peer message whose sender is the reader', () => {
    const peer = { id: 50, isOwn: false, senderId: 12, readBy: [] }
    expect(cursor(peer, 12).readBy).toEqual([])
  })

  it('does not double-count a reader already in the set', () => {
    const after = cursor({ ...myMessage, readBy: [11], readCount: 1 }, 11)
    expect(after.readCount).toBe(1)
  })

  it('leaves messages newer than the cursor alone', () => {
    const newer = applyCursorToMessage({ id: 200, isOwn: true, readBy: [] }, {
      userId: 11, upToId: 100, field: 'read', recipientIds: RECIPIENT_IDS, currentUserId: ME,
    })
    expect(newer.readBy).toEqual([])
  })

  it('treats a read as implying delivery', () => {
    const after = cursor(myMessage, 11)
    expect(after.deliveredTo).toEqual([11])
    expect(after.deliveredCount).toBe(1)
  })

  it('a delivered cursor does not mark anything read', () => {
    const after = cursor(myMessage, 11, 'delivered')
    expect(after.deliveredCount).toBe(1)
    expect(after.readBy).toEqual([])
  })

  it('cannot reach all-read on supervisor traffic alone', () => {
    // End to end: 2 of 3 students read, then the supervisor and an admin open
    // the board. The tick must stay partial.
    let msg: CursorMessage = { id: 50, isOwn: true, readBy: [], deliveredTo: [] }
    for (const uid of [11, 12, 14, 99]) msg = cursor(msg, uid)
    const recipientsForMe = RECIPIENT_IDS.length - 1
    expect(getReceiptState(msg, recipientsForMe)).toBe('partial')
    expect(getReceiptAriaLabel(msg, recipientsForMe)).toBe('Read by 2 of 3')
  })
})
