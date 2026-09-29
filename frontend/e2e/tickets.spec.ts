import {
  test,
  expect as baseExpect,
  type Browser,
  type BrowserContext,
  type Page,
  type TestInfo
} from '@playwright/test'
import { readFile, writeFile } from 'node:fs/promises'
import { inflateRawSync } from 'node:zlib'

/**
 * Support tickets end to end, both sides in the one Vue portal.
 *
 * A student raises and follows an enquiry in the Support Centre (/support);
 * a pure support agent works it in the portal's ticket queue
 * (/admin/tickets, ?ticket=<id> opens the detail panel). The agent side used
 * to be the React admin app; this suite drives the Vue port that replaces it.
 *
 * Every persona gets its own browser context (its own cookie jar): both talk
 * to one backend, and cookies ignore ports, so in one shared context the
 * agent's sign-in would silently replace the student's session and every
 * "the student sees X" after it would be testing the agent. The one place
 * that sharing is the point is the T01 block at the bottom, which puts two
 * tabs in ONE context on purpose.
 *
 * Requires (started by the harness, see e2e/README.md):
 *   - the backend, on a scratch database seeded with `seed_e2e`
 *   - the portal dev server (E2E_PORTAL_URL), built against that backend
 *   - E2E_API_URL, the same backend, for the checks that read it directly
 *
 * Each test raises the tickets it needs, with a subject no other run shares,
 * so nothing depends on what earlier runs left in the database. The backend
 * throttles ticket creation to 30 an hour per requester (ticket_create); a
 * full run raises five. Restarting the backend clears the counter (the local
 * cache is per process).
 */

const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8000'

type Account = { email: string; password: string }
const STUDENT: Account = { email: 'e2e.student@example.com', password: 'E2eStudent1!' }
const AGENT: Account = { email: 'e2e.agent@example.com', password: 'E2eAgent1!' }

// The requester's wording (utils/ticketTransport.ts SIGNED_IN_AS_SOMEONE_ELSE).
// Matched on its core so a change to the rest of the sentence does not read
// as the guard having stopped working.
const SIGNED_IN_AS_SOMEONE_ELSE = /signed in as someone else/

// The line the platform used to add under every new ticket, removed on the
// client's request (C-05). Both halves, so neither can come back alone.
const OLD_ACKNOWLEDGEMENT = /looking into this|get back to you shortly/i

// A first render of a route on the Vite dev server compiles it on demand, so
// the first visit to a page can take seconds. Every wait here polls; none of
// them sleeps.
const expect = baseExpect.configure({ timeout: 15_000 })
// The config leaves actions without a limit (actionTimeout: 0), so a click on
// something that never appears would sit until the test's own two minutes ran
// out and say nothing about what it was waiting for.
test.use({ actionTimeout: 15_000 })

// ---------------------------------------------------------------------------
// Evidence: every page's console and API traffic, written out with a
// screenshot when a test fails (under the run's --output directory).
// ---------------------------------------------------------------------------

type Tracked = { label: string; page: Page; consoleLog: string[]; networkLog: string[] }
const tracked: Tracked[] = []
const openContexts: BrowserContext[] = []

function track(page: Page, label: string) {
  const entry: Tracked = { label, page, consoleLog: [], networkLog: [] }
  tracked.push(entry)
  const at = () => new Date().toISOString()
  // The timezone prompt after sign-in is a window.confirm, and it appears
  // whenever the account's zone differs from the machine's. Dismissed, the
  // sign-in carries on to the landing page, which is what these tests check.
  page.on('dialog', (dialog) => {
    entry.consoleLog.push(`${at()} dialog.${dialog.type()}: ${dialog.message()}`)
    void dialog.dismiss()
  })
  page.on('console', (message) =>
    entry.consoleLog.push(`${at()} console.${message.type()}: ${message.text()}`)
  )
  page.on('pageerror', (error) => entry.consoleLog.push(`${at()} pageerror: ${error.message}`))
  page.on('response', (response) => {
    const request = response.request()
    if (!request.url().startsWith(API_URL)) return
    const csrf = request.headers()['x-csrftoken'] ? ' [X-CSRFToken]' : ''
    entry.networkLog.push(
      `${at()} ${request.method()} ${request.url()} -> ${response.status()}${csrf}`
    )
  })
  page.on('requestfailed', (request) => {
    if (!request.url().startsWith(API_URL)) return
    entry.networkLog.push(
      `${at()} ${request.method()} ${request.url()} FAILED ${request.failure()?.errorText ?? ''}`
    )
  })
}

async function persona(browser: Browser, label: string) {
  const context = await browser.newContext()
  openContexts.push(context)
  let extra = 0
  // Tabs opened later in the same context (the T01 tests) are tracked too.
  context.on('page', (page) => {
    if (!tracked.some((entry) => entry.page === page)) track(page, `${label}-tab${++extra}`)
  })
  const page = await context.newPage()
  // The listener above may have registered it already under a tab label.
  const known = tracked.find((entry) => entry.page === page)
  if (known) known.label = label
  else track(page, label)
  return { context, page }
}

test.afterEach(async ({}, testInfo: TestInfo) => {
  const failed = testInfo.status !== testInfo.expectedStatus
  if (failed) {
    for (const entry of tracked) {
      const base = testInfo.outputPath(entry.label)
      if (!entry.page.isClosed()) {
        await entry.page
          .screenshot({ path: `${base}-screenshot.png`, fullPage: true })
          .catch(() => undefined)
        entry.networkLog.push(`final URL: ${entry.page.url()}`)
      }
      await writeFile(`${base}-console.txt`, entry.consoleLog.join('\n') + '\n')
      await writeFile(`${base}-network.txt`, entry.networkLog.join('\n') + '\n')
    }
  }
  tracked.length = 0
  for (const context of openContexts.splice(0)) await context.close().catch(() => undefined)
})

// ---------------------------------------------------------------------------
// Steps
// ---------------------------------------------------------------------------

function uniqueSubject(what: string) {
  return `E2E ${what} ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

async function signIn(page: Page, who: Account) {
  await page.goto('/#/login', { waitUntil: 'domcontentloaded' })
  // Password is the second tab; the default one sends a magic-link code.
  await page.getByRole('tab', { name: 'Password Sign-in' }).click()
  await page.locator('#login-email').fill(who.email)
  await page.locator('#login-password').fill(who.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page).not.toHaveURL(/#\/login/)
}

const DASHBOARD = /#\/dashboard$/
const QUEUE = /#\/admin\/tickets(\?.*)?$/

type RaisedTicket = { id: number; number: string; subject: string }
type Attachment = { name: string; mimeType: string; buffer: Buffer }

// Not exact. Each form label wraps its control, and a control inside its own
// label adds its current value to the name ("Issue category Select a
// category"), so the exact words never match.
async function raiseEnquiry(
  page: Page,
  subject: string,
  options: { body?: string; attachment?: Attachment } = {}
): Promise<RaisedTicket> {
  await expect(page.getByRole('heading', { name: 'How can we help?' })).toBeVisible()
  await page.getByLabel('Issue category').selectOption('technical_issue')
  await page.getByLabel('Subject').fill(subject)
  await page
    .getByLabel('Message')
    .fill(options.body ?? 'The group workspace shows an error when I open it.')
  if (options.attachment) {
    await page.locator('.ticket-form input[type="file"]').setInputFiles(options.attachment)
    await expect(page.locator('.attach__name')).toHaveText(options.attachment.name)
  }
  await page.getByRole('button', { name: 'Submit ticket' }).click()
  // Success is a redirect straight into the new ticket's page.
  await page.waitForURL(/#\/support\/tickets\/\d+$/)
  const id = Number(/tickets\/(\d+)$/.exec(page.url())![1])
  const number = ((await page.locator('p.ticket__number').textContent()) ?? '')
    .replace('#', '')
    .trim()
  expect(number).toMatch(/^SUP-\d{4}-\d{5}$/)
  return { id, number, subject }
}

/** A sidebar entry by its visible words. The icons are <i> elements with a
 *  Font Awesome glyph and no aria-hidden, so the glyph is part of every
 *  link's accessible name (" Home"), and `exact: true` on the bare word
 *  matches nothing. That is harmless for a click, which fails loudly, and
 *  dangerous for a toHaveCount(0), which would pass on a locator that can
 *  never match: the student test uses these same locators to see the links
 *  first, so the agent test's zero counts mean something. */
function sidebarLink(page: Page, words: string) {
  return page
    .locator('aside.sidebar')
    .getByRole('link', { name: new RegExp(`^[^A-Za-z0-9]*${words}\\s*$`) })
}

const MEMBER_PAGES = ['Home', 'Groups', 'Events', 'Announcements', 'Resources', 'Support']

async function openSupportCentre(page: Page) {
  // Through the sidebar, not page.goto: a client-side move keeps the page's
  // module state, which is what "without reloading" means in the T01 tests.
  await sidebarLink(page, 'Support').click()
  await expect(page).toHaveURL(/#\/support$/)
  await expect(page.getByRole('heading', { name: 'Support Centre' })).toBeVisible()
}

async function signInAsStudentToSupportCentre(browser: Browser, label = 'student') {
  const student = await persona(browser, label)
  await signIn(student.page, STUDENT)
  await expect(student.page).toHaveURL(DASHBOARD)
  await openSupportCentre(student.page)
  return student
}

async function signInAsAgent(browser: Browser, label = 'agent') {
  const agent = await persona(browser, label)
  await signIn(agent.page, AGENT)
  await expect(agent.page).toHaveURL(QUEUE)
  return agent
}

/** GET on the backend with the context's own cookies: whoever that context
 *  is signed in as. Accept: application/json, or DRF answers a browser-ish
 *  request with its HTML page. */
async function apiData(context: BrowserContext, path: string) {
  const response = await context.request.get(`${API_URL}${path}`, {
    headers: { Accept: 'application/json' }
  })
  expect(response.status(), `GET ${path}`).toBe(200)
  return (await response.json()).data
}

function pdf(name: string): Attachment {
  return {
    name,
    mimeType: 'application/pdf',
    buffer: Buffer.from(`%PDF-1.4\n% ${name}, attached by the e2e suite\n%%EOF\n`)
  }
}

/** The members of a zip archive, by name. Enough of the format for an .xlsx:
 *  the central directory, stored and deflated members. */
function unzip(archive: Buffer): Map<string, Buffer> {
  let end = archive.length - 22
  while (end >= 0 && archive.readUInt32LE(end) !== 0x06054b50) end--
  if (end < 0) throw new Error('not a zip archive: no end-of-central-directory record')
  const members = new Map<string, Buffer>()
  const count = archive.readUInt16LE(end + 10)
  let at = archive.readUInt32LE(end + 16)
  for (let i = 0; i < count; i++) {
    if (archive.readUInt32LE(at) !== 0x02014b50) throw new Error('bad central directory entry')
    const method = archive.readUInt16LE(at + 10)
    const size = archive.readUInt32LE(at + 20)
    const nameLength = archive.readUInt16LE(at + 28)
    const extraLength = archive.readUInt16LE(at + 30)
    const commentLength = archive.readUInt16LE(at + 32)
    const local = archive.readUInt32LE(at + 42)
    const name = archive.toString('utf8', at + 46, at + 46 + nameLength)
    const start = local + 30 + archive.readUInt16LE(local + 26) + archive.readUInt16LE(local + 28)
    const raw = archive.subarray(start, start + size)
    members.set(name, method === 8 ? inflateRawSync(raw) : Buffer.from(raw))
    at += 46 + nameLength + extraLength + commentLength
  }
  return members
}

// ---------------------------------------------------------------------------

test.describe('support tickets, both sides in the portal', () => {
  // Without the harness (signalled by E2E_PORTAL_URL) nothing started a
  // backend, and every step here would fail on a refused connection. Skip
  // rather than report a false failure to someone running the default
  // `playwright test`, which only vue.spec.ts can pass on its own.
  test.skip(!process.env.E2E_PORTAL_URL, 'needs the harness (E2E_PORTAL_URL); see e2e/README.md')
  test.describe.configure({ timeout: 120_000 })

  test('a student raises an enquiry with an attachment and follows it in the Support Centre', async ({
    browser
  }) => {
    const { page } = await signInAsStudentToSupportCentre(browser)
    const subject = uniqueSubject('raise')
    const body = 'The group workspace shows an error when I open it.'
    const ticket = await raiseEnquiry(page, subject, { body, attachment: pdf('screenshot.pdf') })

    await expect(page.getByRole('heading', { level: 1, name: subject })).toBeVisible()
    const rows = page.locator('ol.timeline > li')
    // Their message and nothing else. There used to be a system line under
    // it, "Thanks. We're looking into this and will get back to you shortly."
    // (C-05: "I don't think that adds anything").
    await expect(rows).toHaveCount(1)
    await expect(page.locator('.timeline__system')).toHaveCount(0)
    await expect(page.locator('body')).not.toContainText(OLD_ACKNOWLEDGEMENT)

    const message = rows.first()
    await expect(message.locator('.timeline__body')).toHaveText(body)
    await expect(message.getByRole('button', { name: 'screenshot.pdf' })).toBeVisible()

    // C-06: the date AND the time, in the reader's own zone. Checked against
    // the instant the element itself carries, so this fails on a time that is
    // present but wrong as well as on one that is missing.
    const stamp = message.locator('.timeline__meta time')
    await expect(stamp).toHaveText(/^\d{1,2} [A-Z][a-z]+ \d{4}, \d{1,2}:\d{2}\s?[ap]m$/i)
    const shown = (await stamp.textContent())!.trim()
    const expected = await stamp.evaluate((element) => {
      const when = new Date(element.getAttribute('datetime')!)
      return when.toLocaleTimeString('en-AU', { hour: 'numeric', minute: '2-digit' })
    })
    expect(shown.endsWith(expected), `"${shown}" should end with "${expected}"`).toBe(true)

    // And it is in their list, linked to its page.
    await page.getByRole('link', { name: /Back to Support Centre/ }).click()
    const row = page.locator('.my-tickets__table tbody tr', { hasText: ticket.number })
    await expect(row).toHaveCount(1)
    await expect(row.getByRole('link', { name: subject })).toBeVisible()
    await expect(row).toContainText('Open')
    await row.getByRole('link', { name: `#${ticket.number}` }).click()
    await expect(page).toHaveURL(new RegExp(`#/support/tickets/${ticket.id}$`))
  })

  test('a pure support agent lands on the queue, sees only the queue, and opens a ticket by click and by keyboard', async ({
    browser
  }) => {
    const student = await signInAsStudentToSupportCentre(browser)
    const attachment = pdf('evidence.pdf')
    const ticket = await raiseEnquiry(student.page, uniqueSubject('agent'), { attachment })

    const { page } = await signInAsAgent(browser)
    // The queue, not the student dashboard every account used to land on.
    await expect(page.getByRole('heading', { level: 1, name: 'Support queue' })).toBeVisible()
    await expect(page.locator('h1.hero-title')).toHaveCount(0)

    // The queue and nothing else in the sidebar. The member pages would only
    // bounce them back here (the guard), and the roster that grants the role
    // is for admins.
    await expect(sidebarLink(page, 'Support queue')).toBeVisible()
    for (const words of MEMBER_PAGES) {
      await expect(sidebarLink(page, words), words).toHaveCount(0)
    }
    await expect(sidebarLink(page, 'Support agents')).toHaveCount(0)

    // Most recently active first, and this is the newest ticket there is.
    const opener = page.getByRole('button', { name: `Open ${ticket.number}` })
    await expect(opener).toBeVisible()

    // By click, anywhere on the row.
    const dialog = page.getByRole('dialog')
    await page.locator('td.queue-table__subject', { hasText: ticket.subject }).click()
    await expect(dialog).toBeVisible()
    await expect(dialog).toContainText(ticket.subject)
    await expect(dialog.getByRole('heading', { level: 2 })).toContainText(ticket.number)
    await expect(page).toHaveURL(new RegExp(`[?&]ticket=${ticket.id}(&|$)`))
    await dialog.getByRole('button', { name: 'Close' }).click()
    await expect(dialog).toHaveCount(0)
    await expect(page).not.toHaveURL(/[?&]ticket=/)

    // By keyboard: Tab from the row's checkbox reaches the row's button,
    // Enter opens the panel with focus inside it, Esc closes it and gives
    // focus back to the button that opened it.
    await page.getByRole('checkbox', { name: `Select ${ticket.number}` }).focus()
    await page.keyboard.press('Tab')
    await expect(opener).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(dialog).toContainText(ticket.subject)
    await expect
      .poll(() => page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]')))
      .toBe(true)
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect(opener).toBeFocused()

    // The student's attachment comes down as a file, byte for byte.
    await page.keyboard.press('Enter')
    await expect(dialog).toContainText(ticket.subject)
    const downloading = page.waitForEvent('download')
    await dialog.getByRole('button', { name: attachment.name }).click()
    const download = await downloading
    expect(download.suggestedFilename()).toBe(attachment.name)
    const bytes = await readFile((await download.path())!)
    expect(bytes.equals(attachment.buffer)).toBe(true)
    // Still the app: a download never navigates away.
    await expect(page).toHaveURL(new RegExp(`[?&]ticket=${ticket.id}(&|$)`))
    await expect(page.locator('.agent-timeline__file-error')).toHaveCount(0)
  })

  test('reply and wait, the student answers, resolve, and a student reply reopens it', async ({
    browser
  }) => {
    const student = await signInAsStudentToSupportCentre(browser)
    const ticket = await raiseEnquiry(student.page, uniqueSubject('lifecycle'))

    const agent = await signInAsAgent(browser)
    // A direct link to the ticket opens its panel over the queue.
    await agent.page.goto(`/#/admin/tickets?ticket=${ticket.id}`)
    const dialog = agent.page.getByRole('dialog')
    const title = dialog.getByRole('heading', { level: 2 })
    const status = dialog.getByLabel('Change status')
    await expect(title).toContainText(ticket.number)
    await expect(title).toContainText('Open')

    // "Reply and wait for their reply": one reply with the box ticked.
    const question = 'Which group is it? Please tell us its name.'
    await dialog.getByRole('textbox', { name: 'Reply to the requester' }).fill(question)
    await dialog.getByLabel('I have asked them for something. Wait for their reply.').check()
    await dialog.getByRole('button', { name: 'Send reply' }).click()
    await expect(dialog.locator('.agent-timeline__body', { hasText: question })).toBeVisible()
    await expect(title).toContainText('Pending user')
    await expect(status).toHaveValue('pending_user')

    // The student sees the question and that it is their turn.
    const badges = student.page.locator('.ticket__badges')
    await student.page.reload()
    await expect(student.page.locator('p.timeline__body', { hasText: question })).toBeVisible()
    await expect(badges).toContainText('Pending user')
    await expect(student.page.locator('.ticket__callout')).toContainText('We are waiting on you.')

    const answer = 'It is the Blue Team group.'
    await student.page.getByLabel('Your reply').fill(answer)
    await student.page.getByRole('button', { name: 'Send reply' }).click()
    await expect(student.page.locator('p.timeline__body', { hasText: answer })).toBeVisible()
    await expect(badges).toContainText('In progress')

    // Back with the agent, in progress again.
    await agent.page.reload()
    await expect(dialog.locator('.agent-timeline__body', { hasText: answer })).toBeVisible()
    await expect(title).toContainText('In progress')
    await expect(status).toHaveValue('in_progress')

    // Resolve. The control shows the server's value, not the pick, so wait
    // for the server's answer rather than for the select.
    const patched = agent.page.waitForResponse(
      (response) =>
        response.request().method() === 'PATCH' &&
        response.url().startsWith(`${API_URL}/api/v1/admin/tickets/${ticket.id}/`)
    )
    await status.selectOption('resolved')
    expect((await patched).status()).toBe(200)
    await expect(title).toContainText('Resolved')

    await student.page.reload()
    await expect(badges).toContainText('Resolved')

    // Replying to a resolved enquiry reopens it (T7).
    const again = 'It is happening again, sorry.'
    await student.page.getByLabel('Your reply').fill(again)
    await student.page.getByRole('button', { name: 'Send reply' }).click()
    await expect(student.page.locator('p.timeline__body', { hasText: again })).toBeVisible()
    await expect(badges).toContainText('Open')
    await expect(student.page.locator('.timeline__system').last()).toContainText(
      'Ticket reopened following your reply.'
    )

    await agent.page.reload()
    await expect(title).toContainText('Open')
    await expect(status).toHaveValue('open')
  })

  test('Export to Excel downloads an .xlsx of what the current filters match', async ({
    browser
  }) => {
    const student = await signInAsStudentToSupportCentre(browser)
    const tag = uniqueSubject('export')
    const ticket = await raiseEnquiry(student.page, tag)

    const { page } = await signInAsAgent(browser)
    await page.getByLabel('Search tickets').fill(tag)
    await page.getByLabel('Filter by status').selectOption('open')
    // The table settles on the one ticket the two filters match.
    await expect(page.getByRole('button', { name: /^Open SUP-/ })).toHaveCount(1)
    await expect(page.getByRole('button', { name: `Open ${ticket.number}` })).toBeVisible()

    const dayBefore = new Date().toISOString().slice(0, 10)
    const requested = page.waitForRequest((request) =>
      request.url().startsWith(`${API_URL}/api/v1/admin/tickets/export/`)
    )
    const downloading = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Export to Excel' }).click()
    const query = new URL((await requested).url()).searchParams
    expect(query.get('search')).toBe(tag)
    expect(query.get('status')).toBe('open')
    // The page on screen is not the export: no paging goes with it.
    expect(query.has('page') || query.has('asOf') || query.has('after')).toBe(false)

    const download = await downloading
    const dayAfter = new Date().toISOString().slice(0, 10)
    // Named by the server for the exporter's day, in the exporter's zone
    // (the seeded agent's is UTC).
    const name = download.suggestedFilename()
    expect(name).toMatch(/^tickets-\d{4}-\d{2}-\d{2}\.xlsx$/)
    expect([`tickets-${dayBefore}.xlsx`, `tickets-${dayAfter}.xlsx`]).toContain(name)

    const bytes = await readFile((await download.path())!)
    expect(bytes.subarray(0, 2).toString('latin1')).toBe('PK')
    const members = unzip(bytes)
    const sheet = members.get('xl/worksheets/sheet1.xml')?.toString('utf8') ?? ''
    const strings = members.get('xl/sharedStrings.xml')?.toString('utf8') ?? ''
    // The heading row and the one ticket the filters match, not the queue.
    expect(sheet.match(/<row\b/g) ?? []).toHaveLength(2)
    expect(sheet + strings).toContain(ticket.number)
    expect(sheet + strings).toContain(tag)
    await expect(page.locator('.ticket-queue__alert')).toHaveCount(0)
  })

  test('a student who opens the queue is sent to their own start page', async ({ browser }) => {
    const { page } = await persona(browser, 'student')
    await signIn(page, STUDENT)
    await expect(page).toHaveURL(DASHBOARD)
    // The member pages, found by the same locators the agent test counts to
    // zero, and no way into the queue.
    for (const words of MEMBER_PAGES) {
      await expect(sidebarLink(page, words), words).toBeVisible()
    }
    await expect(sidebarLink(page, 'Support queue')).toHaveCount(0)

    // Moving inside the app, the way a pasted link in an open tab would.
    await page.goto(`/#/admin/tickets`)
    await expect(page).toHaveURL(DASHBOARD)
    await page.goto(`/#/admin/tickets?ticket=1`)
    await expect(page).toHaveURL(DASHBOARD)
    await page.goto(`/#/admin/tickets/audit`)
    await expect(page).toHaveURL(DASHBOARD)

    // And a fresh load of the link, which runs the guard before the app has
    // anything on screen.
    await page.goto('about:blank')
    await page.goto(`/#/admin/tickets`)
    await expect(page).toHaveURL(DASHBOARD)
    await expect(page.locator('h1.hero-title')).toContainText('Welcome back,')
    await expect(page.getByRole('heading', { name: 'Support queue' })).toHaveCount(0)
  })
})

/**
 * T01 in a real browser: two tabs, one cookie jar.
 *
 * Tab A is the student's. Tab B, in the SAME context, signs the student out
 * and signs in as the agent, so the session tab A's page is still using now
 * belongs to somebody else. Tab A still shows the student's page and still
 * believes it is the student (its store is its own memory). Anything it sends
 * now would be filed under the agent's name, so the transport must refuse it
 * with the requester's sentence, and the backend must hold nothing new under
 * the agent.
 *
 * Three orderings, because the transport has two guards and they cover
 * different ones (ticketTransport.ts requestJson). Measured by switching each
 * guard off in turn (2026-09-29):
 *  - reloaded before the takeover: the cache is empty, and the token the
 *    write fetches for itself is valid for the agent's session. Only the
 *    check before sending stops it; without that check the enquiry was
 *    filed under the agent. This is T01 proper.
 *  - after a write of its own went through: the token is one the transport
 *    has already checked, the takeover rotates it, and only the 403 branch
 *    stops it.
 *  - never reloaded: the cache still holds the token from tab A's own
 *    sign-in. Either guard stops it (the check first, the 403 branch if the
 *    check is gone); with both gone the enquiry was filed under the agent.
 */
test.describe('T01: a tab whose session changed hands is refused', () => {
  test.skip(!process.env.E2E_PORTAL_URL, 'needs the harness (E2E_PORTAL_URL); see e2e/README.md')
  test.describe.configure({ timeout: 120_000 })

  async function agentTakesOverIn(context: BrowserContext) {
    const tabB = await context.newPage()
    // The student is signed in on this browser, so the sign-in page sends
    // this tab to their dashboard. Signing out first is what a second person
    // at the same computer would do.
    await tabB.goto('/#/login', { waitUntil: 'domcontentloaded' })
    await expect(tabB).toHaveURL(DASHBOARD)
    await tabB.getByRole('button', { name: 'Open account menu' }).click()
    await tabB.getByRole('button', { name: 'Log out' }).click()
    await expect(tabB).toHaveURL(/#\/login/)
    await signIn(tabB, AGENT)
    await expect(tabB).toHaveURL(QUEUE)
    // Settled: the shared session is the agent's now.
    const me = await context.request.get(`${API_URL}/api/v1/users/me/`, {
      headers: { Accept: 'application/json' }
    })
    expect((await me.json()).email).toBe(AGENT.email)
    return tabB
  }

  async function nothingFiledUnderTheAgent(context: BrowserContext, subject: string) {
    // The context's cookies are the agent's now, so these ask as the agent:
    // the whole queue, and the agent's own list as a requester.
    const queue = await apiData(
      context,
      `/api/v1/admin/tickets/?search=${encodeURIComponent(subject)}`
    )
    expect(queue.total).toBe(0)
    const own = await apiData(context, '/api/v1/tickets/?limit=50')
    expect(own.items.map((row: { subject: string }) => row.subject)).not.toContain(subject)
  }

  async function submitEnquiryAndExpectRefusal(tabA: Page, subject: string) {
    await tabA.getByLabel('Issue category').selectOption('account_access')
    await tabA.getByLabel('Subject').fill(subject)
    await tabA.getByLabel('Message').fill('I cannot see my group.')
    await tabA.getByRole('button', { name: 'Submit ticket' }).click()
    await expect(tabA.locator('.ticket-form__error')).toHaveText(SIGNED_IN_AS_SOMEONE_ELSE)
    // Nowhere new, and their words are still in the form.
    await expect(tabA).toHaveURL(/#\/support$/)
    await expect(tabA.getByLabel('Subject')).toHaveValue(subject)
  }

  test('tab A, never reloaded, is refused a new enquiry', async ({ browser }) => {
    const { context, page: tabA } = await signInAsStudentToSupportCentre(browser, 'tabA-student')
    await agentTakesOverIn(context)
    // Tab A has not moved: still the student's Support Centre, still the page
    // that was loaded before the takeover.
    await expect(tabA).toHaveURL(/#\/support$/)

    const subject = uniqueSubject('T01 warm')
    await submitEnquiryAndExpectRefusal(tabA, subject)
    await nothingFiledUnderTheAgent(context, subject)
  })

  test('tab A, reloaded before the takeover, is refused a new enquiry', async ({ browser }) => {
    const { context, page: tabA } = await signInAsStudentToSupportCentre(browser, 'tabA-student')
    // A cold cache: the reload empties the CSRF token and everything the
    // transport had checked, while the session is still the student's.
    await tabA.reload()
    await expect(tabA.getByRole('heading', { name: 'How can we help?' })).toBeVisible()
    await expect(tabA.getByText(/My support tickets/)).toBeVisible()

    await agentTakesOverIn(context)

    const subject = uniqueSubject('T01 cold')
    await submitEnquiryAndExpectRefusal(tabA, subject)
    await nothingFiledUnderTheAgent(context, subject)
  })

  test('tab A, after a write of its own went through, is refused a reply', async ({ browser }) => {
    const { context, page: tabA } = await signInAsStudentToSupportCentre(browser, 'tabA-student')
    const ticket = await raiseEnquiry(tabA, uniqueSubject('T01 checked'))

    await agentTakesOverIn(context)

    const reply = `T01 reply that must not be filed ${Date.now()}`
    await tabA.getByLabel('Your reply').fill(reply)
    await tabA.getByRole('button', { name: 'Send reply' }).click()
    await expect(tabA.locator('.reply__error')).toHaveText(SIGNED_IN_AS_SOMEONE_ELSE)
    await expect(tabA.getByLabel('Your reply')).toHaveValue(reply)

    // The ticket as the agent sees it: the student's first message, and not
    // the reply, under anybody's name.
    const detail = await apiData(context, `/api/v1/admin/tickets/${ticket.id}/`)
    const bodies = detail.messages.map((message: { body: string }) => message.body)
    expect(bodies).not.toContain(reply)
    expect(detail.messages).toHaveLength(1)
  })
})
