import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import DeadlineExtensionPage from '@/views/grading/DeadlineExtensionPage.vue'
import {
  fetchGroupExtensions,
  fetchSubmissionDeadline,
  removeGroupExtension,
  saveGroupExtension
} from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  fetchGroupExtensions: vi.fn(),
  fetchSubmissionDeadline: vi.fn(),
  removeGroupExtension: vi.fn(),
  saveGroupExtension: vi.fn()
}))
const listMock = vi.mocked(fetchGroupExtensions)
const deadlineMock = vi.mocked(fetchSubmissionDeadline)
const removeMock = vi.mocked(removeGroupExtension)
const saveMock = vi.mocked(saveGroupExtension)

// The page resolves the picked group through the search input's exposed
// resolveId — stub the child and steer that resolution per test.
const resolveIdMock = vi.fn<() => number | null>()
const GroupSearchInputStub = defineComponent({
  name: 'GroupSearchInput',
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue'],
  methods: {
    resolveId(): number | null {
      return resolveIdMock()
    }
  },
  template:
    '<input class="picker" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />'
})

const NOW = new Date('2026-09-23T12:00:00Z')

const extension = (over: Record<string, unknown> = {}) => ({
  id: 1,
  group_id: 7,
  group_name: 'BTF-1',
  extended_until: '2026-11-05T13:00:00Z',
  grace_hours: 6,
  reason: 'School flood.',
  granted_at: '2026-09-20T00:00:00Z',
  granted_by: 'Ada Admin',
  revoked_at: null,
  revoked_by: null,
  ...over
})

const mountPage = async () => {
  const wrapper = mount(DeadlineExtensionPage, {
    global: { stubs: { GroupSearchInput: GroupSearchInputStub } }
  })
  await flushPromises()
  return wrapper
}

const fillForm = async (wrapper: Awaited<ReturnType<typeof mountPage>>) => {
  await wrapper.find('.picker').setValue('BTF-1')
  await wrapper.find('input[type="datetime-local"]').setValue('2026-11-08T09:00')
}

const grantButton = (wrapper: Awaited<ReturnType<typeof mountPage>>) =>
  wrapper.findAll('button').find((b) => /^(Grant|Saving…)$/.test(b.text().trim()))!

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(NOW)
  listMock.mockReset()
  deadlineMock.mockReset()
  removeMock.mockReset()
  saveMock.mockReset()
  resolveIdMock.mockReset()
  listMock.mockResolvedValue({ extensions: [extension()] })
  deadlineMock.mockResolvedValue({
    deadline: {
      closes_at: '2026-10-30T13:00:00Z', grace_hours: 6, is_open: true,
      set_by: 'Ada Admin', created_at: '2026-09-01T00:00:00Z'
    }
  })
})

afterEach(() => {
  vi.useRealTimers()
})

describe('the extensions table', () => {
  it('lists each extension with its grace, author and reason row', async () => {
    const wrapper = await mountPage()
    const text = wrapper.text()
    expect(text).not.toContain('#7') // group ids are not exposed
    expect(text).toContain('BTF-1')
    expect(text).toContain('+6h')
    expect(text).toContain('Ada Admin')
    expect(wrapper.find('.extensions__reason-row').text()).toContain('School flood.')
  })

  it('labels rows Active, In grace, Expired or Revoked by their own clock', async () => {
    listMock.mockResolvedValue({
      extensions: [
        extension({ id: 1, extended_until: '2026-11-05T13:00:00Z' }),
        extension({ id: 2, extended_until: '2026-09-23T10:00:00Z', grace_hours: 6, reason: '' }),
        extension({ id: 3, extended_until: '2026-09-01T10:00:00Z', reason: '' }),
        extension({ id: 4, revoked_at: '2026-09-10T00:00:00Z', revoked_by: 'Ada Admin', reason: '' })
      ]
    })
    const wrapper = await mountPage()
    const labels = wrapper.findAll('tbody td:nth-child(4)').map((c) => c.text())
    expect(labels).toEqual(['Active', 'In grace', 'Expired', 'Revoked'])
    // A revoked row loses its Revoke button.
    const lastRow = wrapper.findAll('tbody tr').at(-1)!
    expect(lastRow.find('button').exists()).toBe(false)
  })

  it('says so when nothing has been granted', async () => {
    listMock.mockResolvedValue({ extensions: [] })
    const wrapper = await mountPage()
    expect(wrapper.find('.extensions__empty').text()).toBe('No extensions granted.')
  })

  it('offers a retry when the list fails to load', async () => {
    listMock.mockRejectedValueOnce(new Error('backend down'))
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Failed to load.')
    await wrapper.find('.extensions__load-error button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('BTF-1')
  })

  it('floors the calendar at the current deadline so nothing can be shortened', async () => {
    const wrapper = await mountPage()
    // The floor is rendered in the admin's local time, like the picker itself.
    const d = new Date('2026-10-30T13:00:00Z')
    const pad = (n: number) => String(n).padStart(2, '0')
    const localFloor = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
    expect(wrapper.find('input[type="datetime-local"]').attributes('min')).toBe(localFloor)
  })
})

describe('granting', () => {
  it('refuses an unresolvable group without calling the server', async () => {
    resolveIdMock.mockReturnValue(null)
    const wrapper = await mountPage()
    await fillForm(wrapper)
    await grantButton(wrapper).trigger('click')
    expect(wrapper.find('.extensions__banner--error').text()).toBe('No group matches that name.')
    expect(saveMock).not.toHaveBeenCalled()
  })

  it('grants, clears the form and refreshes the table', async () => {
    // Group 8 has no extension yet, so no replace warning intervenes.
    resolveIdMock.mockReturnValue(8)
    saveMock.mockResolvedValueOnce({ extension: extension({ group_id: 8 }) })
    const wrapper = await mountPage()
    await fillForm(wrapper)
    await wrapper.find('textarea').setValue('Storm damage')
    await grantButton(wrapper).trigger('click')
    await flushPromises()

    expect(saveMock).toHaveBeenCalledWith(
      8, new Date('2026-11-08T09:00').toISOString(), 24, 'Storm damage'
    )
    expect(wrapper.find('.extensions__banner--ok').text()).toBe('Extension granted.')
    expect((wrapper.find('.picker').element as HTMLInputElement).value).toBe('')
    expect(listMock).toHaveBeenCalledTimes(2) // mount + refresh

    // The success message clears itself after 3.5 seconds.
    await vi.advanceTimersByTimeAsync(3500)
    expect(wrapper.find('.extensions__banner--ok').exists()).toBe(false)
  })

  it('shows the server refusal when a grant bounces', async () => {
    resolveIdMock.mockReturnValue(8)
    saveMock.mockRejectedValueOnce(new Error('must be later than the current deadline'))
    const wrapper = await mountPage()
    await fillForm(wrapper)
    await grantButton(wrapper).trigger('click')
    await flushPromises()
    expect(wrapper.find('.extensions__banner--error').text()).toContain(
      'must be later than the current deadline'
    )
  })

  it('warns before replacing a group with an active extension', async () => {
    resolveIdMock.mockReturnValue(7) // group 7 already has an active extension
    saveMock.mockResolvedValueOnce({ extension: extension() })
    const wrapper = await mountPage()
    await fillForm(wrapper)
    await grantButton(wrapper).trigger('click')
    await flushPromises()

    // Nothing saved yet — the warning dialog intervenes, naming the group.
    expect(saveMock).not.toHaveBeenCalled()
    const dialog = wrapper.find('.extensions__dialog')
    expect(dialog.exists()).toBe(true)
    expect(dialog.text()).toContain('BTF-1')

    await dialog.findAll('button').at(-1)!.trigger('click') // Replace extension
    await flushPromises()
    expect(saveMock).toHaveBeenCalledWith(7, new Date('2026-11-08T09:00').toISOString(), 24, '')
    expect(wrapper.find('.extensions__dialog').exists()).toBe(false)
  })

  it('cancelling the replace warning saves nothing', async () => {
    resolveIdMock.mockReturnValue(7)
    const wrapper = await mountPage()
    await fillForm(wrapper)
    await grantButton(wrapper).trigger('click')
    await flushPromises()

    await wrapper.find('.extensions__dialog button').trigger('click') // Cancel
    expect(wrapper.find('.extensions__dialog').exists()).toBe(false)
    expect(saveMock).not.toHaveBeenCalled()
  })

  it('a revoked extension does not trigger the replace warning', async () => {
    listMock.mockResolvedValue({
      extensions: [extension({ revoked_at: '2026-09-10T00:00:00Z', revoked_by: 'Ada Admin' })]
    })
    resolveIdMock.mockReturnValue(7)
    saveMock.mockResolvedValueOnce({ extension: extension() })
    const wrapper = await mountPage()
    await fillForm(wrapper)
    await grantButton(wrapper).trigger('click')
    await flushPromises()
    expect(wrapper.find('.extensions__dialog').exists()).toBe(false)
    expect(saveMock).toHaveBeenCalled()
  })

  it('cannot grant with the group or date missing', async () => {
    const wrapper = await mountPage()
    expect(grantButton(wrapper).attributes('disabled')).toBeDefined()
    await fillForm(wrapper)
    expect(grantButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('pressing Enter in the form does not grant', async () => {
    resolveIdMock.mockReturnValue(8)
    const wrapper = await mountPage()
    await fillForm(wrapper)
    await wrapper.find('.picker').trigger('keydown', { key: 'Enter' })
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(saveMock).not.toHaveBeenCalled()
    expect(wrapper.find('.extensions__banner--error').exists()).toBe(false)
  })
})

describe('revoking', () => {
  const confirmRevoke = async (wrapper: Awaited<ReturnType<typeof mountPage>>) => {
    await wrapper.find('.extensions__dialog').findAll('button').at(-1)!.trigger('click')
    await flushPromises()
  }

  it('the row button asks first, naming the group and its extension', async () => {
    const wrapper = await mountPage()
    await wrapper.find('tbody button').trigger('click')
    const dialog = wrapper.find('.extensions__dialog')
    expect(dialog.exists()).toBe(true)
    expect(dialog.text()).toContain('Revoke this extension?')
    expect(dialog.text()).toContain('BTF-1')
    expect(removeMock).not.toHaveBeenCalled()
  })

  it('confirming revokes and refreshes', async () => {
    removeMock.mockResolvedValueOnce(undefined as never)
    const wrapper = await mountPage()
    await wrapper.find('tbody button').trigger('click')
    await confirmRevoke(wrapper)
    expect(removeMock).toHaveBeenCalledWith(7)
    expect(wrapper.find('.extensions__dialog').exists()).toBe(false)
    // The refreshed table is the confirmation; no success banner.
    expect(wrapper.find('.extensions__banner--ok').exists()).toBe(false)
    expect(listMock).toHaveBeenCalledTimes(2)
  })

  it('cancelling revokes nothing', async () => {
    const wrapper = await mountPage()
    await wrapper.find('tbody button').trigger('click')
    await wrapper.find('.extensions__dialog button').trigger('click') // Cancel
    expect(wrapper.find('.extensions__dialog').exists()).toBe(false)
    expect(removeMock).not.toHaveBeenCalled()
  })

  it('reports a failed revoke', async () => {
    removeMock.mockRejectedValueOnce(new Error('gone already'))
    const wrapper = await mountPage()
    await wrapper.find('tbody button').trigger('click')
    await confirmRevoke(wrapper)
    expect(wrapper.find('.extensions__banner--error').text()).toContain('gone already')
  })
})
