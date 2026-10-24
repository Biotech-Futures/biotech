import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import GroupPlanSection from '@/components/plans/GroupPlanSection.vue'
import { ApiError } from '@/utils/apiError'
import { formatShortDate, getSetTimeZone, toTimeZoneDateKey } from '@/utils/date'
import { toggleGroupPlanTask, type GroupPlanTask, type PlanStage } from '@/utils/plansAPI'

vi.mock('@/utils/plansAPI', () => ({ toggleGroupPlanTask: vi.fn() }))
const toggleMock = vi.mocked(toggleGroupPlanTask)

// "Today" exactly as the component works it out, so tests hold in any zone.
const today = toTimeZoneDateKey(new Date(), getSetTimeZone())
const shift = (key: string, days: number) => {
  const date = new Date(`${key}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

const stages: PlanStage[] = [
  { id: 1, name: 'Getting started', description: 'Meet your team.\nThen set up.', position: 0 },
  { id: 2, name: 'Developing your project', description: '', position: 1 },
]

const task = (id: number, overrides: Partial<GroupPlanTask> = {}): GroupPlanTask => ({
  id,
  stage_id: 1,
  position: 0,
  name: `Task ${id}`,
  description: '',
  resource_url: '',
  resource_label: '',
  due_date: null,
  audience_role: 'student',
  completion_mode: 'per_person',
  completed: false,
  can_toggle: true,
  ...overrides,
})

// A student's view of a realistic plan.
const items = (): GroupPlanTask[] => [
  task(11, {
    name: 'Introduce yourself',
    description: 'Post a short <b>hello</b> in chat.',
    completed: true,
    resource_url: 'https://example.com/guide',
    resource_label: 'Welcome guide',
  }),
  task(12, { name: 'Agree a meeting time', completion_mode: 'per_group', completed: false }),
  // Someone else's individual task, as an admin would see it.
  task(13, { name: 'Mentor check-in', audience_role: 'mentor', completed: null, can_toggle: false }),
  task(21, { stage_id: 2, name: 'Draft your poster', due_date: shift(today, -1) }),
  task(22, { stage_id: 2, name: 'Read the brief', completion_mode: 'per_group', completed: true, can_toggle: false }),
]

let wrapper: VueWrapper | null = null

const mountSection = (planItems = items(), planStages = stages) => {
  wrapper = mount(GroupPlanSection, { props: { groupId: '7', stages: planStages, items: planItems } })
  return wrapper
}

const row = (id: number) => wrapper!.find(`[data-testid="plan-task-${id}"]`)
const box = (id: number) => row(id).find<HTMLInputElement>('input[type="checkbox"]')
const summary = (stageId: number) =>
  wrapper!.find(`[data-testid="plan-stage-${stageId}"] [data-testid="plan-stage-summary"]`)

/** A request the test settles itself. */
const pending = () => {
  let resolve!: (value: GroupPlanTask) => void
  let reject!: (error: unknown) => void
  toggleMock.mockReturnValueOnce(
    new Promise<GroupPlanTask>((res, rej) => {
      resolve = res
      reject = rej
    }),
  )
  return { resolve, reject }
}

beforeEach(() => {
  toggleMock.mockReset()
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('GroupPlanSection', () => {
  describe('stages and tasks', () => {
    it('shows each stage with its introduction and its own tasks, in order', () => {
      mountSection()
      const sections = wrapper!.findAll('section')
      expect(sections.map((s) => s.find('h2').text())).toEqual(['Getting started', 'Developing your project'])
      expect(sections[0].text()).toContain('Meet your team.')
      expect(sections[0].findAll('li').map((li) => li.find('label').text())).toEqual([
        'Introduce yourself',
        'Agree a meeting time',
        'Mentor check-in',
      ])
      expect(sections[1].findAll('li').map((li) => li.find('label').text())).toEqual([
        'Draft your poster',
        'Read the brief',
      ])
    })

    it('renders instructions as plain text, never HTML', () => {
      mountSection()
      expect(row(11).text()).toContain('Post a short <b>hello</b> in chat.')
      expect(row(11).find('b').exists()).toBe(false)
    })

    it('leaves out stages with no tasks and says so when there are none', () => {
      mountSection([task(21, { stage_id: 2 })])
      expect(wrapper!.findAll('section').map((s) => s.find('h2').text())).toEqual(['Developing your project'])

      wrapper!.unmount()
      mountSection([], stages)
      expect(wrapper!.text()).toContain('There are no plan tasks yet.')
    })
  })

  describe('stage summary', () => {
    it('counts only tasks with a boolean completion', () => {
      mountSection()
      // Stage 1: true + false counted; the null mentor task is left out.
      expect(summary(1).text()).toBe('Your view: 1/2 tasks complete')
      expect(summary(2).text()).toBe('Your view: 1/2 tasks complete')
    })

    it('is hidden when nothing in the stage is the viewer’s to count', () => {
      mountSection([task(13, { completed: null, can_toggle: false })])
      expect(summary(1).exists()).toBe(false)
    })
  })

  describe('completion state', () => {
    it('reflects completed and can_toggle', () => {
      mountSection()
      expect(box(11).element.checked).toBe(true)
      expect(box(12).element.checked).toBe(false)
      expect(box(11).attributes('disabled')).toBeUndefined()
      // Visible but not the viewer's to tick: shown, read-only.
      expect(box(22).element.checked).toBe(true)
      expect(box(22).attributes('disabled')).toBeDefined()
    })

    it('shows "Each person ticks their own" instead of a box for null', () => {
      mountSection()
      expect(box(13).exists()).toBe(false)
      expect(row(13).text()).toContain('Each person ticks their own')
      expect(row(11).text()).not.toContain('Each person ticks their own')
    })

    it('tags shared tasks "Whole group"', () => {
      mountSection()
      expect(row(12).text()).toContain('Whole group')
      expect(row(22).text()).toContain('Whole group')
      expect(row(11).text()).not.toContain('Whole group')
    })
  })

  describe('due dates', () => {
    it('formats the date without a day shift', () => {
      mountSection([task(31, { due_date: '2026-11-05' })])
      expect(row(31).text()).toContain(`Due ${formatShortDate('2026-11-05', 'UTC')}`)
      expect(row(31).text()).toContain('Due 05/11/26')
    })

    it('marks only incomplete, past-due tasks as overdue', () => {
      const yesterday = shift(today, -1)
      mountSection([
        task(41, { due_date: yesterday, completed: false }),
        task(42, { due_date: today, completed: false }),
        task(43, { due_date: yesterday, completed: true }),
        task(44, { due_date: yesterday, completed: null, can_toggle: false }),
        task(45, { due_date: shift(today, 1), completed: false }),
        task(46, { due_date: null, completed: false }),
      ])
      const overdue = [41, 42, 43, 44, 45, 46].filter((id) => row(id).text().includes('Overdue'))
      expect(overdue).toEqual([41])
    })
  })

  describe('resource links', () => {
    it('links to the resource with its label, safely, in a new tab', () => {
      mountSection()
      const link = row(11).find('a')
      expect(link.attributes('href')).toBe('https://example.com/guide')
      expect(link.text()).toBe('Welcome guide')
      expect(link.attributes('target')).toBe('_blank')
      expect(link.attributes('rel')).toBe('noopener noreferrer')
    })

    it('falls back to "Open resource" and shows no link without a web address', () => {
      mountSection([
        task(51, { resource_url: 'https://example.com/a', resource_label: '  ' }),
        task(52, { resource_url: '' }),
        task(53, { resource_url: 'javascript:alert(1)', resource_label: 'Bad' }),
      ])
      expect(row(51).find('a').text()).toBe('Open resource')
      expect(row(52).find('a').exists()).toBe(false)
      expect(row(53).find('a').exists()).toBe(false)
    })
  })

  describe('ticking', () => {
    it('sends the desired value and shows it only once the server agrees', async () => {
      mountSection()
      const request = pending()

      await box(12).setValue(true)
      expect(toggleMock).toHaveBeenCalledWith('7', 12, true)
      // Still the saved state, and locked, until the response.
      expect(box(12).element.checked).toBe(false)
      expect(box(12).attributes('disabled')).toBeDefined()
      expect(summary(1).text()).toBe('Your view: 1/2 tasks complete')

      request.resolve(task(12, { name: 'Agree a meeting time', completion_mode: 'per_group', completed: true }))
      await flushPromises()
      expect(box(12).element.checked).toBe(true)
      expect(box(12).attributes('disabled')).toBeUndefined()
      expect(summary(1).text()).toBe('Your view: 2/2 tasks complete')
    })

    it('unticks with an explicit false', async () => {
      mountSection()
      toggleMock.mockResolvedValueOnce(task(11, { name: 'Introduce yourself', completed: false }))
      await box(11).setValue(false)
      await flushPromises()
      expect(toggleMock).toHaveBeenCalledWith('7', 11, false)
      expect(box(11).element.checked).toBe(false)
    })

    it('keeps the saved state and explains when the tick fails', async () => {
      mountSection()
      const request = pending()
      await box(12).setValue(true)
      request.reject(
        new ApiError({ error: "You can't tick this task.", code: 'permission_denied', request_id: 'r1' }, 403),
      )
      await flushPromises()

      expect(box(12).element.checked).toBe(false)
      expect(box(12).attributes('disabled')).toBeUndefined()
      expect(row(12).find('[role="alert"]').text()).toContain("You can't tick this task.")
      expect(summary(1).text()).toBe('Your view: 1/2 tasks complete')

      // Trying again clears the message and can succeed.
      toggleMock.mockResolvedValueOnce(task(12, { completion_mode: 'per_group', completed: true }))
      await box(12).setValue(true)
      await flushPromises()
      expect(row(12).find('[role="alert"]').exists()).toBe(false)
      expect(box(12).element.checked).toBe(true)
    })

    it('sends one request when changed again while saving', async () => {
      mountSection()
      const request = pending()
      await box(12).setValue(true)
      expect(box(12).attributes('disabled')).toBeDefined()
      // test-utils' trigger() skips disabled elements, so dispatch directly:
      // a second change reaching the handler while the first is in flight.
      box(12).element.checked = true
      box(12).element.dispatchEvent(new Event('change'))
      await flushPromises()
      expect(toggleMock).toHaveBeenCalledTimes(1)
      expect(box(12).element.checked).toBe(false)
      request.resolve(task(12, { completion_mode: 'per_group', completed: true }))
      await flushPromises()
    })

    it('tells the parent about a saved tick, with its group, and nothing for a failed one', async () => {
      mountSection()
      const saved = task(12, { completion_mode: 'per_group', completed: true })
      toggleMock.mockResolvedValueOnce(saved)
      await box(12).setValue(true)
      await flushPromises()
      expect(wrapper!.emitted('taskUpdated')).toEqual([['7', saved]])

      toggleMock.mockRejectedValueOnce(new Error('Network down'))
      await box(11).setValue(false)
      await flushPromises()
      expect(wrapper!.emitted('taskUpdated')).toHaveLength(1)
    })

    it('resets to a new list from the parent', async () => {
      mountSection()
      await wrapper!.setProps({ items: [task(11, { name: 'Introduce yourself', completed: false })] })
      expect(box(11).element.checked).toBe(false)
      expect(row(12).exists()).toBe(false)
    })
  })
})
