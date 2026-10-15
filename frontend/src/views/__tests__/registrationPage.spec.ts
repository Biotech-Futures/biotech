import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import RegistrationPage from '@/views/RegistrationPage.vue'
import pageSource from '@/views/RegistrationPage.vue?raw'
import globalCss from '@/assets/main.css?raw'
import { createStudent } from '@/registration/registration'

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

beforeEach(() => {
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
      const heading = wrapper.get('.setup-heading h1')
      const fontSize = getComputedStyle(heading.element).fontSize
      const size = /^([\d.]+)(px|rem)$/.exec(fontSize)
      if (!size) throw new Error(`Unexpected rendered heading size: ${fontSize}`)
      const pixels = Number(size[1]) * (size[2] === 'rem' ? 16 : 1)
      expect(pixels).toBeLessThanOrEqual(28)
      expect(pixels).toBeGreaterThan(0)
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

  it('keeps student-created groups between two and five members', async () => {
    const wrapper = mountPage()
    try {
      await clickButton(wrapper, 'Student')
      await clickButton(wrapper, 'Create a student group')
      const setup = wrapper.vm as unknown as { currentStep: number }
      setup.currentStep = 2
      await wrapper.vm.$nextTick()
      expect(wrapper.findAll('.student-entry')).toHaveLength(2)
      expect(
        wrapper.findAll('.student-entry__heading button').map((button) => button.text()),
      ).not.toContain('Remove')
      for (let index = 0; index < 3; index += 1) await clickButton(wrapper, 'Add member')
      expect(wrapper.findAll('.student-entry')).toHaveLength(5)
      const add = wrapper.findAll('button').find((button) => button.text() === 'Add member')!
      expect(add.attributes('disabled')).toBeDefined()
      for (let index = 0; index < 3; index += 1) await clickButton(wrapper, 'Remove')
      expect(wrapper.findAll('.student-entry')).toHaveLength(2)
      expect(
        wrapper.findAll('.student-entry__heading button').map((button) => button.text()),
      ).not.toContain('Remove')
    } finally {
      wrapper.unmount()
    }
  })

  it.each([
    { mode: 'canonical', journey: 'Register as an individual student', steps: 4 },
    { mode: 'canonical', journey: 'Create a student group', steps: 4 },
    { mode: 'canonical', journey: 'Register as a mentor', steps: 5 },
    { mode: 'supervisor', journey: 'Register one student', steps: 2 },
    { mode: 'supervisor', journey: 'Register a student group', steps: 3 },
    { mode: 'supervisor', journey: 'Upload students by CSV', steps: 3 },
  ] as const)(
    'keeps numbered tabs without a percentage bar for $journey',
    async ({ mode, journey, steps }) => {
      const wrapper = mountPage(mode)
      try {
        if (mode === 'canonical') {
          await clickButton(wrapper, journey === 'Register as a mentor' ? 'Mentor' : 'Student')
        }
        if (journey !== 'Register as a mentor') {
          await clickButton(wrapper, journey)
        }
        expect(wrapper.find('[role="progressbar"]').exists()).toBe(false)
        expect(wrapper.find('.form-progress').exists()).toBe(false)
        expect(wrapper.text()).not.toMatch(/\d+% complete/)
        const tabs = wrapper.findAll('.step-navigation button')
        expect(tabs.map((tab) => tab.find('span').text())).toEqual(
          Array.from({ length: steps }, (_, index) => String(index + 1)),
        )
        expect(tabs[0]!.attributes('aria-current')).toBe('step')
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
      await clickButton(wrapper, 'Create a student group')
      await wrapper.setProps({ invitationToken: 'late-token' })
      expect(wrapper.find('.role-options').exists()).toBe(true)
      await clickButton(wrapper, 'Student')
      expect(wrapper.text()).not.toContain('Create a student group')
      await wrapper.setProps({ invitationToken: null })
      await clickButton(wrapper, 'Student')
      expect(wrapper.text()).toContain('Create a student group')
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
      await clickButton(wrapper, 'Student')
      expect(wrapper.text()).toContain('Register as an individual student')
      expect(wrapper.text()).not.toContain('Create a student group')
    } finally {
      wrapper.unmount()
      window.history.replaceState({}, '', previous)
    }
  })
  it('limits public role selection to student and mentor', async () => {
    const wrapper = mountPage()

    expect(wrapper.text()).not.toContain('guardian consent invitation')
    expect(wrapper.find('.welcome-layout').exists()).toBe(false)
    expect(wrapper.text()).toContain('Who are you registering as?')
    expect(wrapper.text()).not.toContain('Guardian')
    expect(wrapper.text()).not.toContain('Supervisor or teacher')
    expect(wrapper.find('.setup-progress').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Registration setup')
    expect(wrapper.text()).not.toContain('Step 1 of 2')
    expect(wrapper.find('.setup-heading > p').exists()).toBe(false)

    await clickButton(wrapper, 'Student')
    expect(wrapper.text()).toContain('Register as an individual student')
    expect(wrapper.text()).toContain('Create a student group')
    expect(wrapper.find('.setup-progress').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Registration setup')
    expect(wrapper.text()).not.toContain('Step 2 of 2')
    expect(wrapper.find('.setup-heading > p').exists()).toBe(false)
  })

  it('preserves conditional mentor affiliation fields and pending-review copy', async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Mentor')
    expect(wrapper.findAll('.step-navigation li')).toHaveLength(5)

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

    setup.currentStep = 4
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Pending administrator review')
    expect(wrapper.text()).not.toContain('Before you submit')
  })

  it('preserves CSV preview and explicit invalid-row exclusion controls', async () => {
    const wrapper = mountPage('supervisor')
    await clickButton(wrapper, 'Upload students by CSV')

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
    expect(wrapper.text()).toContain('Exclude this row')
  })

  it('explains guardian permission on the contact step without a before-submit bubble', async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, 'Register as an individual student')

    const setup = wrapper.vm as unknown as { currentStep: number }
    setup.currentStep = 2
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain(
      'Your nominated guardian must provide permission through the existing guardian consent process',
    )
    expect(wrapper.text()).toContain(
      'before you can access most features of the program.',
    )
    expect(wrapper.text()).toContain('it does not send a permission email or record consent.')
    expect(wrapper.text()).toContain('Teacher / school supervisor')
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
    expect(wrapper.findAll('.step-navigation__label').map((item) => item.text())).toEqual([
      'Student',
      'Review',
    ])
    expect(wrapper.find('#supervisorIndividual-student-email').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Confirm the signed-in account')
    expect(wrapper.find('.form-progress').exists()).toBe(false)
    expect(wrapper.find('.step-navigation').attributes('aria-label')).toBe('Registration progress')
    expect(wrapper.findAll('.step-navigation li')).toHaveLength(2)
    expect(wrapper.text()).not.toContain('School-only grouping')
    expect(wrapper.text()).not.toContain('Cross-school grouping')

    const group = mountPage('supervisor')
    await clickButton(group, 'Register a student group')
    expect(group.text()).toContain('Mutual Areas of Interest')
    expect(
      group.find('input[name="supervisor-group-interests"]').attributes('disabled'),
    ).toBeUndefined()
    await group
      .find('input[name="supervisor-group-interests"][value="Water & Energy Tech"]')
      .setValue(true)
    await group.get('form').trigger('submit')
    expect(group.text()).toContain('Add 2–5 students')

    const csv = mountPage('supervisor')
    await clickButton(csv, 'Upload students by CSV')
    expect(csv.text()).toContain('Choose completed CSV')
  })

  it('puts creator profile and support before team configuration and removes naming', async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, 'Create a student group')

    const labels = wrapper.findAll('.step-navigation__label').map((item) => item.text())
    expect(labels).toEqual(['Creator', 'Your profile', 'Group', 'Review'])
    expect(wrapper.text()).not.toContain('Custom team name')
    expect(wrapper.text()).not.toContain('Automatic BTF name')
  })

  it("confirms the email of students registering themselves, not of a supervisor's students", async () => {
    const team = mountPage()
    await clickButton(team, 'Student')
    await clickButton(team, 'Create a student group')
    const teamSetup = team.vm as unknown as { currentStep: number }
    teamSetup.currentStep = 2
    await team.vm.$nextTick()
    expect(team.findAll('input[type="email"]').length).toBe(2)

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
    await clickButton(csv, 'Upload students by CSV')
    const csvSetup = csv.vm as unknown as { currentStep: number }
    csvSetup.currentStep = 0
    await csv.vm.$nextTick()
    expect(csv.text()).not.toContain('Confirm student email')
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

    const asked = send.mock.calls.map(([url]) => String(url))
    expect(asked.some((url) => url.includes('/api/v1/registration/countries/'))).toBe(true)
    expect(asked.some((url) => url.includes('/api/v1/registration/states/?country=Australia'))).toBe(true)
    expect(country().element.tagName).toBe('SELECT')
    expect(
      country()
        .findAll('option')
        .slice(1)
        .map((option) => option.attributes('value')),
    ).toEqual(countries)
    expect((country().element as HTMLSelectElement).value).toBe('Australia')
    expect(state().element.tagName).toBe('SELECT')
    expect(
      state()
        .findAll('option')
        .slice(1)
        .map((option) => option.attributes('value')),
    ).toEqual(states)
    await state().setValue('VIC')
    expect((state().element as HTMLSelectElement).value).toBe('VIC')

    await country().setValue('New Zealand')
    expect(state().element.tagName).toBe('INPUT')
  })

  it("gives a supervisor's student one full width email, and Areas of Interest with no *", async () => {
    const wrapper = mountPage('supervisor')
    await clickButton(wrapper, 'Register one student')
    const email = wrapper.get('#supervisorIndividual-student-email').element.closest('.registration-field')
    expect(email?.classList.contains('registration-field--wide')).toBe(true)

    const legend = wrapper.get('.interest-selector legend')
    expect(legend.text()).toBe('Areas of Interest')
    expect(wrapper.text()).not.toContain('Choose one or more areas')
  })

  it('shows Member 1, group-only interests and optional member guardian contact', async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, 'Create a student group')
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
    expect(wrapper.find('.interest-selector').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Add guardian contact (optional)')
    expect(
      wrapper.get('#studentTeam-creator-guardian-firstName').attributes('required'),
    ).toBeDefined()
    setup.currentStep = 2
    setup.maxReachedStep = 2
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Member 1 (you)')
    expect(wrapper.text()).toContain('Jordan Rivera')
    expect(wrapper.text()).toContain('jordan@example.test')
    expect(wrapper.text()).toContain('Member 2')
    expect(wrapper.text()).toContain('There may be between 2 and 5 students per group.')
    const optional = wrapper.get('.defer-control input')
    expect((optional.element as HTMLInputElement).checked).toBe(false)
    expect(wrapper.find('#studentTeam-teammates-0-guardian-firstName').exists()).toBe(false)
    await optional.setValue(true)
    expect(wrapper.find('#studentTeam-teammates-0-guardian-firstName').exists()).toBe(true)
    await clickButton(wrapper, 'Edit your details')
    expect(setup.currentStep).toBe(0)
    expect(wrapper.get('#studentTeam-creator-firstName').element).toHaveProperty('value', 'Jordan')
  })

  it('provides first-time supervisor guidance without granting public supervisor access', () => {
    const wrapper = mountPage()
    expect(wrapper.get('.supervisor-guidance').text()).toContain(
      'Contact BIOTech for an invitation',
    )
    expect(wrapper.get('.supervisor-guidance a').attributes('href')).toBe(
      '/supervisor/registration',
    )
    expect(wrapper.findAll('.role-option')).toHaveLength(2)
  })

  it('gives every logical radio group a shared native name', async () => {
    const assertRadioGroup = (wrapper: VueWrapper, expectedName: string) => {
      const radios = wrapper.findAll('input[type="radio"]')
      expect(radios.length).toBeGreaterThan(1)
      expect(new Set(radios.map((radio) => radio.attributes('name')))).toEqual(
        new Set([expectedName]),
      )
    }

    const individual = mountPage()
    await clickButton(individual, 'Student')
    await clickButton(individual, 'Register as an individual student')
    ;(individual.vm as unknown as { currentStep: number }).currentStep = 2
    await individual.vm.$nextTick()
    assertRadioGroup(individual, 'student-individual-supervisor-mode')

    const team = mountPage()
    await clickButton(team, 'Student')
    await clickButton(team, 'Create a student group')
    ;(team.vm as unknown as { currentStep: number }).currentStep = 1
    await team.vm.$nextTick()
    assertRadioGroup(team, 'student-team-supervisor-mode')

    const mentor = mountPage()
    await clickButton(mentor, 'Mentor')
    ;(mentor.vm as unknown as { currentStep: number }).currentStep = 1
    await mentor.vm.$nextTick()
    assertRadioGroup(mentor, 'mentor-affiliation')
  })
})
