import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import RegistrationDemoPage from '@/views/RegistrationDemoPage.vue'

const mountPage = (
  mode: 'canonical' | 'demo' | 'supervisor' | 'embedded-supervisor' = 'canonical',
) =>
  mount(RegistrationDemoPage, {
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
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('canonical registration intake', () => {
  it('limits public role selection to student and mentor', async () => {
    const wrapper = mountPage()

    expect(wrapper.text()).not.toContain('vision demo')
    expect(wrapper.text()).not.toContain('guardian consent invitation')
    await clickButton(wrapper, 'Register now')
    expect(wrapper.text()).toContain('Who are you registering as?')
    expect(wrapper.text()).not.toContain('Guardian')
    expect(wrapper.text()).not.toContain('Supervisor or teacher')

    await clickButton(wrapper, 'Student')
    expect(wrapper.text()).toContain('Register as an individual student')
    expect(wrapper.text()).toContain('Create a student team')
  })

  it('preserves conditional mentor affiliation fields and pending-review copy', async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Register now')
    await clickButton(wrapper, 'Mentor')

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
    expect(wrapper.text()).toContain('pending safeguarding and administrator review')
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
    expect(wrapper.text()).toContain('Exclude this invalid row')
  })

  it('keeps guardian consent clearly required on every student review', async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Register now')
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, 'Register as an individual student')

    const setup = wrapper.vm as unknown as { currentStep: number }
    setup.currentStep = 3
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Guardian consent is still required before every student')
    expect(wrapper.text()).toContain('initial feedback only')
  })

  it('retains the explicitly labelled local prototype route mode', () => {
    const wrapper = mountPage('demo')

    expect(wrapper.text()).toContain('Local vision demo')
    expect(wrapper.text()).toContain('Have a guardian consent invitation?')
  })

  it('starts every supervisor flow at its first student, group, or upload field', async () => {
    const wrapper = mountPage('supervisor')

    expect(wrapper.find('.registration-header').exists()).toBe(false)
    expect(wrapper.text()).toContain('How are you registering students?')
    await clickButton(wrapper, 'Register one student')
    expect(wrapper.findAll('.step-navigation__label').map((item) => item.text())).toEqual([
      'Student',
      'Grouping',
      'Review',
    ])
    expect(wrapper.find('#supervisorIndividual-student-email').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Confirm the signed-in account')

    const group = mountPage('supervisor')
    await clickButton(group, 'Register a student group')
    expect(group.text()).toContain('Group interests')

    const csv = mountPage('supervisor')
    await clickButton(csv, 'Upload students by CSV')
    expect(csv.text()).toContain('Choose completed CSV')
  })

  it('starts embedded supervisor mode at the chooser without a standalone header', () => {
    const wrapper = mountPage('embedded-supervisor')

    expect(wrapper.find('.registration-header').exists()).toBe(false)
    expect(wrapper.text()).toContain('How are you registering students?')
    expect(wrapper.text()).toContain('Register one student')
    expect(wrapper.text()).toContain('Register a student group')
    expect(wrapper.text()).toContain('Upload students by CSV')
  })

  it('puts creator profile and support before team configuration and removes naming', async () => {
    const wrapper = mountPage()
    await clickButton(wrapper, 'Register now')
    await clickButton(wrapper, 'Student')
    await clickButton(wrapper, 'Create a student team')

    const labels = wrapper.findAll('.step-navigation__label').map((item) => item.text())
    expect(labels).toEqual(['Creator', 'Your profile', 'Team', 'Review'])
    expect(wrapper.text()).not.toContain('Custom team name')
    expect(wrapper.text()).not.toContain('Automatic BTF name')
  })

  it('requires confirmation email for every manually entered student but not CSV', async () => {
    const team = mountPage()
    await clickButton(team, 'Register now')
    await clickButton(team, 'Student')
    await clickButton(team, 'Create a student team')
    const teamSetup = team.vm as unknown as { currentStep: number }
    teamSetup.currentStep = 2
    await team.vm.$nextTick()
    expect(team.findAll('input[type="email"]').length).toBe(2)

    const supervisor = mountPage('supervisor')
    await clickButton(supervisor, 'Register one student')
    const supervisorSetup = supervisor.vm as unknown as { currentStep: number }
    supervisorSetup.currentStep = 0
    await supervisor.vm.$nextTick()
    expect(supervisor.text()).toContain('Confirm student email')

    const group = mountPage('supervisor')
    await clickButton(group, 'Register a student group')
    const groupSetup = group.vm as unknown as { currentStep: number }
    groupSetup.currentStep = 1
    await group.vm.$nextTick()
    expect(group.text().match(/Confirm student email/g)).toHaveLength(2)
    expect(group.text()).not.toContain('group name')

    const csv = mountPage('supervisor')
    await clickButton(csv, 'Upload students by CSV')
    const csvSetup = csv.vm as unknown as { currentStep: number }
    csvSetup.currentStep = 0
    await csv.vm.$nextTick()
    expect(csv.text()).not.toContain('Confirm student email')
  })
})
