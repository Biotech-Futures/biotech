import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type DOMWrapper, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { createRouter, createWebHashHistory, type Router } from 'vue-router'

import routes from '@/router/routes'
import SupportAgentsPage from '@/views/admin/SupportAgentsPage.vue'
import { useAuthStore } from '@/stores/auth'
import { apiErrorFromResponse } from '@/utils/apiError'
import { fetchAdminUsers } from '@/utils/adminAPI'
import { fetchSupportRoster, grantSupport, revokeSupport } from '@/utils/ticketAgentAPI'
import { pureAgent, ticketAdmin } from '@/__tests__/supportAccountFixtures'

// The network calls are replaced at the module boundary; everything else in
// both modules is real, serverMessage included, so what the page makes of a
// refusal is what it would make of the real one.
vi.mock('@/utils/ticketAgentAPI', async () => ({
  ...(await vi.importActual<typeof import('@/utils/ticketAgentAPI')>('@/utils/ticketAgentAPI')),
  fetchSupportRoster: vi.fn(),
  grantSupport: vi.fn(),
  revokeSupport: vi.fn()
}))

vi.mock('@/utils/adminAPI', async () => ({
  ...(await vi.importActual<typeof import('@/utils/adminAPI')>('@/utils/adminAPI')),
  fetchAdminUsers: vi.fn()
}))

const AGENT = {
  id: 4,
  name: 'Sam Reid',
  email: 'sam@example.com',
  openTickets: 3,
  accountStatus: 'active'
}

const LIVE = { id: 8, firstName: 'Rae', lastName: 'Wills', email: 'rae@example.com', isActive: true }
const DEAD = { id: 9, firstName: 'Ola', lastName: 'Nunes', email: 'ola@example.com', isActive: false }

const SEARCH_LABEL = 'Search for a person to grant support access'

function userPage(items: unknown[]) {
  return { items, total: items.length, page: 1, limit: 10, hasMore: false } as never
}

/** A 400 the way these endpoints send one, through the real error reader.
 *
 *  The support-scope refusals answer {msg, data} directly rather than raising
 *  through config/exception_handler.py, so the sentence is in msg and not in
 *  the {error, code} envelope the ticket write path uses. */
function refusal(msg: string, status = 400) {
  return apiErrorFromResponse(
    new Response(JSON.stringify({ msg, data: null }), {
      status,
      headers: { 'Content-Type': 'application/json' }
    })
  )
}

let wrapper: VueWrapper | null = null
let router: Router

async function mountPage(user: object = ticketAdmin, { stubTeleport = true } = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().loginWithUser(user as never)
  // The real route table, so the create link is checked against the People
  // page's actual address rather than a stub's idea of it.
  router = createRouter({ history: createWebHashHistory(), routes })
  await router.push('/admin/support-agents')
  await router.isReady()
  wrapper = mount(SupportAgentsPage, {
    attachTo: document.body,
    global: { plugins: [router, pinia], stubs: stubTeleport ? { Teleport: true } : {} }
  })
  await flushPromises()
  return wrapper
}

const page = () => wrapper!
const buttonNamed = (label: string) =>
  page()
    .findAll('button')
    .find((button) => button.text() === label || button.text().startsWith(`${label} `))

async function openRevoke() {
  const revoke = buttonNamed('Revoke')!
  ;(revoke.element as HTMLButtonElement).focus()
  await revoke.trigger('click')
  await flushPromises()
  return revoke
}

async function search(text: string) {
  await page().find(`input[aria-label="${SEARCH_LABEL}"]`).setValue(text)
  vi.advanceTimersByTime(300)
  await flushPromises()
}

/** Lets Vue re-render the pressed button as disabled, then does what a
 *  browser does and jsdom does not: a focused button that becomes disabled
 *  loses focus to the page body (the HTML "focus fixup" rule).
 *
 *  jsdom also ignores blur() on a disabled element, so the button is enabled
 *  for that one call and disabled again straight after. Vue compares against
 *  its own record of the attribute, not the DOM, so the next render is not
 *  affected. Both expects are there because a first version of this helper
 *  did nothing at all and every test built on it still passed. */
async function nextTickAndBlur() {
  await nextTick()
  const active = document.activeElement
  expect(active).toBeInstanceOf(HTMLButtonElement)
  expect((active as HTMLButtonElement).disabled).toBe(true)
  const button = active as HTMLButtonElement
  button.disabled = false
  button.blur()
  button.disabled = true
  expect(document.activeElement).toBe(document.body)
}

const candidateRow = (name: string) =>
  page()
    .findAll('li')
    .find((li) => li.text().includes(name)) as DOMWrapper<HTMLLIElement>

const rosterCell = (name: string) =>
  page()
    .findAll('td')
    .find((td) => td.text().includes(name)) as DOMWrapper<HTMLTableCellElement>

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(fetchSupportRoster).mockResolvedValue([AGENT])
  vi.mocked(fetchAdminUsers).mockResolvedValue(userPage([]))
  vi.mocked(grantSupport).mockResolvedValue(undefined)
  vi.mocked(revokeSupport).mockResolvedValue(undefined)
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  localStorage.clear()
  vi.useRealTimers()
})

describe('SupportAgentsPage: who may use it (RO-01)', () => {
  it('answers a support agent who reaches the URL instead of failing to load', async () => {
    // The route admits anyone the store calls an admin, and the store reads
    // the role name. A support agent who is not an admin can still type this
    // address; the server refuses them either way, and without this branch
    // they would sit in front of a table that never loads.
    await mountPage(pureAgent)

    expect(page().find('h1').text()).toBe('Support agents')
    expect(page().text()).toContain('Only administrators can change who works the support queue.')
    expect(page().find('table').exists()).toBe(false)
  })

  it('sends no request at all for somebody who is not the server’s admin', async () => {
    // The React page ran its queries before its own admin check and ate a 403
    // for every agent who opened it.
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    await mountPage(pureAgent)
    vi.advanceTimersByTime(1000)
    await flushPromises()

    expect(fetchSupportRoster).not.toHaveBeenCalled()
    expect(fetchAdminUsers).not.toHaveBeenCalled()
    expect(page().find(`input[aria-label="${SEARCH_LABEL}"]`).exists()).toBe(false)
  })

  it('goes by the server’s admin flag, not by a role name that says admin', async () => {
    // Role name "admin" with no AdminScope row behind it: the store's isAdmin
    // lets them through the route, and every roster endpoint would 403.
    await mountPage({ ...ticketAdmin, isAdmin: false })

    expect(page().text()).toContain('Only administrators can change who works the support queue.')
    expect(fetchSupportRoster).not.toHaveBeenCalled()
  })

  it('loads the roster once for an administrator', async () => {
    await mountPage(ticketAdmin)

    expect(fetchSupportRoster).toHaveBeenCalledTimes(1)
    expect(page().text()).not.toContain('Only administrators can change')
  })
})

describe('the roster table (RO-02, RO-11)', () => {
  it('shows how much work a person is carrying before you remove them', async () => {
    await mountPage()

    const row = page().findAll('tr').find((tr) => tr.text().includes('Sam Reid'))!
    expect(row.text()).toContain('sam@example.com')
    expect(row.findAll('td')[2].text()).toBe('3')
  })

  it('keeps the order the server sent rather than sorting the rows again', async () => {
    // The server orders on first name, last name, then email, because first
    // name alone shuffles rows between requests. A second sort here would
    // undo that.
    vi.mocked(fetchSupportRoster).mockResolvedValue([
      { ...AGENT, id: 1, name: 'Zed Young', email: 'zed@example.com' },
      { ...AGENT, id: 2, name: 'Amy Ball', email: 'amy@example.com' }
    ])
    await mountPage()

    const names = page()
      .findAll('tbody tr')
      .map((tr) => tr.findAll('td')[0].text())
    expect(names).toEqual(['Zed Young', 'Amy Ball'])
  })

  it('says so when nobody has been granted access yet', async () => {
    vi.mocked(fetchSupportRoster).mockResolvedValue([])
    await mountPage()

    expect(page().find('tbody').text()).toBe(
      'Nobody has been granted support access yet. Administrators can still work the queue.'
    )
  })

  it('says the roster could not be loaded instead of showing an empty table', async () => {
    vi.mocked(fetchSupportRoster).mockRejectedValue(new TypeError('Failed to fetch'))
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    await mountPage()

    expect(page().find('[role="alert"]').text()).toBe('The roster could not be loaded.')
    expect(page().find('table').exists()).toBe(false)
    expect(page().text()).not.toContain('Nobody has been granted support access yet.')
  })

  it('says administrators work the queue without being listed', async () => {
    await mountPage()

    expect(page().find('.support-agents__subtitle').text()).toBe(
      'Everyone here can open the support queue. Administrators can already work it without being listed.'
    )
  })
})

describe('reloading the roster (RO-02)', () => {
  // Roster rows for the two candidates, as the server would send them once
  // each has been granted.
  const OLA_ROW = { ...AGENT, id: 9, name: 'Ola Nunes', email: 'ola@example.com', openTickets: 0 }
  const RAE_ROW = { ...AGENT, id: 8, name: 'Rae Wills', email: 'rae@example.com', openTickets: 0 }
  const rosterNames = () =>
    page()
      .findAll('tbody tr')
      .map((tr) => tr.findAll('td')[0].text())

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    vi.mocked(fetchSupportRoster).mockResolvedValue([])
    vi.mocked(fetchAdminUsers).mockResolvedValue(userPage([LIVE, DEAD]))
  })

  it('paints the newest reload when two of them answer out of order', async () => {
    // Two grants in a row start two reloads. If the first one answers last,
    // its older list must not replace the newer one: Rae would vanish from
    // the table although the server has her.
    await mountPage()
    const reloads: Array<(rows: never) => void> = []
    vi.mocked(fetchSupportRoster).mockImplementation(
      () => new Promise((resolve) => reloads.push(resolve as (rows: never) => void))
    )

    await search('a')
    await candidateRow('ola@example.com').find('button').trigger('click')
    await flushPromises()
    await search('a')
    await candidateRow('rae@example.com').find('button').trigger('click')
    await flushPromises()
    expect(reloads).toHaveLength(2)

    // The newer answer first, then the late older one.
    reloads[1]([OLA_ROW, RAE_ROW] as never)
    await flushPromises()
    reloads[0]([OLA_ROW] as never)
    await flushPromises()

    expect(rosterNames()).toEqual(['Ola Nunes', 'Rae Wills'])
  })

  it('drops an earlier load error once a later reload succeeds', async () => {
    // The table is replaced by the error line while a load has failed. A
    // grant reloads it, and when that works the table has to come back.
    vi.mocked(fetchSupportRoster).mockRejectedValueOnce(new TypeError('Failed to fetch'))
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    await mountPage()
    expect(page().text()).toContain('The roster could not be loaded.')

    vi.mocked(fetchSupportRoster).mockResolvedValue([OLA_ROW])
    await search('ola')
    await candidateRow('ola@example.com').find('button').trigger('click')
    await flushPromises()

    expect(page().text()).not.toContain('The roster could not be loaded.')
    expect(rosterNames()).toEqual(['Ola Nunes'])
  })
})

describe('an agent whose account was switched off after they were added (RO-03)', () => {
  // Granting and revoking never touch the account, and switching an account
  // off never touches the roster. That is deliberate, and it leaves rows on
  // this table that nobody can sign into.

  it('says so beside the name', async () => {
    vi.mocked(fetchSupportRoster).mockResolvedValue([{ ...AGENT, accountStatus: 'deactivated' }])
    await mountPage()

    expect(rosterCell('Sam Reid').text()).toBe('Sam Reid Deactivated · cannot work the queue')
  })

  it('uses the account’s own word, because the two are acted on differently', async () => {
    vi.mocked(fetchSupportRoster).mockResolvedValue([{ ...AGENT, accountStatus: 'suspended' }])
    await mountPage()

    expect(rosterCell('Sam Reid').text()).toBe('Sam Reid Suspended · cannot work the queue')
  })

  it('leaves an agent who is working today unmarked', async () => {
    // Load-bearing. A mark rendered on every row satisfies the two above and
    // tells the reader nothing.
    await mountPage()

    expect(rosterCell('Sam Reid').text()).toBe('Sam Reid')
  })

  it('leaves an invited colleague unmarked, because they can sign in', async () => {
    // is_active is false for them as well. INACTIVE_LOGIN_STATUSES leaves
    // invited out and the grant endpoint accepts it, so a mark here would
    // contradict the server about an ordinary case.
    vi.mocked(fetchSupportRoster).mockResolvedValue([{ ...AGENT, accountStatus: 'invited' }])
    await mountPage()

    expect(rosterCell('Sam Reid').text()).toBe('Sam Reid')
  })
})

describe('searching for somebody to add (RO-04)', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    vi.mocked(fetchSupportRoster).mockResolvedValue([])
  })

  it('does not search for a blank term', async () => {
    // The React comment promised this and its query ran anyway, pulling a
    // page of the whole user list to fill a dropdown nobody opened.
    await mountPage()
    // A letter typed and then taken back before the pause runs out: the box
    // is blank again, and the search it had queued must not go out, nor one
    // for the blank term.
    await page().find(`input[aria-label="${SEARCH_LABEL}"]`).setValue('a')
    await search('   ')

    expect(fetchAdminUsers).not.toHaveBeenCalled()
    expect(page().find('ul').exists()).toBe(false)
  })

  it('asks for ten people matching the trimmed term', async () => {
    await mountPage()
    await search('  ola ')

    expect(fetchAdminUsers).toHaveBeenCalledTimes(1)
    expect(fetchAdminUsers).toHaveBeenCalledWith({ search: 'ola', limit: 10 })
  })

  it('says it is searching until the answer arrives, then that nobody matched', async () => {
    let answer: (value: never) => void = () => {}
    vi.mocked(fetchAdminUsers).mockReturnValue(new Promise((resolve) => (answer = resolve)))
    await mountPage()
    await search('zz')

    expect(page().find('[role="status"]').text()).toBe('Searching…')

    answer(userPage([]))
    await flushPromises()
    expect(page().find('[role="status"]').text()).toBe('Nobody matched.')
  })

  it('keeps the searching line a plain item of the list', async () => {
    // A role on the li itself replaces "listitem", and a list whose child is
    // not a list item is broken for a screen reader (axe "list" rule). The
    // live region sits inside the item instead.
    vi.mocked(fetchAdminUsers).mockReturnValue(new Promise(() => {}))
    await mountPage()
    await search('zz')

    const items = page().find('ul').element.children
    expect(Array.from(items).map((item) => [item.tagName, item.getAttribute('role')])).toEqual([
      ['LI', null]
    ])
    expect(page().find('li [role="status"]').text()).toBe('Searching…')
  })

  it('does not tell the admin nobody matched when the search itself failed', async () => {
    vi.mocked(fetchAdminUsers).mockRejectedValue(new TypeError('Failed to fetch'))
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    await mountPage()
    await search('ola')

    expect(page().find('[role="status"]').text()).toBe('The search could not be run. Try again.')
  })

  it('never lists an older answer under a newer term', async () => {
    const answers: Array<(value: never) => void> = []
    vi.mocked(fetchAdminUsers).mockImplementation(
      () => new Promise((resolve) => answers.push(resolve as (value: never) => void))
    )
    await mountPage()
    await search('ra')
    await search('ola')

    // The answer for "ola" first, then the late one for "ra".
    answers[1](userPage([DEAD]))
    await flushPromises()
    answers[0](userPage([LIVE]))
    await flushPromises()

    expect(page().find(`input[aria-label="${SEARCH_LABEL}"]`).element).toHaveProperty('value', 'ola')
    expect(page().text()).toContain('Ola Nunes')
    expect(page().text()).not.toContain('Rae Wills')
  })

  it('offers "Already on", disabled, for somebody already on the roster', async () => {
    vi.mocked(fetchSupportRoster).mockResolvedValue([{ ...AGENT, id: 8, name: 'Rae Wills' }])
    vi.mocked(fetchAdminUsers).mockResolvedValue(userPage([LIVE, DEAD]))
    await mountPage()
    await search('a')

    const onRoster = candidateRow('rae@example.com').find('button')
    expect(onRoster.text()).toBe('Already on Rae Wills')
    expect((onRoster.element as HTMLButtonElement).disabled).toBe(true)
    const notOnRoster = candidateRow('ola@example.com').find('button')
    expect(notOnRoster.text()).toBe('Grant Ola Nunes')
    expect((notOnRoster.element as HTMLButtonElement).disabled).toBe(false)
  })

  it('grants with the number for the id the search handed back', async () => {
    // adminAPI.ts does not validate what it receives, and adminweb's copy of
    // this endpoint handed out string ids. The ticket module works in numbers.
    vi.mocked(fetchAdminUsers).mockResolvedValue(userPage([{ ...DEAD, id: '9' }]))
    await mountPage()
    await search('ola')

    await candidateRow('ola@example.com').find('button').trigger('click')
    await flushPromises()

    expect(grantSupport).toHaveBeenCalledTimes(1)
    expect(grantSupport).toHaveBeenCalledWith(9)
  })

  it('empties the search, reloads the roster and returns focus to the box after a grant', async () => {
    vi.mocked(fetchAdminUsers).mockResolvedValue(userPage([DEAD]))
    await mountPage()
    await search('ola')
    vi.mocked(fetchSupportRoster).mockResolvedValue([
      { ...AGENT, id: 9, name: 'Ola Nunes', email: 'ola@example.com', openTickets: 0 }
    ])

    await candidateRow('ola@example.com').find('button').trigger('click')
    await flushPromises()

    const box = page().find(`input[aria-label="${SEARCH_LABEL}"]`)
    expect((box.element as HTMLInputElement).value).toBe('')
    expect(page().find('ul').exists()).toBe(false)
    expect(fetchSupportRoster).toHaveBeenCalledTimes(2)
    expect(rosterCell('Ola Nunes').text()).toBe('Ola Nunes')
    expect(document.activeElement).toBe(box.element)
  })

  it('does not send a second grant while the first is still in flight', async () => {
    let finish: () => void = () => {}
    vi.mocked(grantSupport).mockReturnValue(new Promise<void>((resolve) => (finish = resolve)))
    vi.mocked(fetchAdminUsers).mockResolvedValue(userPage([LIVE, DEAD]))
    await mountPage()
    await search('a')

    // Both presses land before Vue has re-rendered, so the buttons are not
    // disabled yet: only the handler reading the live flag stands between
    // the second press and a second request.
    const first = candidateRow('ola@example.com').find('button').element as HTMLButtonElement
    const second = candidateRow('rae@example.com').find('button').element as HTMLButtonElement
    first.click()
    second.click()
    await flushPromises()
    finish()
    await flushPromises()

    expect(grantSupport).toHaveBeenCalledTimes(1)
  })

  it('disables every Grant button while a grant is in flight', async () => {
    // React's disabled={grant.isPending}. The test above covers the press
    // that lands before the re-render; this covers what the admin sees after.
    let finish: () => void = () => {}
    vi.mocked(grantSupport).mockReturnValue(new Promise<void>((resolve) => (finish = resolve)))
    vi.mocked(fetchAdminUsers).mockResolvedValue(userPage([LIVE, DEAD]))
    await mountPage()
    await search('a')

    await candidateRow('ola@example.com').find('button').trigger('click')

    const disabled = page()
      .findAll('li button')
      .map((button) => (button.element as HTMLButtonElement).disabled)
    expect(disabled).toEqual([true, true])
    finish()
    await flushPromises()
  })
})

describe('granting access to an account that is switched off (RO-05, RO-06, RO-07)', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    vi.mocked(fetchSupportRoster).mockResolvedValue([])
    vi.mocked(fetchAdminUsers).mockResolvedValue(userPage([LIVE, DEAD]))
  })

  it('marks the candidate whose account is not active', async () => {
    // The mark used to read "Deactivated", and this list has only is_active
    // to go on: that is false for an invited or a pending account too, and
    // the server grants both of those, so the word named a decision nobody
    // had made.
    await mountPage()
    await search('a')

    const row = candidateRow('Ola Nunes')
    expect(row.text()).toContain('Not an active account')
    expect(row.text()).not.toContain('Deactivated')
  })

  it('does not put that mark on an account that is fine', async () => {
    // Load-bearing. Rendering the mark unconditionally satisfies the test
    // above on its own, and would label every candidate on the page.
    await mountPage()
    await search('a')

    expect(candidateRow('Rae Wills').text()).not.toContain('Not an active account')
  })

  it('still sends the grant rather than guessing the answer here', async () => {
    // is_active is false for an invited account the server is happy to
    // grant. Refusing here would block that ordinary case on a signal that
    // does not decide it. The server owns the rule.
    await mountPage()
    await search('a')

    const button = candidateRow('Ola Nunes').find('button')
    expect((button.element as HTMLButtonElement).disabled).toBe(false)
    await button.trigger('click')
    await flushPromises()
    expect(grantSupport).toHaveBeenCalledWith(9)
  })

  it('shows what the server said when it refused the grant', async () => {
    // Without this the press did nothing visible at all: the roster did not
    // change, the button stayed enabled, and the admin pressed it again.
    vi.mocked(grantSupport).mockRejectedValue(
      await refusal(
        'This account is switched off, so it cannot work the queue. ' +
          'Reactivate it first, then grant support access.'
      )
    )
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    await mountPage()
    await search('a')
    await candidateRow('Ola Nunes').find('button').trigger('click')
    await flushPromises()

    expect(page().find('[role="alert"]').text()).toBe(
      'This account is switched off, so it cannot work the queue. ' +
        'Reactivate it first, then grant support access.'
    )
  })

  it('says something even when the failure carried no sentence', async () => {
    // Load-bearing. A network fault has no msg, and rendering only
    // serverMessage would print an empty alert for it.
    vi.mocked(grantSupport).mockRejectedValue(new TypeError('Failed to fetch'))
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    await mountPage()
    await search('a')
    await candidateRow('Ola Nunes').find('button').trigger('click')
    await flushPromises()

    expect(page().find('[role="alert"]').text()).toBe('That person was not added to the queue.')
  })

  it('stays quiet while nothing has been refused', async () => {
    await mountPage()
    await search('a')

    expect(page().find('[role="alert"]').exists()).toBe(false)
  })

  it('puts focus back on the Grant button after a refusal', async () => {
    // A browser drops focus from a button that becomes disabled to the page
    // body, and every Grant button is disabled while the request runs. jsdom
    // does not do that, so the test does it by hand.
    vi.mocked(grantSupport).mockRejectedValue(await refusal('Students cannot work the support queue.'))
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    await mountPage()
    await search('a')
    const button = candidateRow('Ola Nunes').find('button').element as HTMLButtonElement
    button.focus()

    button.click()
    await nextTickAndBlur()
    await flushPromises()

    expect(document.activeElement).toBe(candidateRow('Ola Nunes').find('button').element)
  })

  it('leaves focus in the search box if the admin went back to it meanwhile', async () => {
    // Load-bearing for the test above: putting focus back is for focus that
    // was lost, not for taking it from where somebody put it.
    vi.mocked(grantSupport).mockRejectedValue(await refusal('Students cannot work the support queue.'))
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    await mountPage()
    await search('a')
    const box = page().find(`input[aria-label="${SEARCH_LABEL}"]`).element as HTMLInputElement

    ;(candidateRow('Ola Nunes').find('button').element as HTMLButtonElement).click()
    box.focus()
    await flushPromises()

    expect(document.activeElement).toBe(box)
  })
})

describe('the create entry point (RO-08)', () => {
  // The client's answer on 2026-09-04 was that an admin creates a NEW account
  // for a support agent, not only that they grant the role to an existing
  // one. Both routes exist; this is the one that has to be findable from the
  // screen somebody lands on when they think "how do I add a support person?".
  const createLink = () =>
    page()
      .findAll('a')
      .find((a) => /create a support agent/i.test(a.text()))

  beforeEach(() => {
    vi.mocked(fetchSupportRoster).mockResolvedValue([])
  })

  it('sends the admin to the People page already filtered to support', async () => {
    await mountPage()

    expect(createLink()!.attributes('href')).toBe('#/admin/users?role=support')
  })

  it('says where the link goes, because it goes somewhere and does not create', async () => {
    // The control is an anchor to a filtered list. It opens no form, and the
    // Add User form waiting on the other side opens on Student, so a label
    // reading only "Create a support agent" promised a step it does not take.
    await mountPage()

    expect(createLink()!.text()).toBe('Create a support agent on the People page')
  })

  it('says the new account still needs Support picked as its role', async () => {
    // The one thing an admin has to do that nothing on the way there tells
    // them. Miss it and the form asks for a school and a year level.
    await mountPage()

    expect(page().text()).toMatch(/needs Support picked as its role/)
  })

  it('says plainly which of the two things each route does', async () => {
    // "Adding" and "creating" are different actions with different results,
    // and a screen that offers both without saying so invites an admin to
    // make a second account for somebody who already has one.
    await mountPage()

    expect(page().text()).toContain('Adding someone here gives an existing account access to the queue.')
    expect(page().text()).toContain(
      'Creating a support agent makes a new account that has queue access and nothing else.'
    )
  })

  it('does not offer it to a support agent who is not an admin', async () => {
    await mountPage(pureAgent)

    expect(createLink()).toBeUndefined()
  })
})

describe('what queue access is, and what it is not (RO-09)', () => {
  it('says the People page’s Role column is not queue access', async () => {
    // The two screens disagree by design and neither is catching up with the
    // other: revoking never touches the role, and somebody listed as Mentor
    // can be on this page working the queue.
    await mountPage()

    expect(page().text()).toContain(
      'The Role column on the People page records what an account is, not whether it can open the queue.'
    )
  })

  it('does not claim to list the administrators, who are not on it', async () => {
    // The assertion above passes with or without this clause. Read flat,
    // "the only place that shows queue access" would hide every administrator
    // from anyone taking stock.
    await mountPage()

    expect(page().text()).toContain(
      'Apart from administrators, this page is the only place that shows queue access.'
    )
  })

  it('says revoking here leaves the role alone, and a role change on the People page removes access too', async () => {
    // The page used to say removing access was only possible here. Saving a
    // Support account with another role on the People page revokes its
    // access as well (the backend's role_moved branch), and the People editor
    // says so. Admin is the exception: an administrator keeps the queue.
    await mountPage()

    expect(page().text()).toContain("Revoking access here leaves the account's role as it is.")
    expect(page().text()).toContain(
      'On the People page, changing a Support account to another role also removes its access, unless the new role is Admin.'
    )
    expect(page().text()).not.toContain('only possible from this page')
  })
})

describe('revoking (RO-10)', () => {
  const dialog = () => page().find('[role="dialog"]')

  it('warns that revoking leaves their tickets in their name', async () => {
    await mountPage()
    await openRevoke()

    expect(dialog().find('h2').text()).toBe('Remove Sam Reid from the support queue?')
    expect(dialog().text()).toContain(
      'They still own 3 tickets that nobody else is working on. Revoking does not hand those to ' +
        "anyone else. They stay in this person's name until somebody reassigns them."
    )
  })

  it('counts one ticket as one ticket', async () => {
    vi.mocked(fetchSupportRoster).mockResolvedValue([{ ...AGENT, openTickets: 1 }])
    await mountPage()
    await openRevoke()

    expect(dialog().text()).toContain('They still own 1 ticket that nobody else is working on.')
  })

  it('does not warn about work when there is none', async () => {
    vi.mocked(fetchSupportRoster).mockResolvedValue([{ ...AGENT, openTickets: 0 }])
    await mountPage()
    await openRevoke()

    expect(dialog().text()).not.toContain('still own')
    expect(dialog().text()).toContain(
      'They will lose access to the support queue. Nothing else about their account changes.'
    )
  })

  it('warns before revoking that the People page will still say Support', async () => {
    vi.mocked(fetchSupportRoster).mockResolvedValue([{ ...AGENT, openTickets: 0 }])
    await mountPage()
    await openRevoke()

    expect(dialog().text()).toContain('The role listed for them on the People page does not change.')
  })

  it('warns about the role even when there are tickets to strand', async () => {
    // The other branch of the same dialog: a warning written into one branch
    // only is a warning half the admins never see.
    await mountPage()
    await openRevoke()

    expect(dialog().text()).toContain('still own 3 tickets')
    expect(dialog().text()).toContain('The role listed for them on the People page does not change.')
  })

  it('asks before it revokes, and only revokes on confirmation', async () => {
    await mountPage()
    await openRevoke()
    // Opening the dialog must not be the action itself.
    expect(revokeSupport).not.toHaveBeenCalled()

    await buttonNamed('Revoke access')!.trigger('click')
    await flushPromises()
    expect(revokeSupport).toHaveBeenCalledTimes(1)
    expect(revokeSupport).toHaveBeenCalledWith(4)
  })

  it('sends one revoke for two quick presses on the confirm button', async () => {
    let finish: () => void = () => {}
    vi.mocked(revokeSupport).mockReturnValue(new Promise<void>((resolve) => (finish = resolve)))
    await mountPage()
    await openRevoke()

    // Both before Vue re-renders the button as busy.
    const confirm = buttonNamed('Revoke access')!.element as HTMLButtonElement
    confirm.click()
    confirm.click()
    await flushPromises()
    finish()
    await flushPromises()

    expect(revokeSupport).toHaveBeenCalledTimes(1)
  })

  it('closes, reloads the roster and puts focus on the heading once the row is gone', async () => {
    await mountPage()
    await openRevoke()
    vi.mocked(fetchSupportRoster).mockResolvedValue([])

    await buttonNamed('Revoke access')!.trigger('click')
    await flushPromises()

    expect(page().find('[role="dialog"]').exists()).toBe(false)
    expect(fetchSupportRoster).toHaveBeenCalledTimes(2)
    expect(page().text()).not.toContain('Sam Reid')
    expect(document.activeElement).toBe(page().find('h1').element)
  })

  it('shows the server’s reason when the revoke is refused, inside the dialog', async () => {
    // React showed nothing: the dialog closed, the row stayed, and the admin
    // was left to guess.
    vi.mocked(revokeSupport).mockRejectedValue(await refusal('Support access not found', 404))
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    await mountPage()
    await openRevoke()

    await buttonNamed('Revoke access')!.trigger('click')
    await flushPromises()

    expect(dialog().find('[role="alert"]').text()).toBe('Support access not found')
  })

  it('still says the revoke failed when the failure carried no sentence', async () => {
    vi.mocked(revokeSupport).mockRejectedValue(new TypeError('Failed to fetch'))
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    await mountPage()
    await openRevoke()

    await buttonNamed('Revoke access')!.trigger('click')
    await flushPromises()

    expect(dialog().find('[role="alert"]').text()).toBe('That person was not removed from the queue.')
  })

  it('reloads the roster after a refused revoke, so a row somebody else removed goes', async () => {
    vi.mocked(revokeSupport).mockRejectedValue(await refusal('Support access not found', 404))
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    await mountPage()
    await openRevoke()

    await buttonNamed('Revoke access')!.trigger('click')
    await flushPromises()

    expect(fetchSupportRoster).toHaveBeenCalledTimes(2)
  })

  it('returns focus to the Revoke button when the dialog is cancelled', async () => {
    await mountPage()
    const revoke = await openRevoke()

    await buttonNamed('Cancel')!.trigger('click')
    await flushPromises()

    expect(page().find('[role="dialog"]').exists()).toBe(false)
    expect(revokeSupport).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(revoke.element)
  })

  it('disables every Revoke button while a revoke is in flight', async () => {
    // React's disabled={revoke.isPending}: a second row cannot be started
    // while the first answer is still out.
    let finish: () => void = () => {}
    vi.mocked(revokeSupport).mockReturnValue(new Promise<void>((resolve) => (finish = resolve)))
    vi.mocked(fetchSupportRoster).mockResolvedValue([
      AGENT,
      { ...AGENT, id: 5, name: 'Amy Ball', email: 'amy@example.com' }
    ])
    await mountPage()
    await openRevoke()

    await buttonNamed('Revoke access')!.trigger('click')

    const rowButtons = () =>
      page()
        .findAll('tbody button')
        .map((button) => (button.element as HTMLButtonElement).disabled)
    expect(rowButtons()).toEqual([true, true])
    finish()
    await flushPromises()
    expect(rowButtons()).toEqual([false, false])
  })

  describe('when the confirmation opens', () => {
    // The real Teleport, as in the block below: the stub re-creates the
    // dialog's buttons on every re-render, which moves focus for a reason a
    // browser does not have.
    const realDialog = () => document.querySelector<HTMLElement>('[role="dialog"]')

    it('puts focus on Cancel, not on the button that revokes', async () => {
      // ConfirmDialog focuses its confirm button, and here that is "Revoke
      // access". React's AlertDialog focused Cancel.
      await mountPage(ticketAdmin, { stubTeleport: false })
      await openRevoke()

      const focused = document.activeElement as HTMLElement
      expect(realDialog()!.contains(focused)).toBe(true)
      expect(focused.tagName).toBe('BUTTON')
      expect(focused.textContent!.trim()).toBe('Cancel')
    })

    it('so an Enter pressed straight after opening revokes nothing', async () => {
      // Enter on a focused button presses it. jsdom does not do that for a
      // key event, so the press is made on whatever has focus, as the key
      // would be.
      await mountPage(ticketAdmin, { stubTeleport: false })
      const revoke = await openRevoke()

      ;(document.activeElement as HTMLButtonElement).click()
      await flushPromises()

      expect(revokeSupport).not.toHaveBeenCalled()
      expect(realDialog()).toBeNull()
      expect(document.activeElement).toBe(revoke.element)
    })
  })

  describe('after a refused revoke, with the dialog still open', () => {
    // These mount the real Teleport, so the dialog sits at the end of body as
    // it does in a browser. The Teleport stub the other tests use re-creates
    // the dialog's buttons on every re-render, which would drop focus for a
    // reason a browser does not have.
    const realDialog = () => document.querySelector<HTMLElement>('[role="dialog"]')
    const dialogButton = (label: string) =>
      Array.from(realDialog()!.querySelectorAll('button')).find(
        (button) => button.textContent!.trim() === label
      )!

    beforeEach(async () => {
      vi.mocked(revokeSupport).mockRejectedValue(await refusal('Support access not found', 404))
      vi.spyOn(console, 'warn').mockImplementation(() => {})
    })

    async function openAndRefuse() {
      await mountPage(ticketAdmin, { stubTeleport: false })
      const revoke = await openRevoke()
      const confirm = dialogButton('Revoke access')
      confirm.focus()
      confirm.click()
      // The busy dialog disables both of its buttons, and a browser moves
      // focus off the disabled one to the page body.
      await nextTickAndBlur()
      await flushPromises()
      return revoke
    }

    it('puts focus on the reason, inside the dialog', async () => {
      // Left on the body, focus is outside the dialog: Esc never reaches it
      // and Tab walks the page behind it. Radix kept focus in the React one.
      await openAndRefuse()

      const reason = realDialog()!.querySelector('[role="alert"]')!
      expect(reason.textContent!.trim()).toBe('Support access not found')
      expect(document.activeElement).toBe(reason)
    })

    it('closes on Esc pressed wherever focus now is, and goes back to the Revoke button', async () => {
      // Keys go to the focused element. This sends Esc there, as a keyboard
      // would, rather than straight to the dialog.
      const revoke = await openAndRefuse()

      document.activeElement!.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
      )
      await flushPromises()

      expect(realDialog()).toBeNull()
      expect(document.activeElement).toBe(revoke.element)
    })

    it('lands on the heading when the reload took the row away, then Cancel', async () => {
      // The 404 case: somebody else removed this person, so the reload after
      // the refusal drops the row and the button that opened the dialog with
      // it. Focus cannot go back to a button that is no longer on the page.
      vi.mocked(fetchSupportRoster).mockResolvedValueOnce([AGENT]).mockResolvedValueOnce([])
      await openAndRefuse()
      expect(page().find('tbody').text()).toBe(
        'Nobody has been granted support access yet. Administrators can still work the queue.'
      )

      dialogButton('Cancel').click()
      await flushPromises()

      expect(realDialog()).toBeNull()
      expect(document.activeElement).toBe(page().find('h1').element)
    })
  })
})
