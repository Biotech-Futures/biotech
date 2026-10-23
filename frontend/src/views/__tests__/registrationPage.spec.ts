import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { routerKey } from 'vue-router'

import RegistrationPage from '@/views/RegistrationPage.vue'
import pageSource from '@/views/RegistrationPage.vue?raw'
import globalCss from '@/assets/main.css?raw'
import { createStudent } from '@/registration/registration'
import { REGISTRATION_GATEWAY_KEY, type RegistrationGateway } from '@/registration/registrationGateway'
import { heldRegistrationPassword } from '@/registration/registrationPassword'
import { setRegistrationState } from '@/composables/useRegistrationOpen'
import { appSelectLabels, appSelectText, pickAppSelect } from '@/__tests__/appSelect'

// Registration as it is by default: open, with no dates.
const OPEN = { open_now: true, opens_at: null, closes_at: null, can_register_students: true }

const mountPage = (mode: 'canonical' | 'supervisor' = 'canonical') =>
  mount(RegistrationPage, {
    props: { mode },
    global: {
      plugins: [createPinia()],
      stubs: {
        RouterLink: {
          props: ['to'],
          template: '<a :href="to"><slot /></a>',
        },
      },
    },
  })

const clickButton = async (wrapper: VueWrapper, label: string) => {
  const button = wrapper.findAll('button').find((candidate) => candidate.text().includes(label))
  expect(button, `button containing "${label}"`).toBeDefined()
  await button!.trigger('click')
}

// Upload student details, chosen as a supervisor would.
const openCsvUpload = async (wrapper: VueWrapper) => {
  await clickButton(wrapper, 'Register students individually or outside of groups using a spreadsheet')
  await wrapper.vm.$nextTick()
}

beforeEach(() => {
  // No registration progress kept from another test.
  sessionStorage.clear()
  vi.stubGlobal('scrollTo', vi.fn())
  // No countries or states to load (text boxes), unless a test gives some.
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({}))))
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('canonical registration intake', () => {
  it('renders compact headings and flat white panels with the target platform green', () => {
    const css = /<style scoped>([\s\S]+)<\/style>/.exec(pageSource)?.[1]
    if (!css) throw new Error('Expected registration stylesheet')
    const style = document.createElement('style')
    style.textContent = `${globalCss}\n${css}`
    document.head.appendChild(style)
    const wrapper = mountPage()
    try {
      // The platform's own page heading, as on the portal's pages.
      expect(wrapper.get('#role-title').classes()).toContain('page-title')
      const panel = getComputedStyle(wrapper.get('.role-option').element)
      expect(['', 'none']).toContain(panel.boxShadow)
      expect(panel.backgroundImage).not.toContain('gradient')
      expect(css).toContain('--registration-green: var(--dark-green)')
      expect(css).toContain('--registration-ink: var(--charcoal)')
      for (const rule of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
        if (!/\bh[1-6]\b/.test(rule[1]!)) continue
        const declaredSize = /font-size:\s*([^;]+);/.exec(rule[2]!)?.[1]
        if (!declaredSize) continue
        for (const unit of declaredSize.matchAll(/([\d.]+)(px|rem)/g)) {
          expect(Number(unit[1]) * (unit[2] === 'rem' ? 16 : 1)).toBeLessThanOrEqual(28)
        }
      }
    } finally {
      wrapper.unmount()
      style.remove()
    }
  })

  it('keeps student-created groups at up to five members, starting with just Member 1', async () => {
    const wrapper = mountPage()
    try {
      await clickButton(wrapper, 'Student')
      await clickButton(wrapper, 'I have a group')
      const setup = wrapper.vm as unknown as { currentStep: number }
      setup.currentStep = 2
      await wrapper.vm.$nextTick()
      expect(wrapper.findAll('.student-entry')).toHaveLength(2)
      for (let index = 0; index < 3; index += 1) await clickButton(wrapper, 'Add member')
      expect(wrapper.findAll('.student-entry')).toHaveLength(5)
      const add = wrapper.findAll('button').find((button) => button.text() === 'Add member')!
      expect(add.attributes('disabled')).toBeDefined()
      // Teammates may join later by the code: every one can be removed.
      for (let index = 0; index < 4; index += 1) await clickButton(wrapper, 'Remove')
      expect(wrapper.findAll('.student-entry')).toHaveLength(1)
      expect(
        wrapper.findAll('.student-entry__heading button').map((button) => button.text()),
      ).not.toContain('Remove')
    } finally {
      wrapper.unmount()
    }
  })

  it('joins a registered group by its code instead of creating one', async () => {
    const send = vi.fn<typeof fetch>(async (url) => {
      const path = String(url)
      if (path.endsWith('/group-code/482915/'))
        return new Response(JSON.stringify({ code: '482915', members: 3, full: false }))
      if (path.endsWith('/group-code/555555/'))
        return new Response(JSON.stringify({ code: '555555', members: 5, full: true }))
      if (/\/group-code\/\d+\/$/.test(path)) return new Response('{}', { status: 404 })
      return new Response(
        JSON.stringify({ code: '730214', token: 'held-token', expires_at: '2999-01-01T00:00:00Z' }),
      )
    })
    vi.stubGlobal('fetch', send)
    vi.useFakeTimers()
    const wrapper = mountPage()
    try {
      await clickButton(wrapper, 'Student')
      await clickButton(wrapper, 'I have a group')
      const setup = wrapper.vm as unknown as {
        currentStep: number
        validateCurrentStep: () => boolean
        errors: Record<string, string>
        forms: { studentTeam: { joinCode: string } }
      }
      setup.currentStep = 2
      await flushPromises()
      // Join a group, then OR, then creating one.
      const html = wrapper.html()
      expect(wrapper.text()).toContain('Join a group')
      expect(html.indexOf('student-team-join-code')).toBeLessThan(html.indexOf('or-divider'))
      expect(html.indexOf('or-divider')).toBeLessThan(html.indexOf('group-code__value'))
      // Its own Continue, before the OR: a code is needed for it.
      const joinContinue = () => wrapper.get('.group-join__actions button')
      expect(html.indexOf('group-join__actions')).toBeLessThan(html.indexOf('or-divider'))
      await joinContinue().trigger('click')
      expect(wrapper.text()).toContain('Enter the 6-digit group code.')
      // Add member beside the step's Continue.
      expect(wrapper.get('.form-footer').text()).toContain('Add member')

      const check = async (code: string) => {
        await wrapper.get('#student-team-join-code').setValue(code)
        await vi.advanceTimersByTimeAsync(300)
        await flushPromises()
      }
      await check('482915')
      expect(wrapper.text()).toContain(
        "You will join this group when you register. It has 3 of 5 members.",
      )
      // Joining: the group's own details aren't asked for.
      expect(wrapper.find('.or-divider').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('Group members')
      expect(wrapper.text()).not.toContain('Member 2')
      expect(setup.validateCurrentStep()).toBe(true)
      // The join's Continue is the step's: none in the footer, nor Add member.
      expect(wrapper.get('.form-footer').text()).not.toContain('Add member')
      expect(wrapper.get('.form-footer').text()).not.toContain('Continue')

      await check('555555')
      expect(wrapper.text()).toContain('This group already has 5 members.')
      expect(setup.validateCurrentStep()).toBe(false)
      await check('111111')
      expect(wrapper.text()).toContain('No group has this code. Check it with your group.')
      expect(setup.validateCurrentStep()).toBe(false)
      await check('12')
      expect(setup.validateCurrentStep()).toBe(false)
      expect(setup.errors['studentTeam.joinCode']).toBe('Enter the 6-digit group code.')

      // Cleared: back to creating one.
      await check('')
      expect(wrapper.find('.or-divider').exists()).toBe(true)
      expect(wrapper.text()).toContain('Group members')

      await check('482915')
      await joinContinue().trigger('click')
      await flushPromises()
      expect(setup.currentStep).toBe(3)
    } finally {
      wrapper.unmount()
      vi.useRealTimers()
    }
  })

  it.each([
    { mode: 'canonical', journey: 'Register as an individual student', choice: "I don't have a group", steps: 4 },
    { mode: 'canonical', journey: 'Register as a group', choice: 'I have a group', steps: 4 },
    { mode: 'canonical', journey: 'Register as a mentor', choice: '', steps: 4 },
    // Its one step has no tabs.
    { mode: 'supervisor', journey: 'Register one student', choice: 'Register one student', steps: 0 },
    { mode: 'supervisor', journey: 'Register a student group', choice: 'Register a student group', steps: 3 },
    { mode: 'supervisor', journey: 'Register students individually or outside of groups using a spreadsheet', choice: '', steps: 3 },
  ] as const)(
    'keeps numbered tabs without a percentage bar for $journey',
    async ({ mode, journey, choice, steps }) => {
      const wrapper = mountPage(mode)
      try {
        if (mode === 'canonical') {
          await clickButton(wrapper, journey === 'Register as a mentor' ? 'Mentor' : 'Student')
        }
        if (journey === 'Register students individually or outside of groups using a spreadsheet') await openCsvUpload(wrapper)
        else if (journey !== 'Register as a mentor') {
          await clickButton(wrapper, choice)
        }
        expect(wrapper.find('[role="progressbar"]').exists()).toBe(false)
        expect(wrapper.find('.form-progress').exists()).toBe(false)
        expect(wrapper.text()).not.toMatch(/\d+% complete/)
        const tabs = wrapper.findAll('.step-navigation button')
        expect(tabs.map((tab) => tab.find('span').text())).toEqual(
          Array.from({ length: steps }, (_, index) => String(index + 1)),
        )
        if (steps) expect(tabs[0]!.attributes('aria-current')).toBe('step')
        expect(wrapper.get('.journey-context h1').text()).toBe(journey)
        expect(wrapper.find('.journey-context > p').exists()).toBe(false)
        expect(wrapper.find('.step-header').exists()).toBe(false)
        const accessibleHeading = wrapper.get('.step-content > h2.sr-only')
        expect(accessibleHeading.attributes('tabindex')).toBe('-1')
        expect(wrapper.get('.step-content').attributes('aria-labelledby')).toBe(
          accessibleHeading.attributes('id'),
        )
        expect(accessibleHeading.text()).not.toBe('')
      } finally {
        wrapper.unmount()
      }
    },
  )
  it('resets the journey when a late invitation changes without remounting', async () => {
    const wrapper = mountPage()
    try {
      await clickButton(wrapper, 'Student')
      await clickButton(wrapper, 'I have a group')
      await wrapper.setProps({ invitationToken: 'late-token' })
      expect(wrapper.find('.role-options').exists()).toBe(true)
      await clickButton(wrapper, 'Student')
      expect(wrapper.text()).not.toContain('I have a group')
      await wrapper.setProps({ invitationToken: null })
      await clickButton(wrapper, 'Student')
      expect(wrapper.text()).toContain('I have a group')
    } finally {
      wrapper.unmount()
    }
  })
  it('limits a late link to a single student', async () => {
    const previous = window.location.href
    window.history.replaceState({}, '', '/#/register?invite=test-token')
    const wrapper = mountPage()
    try {
      expect(wrapper.text()).not.toContain('Mentor')
      expect(wrapper.findAll('.role-option').map((option) => option.get('strong').text())).toEqual(['Student'])
      await clickButton(wrapper, 'Student')
      expect(wrapper.text()).toContain('Register as an individual student')
      expect(wrapper.text()).not.toContain('Register as a group')
    } finally {
      wrapper.unmount()
      window.history.replaceState({}, '', previous)
    }
  })
  it('says registration is closed while its dates have closed it', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        new Response(JSON.stringify(String(url).includes('/registration-open/') ? { open_now: false } : {})),
      ),
    )
    const wrapper = mountPage()
    try {
      await flushPromises()
      expect(wrapper.get('.page-title').text()).toBe('Registration is closed')
      expect(wrapper.find('.role-options').exists()).toBe(false)
      // A supervisor still registers their students.
      const supervisor = mountPage('supervisor')
      await flushPromises()
      expect(supervisor.text()).not.toContain('Registration is closed')
      supervisor.unmount()
    } finally {
      wrapper.unmount()
      setRegistrationState(OPEN)
    }
  })

  it("closes a supervisor's registration once its dates have, unless they're let register after", async () => {
    const closed = { open_now: false, opens_at: null, closes_at: '2026-10-01T00:00:00Z' }
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        new Response(
          JSON.stringify(
            String(url).includes('/registration-open/') ? { ...closed, can_register_students: false } : {},
          ),
        ),
      ),
    )
    const supervisor = mountPage('supervisor')
    try {
      await flushPromises()
      expect(supervisor.get('.page-title').text()).toBe('Registration is closed')
      expect(supervisor.text()).toContain("students can't be registered here")
      // No Back to the sign-in page from the portal.
      expect(supervisor.find('.setup-back').exists()).toBe(false)
      setRegistrationState({ ...closed, can_register_students: true })
      await flushPromises()
      expect(supervisor.text()).not.toContain('Registration is closed')
    } finally {
      supervisor.unmount()
      setRegistrationState(OPEN)
    }
  })

  it('offers students, supervisors and mentors their registration', async () => {
    const wrapper = mountPage()

    expect(wrapper.text()).not.toContain('guardian consent invitation')
    expect(wrapper.find('.welcome-layout').exists()).toBe(false)
    expect(wrapper.text()).toContain('Who are you registering as?')
    expect(wrapper.text()).not.toContain('Guardian')
    expect(wrapper.findAll('.role-option').map((option) => option.get('strong').text())).toEqual([
      'Student',
      'Mentor',
      'Supervisor',
    ])
    expect(wrapper.find('.setup-progress').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Registration setup')
    expect(wrapper.text()).not.toContain('Step 1 of 2')
    expect(wrapper.find('.page-header > p').exists()).toBe(false)

    await clickButton(wrapper, 'Student')
    expect(wrapper.get('.page-title').text()).toBe('Do you have a group?')
    expect(wrapper.text()).toContain('I have a group')
    expect(wrapper.text()).toContain("I don't have a group")
    expect(wrapper.find('.setup-progress').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Registration setup')
    expect(wrapper.text()).not.toContain('Step 2 of 2')
    expect(wrapper.find('.page-header > p').exists()).toBe(false)
  })

  it('preserves conditional mentor affiliation fields and pending-review copy', async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Mentor')
    // Contact, Affiliation, Mentoring, Review: no Compliance step.
    expect(wrapper.findAll('.step-navigation li')).toHaveLength(4)
    expect(wrapper.text()).not.toContain('Compliance')

    const setup = wrapper.vm as unknown as {
      currentStep: number
      forms: { mentor: { affiliation: string } }
    }
    setup.currentStep = 1
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Current affiliation')
    expect(wrapper.text()).not.toContain('Company or organisation')

    setup.forms.mentor.affiliation = 'industry'
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Company or organisation')

    setup.currentStep = 3
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Mentoring')
    expect(wrapper.text()).not.toContain('Matching access')
    expect(wrapper.text()).not.toContain('Safeguarding')
    expect(wrapper.text()).not.toContain('Before you submit')
  })

  it('preserves CSV preview and explicit invalid-row exclusion controls', async () => {
    const wrapper = mountPage('supervisor')
    await openCsvUpload(wrapper)

    const setup = wrapper.vm as unknown as {
      currentStep: number
      forms: {
        supervisorCsv: {
          rows: Array<{
            rowNumber: number
            values: Record<string, string>
            category: string
            issues: string[]
          }>
        }
      }
    }
    setup.forms.supervisorCsv.rows = [
      {
        rowNumber: 2,
        values: {
          first_name: 'Alex',
          last_name: 'Morgan',
          email: 'invalid',
        },
        category: 'invalid',
        issues: ['Student email format is invalid.'],
      },
    ]
    setup.currentStep = 1
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Student email format is invalid.')
    expect(wrapper.text()).toContain('Exclude')
  })

  it('explains guardian permission on the contact step without a before-submit bubble', async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, "I don't have a group")

    const setup = wrapper.vm as unknown as { currentStep: number }
    setup.currentStep = 2
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain(
      'Your nominated guardian must provide permission through the existing guardian consent process',
    )
    expect(wrapper.text()).toContain(
      'before you can access most features of the program.',
    )
    expect(wrapper.text()).toContain('It does not send a permission email or record consent.')
    // A nominated supervisor is their name and email: no type or school.
    expect(wrapper.text()).not.toContain('Teacher / school supervisor')
    expect(wrapper.text()).not.toContain('Nominated parent-supervisor')
    expect(wrapper.text()).not.toContain('Supervisor school')
    expect(wrapper.text()).not.toContain('Existing school supervisor')
    setup.currentStep = 3
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).not.toContain('Before you submit')
  })

  it('starts every supervisor flow at its first student, group, or upload field', async () => {
    const wrapper = mountPage('supervisor')

    expect(wrapper.find('.registration-header').exists()).toBe(false)
    expect(wrapper.text()).toContain('Register students')
    expect(wrapper.text()).not.toContain('How are you registering students?')
    expect(wrapper.text()).not.toContain('Step 2 of 2')
    // The platform's own page heading, as on the portal's other pages.
    expect(wrapper.find('#pathway-title').classes()).toContain('page-title')
    await clickButton(wrapper, 'Register one student')
    // One step, no Review: no steps to show, and it registers from here.
    expect(wrapper.find('.step-navigation').exists()).toBe(false)
    expect(wrapper.find('.review-step').exists()).toBe(false)
    expect(wrapper.find('.form-footer button[type="submit"]').text()).toBe('Submit registration')
    expect(wrapper.find('#supervisorIndividual-student-email').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Confirm the signed-in account')
    expect(wrapper.find('.form-progress').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('School-only grouping')
    expect(wrapper.text()).not.toContain('Cross-school grouping')

    // A group starts at its students; its Mutual Area(s) of Interest come after.
    const group = mountPage('supervisor')
    await clickButton(group, 'Register a student group')
    expect(group.text()).toContain('Add 2–5 students')
    expect(group.find('#supervisorGroup-students-0-email').exists()).toBe(true)
    expect(group.text()).not.toContain('Mutual Area(s) of Interest')

    const csv = mountPage('supervisor')
    await openCsvUpload(csv)
    expect(csv.text()).toContain('Choose completed .xlsx or .csv')
  })

  it('puts the creator profile before team configuration and removes naming', async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, 'I have a group')

    const labels = wrapper.findAll('.step-navigation__label').map((item) => item.text())
    expect(labels).toEqual(['Your details', 'Your profile', 'Group', 'Review'])
    expect(wrapper.text()).not.toContain('Custom team name')
    expect(wrapper.text()).not.toContain('Automatic BTF name')
  })

  it('asks every student for their email once, with no confirming it', async () => {
    const team = mountPage()
    await clickButton(team, 'Student')
    await clickButton(team, 'I have a group')
    const teamSetup = team.vm as unknown as { currentStep: number }
    teamSetup.currentStep = 2
    await team.vm.$nextTick()
    expect(team.text()).not.toContain('Confirm student email')

    const individual = mountPage()
    await clickButton(individual, 'Student')
    await clickButton(individual, "I don't have a group")
    expect(individual.text()).not.toContain('Confirm student email')
    expect(
      individual.get('#studentIndividual-student-email').element.closest('.registration-field')
        ?.classList.contains('registration-field--wide'),
    ).toBe(true)

    const supervisor = mountPage('supervisor')
    await clickButton(supervisor, 'Register one student')
    const supervisorSetup = supervisor.vm as unknown as { currentStep: number }
    supervisorSetup.currentStep = 0
    await supervisor.vm.$nextTick()
    expect(supervisor.text()).not.toContain('Confirm student email')

    const group = mountPage('supervisor')
    await clickButton(group, 'Register a student group')
    const groupSetup = group.vm as unknown as { currentStep: number }
    groupSetup.currentStep = 1
    await group.vm.$nextTick()
    expect(group.text()).not.toContain('Confirm student email')
    expect(group.text()).not.toContain('group name')

    const csv = mountPage('supervisor')
    await openCsvUpload(csv)
    const csvSetup = csv.vm as unknown as { currentStep: number }
    csvSetup.currentStep = 0
    await csv.vm.$nextTick()
    expect(csv.text()).not.toContain('Confirm student email')
  })

  it('adds students to Register one student on the same page, then a Review step until they go again', async () => {
    const wrapper = mountPage('supervisor')
    await clickButton(wrapper, 'Register one student')
    expect(wrapper.find('.step-navigation').exists()).toBe(false)
    const add = wrapper.findAll('.form-footer button').find((button) => button.text() === 'Add student')!
    await add.trigger('click')

    expect(wrapper.get('.page-title').text()).toBe('Register one student')
    expect(wrapper.findAll('.step-navigation__label').map((item) => item.text())).toEqual([
      'Student',
      'Review',
    ])
    expect(wrapper.find('.form-footer button[type="submit"]').text()).toBe('Continue')
    expect(wrapper.findAll('.student-entry__heading h3').map((heading) => heading.text())).toEqual([
      'Student 1',
      'Student 2',
    ])
    expect(wrapper.find('#supervisorIndividual-student-email').exists()).toBe(true)
    expect(wrapper.find('#supervisorIndividual-extraStudents-0-email').exists()).toBe(true)

    // Student 2 can go again; Student 1 can't.
    const removes = wrapper.findAll('.student-entry__heading button')
    expect(removes).toHaveLength(1)
    await removes[0]!.trigger('click')
    expect(wrapper.find('.student-entry__heading').exists()).toBe(false)
    // On its own again: no Review.
    expect(wrapper.find('.step-navigation').exists()).toBe(false)
    expect(wrapper.find('.form-footer button[type="submit"]').text()).toBe('Submit registration')
  })

  it("lets a student leave out their supervisor, but asks for all of one that's started", async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, "I don't have a group")
    const setup = wrapper.vm as unknown as {
      currentStep: number
      validateCurrentStep: () => boolean
      errors: Record<string, string>
      forms: { studentIndividual: { supervisor: { firstName: string } } }
    }
    setup.currentStep = 2
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('A supervisor is usually a teacher, but can also be a guardian.')
    // No * on the supervisor's fields.
    for (const id of ['first', 'last', 'email']) {
      expect(wrapper.get(`#student-individual-supervisor-${id}-label`).text()).not.toContain('*')
    }

    setup.validateCurrentStep()
    expect(Object.keys(setup.errors).some((key) => key.includes('.supervisor.'))).toBe(false)

    setup.forms.studentIndividual.supervisor.firstName = 'Sam'
    setup.validateCurrentStep()
    expect(setup.errors['studentIndividual.supervisor.lastName']).toBeTruthy()
    expect(setup.errors['studentIndividual.supervisor.email']).toBeTruthy()
  })

  it("starts each member in Member 1's country, and offers the group's schools", async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, 'I have a group')
    const setup = wrapper.vm as unknown as {
      currentStep: number
      forms: { studentTeam: { creator: { country: string; school: string }; teammates: { country: string; state: string }[] } }
      addStudentTeammate: () => void
    }
    // Member 2 starts before Member 1 picks: it follows Member 1's country.
    setup.forms.studentTeam.creator.country = 'New Zealand'
    setup.forms.studentTeam.creator.school = 'Kiwi High'
    await wrapper.vm.$nextTick()
    expect(setup.forms.studentTeam.teammates[0].country).toBe('New Zealand')
    // One added later starts there too; one who chose another keeps it.
    setup.forms.studentTeam.teammates[0].country = 'Fiji'
    setup.addStudentTeammate()
    expect(setup.forms.studentTeam.teammates[1].country).toBe('New Zealand')
    setup.forms.studentTeam.creator.country = 'Australia'
    await wrapper.vm.$nextTick()
    expect(setup.forms.studentTeam.teammates.map((teammate) => teammate.country)).toEqual(['Fiji', 'Australia'])

    setup.currentStep = 2
    await wrapper.vm.$nextTick()
    await wrapper.get('#studentTeam-teammates-0-school').trigger('focus')
    expect(wrapper.findAll('.registration-field__suggestion').map((option) => option.text())).toEqual(['Kiwi High'])
  })

  it("asks every group member for their school, year and location, as Member 1's", async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, 'I have a group')
    const setup = wrapper.vm as unknown as {
      currentStep: number
      validateCurrentStep: () => boolean
      errors: Record<string, string>
    }
    setup.currentStep = 2
    await wrapper.vm.$nextTick()
    for (const field of ['school', 'yearLevel', 'country', 'state']) {
      expect(wrapper.find(`#studentTeam-teammates-0-${field}`).exists()).toBe(true)
    }
    // Every member's own Areas of Interest (optional), as Member 1's.
    expect(wrapper.find('input[name="studentTeam-teammates-0-interests"]').exists()).toBe(true)

    // Left empty, Member 2 isn't asked for (Member 1 may register alone).
    setup.validateCurrentStep()
    expect(Object.keys(setup.errors).filter((key) => key.includes('teammates'))).toEqual([])
    // Any of it given, all of it is.
    await wrapper.get('#studentTeam-teammates-0-firstName').setValue('Jamie')
    setup.validateCurrentStep()
    expect(setup.errors['studentTeam.teammates.0.lastName']).toBeTruthy()
    expect(setup.errors['studentTeam.teammates.0.email']).toBeTruthy()
    expect(setup.errors['studentTeam.teammates.0.school']).toBeTruthy()
    expect(setup.errors['studentTeam.teammates.0.yearLevel']).toBeTruthy()
  })

  it("starts a supervisor's students in their country, and offers their school and state", async () => {
    const { setActivePinia } = await import('pinia')
    const { useAuthStore } = await import('@/stores/auth')
    const pinia = createPinia()
    setActivePinia(pinia)
    useAuthStore().user = {
      id: 9, email: 'grace@school.edu', first_name: 'Grace', last_name: 'Green', current_role_name: 'supervisor',
      supervisor_school_name: 'Kiwi High', country: { id: 2, countryName: 'New Zealand' }, state: { id: 5, stateName: 'Auckland' },
    } as never
    const wrapper = mount(RegistrationPage, {
      props: { mode: 'supervisor' },
      global: { plugins: [pinia], stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } },
    })
    await clickButton(wrapper, 'Register a student group')
    const setup = wrapper.vm as unknown as {
      currentStep: number
      forms: { supervisorGroup: { students: { country: string; school: string }[] } }
      addSupervisorGroupStudent: () => void
    }
    expect(setup.forms.supervisorGroup.students.map((student) => student.country)).toEqual(['New Zealand', 'New Zealand'])
    setup.addSupervisorGroupStudent()
    expect(setup.forms.supervisorGroup.students[2].country).toBe('New Zealand')

    setup.forms.supervisorGroup.students[0].school = 'Cardinal College'
    setup.currentStep = 0
    await flushPromises()
    await wrapper.get('#supervisorGroup-students-1-school').trigger('focus')
    expect(wrapper.findAll('.registration-field__suggestion').map((option) => option.text())).toEqual([
      'Kiwi High',
      'Cardinal College',
    ])
    await wrapper.get('#supervisorGroup-students-1-school').trigger('blur')
    await wrapper.get('#supervisorGroup-students-1-state').trigger('focus')
    expect(wrapper.findAll('.registration-field__suggestion').map((option) => option.text())).toEqual(['Auckland'])
  })

  it("asks a group's interests after its students: all theirs ticked, every area by how many chose it", async () => {
    const wrapper = mountPage('supervisor')
    await clickButton(wrapper, 'Register a student group')
    const setup = wrapper.vm as unknown as {
      currentStep: number
      forms: { supervisorGroup: { students: { interests: string[] }[]; interests: string[] } }
    }
    setup.forms.supervisorGroup.students[0].interests = ['Space & Astrobiology', 'Water & Energy Tech']
    setup.forms.supervisorGroup.students[1].interests = ['Water & Energy Tech']
    setup.currentStep = 1
    await flushPromises()

    // What both chose is ticked; the list puts the most chosen first.
    expect(setup.forms.supervisorGroup.interests).toEqual(['Water & Energy Tech'])
    const labels = wrapper.findAll('.interest-selector__options label').map((label) => label.text())
    expect(labels[0]).toBe('Water & Energy Tech 2 of 2')
    expect(labels[1]).toBe('Space & Astrobiology 1 of 2')
    expect(labels).toHaveLength(9)

    // Back to the students, then here again: one ticked already (as a saved
    // draft's), and what they now all chose ticked beside it.
    setup.currentStep = 0
    await flushPromises()
    setup.forms.supervisorGroup.interests = ['Food & Agriculture Technology']
    setup.forms.supervisorGroup.students[1].interests = ['Water & Energy Tech', 'Space & Astrobiology']
    setup.currentStep = 1
    await flushPromises()
    expect(setup.forms.supervisorGroup.interests).toEqual([
      'Food & Agriculture Technology',
      'Space & Astrobiology',
      'Water & Energy Tech',
    ])
  })

  it('turns a group down to one student into Register one student, with no policies to tick', async () => {
    const wrapper = mountPage('supervisor')
    await clickButton(wrapper, 'Register a student group')
    const setup = wrapper.vm as unknown as {
      journey: string
      forms: {
        supervisorGroup: { students: { firstName: string }[] }
        supervisorIndividual: { student: { firstName: string } }
      }
    }
    setup.forms.supervisorGroup.students[0].firstName = 'Ada'
    await wrapper.vm.$nextTick()
    const remove = () =>
      wrapper.findAll('.student-entry__heading button').filter((button) => button.text().includes('Remove'))
    // Student 1 always stays; Student 2 can go.
    expect(remove()).toHaveLength(1)
    await remove()[0].trigger('click')
    await flushPromises()

    expect(setup.journey).toBe('supervisor_individual')
    expect(setup.forms.supervisorIndividual.student.firstName).toBe('Ada')
    expect(wrapper.find('.step-navigation').exists()).toBe(false)
    // A supervisor registering students isn't agreeing for them.
    expect(wrapper.find('[data-test="policies-agree"]').exists()).toBe(false)
  })

  it("suggests Management's known universities as a mentor types theirs", async () => {
    const universities = ['Monash University', 'The University of Sydney', 'UNSW Sydney']
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>(async (url) =>
        new Response(JSON.stringify(String(url).includes('/universities/') ? { universities } : { countries: [] })),
      ),
    )
    const wrapper = mountPage()
    await clickButton(wrapper, 'Mentor')
    const setup = wrapper.vm as unknown as { currentStep: number; forms: { mentor: { affiliation: string; institution: string } } }
    setup.forms.mentor.affiliation = 'academic'
    setup.currentStep = 1
    await flushPromises()

    const institution = wrapper.get('#mentor-institution')
    await institution.trigger('focus')
    expect(wrapper.findAll('.registration-field__suggestion').map((option) => option.text())).toEqual(universities)
    setup.forms.mentor.institution = 'sydney'
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.registration-field__suggestion').map((option) => option.text())).toEqual([
      'The University of Sydney',
      'UNSW Sydney',
    ])
    vi.unstubAllGlobals()
  })

  it("asks a mentor only why they'd mentor, in 150 words at most", async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Mentor')
    const setup = wrapper.vm as unknown as {
      currentStep: number
      validateCurrentStep: () => boolean
      errors: Record<string, string>
      forms: { mentor: { interests: string[]; capacity: string; motivation: string } }
    }
    setup.currentStep = 2
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Why would you like to mentor?')
    for (const gone of ['How would you mentor BIOTech groups?', 'Relevant background', 'Hours per week']) {
      expect(wrapper.text()).not.toContain(gone)
    }
    expect(wrapper.find('#mentor-hours').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Weekly availability')
    expect(wrapper.text()).toContain('0 / 150 words')

    Object.assign(setup.forms.mentor, {
      interests: ['Biomedical Innovations'],
      capacity: '2',
      motivation: 'word '.repeat(151),
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('151 / 150 words')
    setup.validateCurrentStep()
    expect(setup.errors['mentor.motivation']).toBe('Keep this to 150 words or fewer.')

    setup.forms.mentor.motivation = 'To help.'
    expect(setup.validateCurrentStep()).toBe(true)
    for (const gone of ['weeklyHours', 'background', 'mentoringApproach']) {
      expect(setup.forms.mentor).not.toHaveProperty(gone)
    }
  })

  it("holds the group's code on its Group step, to copy and share", async () => {
    const send = vi.fn<typeof fetch>(async (url) =>
      new Response(
        JSON.stringify(
          String(url).includes('/group-code/')
            ? { code: '482915', token: 'held-token', expires_at: '2999-01-01T00:00:00Z' }
            : {},
        ),
      ),
    )
    vi.stubGlobal('fetch', send)
    const writeText = vi.fn(async () => {})
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    const wrapper = mountPage()
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, 'I have a group')
    const setup = wrapper.vm as unknown as {
      currentStep: number
      forms: { studentTeam: { groupCode: string; groupCodeToken: string } }
    }
    setup.currentStep = 2
    await flushPromises()

    const block = wrapper.get('.group-code')
    expect(block.get('.group-code__value').text()).toBe('482915')
    expect(block.text()).toContain('Save this code for future reference and share it with your teammates.')
    expect(block.text()).toContain('held for you for 24 hours until you register')
    // Before the group's interests.
    const html = wrapper.html()
    expect(html.indexOf('group-code')).toBeLessThan(html.indexOf('Group members'))
    await block.get('button').trigger('click')
    expect(writeText).toHaveBeenCalledWith('482915')
    expect(setup.forms.studentTeam.groupCodeToken).toBe('held-token')

    // Held once: back to the step again asks for no other.
    setup.currentStep = 1
    await flushPromises()
    setup.currentStep = 2
    await flushPromises()
    expect(send.mock.calls.filter(([url]) => String(url).includes('/group-code/'))).toHaveLength(1)

    // On Review too, beside the code.
    setup.currentStep = 3
    await flushPromises()
    writeText.mockClear()
    await wrapper.get('.review-copy button').trigger('click')
    expect(writeText).toHaveBeenCalledWith('482915')
  })

  it('keeps a public registration in progress through a refresh, and lets it go once registered', async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, "I don't have a group")
    const setup = wrapper.vm as unknown as {
      forms: { studentIndividual: { student: { firstName: string } } }
      success: unknown
    }
    setup.forms.studentIndividual.student.firstName = 'Ada'
    await new Promise((resolve) => setTimeout(resolve, 300))
    wrapper.unmount()

    // As after a refresh: the option and what was typed are back.
    const again = mountPage()
    await again.vm.$nextTick()
    expect(again.get('.page-title').text()).toBe('Register as an individual student')
    expect(again.get('#studentIndividual-student-firstName').element).toHaveProperty('value', 'Ada')

    ;(again.vm as unknown as { success: unknown }).success = {
      referenceCode: 'REG-1',
      journey: 'student_individual',
      studentCount: 1,
      submittedAt: '2026-10-17T00:00:00Z',
    }
    await again.vm.$nextTick()
    expect(sessionStorage.getItem('biotech.registration.draft')).toBeNull()
  })

  it("keeps no supervisor's registration in progress", async () => {
    const wrapper = mountPage('supervisor')
    await clickButton(wrapper, 'Register one student')
    await new Promise((resolve) => setTimeout(resolve, 300))
    expect(sessionStorage.getItem('biotech.registration.draft')).toBeNull()
  })

  it('holds a new group code once a kept one has run out', async () => {
    const send = vi.fn<typeof fetch>(async (url) =>
      new Response(
        JSON.stringify(
          String(url).includes('/group-code/')
            ? { code: '730214', token: 'new-token', expires_at: '2999-01-01T00:00:00Z' }
            : {},
        ),
      ),
    )
    vi.stubGlobal('fetch', send)
    const wrapper = mountPage()
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, 'I have a group')
    const setup = wrapper.vm as unknown as {
      currentStep: number
      forms: {
        studentTeam: { groupCode: string; groupCodeToken: string; groupCodeExpiresAt: string }
      }
    }
    // As a kept (restored) code whose 24 hours are up.
    Object.assign(setup.forms.studentTeam, {
      groupCode: '111111',
      groupCodeToken: 'old-token',
      groupCodeExpiresAt: '2000-01-01T00:00:00Z',
    })
    setup.currentStep = 2
    await flushPromises()
    expect(wrapper.get('.group-code__value').text()).toBe('730214')
    expect(setup.forms.studentTeam.groupCodeToken).toBe('new-token')
  })

  it('opens the steps already filled in when coming back to a form', async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, "I don't have a group")
    const setup = wrapper.vm as unknown as {
      forms: { studentIndividual: { student: Record<string, unknown> } }
      changeJourney: () => void
    }
    // About you and School & profile filled in, then Back.
    Object.assign(setup.forms.studentIndividual.student, {
      firstName: 'Ada',
      lastName: 'Lovelace',
      email: 'ada@example.com',
      school: 'Example High',
      yearLevel: '10',
      country: 'Australia',
      state: 'NSW',
    })
    setup.changeJourney()
    await wrapper.vm.$nextTick()
    await clickButton(wrapper, "I don't have a group")

    const disabled = wrapper
      .findAll('.step-navigation button')
      .map((button) => button.attributes('disabled') !== undefined)
    // About you, School & profile and Support open; Review not yet.
    expect(disabled).toEqual([false, false, false, true])
  })

  it('offers a supervisor all three ways to register students', () => {
    const wrapper = mountPage('supervisor')
    expect(wrapper.text()).toContain('Register one student')
    expect(wrapper.text()).toContain('Register a student group')
    expect(wrapper.text()).toContain('Register students individually or outside of groups using a spreadsheet')
  })

  it("offers the database's countries, and Australia's states, as dropdowns", async () => {
    const countries = ['Australia', 'New Zealand']
    const states = ['ACT', 'NSW', 'NT', 'QLD', 'SA', 'TAS', 'VIC', 'WA']
    const send = vi.fn<typeof fetch>(async (url) =>
      new Response(JSON.stringify(String(url).includes('/states/') ? { states } : { countries })),
    )
    vi.stubGlobal('fetch', send)
    const wrapper = mountPage('supervisor')
    await clickButton(wrapper, 'Register one student')
    await flushPromises()
    const country = () => wrapper.find('#supervisorIndividual-student-country')
    const state = () => wrapper.find('#supervisorIndividual-student-state')

    const asked = () => send.mock.calls.map(([url]) => String(url))
    expect(asked().some((url) => url.includes('/api/v1/registration/countries/'))).toBe(true)
    // Dropdowns (a combobox's field), each choice as the database names it,
    // and none chosen for them.
    expect(country().attributes('role')).toBe('combobox')
    expect(appSelectText(wrapper, '#supervisorIndividual-student-country')).toBe('')
    expect(await appSelectLabels(wrapper, '#supervisorIndividual-student-country')).toEqual(countries)
    await pickAppSelect(wrapper, '#supervisorIndividual-student-country', 'Australia')
    await flushPromises()
    expect(asked().some((url) => url.includes('/api/v1/registration/states/?country=Australia'))).toBe(true)
    await country().trigger('blur')
    expect(state().attributes('role')).toBe('combobox')
    expect(wrapper.get('#supervisorIndividual-student-state-label').text()).toBe('State *')
    expect(await appSelectLabels(wrapper, '#supervisorIndividual-student-state')).toEqual(states)
    await pickAppSelect(wrapper, '#supervisorIndividual-student-state', 'VIC')
    expect(appSelectText(wrapper, '#supervisorIndividual-student-state')).toBe('VIC')

    await pickAppSelect(wrapper, '#supervisorIndividual-student-country', 'New Zealand')
    // A text box to type in.
    expect(state().element.tagName).toBe('INPUT')
    expect(state().attributes('role')).toBeUndefined()
    // Elsewhere still State, but optional; the Australian state isn't kept.
    expect(wrapper.get('#supervisorIndividual-student-state-label').text()).toBe('State (Optional)')
    expect((state().element as HTMLInputElement).value).toBe('')
  })

  it("shows a supervisor's saved registration as the steps' last page, with what Review showed", async () => {
    const wrapper = mountPage('supervisor')
    await clickButton(wrapper, 'Register a student group')
    const setup = wrapper.vm as unknown as { success: unknown }
    setup.success = {
      referenceCode: 'REG-1',
      journey: 'supervisor_group',
      studentCount: 1,
      submittedAt: '2026-10-16T00:08:00Z',
    }
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.success-body .form-footer').exists()).toBe(true)
    expect(wrapper.get('.page-title').text()).toBe('Register a student group')
    expect(wrapper.findAll('.step-navigation .tab-pill.complete')).toHaveLength(3)
    const body = wrapper.get('.success-body')
    expect(body.get('h3').text()).toBe('Registration Complete')
    expect(body.text()).not.toContain('REG-1')
    // What Review showed (the group's students), then when it was registered.
    expect(body.findAll('.review-section h3').map((heading) => heading.text())).toEqual([
      'Group members',
    ])
    // The last section's last row.
    const completed = body.findAll('.review-section dl > div').at(-1)!
    expect(completed.get('dt').text()).toBe('Registration completed')
    expect(completed.get('dd').text()).toMatch(/16 Oct|15 Oct/)
    // Back on top to the options; one button for another group.
    expect(body.get('.form-footer').text()).toBe('Register Another Group')
    expect(wrapper.get('.journey-context .back-button').text()).toBe('Back')

    await body.get('.form-footer button').trigger('click')
    expect(wrapper.find('.success-body').exists()).toBe(false)
    expect(wrapper.get('.page-title').text()).toBe('Register a student group')
    expect(wrapper.get('.step-navigation .tab-pill').attributes('aria-current')).toBe('step')
  })

  it("goes back to the options from a supervisor's saved registration", async () => {
    const wrapper = mountPage('supervisor')
    await clickButton(wrapper, 'Register a student group')
    const setup = wrapper.vm as unknown as { success: unknown }
    setup.success = {
      referenceCode: 'REG-1',
      journey: 'supervisor_group',
      studentCount: 1,
      submittedAt: '2026-10-16T00:08:00Z',
    }
    await wrapper.vm.$nextTick()

    await wrapper.get('.journey-context .back-button').trigger('click')
    expect(wrapper.find('.success-body').exists()).toBe(false)
    expect(wrapper.text()).toContain('Register students')
  })

  it("gives a supervisor's student one full width email, and Areas of Interest with no *", async () => {
    const wrapper = mountPage('supervisor')
    await clickButton(wrapper, 'Register one student')
    const email = wrapper.get('#supervisorIndividual-student-email').element.closest('.registration-field')
    expect(email?.classList.contains('registration-field--wide')).toBe(true)

    const legend = wrapper.get('.interest-selector legend')
    expect(legend.text()).toBe('Area(s) of Interest')
    expect(wrapper.text()).not.toContain('Choose one or more areas')
  })

  it("shows Member 1's own interests, the group's on Group, and optional member guardian contact", async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, 'I have a group')
    const setup = wrapper.vm as unknown as {
      currentStep: number
      maxReachedStep: number
      forms: { studentTeam: { creator: ReturnType<typeof createStudent> } }
    }
    Object.assign(setup.forms.studentTeam.creator, {
      firstName: 'Jordan',
      lastName: 'Rivera',
      email: 'jordan@example.test',
    })
    setup.currentStep = 1
    await wrapper.vm.$nextTick()
    // Member 1's own Areas of Interest, after their State; the group's are on Group.
    expect(wrapper.get('.interest-selector legend').text()).toBe('Area(s) of Interest')
    const html = wrapper.html()
    expect(html.indexOf('studentTeam-creator-state')).toBeLessThan(html.indexOf('interest-selector'))
    expect(wrapper.text()).not.toContain('Mutual Area(s) of Interest')
    // Their guardian on Your profile, after their profile; their supervisor on Group.
    expect(wrapper.text()).not.toContain('A supervisor is usually a teacher, but can also be a guardian.')
    expect(wrapper.text()).not.toContain('Add guardian contact (optional)')
    expect(
      wrapper.get('#studentTeam-creator-guardian-firstName').attributes('required'),
    ).toBeDefined()
    expect(html.indexOf('studentTeam-creator-profilePhoto')).toBeLessThan(
      html.indexOf('studentTeam-creator-guardian-firstName'),
    )
    setup.currentStep = 2
    setup.maxReachedStep = 2
    await wrapper.vm.$nextTick()
    // The supervisor before Member 1, and no shared interests.
    expect(wrapper.text()).toContain('A supervisor is usually a teacher, but can also be a guardian.')
    expect(wrapper.text()).not.toContain('Mutual Area(s) of Interest')
    const group = wrapper.html()
    expect(group.indexOf('student-team-supervisor-first')).toBeLessThan(
      group.indexOf('Group members'),
    )
    // Group members just before Member 1.
    expect(group.indexOf('Group members')).toBeLessThan(group.indexOf('Member 1 (You)'))
    expect(wrapper.text()).toContain('Member 1 (You)')
    expect(wrapper.text()).toContain('Jordan Rivera')
    expect(wrapper.text()).toContain('jordan@example.test')
    expect(wrapper.text()).toContain('Member 2')
    expect(wrapper.text()).toContain('There may be up to 5 students per group.')
    const optional = wrapper.get('.defer-control input')
    expect((optional.element as HTMLInputElement).checked).toBe(false)
    expect(wrapper.find('#studentTeam-teammates-0-guardian-firstName').exists()).toBe(false)
    await optional.setValue(true)
    expect(wrapper.find('#studentTeam-teammates-0-guardian-firstName').exists()).toBe(true)
    await clickButton(wrapper, 'Edit your details')
    expect(setup.currentStep).toBe(0)
    expect(wrapper.get('#studentTeam-creator-firstName').element).toHaveProperty('value', 'Jordan')
  })

  it("registers a supervisor as a mentor's registration goes: contact, school, review", async () => {
    const wrapper = mountPage()
    // No invitation to ask Support for any more.
    expect(wrapper.text()).not.toContain('for an invitation')
    await clickButton(wrapper, 'Supervisor')
    expect(wrapper.get('.journey-context .page-title').text()).toBe('Register as a supervisor')
    expect(wrapper.findAll('.step-navigation .tab-pill').map((step) => step.text())).toEqual([
      '1Contact',
      '2School & profile',
      '3Review',
    ])

    const setup = wrapper.vm as unknown as {
      currentStep: number
      validateCurrentStep: () => boolean
      errors: Record<string, string>
      forms: { supervisor: Record<string, string> }
    }
    // Their name and email first.
    expect(wrapper.find('#supervisor-email').exists()).toBe(true)
    expect(wrapper.find('#supervisor-school').exists()).toBe(false)
    expect(setup.validateCurrentStep()).toBe(false)
    expect(setup.errors).toMatchObject({
      'supervisor.firstName': 'Enter your first name.',
      'supervisor.lastName': 'Enter your last name.',
      'supervisor.email': 'Enter the email.',
    })
    Object.assign(setup.forms.supervisor, { firstName: 'Sam', lastName: 'Teacher', email: 'teacher@example.com' })
    expect(setup.validateCurrentStep()).toBe(true)

    // Then their school with teacher or parent beside it, where it is (a
    // state in Australia), and a student's optional pronouns and photo.
    setup.currentStep = 1
    await wrapper.vm.$nextTick()
    expect(wrapper.find('#supervisor-email').exists()).toBe(false)
    const grid = wrapper.findAll('.field-grid .registration-field__label').map((label) => label.text())
    expect(grid.slice(0, 2)).toEqual(['School *', 'Teacher or parent *'])
    expect(wrapper.find('#supervisor-pronouns').exists()).toBe(true)
    expect(wrapper.find('#supervisor-profilePhoto').exists()).toBe(true)
    setup.forms.supervisor.country = 'Australia'
    setup.forms.supervisor.pronouns = 'Other'
    expect(setup.validateCurrentStep()).toBe(false)
    expect(setup.errors).toMatchObject({
      'supervisor.school': 'Enter your school.',
      'supervisor.relationship': 'Choose teacher or parent.',
      'supervisor.state': 'Enter your state.',
      'supervisor.pronounsOther': 'Enter your pronouns.',
    })
    Object.assign(setup.forms.supervisor, {
      school: 'Example High',
      relationship: 'parent',
      state: 'NSW',
      pronouns: 'she/her',
    })
    expect(setup.validateCurrentStep()).toBe(true)

    // Review, with the policies to agree to before Submit registration.
    setup.currentStep = 2
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.review-section h3').map((title) => title.text())).toEqual(['Supervisor', 'School'])
    expect(wrapper.text()).toContain('Sam Teacher')
    expect(wrapper.text()).toContain('Example High')
    expect(wrapper.text()).toContain('Teacher or parent')
    expect(wrapper.text()).toContain('Parent')
    expect(wrapper.find('[data-test="policies-agree"]').exists()).toBe(true)
    expect(wrapper.get('.form-footer .primary-action').text()).toBe('Submit registration')
  })

  it('sends a supervisor\'s registration as a mentor\'s, and says they can sign in', async () => {
    const submit = vi.fn<RegistrationGateway['submit']>(async () => ({
      ok: true,
      receipt: {
        referenceCode: 'ref',
        journey: 'supervisor',
        studentCount: 0,
        submittedAt: '2026-10-24T00:00:00Z',
      },
    }))
    const blobUrls = { createObjectURL: URL.createObjectURL, revokeObjectURL: URL.revokeObjectURL }
    const wrapper = mount(RegistrationPage, {
      props: { mode: 'canonical' },
      global: {
        plugins: [createPinia()],
        provide: { [REGISTRATION_GATEWAY_KEY as symbol]: { submit } },
        stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
      },
    })
    try {
      await clickButton(wrapper, 'Supervisor')
      const setup = wrapper.vm as unknown as {
        currentStep: number
        maxReachedStep: number
        forms: { supervisor: Record<string, string> }
      }
      Object.assign(setup.forms.supervisor, {
        firstName: 'Sam',
        lastName: 'Teacher',
        email: 'teacher@example.com',
        school: 'Example High',
        relationship: 'teacher',
        country: 'New Zealand',
      })
      // Their photo, chosen on the School & profile step (jsdom has no blob URLs).
      Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:photo'), revokeObjectURL: vi.fn() })
      setup.currentStep = setup.maxReachedStep = 1
      await wrapper.vm.$nextTick()
      const photo = new File(['png'], 'portrait.png', { type: 'image/png' })
      Object.defineProperty(wrapper.get('#supervisor-profilePhoto').element, 'files', { value: [photo] })
      await wrapper.get('#supervisor-profilePhoto').trigger('change')
      setup.currentStep = setup.maxReachedStep = 2
      await wrapper.vm.$nextTick()
      await wrapper.get('[data-test="policies-agree"]').setValue(true)
      await wrapper.get('form').trigger('submit')
      await flushPromises()
      expect(submit.mock.calls[0]?.[0]).toEqual({
        journey: 'supervisor',
        payload: {
          supervisor: {
            firstName: 'Sam',
            lastName: 'Teacher',
            email: 'teacher@example.com',
            school: 'Example High',
            relationship: 'teacher',
            country: 'New Zealand',
            state: '',
            pronouns: '',
            pronounsOther: '',
            profilePhoto: { name: 'portrait.png', type: 'image/png', size: 3 },
          },
        },
      })
      // The file itself goes with it, as a student's does.
      expect(submit.mock.calls[0]?.[1]?.attachments).toEqual({ supervisor: photo })
      // Active at once: no "we'll activate it", but sign in.
      expect(wrapper.get('.success-intro h3').text()).toBe('Registration Complete')
      expect(wrapper.get('.success-note').text()).toBe('You can now sign in to register your students.')
      expect(wrapper.text()).not.toContain('We will contact you after we set up and activate your account')
      expect(wrapper.get('.form-footer .primary-action').attributes('href')).toBe('/login')
    } finally {
      wrapper.unmount()
      Object.assign(URL, blobUrls)
    }
  })

  it('takes someone registering themselves to set their password, not the Complete page', async () => {
    const push = vi.fn()
    const submit = vi.fn<RegistrationGateway['submit']>(async () => ({
      ok: true,
      receipt: {
        referenceCode: 'ref',
        journey: 'mentor',
        studentCount: 0,
        submittedAt: '2026-10-24T00:00:00Z',
        passwordToken: 'signed-token',
      },
    }))
    const wrapper = mount(RegistrationPage, {
      props: { mode: 'canonical' },
      global: {
        plugins: [createPinia()],
        provide: {
          [REGISTRATION_GATEWAY_KEY as symbol]: { submit },
          [routerKey as symbol]: { push },
        },
        stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
      },
    })
    try {
      await clickButton(wrapper, 'Mentor')
      const setup = wrapper.vm as unknown as {
        currentStep: number
        maxReachedStep: number
        forms: { mentor: Record<string, unknown> }
      }
      Object.assign(setup.forms.mentor, {
        firstName: 'Jordan',
        lastName: 'Ng',
        email: 'jordan.ng@example.com',
        country: 'New Zealand',
        affiliation: 'academic',
        institution: 'University of Auckland',
        fieldOfStudy: 'Biology',
        interests: ['Biomedical Innovations'],
        capacity: '2',
        motivation: 'To help.',
      })
      setup.currentStep = setup.maxReachedStep = 3
      await wrapper.vm.$nextTick()
      await wrapper.get('[data-test="policies-agree"]').setValue(true)
      await wrapper.get('form').trigger('submit')
      await flushPromises()
      expect(submit).toHaveBeenCalledOnce()
      expect(push).toHaveBeenCalledWith('/register/password')
      expect(heldRegistrationPassword()).toEqual({ token: 'signed-token', mentor: true })
      expect(wrapper.find('.success-body').exists()).toBe(false)
    } finally {
      wrapper.unmount()
      sessionStorage.clear()
    }
  })

  it('gives every logical radio group a shared native name', async () => {
    const assertRadioGroup = (wrapper: VueWrapper, expectedName: string) => {
      const radios = wrapper.findAll('input[type="radio"]')
      expect(radios.length).toBeGreaterThan(1)
      expect(new Set(radios.map((radio) => radio.attributes('name')))).toEqual(
        new Set([expectedName]),
      )
    }

    const mentor = mountPage()
    await clickButton(mentor, 'Mentor')
    ;(mentor.vm as unknown as { currentStep: number }).currentStep = 1
    await mentor.vm.$nextTick()
    assertRadioGroup(mentor, 'mentor-affiliation')
  })
})
