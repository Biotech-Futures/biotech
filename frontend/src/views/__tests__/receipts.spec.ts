import { describe, expect, it } from 'vitest'
import { getReceiptAriaLabel, getReceiptState } from '@/utils/receipts'

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
