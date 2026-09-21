import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AdminViewQueryDrawer from '../AdminViewQueryDrawer.vue'
import * as adminAPI from '@/utils/adminAPI'

vi.mock('@/utils/adminAPI', async (importOriginal) => {
  const actual = await importOriginal<typeof adminAPI>()
  return {
    ...actual,
    createAdminView: vi.fn(),
    updateAdminView: vi.fn(),
    fetchAdminCountries: vi.fn().mockResolvedValue([{ id: 1, countryName: 'Australia' }]),
    fetchAdminStates: vi.fn().mockResolvedValue([{ id: 1, stateName: 'NSW' }]),
  }
})

const mountDrawer = (props: Record<string, unknown> = {}) => {
  return mount(AdminViewQueryDrawer, {
    props: {
      modelValue: true,
      view: null,
      ...props,
    },
    global: {
      stubs: {
        FormSheet: {
          props: ['modelValue', 'title', 'description'],
          template: '<div class="form-sheet-stub" v-if="modelValue"><h2>{{ title }}</h2><slot /><slot name="footer" /></div>',
        },
      },
    },
  })
}

describe('AdminViewQueryDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders correctly when open in create mode', async () => {
    const wrapper = mountDrawer()
    await flushPromises()

    expect(wrapper.text()).toContain('Create View')
    expect(wrapper.text()).toContain('View Details')
    expect(wrapper.text()).toContain('Target Roles & Base Filters')
    expect(wrapper.text()).toContain('Advanced Conditions')
    expect(wrapper.text()).toContain('Visible Fields / Columns to Show')
  })

  it('shows error message if submitted with empty name', async () => {
    const wrapper = mountDrawer()
    await flushPromises()

    const nameInput = wrapper.find('#view-name')
    await nameInput.setValue('')

    const form = wrapper.find('form')
    await form.trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.text()).toContain('View Name is required.')
    expect(adminAPI.createAdminView).not.toHaveBeenCalled()
  })

  it('submits create payload when valid', async () => {
    const mockCreatedView: adminAPI.AdminView = {
      id: 99,
      name: 'Test View',
      description: 'Test Description',
      isDefault: false,
      targetRoles: ['student'],
      accountStatus: 'active',
      engagementStatus: 'all',
      advancedConditions: [],
      visibleColumns: ['name', 'email', 'role', 'status'],
    }
    vi.mocked(adminAPI.createAdminView).mockResolvedValueOnce(mockCreatedView)

    const wrapper = mountDrawer()
    await flushPromises()

    await wrapper.find('#view-name').setValue('Test View')
    await wrapper.find('#view-desc').setValue('Test Description')

    const form = wrapper.find('form')
    await form.trigger('submit.prevent')
    await flushPromises()

    expect(adminAPI.createAdminView).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Test View',
        description: 'Test Description',
      })
    )
    expect(wrapper.emitted('saved')).toBeTruthy()
    expect(wrapper.emitted('saved')![0][0]).toEqual(mockCreatedView)
  })

  it('populates fields and calls updateAdminView in edit mode', async () => {
    const existingView: adminAPI.AdminView = {
      id: 42,
      name: 'Existing View',
      description: 'Existing Description',
      isDefault: false,
      targetRoles: ['mentor'],
      accountStatus: 'inactive',
      engagementStatus: 'matched',
      advancedConditions: [{ field: 'state', operator: 'equals', value: 'NSW' }],
      visibleColumns: ['name', 'email', 'state'],
    }

    const mockUpdatedView = { ...existingView, name: 'Updated View' }
    vi.mocked(adminAPI.updateAdminView).mockResolvedValueOnce(mockUpdatedView)

    const wrapper = mountDrawer({ view: existingView })
    await flushPromises()

    expect(wrapper.text()).toContain('Edit View')
    const nameInput = wrapper.find('#view-name')
    expect((nameInput.element as HTMLInputElement).value).toBe('Existing View')

    await nameInput.setValue('Updated View')
    const form = wrapper.find('form')
    await form.trigger('submit.prevent')
    await flushPromises()

    expect(adminAPI.updateAdminView).toHaveBeenCalledWith(
      42,
      expect.objectContaining({
        name: 'Updated View',
      })
    )
    expect(wrapper.emitted('saved')![0][0]).toEqual(mockUpdatedView)
  })
})
