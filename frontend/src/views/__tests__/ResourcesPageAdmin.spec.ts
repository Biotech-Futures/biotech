import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import ResourcesPage from '@/views/ResourcesPage.vue'
import AdminResourceFormSheet from '@/components/admin/resources/AdminResourceFormSheet.vue'
import { useAuthStore } from '@/stores/auth'
import * as resourcesApi from '@/utils/resourcesAPI'
import * as adminApi from '@/utils/adminAPI'

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: vi.fn(() => ({ params: {}, name: 'resources' })),
  useRouter: vi.fn(() => ({ push: mockPush }))
}))

const mockResource1: resourcesApi.Resource = {
  id: 101,
  name: 'Mentor Handbook 2026',
  description: 'Comprehensive guidebook for student mentors.',
  kind: 'file',
  type_name: 'Guide',
  file_mime_type: 'application/pdf',
  file_size: 1024 * 1024 * 2,
  uploaded_at: '2026-03-01T10:00:00Z',
  file_name: 'mentor_handbook.pdf',
  labels: [{ id: 1, name: 'Mentorship' }]
}

const mockResource2: resourcesApi.Resource = {
  id: 102,
  name: 'Biotech Competition Rules',
  description: 'Rules and evaluation criteria.',
  kind: 'page',
  type_name: 'Documentation',
  file_mime_type: 'text/html',
  file_size: null,
  uploaded_at: '2026-03-05T12:00:00Z',
  file_name: null,
  labels: [{ id: 2, name: 'Rules' }]
}

const studentUser = {
  id: 10,
  email: 'student@example.com',
  first_name: 'Sam',
  last_name: 'Student',
  current_role_name: 'student'
} as never

const adminUser = {
  id: 1,
  email: 'admin@example.com',
  first_name: 'Alex',
  last_name: 'Admin',
  current_role_name: 'admin'
} as never

let wrapper: VueWrapper | null = null

describe('ResourcesPage - Admin Integration & Role Access', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockPush.mockClear()

    vi.spyOn(resourcesApi, 'fetchResources').mockResolvedValue({
      results: [mockResource1, mockResource2],
      count: 2
    })
    vi.spyOn(resourcesApi, 'fetchResourceLabels').mockResolvedValue([
      { id: 1, name: 'Mentorship', resource_count: 5 },
      { id: 2, name: 'Rules', resource_count: 2 }
    ])
    vi.spyOn(resourcesApi, 'fetchResourceTypes').mockResolvedValue([
      { id: 1, type_name: 'Guide', type_description: 'Guidebooks' },
      { id: 2, type_name: 'Documentation', type_description: 'Docs' }
    ])

    vi.spyOn(adminApi, 'fetchAdminResourceRoles').mockResolvedValue([
      { id: 1, slug: 'student', type_name: 'Student' },
      { id: 2, slug: 'mentor', type_name: 'Mentor' },
      { id: 3, slug: 'admin', type_name: 'Admin' }
    ])
    vi.spyOn(adminApi, 'uploadAdminResource').mockResolvedValue({} as any)
    vi.spyOn(adminApi, 'createAdminResource').mockResolvedValue({} as any)
    vi.spyOn(adminApi, 'updateAdminResource').mockResolvedValue({} as any)
    vi.spyOn(adminApi, 'deleteAdminResource').mockResolvedValue(null as any)
    vi.spyOn(adminApi, 'downloadAdminResourceFile').mockResolvedValue(undefined)
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    vi.restoreAllMocks()
  })

  describe('Student Access View', () => {
    it('does NOT render admin controls (Upload button, Actions column, More buttons)', async () => {
      const auth = useAuthStore()
      auth.user = studentUser
      auth.initialized = true

      wrapper = mount(ResourcesPage, {
        global: {
          stubs: {
            AdminResourceFormSheet: true,
            ConfirmDialog: true
          }
        }
      })
      await flushPromises()

      // Header button
      expect(wrapper.text()).not.toContain('Upload Resource')

      // Table headers
      expect(wrapper.find('.th-actions').exists()).toBe(false)

      // More buttons
      expect(wrapper.findAll('.resource-more-btn')).toHaveLength(0)

      // Rows are still rendered for student
      const rows = wrapper.findAll('.resource-row')
      expect(rows).toHaveLength(2)

      // Clicking row calls router.push
      await rows[0].trigger('click')
      expect(mockPush).toHaveBeenCalledWith({
        name: 'resource-detail',
        params: { id: 101 }
      })
    })
  })

  describe('Admin Access View', () => {
    beforeEach(async () => {
      const auth = useAuthStore()
      auth.user = adminUser
      auth.initialized = true

      wrapper = mount(ResourcesPage, {
        global: {
          stubs: {
            AdminResourceFormSheet: true,
            ConfirmDialog: true
          }
        }
      })
      await flushPromises()
    })

    it('renders elevated admin controls (Upload Resource button, Actions header, More buttons)', () => {
      expect(wrapper?.text()).toContain('Upload Resource')
      expect(wrapper?.find('.th-actions').exists()).toBe(true)

      const moreButtons = wrapper?.findAll('.resource-more-btn')
      expect(moreButtons?.length).toBe(2)
    })

    it('opens Upload Resource side panel when clicking Upload Resource button', async () => {
      const uploadBtn = wrapper?.findAll('button').find((b) => b.text().includes('Upload Resource'))
      expect(uploadBtn).toBeDefined()

      await uploadBtn?.trigger('click')
      await flushPromises()

      const formSheet = wrapper?.findComponent({ name: 'AdminResourceFormSheet' })
      expect(formSheet?.exists()).toBe(true)
      expect(formSheet?.props('modelValue')).toBe(true)
      expect(formSheet?.props('resource')).toBeNull()
    })

    it('toggles the More actions dropdown on resource row', async () => {
      const moreBtn = wrapper?.find('.resource-more-btn')
      expect(moreBtn?.exists()).toBe(true)

      expect(wrapper?.find('.resource-dropdown').exists()).toBe(false)

      await moreBtn?.trigger('click')
      await flushPromises()

      const dropdown = wrapper?.find('.resource-dropdown')
      expect(dropdown?.exists()).toBe(true)
      expect(dropdown?.text()).toContain('View Details')
      expect(dropdown?.text()).toContain('Edit Resource')
      expect(dropdown?.text()).toContain('Download')
      expect(dropdown?.text()).toContain('Delete Resource')

      // Clicking outside / toggling again closes it
      await moreBtn?.trigger('click')
      await flushPromises()
      expect(wrapper?.find('.resource-dropdown').exists()).toBe(false)
    })

    it('navigates to detail page when clicking View Details in More dropdown without triggering row click collision', async () => {
      const moreBtn = wrapper?.find('.resource-more-btn')
      await moreBtn?.trigger('click')
      await flushPromises()

      const viewDetailsBtn = wrapper?.findAll('.resource-dropdown-item').find((b) => b.text().includes('View Details'))
      expect(viewDetailsBtn).toBeDefined()

      await viewDetailsBtn?.trigger('click')
      await flushPromises()

      expect(mockPush).toHaveBeenCalledWith({
        name: 'resource-detail',
        params: { id: 101 }
      })
    })

    it('opens Edit Resource form sheet when clicking Edit in dropdown', async () => {
      const moreBtn = wrapper?.find('.resource-more-btn')
      await moreBtn?.trigger('click')
      await flushPromises()

      const editBtn = wrapper?.findAll('.resource-dropdown-item').find((b) => b.text().includes('Edit Resource'))
      expect(editBtn).toBeDefined()

      await editBtn?.trigger('click')
      await flushPromises()

      const formSheet = wrapper?.findComponent({ name: 'AdminResourceFormSheet' })
      expect(formSheet?.props('modelValue')).toBe(true)
      expect(formSheet?.props('resource')).toEqual(mockResource1)
    })

    it('triggers download when clicking Download in dropdown for file resource', async () => {
      const moreBtn = wrapper?.find('.resource-more-btn')
      await moreBtn?.trigger('click')
      await flushPromises()

      const downloadBtn = wrapper?.findAll('.resource-dropdown-item').find((b) => b.text().includes('Download'))
      expect(downloadBtn).toBeDefined()

      await downloadBtn?.trigger('click')
      await flushPromises()

      expect(adminApi.downloadAdminResourceFile).toHaveBeenCalledWith(101, 'mentor_handbook.pdf')
    })

    it('opens ConfirmDialog when clicking Delete Resource in dropdown and executes delete', async () => {
      const moreBtn = wrapper?.find('.resource-more-btn')
      await moreBtn?.trigger('click')
      await flushPromises()

      const deleteBtn = wrapper?.findAll('.resource-dropdown-item').find((b) => b.text().includes('Delete Resource'))
      expect(deleteBtn).toBeDefined()

      await deleteBtn?.trigger('click')
      await flushPromises()

      const confirmDialog = wrapper?.findComponent({ name: 'ConfirmDialog' })
      expect(confirmDialog?.props('modelValue')).toBe(true)
      expect(confirmDialog?.props('message')).toContain('Mentor Handbook 2026')

      // Emit confirm on dialog
      confirmDialog?.vm.$emit('confirm')
      await flushPromises()

      expect(adminApi.deleteAdminResource).toHaveBeenCalledWith(101)
      expect(resourcesApi.fetchResources).toHaveBeenCalled()
    })
  })

  describe('AdminResourceFormSheet Component', () => {
    it('validates required fields and shows visible roles on role-based visibility', async () => {
      const sheetWrapper = mount(AdminResourceFormSheet, {
        props: {
          modelValue: true,
          resource: null
        },
        global: {
          stubs: {
            FormSheet: {
              template: '<div><slot /></div>'
            }
          }
        }
      })
      await flushPromises()

      expect(sheetWrapper.text()).toContain('Upload Resource')
      expect(sheetWrapper.find('#res-kind').exists()).toBe(true)
      expect(sheetWrapper.find('#res-name').exists()).toBe(true)
      expect(sheetWrapper.find('#res-desc').exists()).toBe(true)
      expect(sheetWrapper.find('#res-visibility').exists()).toBe(true)

      // Submit empty form -> shows validation error
      await sheetWrapper.find('form').trigger('submit')
      await flushPromises()
      expect(sheetWrapper.find('.admin-resource-form__error').text()).toContain('Resource name is required')

      // Fill name & description
      await sheetWrapper.find('#res-name').setValue('New Handbook')
      await sheetWrapper.find('#res-desc').setValue('Handbook description')

      // Switch to role_based
      await sheetWrapper.find('#res-visibility').setValue('role_based')
      await flushPromises()

      // Shows visible roles checkboxes (Student and Mentor, excluding Admin)
      expect(sheetWrapper.text()).toContain('Visible Roles')
      expect(sheetWrapper.text()).toContain('Student')
      expect(sheetWrapper.text()).toContain('Mentor')
      expect(sheetWrapper.text()).not.toContain('Admin')

      // Submit without selecting roles -> error
      await sheetWrapper.find('form').trigger('submit')
      await flushPromises()
      expect(sheetWrapper.find('.admin-resource-form__error').text()).toContain('Please select at least one visible role')

      sheetWrapper.unmount()
    })
  })
})
