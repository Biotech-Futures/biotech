import { afterEach, describe, expect, it, vi } from 'vitest'

import { withConsentSignatures } from '@/utils/supervisedStudents'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('consent form signatures', () => {
  it('are fetched for just the rows opened, and added to them', async () => {
    const send = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify({ signatures: { '7': 'data:image/png;base64,AAAA', '9': null } })),
    )
    vi.stubGlobal('fetch', send)

    const rows = await withConsentSignatures([
      { id: 7, student: 'Ada' },
      { id: 9, student: 'Alan' },
      { id: 7, student: 'Ada again' },
    ])

    expect(send).toHaveBeenCalledTimes(1)
    expect(String(send.mock.calls[0]![0])).toContain(
      '/api/v1/users/supervised-students/signatures/?ids=7%2C9',
    )
    expect(rows.map((row) => row.signature)).toEqual(['data:image/png;base64,AAAA', '', 'data:image/png;base64,AAAA'])
    expect(rows[1]!.student).toBe('Alan')
  })

  it('asks for nothing when there are no rows', async () => {
    const send = vi.fn<typeof fetch>()
    vi.stubGlobal('fetch', send)
    expect(await withConsentSignatures([])).toEqual([])
    expect(send).not.toHaveBeenCalled()
  })
})
