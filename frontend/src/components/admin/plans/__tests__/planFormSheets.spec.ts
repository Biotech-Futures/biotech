import { afterEach, describe, expect, it } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import AdminPlanStageFormSheet from '@/components/admin/plans/AdminPlanStageFormSheet.vue'
import AdminPlanTaskFormSheet from '@/components/admin/plans/AdminPlanTaskFormSheet.vue'

const stages = [
  { id: 1, name: 'Getting started', description: '', position: 0 },
  { id: 2, name: 'Next step', description: '', position: 1 }
]

const mountSheet = (component: unknown, props: Record<string, unknown> = {}) => {
  const comp = component as any
  return mount(comp, {
    props: { modelValue: true, ...props },
    global: { stubs: { Teleport: true } }
  })
}

const emitSave = (wrapper: VueWrapper) => wrapper.emitted('save')?.[0]?.[0]

let wrapper: VueWrapper | null = null
afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('AdminPlanStageFormSheet', () => {
  it('requires a name before saving', async () => {
    wrapper = mountSheet(AdminPlanStageFormSheet)
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.emitted('save')).toBeUndefined()
    expect(wrapper.text()).toContain('Stage name is required')
  })

  it('emits the trimmed stage payload with a clamped position', async () => {
    wrapper = mountSheet(AdminPlanStageFormSheet, { nextPosition: 3 })
    await wrapper.find('#plan-stage-name').setValue('  Wrap up  ')
    await wrapper.find('#plan-stage-description').setValue('  Final checks  ')
    await wrapper.find('#plan-stage-position').setValue('2')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(emitSave(wrapper)).toEqual({ name: 'Wrap up', description: 'Final checks', position: 2 })
  })

  it('seeds the form from an edited stage', async () => {
    wrapper = mountSheet(AdminPlanStageFormSheet, {
      stage: { id: 5, name: 'Edit me', description: 'Body', position: 4 }
    })
    await flushPromises()
    expect((wrapper.find('#plan-stage-name').element as HTMLInputElement).value).toBe('Edit me')
    expect((wrapper.find('#plan-stage-position').element as HTMLInputElement).value).toBe('4')
  })
})

describe('AdminPlanTaskFormSheet', () => {
  it('defaults to the selected stage and per-person mode', async () => {
    wrapper = mountSheet(AdminPlanTaskFormSheet, { stages, defaultStageId: 2 })
    await wrapper.find('#plan-task-name').setValue('Do it')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(emitSave(wrapper)).toMatchObject({
      name: 'Do it',
      stage_id: 2,
      audience_role: 'student',
      completion_mode: 'per_person',
      due_date: null
    })
  })

  it('refuses a lone resource label without a link', async () => {
    wrapper = mountSheet(AdminPlanTaskFormSheet, { stages, defaultStageId: 1 })
    await wrapper.find('#plan-task-name').setValue('Do it')
    await wrapper.find('#plan-task-resource-label').setValue('Read this')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.emitted('save')).toBeUndefined()
    expect(wrapper.text()).toContain('both a label and a link')
  })

  it('blocks saving when no stage is available', async () => {
    wrapper = mountSheet(AdminPlanTaskFormSheet, { stages: [], defaultStageId: null })
    await wrapper.find('#plan-task-name').setValue('Do it')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.emitted('save')).toBeUndefined()
    expect(wrapper.text()).toContain('Select a stage')
  })

  it('disables audience and mode when the task already has completions', async () => {
    wrapper = mountSheet(AdminPlanTaskFormSheet, {
      stages,
      task: {
        id: 9,
        stage_id: 1,
        position: 0,
        name: 'Locked',
        description: '',
        resource_url: '',
        resource_label: '',
        due_date: null,
        audience_role: 'student',
        completion_mode: 'per_person',
        has_completions: true,
        created_by: null,
        created_at: '2026-09-01T00:00:00+00:00',
        updated_at: '2026-09-01T00:00:00+00:00'
      }
    })
    await flushPromises()
    expect(wrapper.find('.app-select.is-disabled').exists()).toBe(true)
    const radios = wrapper.findAll('.admin-plan-task-form__radio input')
    expect(radios.every((radio) => radio.attributes('disabled') !== undefined)).toBe(true)
    expect(wrapper.text()).toContain('locked')
  })
})
