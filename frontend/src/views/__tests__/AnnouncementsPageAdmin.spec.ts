import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import AnnouncementsPage from '@/views/AnnouncementsPage.vue'
import AdminAnnouncementFormSheet from '@/components/admin/announcements/AdminAnnouncementFormSheet.vue'
import AnnouncementCard from '@/components/announcements/AnnouncementCard.vue'
import { useAuthStore } from '@/stores/auth'
import * as adminApi from '@/utils/adminAPI'

const mockPush = vi.fn()
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: vi.fn(() => ({ params: {}, name: 'announcements' })),
    useRouter: vi.fn(() => ({ push: mockPush }))
  }
})

const mockApiAnnouncements = [
  {
    id: 201,
    title: 'Welcome to the Biotech Competition',
    body: '<p>Welcome all participants! Please check the guidelines.</p>',
    visibility_scope: 'global',
    published_at: '2026-04-10T09:00:00Z',
    archived_at: null,
    sender_name: 'Administrator',
    images: [],
    audiences: []
  },
  {
    id: 202,
    title: 'Mentor Briefing Session',
    body: '<p>Briefing session scheduled for all mentors.</p>',
    visibility_scope: 'role_based',
    published_at: '2026-04-05T14:00:00Z',
    archived_at: null,
    sender_name: 'Administrator',
    images: [],
    audiences: [{ id: 1, role_name: 'Mentor', group: null }]
  }
]

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

describe('AnnouncementsPage - Admin Integration', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockPush.mockClear()

    globalThis.fetch = vi.fn((url: RequestInfo | URL) => {
      const urlStr = String(url)
      if (urlStr.includes('/announcements/v1/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ results: mockApiAnnouncements }),
          text: async () => JSON.stringify({ results: mockApiAnnouncements }),
          headers: new Headers()
        } as unknown as Response)
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({ results: [] }),
        text: async () => JSON.stringify({ results: [] }),
        headers: new Headers()
      } as unknown as Response)
    }) as unknown as typeof fetch

    vi.spyOn(adminApi, 'fetchAnnouncementRoles').mockResolvedValue([
      { id: 1, name: 'Student' },
      { id: 2, name: 'Mentor' }
    ])
    vi.spyOn(adminApi, 'fetchAnnouncementGroups').mockResolvedValue([
      { id: 10, name: 'Team Alpha' },
      { id: 20, name: 'Team Beta' }
    ])
    vi.spyOn(adminApi, 'createAdminAnnouncement').mockResolvedValue({
      id: 203,
      title: 'New Announcement',
      body: '<p>Created content</p>',
      visibilityScope: 'global',
      publishedAt: '2026-04-10T10:00:00Z',
      archivedAt: null,
      authorUserId: 1,
      audiences: []
    })
    vi.spyOn(adminApi, 'updateAdminAnnouncement').mockResolvedValue({
      id: 201,
      title: 'Updated Welcome Title',
      body: '<p>Updated content</p>',
      visibilityScope: 'global',
      publishedAt: '2026-04-01T09:00:00Z',
      archivedAt: null,
      authorUserId: 1,
      audiences: []
    })
    vi.spyOn(adminApi, 'archiveAdminAnnouncement').mockResolvedValue({
      id: 201,
      title: 'Welcome to the Biotech Competition',
      visibilityScope: 'global',
      publishedAt: '2026-04-01T09:00:00Z',
      archivedAt: '2026-04-06T10:00:00Z',
      authorUserId: 1,
      audiences: []
    })
    vi.spyOn(adminApi, 'deleteAdminAnnouncement').mockResolvedValue({} as any)
    vi.spyOn(adminApi, 'notifyAdminAnnouncement').mockResolvedValue({
      msg: 'Announcement email sent successfully',
      status: 'success',
      attempted: 5,
      succeeded: 5,
      failed: 0
    })
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    vi.restoreAllMocks()
  })

  describe('Student Access View', () => {
    it('does NOT render admin buttons or dropdown menus for students', async () => {
      const auth = useAuthStore()
      auth.user = studentUser
      auth.initialized = true

      wrapper = mount(AnnouncementsPage, {
        global: {
          stubs: {
            RouterLink: true,
            AdminAnnouncementFormSheet: true,
            ConfirmDialog: true,
            BulkActionsBar: true
          }
        }
      })
      await flushPromises()

      // Header admin buttons
      expect(wrapper.text()).not.toContain('New Announcement')
      expect(wrapper.text()).not.toContain('Batch Mode')

      // No more options dropdown button
      expect(wrapper.findAll('.announcement__more-btn')).toHaveLength(0)

      // No checkboxes
      expect(wrapper.findAll('.announcement__checkbox')).toHaveLength(0)
    })
  })

  describe('Admin Access View', () => {
    beforeEach(() => {
      const auth = useAuthStore()
      auth.user = adminUser
      auth.initialized = true
    })

    it('renders "New Announcement" and "Batch Mode" buttons for admins', async () => {
      wrapper = mount(AnnouncementsPage, {
        global: {
          stubs: {
            RouterLink: true,
            AdminAnnouncementFormSheet: true,
            ConfirmDialog: true,
            BulkActionsBar: true
          }
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('New Announcement')
      expect(wrapper.text()).toContain('Batch Mode')

      // Announcement cards render the More actions button
      const moreBtns = wrapper.findAll('.announcement__more-btn')
      expect(moreBtns.length).toBeGreaterThan(0)
    })

    it('opens card more dropdown with View Details, Edit, Send Notification, Archive, and Delete', async () => {
      wrapper = mount(AnnouncementsPage, {
        global: {
          stubs: {
            RouterLink: true,
            AdminAnnouncementFormSheet: true,
            ConfirmDialog: true,
            BulkActionsBar: true
          }
        }
      })
      await flushPromises()

      const firstMoreBtn = wrapper.find('.announcement__more-btn')
      expect(firstMoreBtn.exists()).toBe(true)

      // Click more button
      await firstMoreBtn.trigger('click')
      await flushPromises()

      const dropdown = wrapper.find('.announcement__dropdown')
      expect(dropdown.exists()).toBe(true)
      expect(dropdown.text()).toContain('View Details')
      expect(dropdown.text()).toContain('Edit')
      expect(dropdown.text()).toContain('Send Notification')
      expect(dropdown.text()).toContain('Archive')
      expect(dropdown.text()).toContain('Delete')
    })

    it('navigates when View Details is clicked in card menu without propagation error', async () => {
      wrapper = mount(AnnouncementsPage, {
        global: {
          stubs: {
            RouterLink: true,
            AdminAnnouncementFormSheet: true,
            ConfirmDialog: true,
            BulkActionsBar: true
          }
        }
      })
      await flushPromises()

      await wrapper.find('.announcement__more-btn').trigger('click')
      await flushPromises()

      const viewBtn = wrapper.findAll('.announcement__dropdown-item').find(b => b.text().includes('View Details'))
      expect(viewBtn).toBeDefined()
      await viewBtn!.trigger('click')

      expect(mockPush).toHaveBeenCalledWith({
        name: 'announcement-detail',
        params: { id: 201 }
      })
    })

    it('opens AdminAnnouncementFormSheet in create mode when New Announcement is clicked', async () => {
      wrapper = mount(AnnouncementsPage, {
        global: {
          stubs: {
            RouterLink: true,
            AdminAnnouncementFormSheet: true,
            ConfirmDialog: true,
            BulkActionsBar: true
          }
        }
      })
      await flushPromises()

      const newBtn = wrapper.findAll('button').find(b => b.text().includes('New Announcement'))
      expect(newBtn).toBeDefined()
      await newBtn!.trigger('click')
      await flushPromises()

      const sheet = wrapper.findComponent(AdminAnnouncementFormSheet)
      expect(sheet.exists()).toBe(true)
      expect(sheet.props('modelValue')).toBe(true)
      expect(sheet.props('announcement')).toBeNull()
    })

    it('opens AdminAnnouncementFormSheet in edit mode when Edit is clicked on card menu', async () => {
      wrapper = mount(AnnouncementsPage, {
        global: {
          stubs: {
            RouterLink: true,
            AdminAnnouncementFormSheet: true,
            ConfirmDialog: true,
            BulkActionsBar: true
          }
        }
      })
      await flushPromises()

      await wrapper.find('.announcement__more-btn').trigger('click')
      await flushPromises()

      const editBtn = wrapper.findAll('.announcement__dropdown-item').find(b => b.text().includes('Edit'))
      expect(editBtn).toBeDefined()
      await editBtn!.trigger('click')
      await flushPromises()

      const sheet = wrapper.findComponent(AdminAnnouncementFormSheet)
      expect(sheet.exists()).toBe(true)
      expect(sheet.props('modelValue')).toBe(true)
      expect(sheet.props('announcement')?.id).toBe(201)
    })

    it('handles archive action from card menu with confirmation', async () => {
      wrapper = mount(AnnouncementsPage, {
        global: {
          stubs: {
            RouterLink: true,
            AdminAnnouncementFormSheet: true,
            BulkActionsBar: true
          }
        }
      })
      await flushPromises()

      await wrapper.find('.announcement__more-btn').trigger('click')
      await flushPromises()

      const archiveBtn = wrapper.findAll('.announcement__dropdown-item').find(b => b.text().includes('Archive'))
      expect(archiveBtn).toBeDefined()
      await archiveBtn!.trigger('click')
      await flushPromises()

      // ConfirmDialog is opened
      const confirmDialog = wrapper.findComponent({ name: 'ConfirmDialog' })
      expect(confirmDialog.exists()).toBe(true)
      expect(confirmDialog.props('modelValue')).toBe(true)

      // Confirm archive
      confirmDialog.vm.$emit('confirm')
      await flushPromises()

      expect(adminApi.archiveAdminAnnouncement).toHaveBeenCalledWith(201)
    })

    it('handles delete action from card menu with confirmation', async () => {
      wrapper = mount(AnnouncementsPage, {
        global: {
          stubs: {
            RouterLink: true,
            AdminAnnouncementFormSheet: true,
            BulkActionsBar: true
          }
        }
      })
      await flushPromises()

      await wrapper.find('.announcement__more-btn').trigger('click')
      await flushPromises()

      const deleteBtn = wrapper.findAll('.announcement__dropdown-item').find(b => b.text().includes('Delete'))
      expect(deleteBtn).toBeDefined()
      await deleteBtn!.trigger('click')
      await flushPromises()

      const confirmDialog = wrapper.findComponent({ name: 'ConfirmDialog' })
      expect(confirmDialog.exists()).toBe(true)
      expect(confirmDialog.props('modelValue')).toBe(true)

      // Confirm delete
      confirmDialog.vm.$emit('confirm')
      await flushPromises()

      expect(adminApi.deleteAdminAnnouncement).toHaveBeenCalledWith(201)
    })

    it('handles send email notification action with confirmation', async () => {
      wrapper = mount(AnnouncementsPage, {
        global: {
          stubs: {
            RouterLink: true,
            AdminAnnouncementFormSheet: true,
            BulkActionsBar: true
          }
        }
      })
      await flushPromises()

      await wrapper.find('.announcement__more-btn').trigger('click')
      await flushPromises()

      const notifyBtn = wrapper.findAll('.announcement__dropdown-item').find(b => b.text().includes('Send Notification'))
      expect(notifyBtn).toBeDefined()
      await notifyBtn!.trigger('click')
      await flushPromises()

      const confirmDialog = wrapper.findComponent({ name: 'ConfirmDialog' })
      expect(confirmDialog.exists()).toBe(true)
      expect(confirmDialog.props('modelValue')).toBe(true)

      // Confirm notify
      confirmDialog.vm.$emit('confirm')
      await flushPromises()

      expect(adminApi.notifyAdminAnnouncement).toHaveBeenCalledWith(201)
      expect(wrapper.text()).toContain('Email notification sent successfully')
    })

    it('toggles batch mode and shows checkboxes on announcement cards', async () => {
      wrapper = mount(AnnouncementsPage, {
        global: {
          stubs: {
            RouterLink: true,
            AdminAnnouncementFormSheet: true,
            ConfirmDialog: true,
            BulkActionsBar: true
          }
        }
      })
      await flushPromises()

      expect(wrapper.findAll('.announcement__checkbox')).toHaveLength(0)

      // Click Batch Mode button
      const batchBtn = wrapper.findAll('button').find(b => b.text().includes('Batch Mode'))
      expect(batchBtn).toBeDefined()
      await batchBtn!.trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('Exit Batch Mode')
      const checkboxes = wrapper.findAll('.announcement__checkbox')
      expect(checkboxes.length).toBe(2)
    })

    it('supports selecting multiple cards and triggers bulk actions', async () => {
      wrapper = mount(AnnouncementsPage, {
        global: {
          stubs: {
            RouterLink: true,
            AdminAnnouncementFormSheet: true
          }
        }
      })
      await flushPromises()

      // Enter Batch Mode
      const batchBtn = wrapper.findAll('button').find(b => b.text().includes('Batch Mode'))
      await batchBtn!.trigger('click')
      await flushPromises()

      // Select both cards
      const cards = wrapper.findAllComponents(AnnouncementCard)
      cards[0].vm.$emit('toggle-select', 201)
      cards[1].vm.$emit('toggle-select', 202)
      await flushPromises()

      // Bulk actions bar should appear
      const bulkBar = wrapper.findComponent({ name: 'BulkActionsBar' })
      expect(bulkBar.exists()).toBe(true)
      expect(bulkBar.props('count')).toBe(2)

      // Click Archive in bulk bar
      const bulkArchiveBtn = bulkBar.findAll('button').find(b => b.text().includes('Archive'))
      expect(bulkArchiveBtn).toBeDefined()
      await bulkArchiveBtn!.trigger('click')
      await flushPromises()

      // Confirm dialog should be open
      const confirmDialog = wrapper.findComponent({ name: 'ConfirmDialog' })
      expect(confirmDialog.exists()).toBe(true)
      confirmDialog.vm.$emit('confirm')
      await flushPromises()

      expect(adminApi.archiveAdminAnnouncement).toHaveBeenCalledWith(201)
      expect(adminApi.archiveAdminAnnouncement).toHaveBeenCalledWith(202)
    })
  })
})
