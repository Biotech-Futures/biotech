import { describe, expect, it } from 'vitest'

import { actorOptions } from '../auditRows'

/**
 * Who the audit page's Who filter offers. The page-level spec shows the
 * options on screen; this pins how the three sources are merged.
 */
const row = (id: number, actor: { id: number; name: string } | null) => ({
  id,
  ticketId: 42,
  action: 'reopen',
  actor,
  beforeState: null,
  afterState: null,
  createdAt: '2026-09-01T09:00:00Z'
})

describe('actorOptions', () => {
  it('merges the roster, the people on the rows and the current pick, once each, by name', () => {
    const options = actorOptions(
      [
        { id: 4, name: 'Sam Reid', assignable: true },
        { id: 9, name: 'Ana Ortiz', assignable: false }
      ],
      [row(1, { id: 7, name: 'Grace Okafor' }), row(2, { id: 4, name: 'Sam Reid' }), row(3, null)],
      { id: 12, name: 'Zoe Park' }
    )

    expect(options).toEqual([
      { id: 9, name: 'Ana Ortiz' },
      { id: 7, name: 'Grace Okafor' },
      { id: 4, name: 'Sam Reid' },
      { id: 12, name: 'Zoe Park' }
    ])
  })

  it('offers a revoked or switched-off agent too, since they still own tickets', () => {
    // The roster endpoint lists everybody who could own a ticket, and
    // `assignable` is about handing them new work. Who did something on the
    // log is a different question, so nobody is dropped for it.
    expect(actorOptions([{ id: 9, name: 'Ana Ortiz', assignable: false }], [], null)).toEqual([
      { id: 9, name: 'Ana Ortiz' }
    ])
  })

  it('keeps two people who share a display name as two options', () => {
    // One per person, not one per name. Folding them together would leave one
    // of the two unselectable, and filtering on the survivor would answer for
    // somebody else's rows.
    expect(
      actorOptions(
        [
          { id: 4, name: 'Sam Reid', assignable: true },
          { id: 5, name: 'Sam Reid', assignable: true }
        ],
        [],
        null
      )
    ).toEqual([
      { id: 4, name: 'Sam Reid' },
      { id: 5, name: 'Sam Reid' }
    ])
  })

  it('names a person the way the newest source does', () => {
    // A row names the actor as the server has them now, which beats a roster
    // entry fetched earlier; the pick is what the reader chose from.
    expect(
      actorOptions(
        [{ id: 4, name: 'Sam Reid', assignable: true }],
        [row(1, { id: 4, name: 'Samuel Reid' })],
        null
      )
    ).toEqual([{ id: 4, name: 'Samuel Reid' }])
  })
})
