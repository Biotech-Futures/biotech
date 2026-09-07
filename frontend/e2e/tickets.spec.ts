import { test, expect, type Page } from '@playwright/test'

/**
 * The ticket lifecycle, driven through both real frontends.
 *
 * One student in the Vue portal, one support agent in the React admin app.
 * They get SEPARATE browser contexts because both apps talk to one backend
 * on localhost and cookies do not care about ports: in a shared context the
 * agent's login would silently replace the student's session, and every
 * "student sees X" assertion after that would be testing the agent.
 *
 * Requires (started by the harness, see e2e/README.md):
 *   - backend with the `seed_e2e` accounts loaded
 *   - the portal dev server (E2E_PORTAL_URL)
 *   - the admin dev server (E2E_ADMIN_URL)
 */

const ADMIN_URL = process.env.E2E_ADMIN_URL ?? 'http://localhost:3000'

const STUDENT = { email: 'e2e.student@example.com', password: 'E2eStudent1!' }
const AGENT = { email: 'e2e.agent@example.com', password: 'E2eAgent1!' }

async function loginToPortal(page: Page) {
  // The timezone-mismatch prompt is a window.confirm that would otherwise
  // hang the run on machines whose clock disagrees with the seeded profile.
  page.on('dialog', (dialog) => dialog.dismiss())
  await page.goto('/#/login')
  // Password is the second tab; the default tab sends a magic-link code.
  await page.getByRole('tab', { name: 'Password Sign-in' }).click()
  await page.locator('#login-email').fill(STUDENT.email)
  await page.locator('#login-password').fill(STUDENT.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.locator('h1.hero-title')).toContainText('Welcome back,', {
    timeout: 15000,
  })
}

async function loginToAdmin(page: Page) {
  await page.goto(`${ADMIN_URL}/signin`)
  await page.locator('#email').fill(AGENT.email)
  await page.locator('#password').fill(AGENT.password)
  await page.getByRole('button', { name: 'Login' }).click()
  // Success is a hard window.location.assign('/'), not a client-side nav.
  await page.waitForURL(`${ADMIN_URL}/`, { timeout: 15000 })
}

test.describe('ticket lifecycle across both apps', () => {
  // This spec drives a second server (the admin app at E2E_ADMIN_URL) that
  // Playwright does not start. Without the three-server harness — signalled
  // by E2E_PORTAL_URL — the admin steps would fail on a refused connection,
  // so skip rather than report a false failure to someone running the
  // default `playwright test`.
  test.skip(
    !process.env.E2E_PORTAL_URL,
    'needs the three-server harness (set E2E_PORTAL_URL / E2E_ADMIN_URL)',
  )

  test('raise, work, resolve, reopen — and the internal note stays inside', async ({
    browser,
  }) => {
    test.setTimeout(180_000)

    const studentPage = await (await browser.newContext()).newPage()
    const agentPage = await (await browser.newContext()).newPage()

    // ---- student raises a ticket -------------------------------------
    await loginToPortal(studentPage)
    await studentPage.goto('/#/support')
    await expect(
      studentPage.getByRole('heading', { name: 'How can we help?' }),
    ).toBeVisible()

    const subject = `E2E run ${Date.now()}`
    await studentPage
      .getByLabel('Issue category')
      .selectOption('help_student_group')
    // The requester's own urgency (client, 2026-09-04). Set to High here
    // rather than left on the default so the value has to travel: form ->
    // serializer -> column -> both apps. A default would pass either way.
    await studentPage.getByLabel('How urgent is this?').selectOption('high')
    await studentPage.getByLabel('Subject').fill(subject)
    await studentPage
      .getByLabel('Message')
      .fill('The group workspace shows an error when I open it.')
    await studentPage.getByRole('button', { name: 'Submit ticket' }).click()

    // Success is a redirect straight into the new ticket's detail page.
    await studentPage.waitForURL(/#\/support\/tickets\/\d+/, {
      timeout: 15000,
    })
    const numberText = await studentPage
      .locator('p.ticket__number')
      .textContent()
    const ticketNumber = (numberText ?? '').replace('#', '').trim()
    expect(ticketNumber).toMatch(/^SUP-\d{4}-\d{5}$/)

    // They can see the urgency they chose. Without this a person picks High,
    // is shown nothing, and cannot tell whether the choice registered.
    await expect(studentPage.getByText('High priority')).toBeVisible()

    // ---- agent works it in the admin app -----------------------------
    await loginToAdmin(agentPage)
    await agentPage.goto(`${ADMIN_URL}/tickets`)
    await agentPage
      .getByRole('button', { name: `Open ${ticketNumber}` })
      .click()
    const panel = agentPage.getByRole('dialog')
    await expect(panel).toContainText(subject)

    // The urgency the student set arrived on the support side, and the agent
    // can change it. Both halves of the client's answer, in one place.
    await expect(
      panel.getByLabel('Change priority'),
    ).toContainText('High')
    // Re-filing, which nothing in any interface could do before the client
    // replaced the three categories with eight.
    await expect(
      panel.getByLabel('Change category'),
    ).toContainText('Help with a student or group')

    // An internal note first: the whole point of the wall is that the
    // student never sees this string. Asserted on the student side below.
    const noteText = 'INTERNAL-E2E do not tell the requester yet'
    await panel
      .getByPlaceholder(
        "Visible to support only. No email is sent and the requester's ticket shows no change.",
      )
      .fill(noteText)
    await panel.getByRole('button', { name: 'Add internal note' }).click()
    await expect(panel).toContainText(noteText)

    const replyText = 'We are on it. Could you tell us which group this is?'
    await panel
      .getByPlaceholder(
        'This goes to the person who raised the ticket, and they are emailed about it.',
      )
      .fill(replyText)
    await panel.getByRole('button', { name: 'Send reply' }).click()
    await expect(panel).toContainText(replyText)

    await panel.getByLabel('Change status').click()
    await agentPage.getByRole('option', { name: 'Resolved' }).click()
    await expect(panel.getByLabel('Change status')).toContainText('Resolved')

    // ---- student sees the reply, never the note, and reopens ---------
    await studentPage.reload()
    await expect(
      studentPage.locator('p.timeline__body', { hasText: replyText }),
    ).toBeVisible({ timeout: 15000 })
    await expect(
      studentPage.locator('span.ticket-badge').first(),
    ).toHaveText('Resolved')
    // The internal note must not appear anywhere on the student's page.
    await expect(studentPage.locator('body')).not.toContainText(noteText)

    await studentPage
      .getByLabel('Your reply')
      .fill('It is still happening, sorry.')
    await studentPage.getByRole('button', { name: 'Send reply' }).click()
    await expect(
      studentPage.locator('p.timeline__body', {
        hasText: 'It is still happening',
      }),
    ).toBeVisible()

    // Replying to a resolved ticket reopens it (T7).
    await studentPage.reload()
    await expect(
      studentPage.locator('span.ticket-badge').first(),
    ).toHaveText('Open', { timeout: 15000 })
  })
})
