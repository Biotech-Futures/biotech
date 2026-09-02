import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import EventsPage from '@/views/EventsPage.vue'
import { useAuthStore } from '@/stores/auth'
import * as eventsApi from '@/utils/eventsAPI'
import * as adminApi from '@/utils/adminAPI'

vi.mock('vue-router', () => ({
  useRoute: vi.fn(() => ({ params: {}, name: 'events' })),
  useRouter: vi.fn(() => ({ push: vi.fn() }))
}))

const mockEvent1: eventsApi.BackendEvent = {
  id: 101,
  event_name: 'Biotech Innovation Summit',
  description: 'Annual gathering of biotech researchers.',
  start_datetime: '2026-10-15T09:00:00Z',
  ends_datetime: '2026-10-15T17:00:00Z',
  event_format: 'in_person',
  event_type: 'workshop',
  location: 'Hall A, Sydney Convention Centre',
  location_link: 'https://maps.google.com/test',
  event_image: 'https://example.com/banner.png',
  event_timezone: 'Australia/Sydney',
  accepted: false
}

const mockEvent2: eventsApi.BackendEvent = {
  id: 102,
  event_name: 'Virtual Mentoring Session',
  description: 'Online Q&A for student teams.',
  start_datetime: '2026-10-20T10:00:00Z',
  ends_datetime: '2026-10-20T11:30:00Z',
  event_format: 'virtual',
  event_type: 'mentoring',
  location: null,
  location_link: 'https://zoom.us/j/123456789',
  event_image: null,
  event_timezone: 'Australia/Sydney',
  accepted: true
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

describe('EventsPage - Admin Integration & Role Access', () => {
  beforeEach(() => {
    setActivePinia(createPinia())

    vi.spyOn(eventsApi, 'fetchEvents').mockResolvedValue({
      results: [mockEvent1, mockEvent2],
      count: 2,
      next: null
    } as any)

    vi.spyOn(eventsApi, 'fetchMyEventRsvps').mockResolvedValue({} as any)

    vi.spyOn(adminApi, 'fetchAdminEventMetaGroups').mockResolvedValue([
      { id: 1, groupName: 'Team Alpha' },
      { id: 2, groupName: 'Team Beta' }
    ])

    vi.spyOn(adminApi, 'fetchAdminEventMetaRoles').mockResolvedValue([
      { id: 1, roleName: 'student' },
      { id: 2, roleName: 'mentor' }
    ])

    vi.spyOn(adminApi, 'fetchAdminEventTargets').mockResolvedValue({
      groupIds: [1],
      roleIds: [1]
    })

    vi.spyOn(adminApi, 'fetchAdminEventRsvps').mockResolvedValue([
      {
        id: 1,
        eventId: 101,
        userId: 10,
        rsvpStatus: 'accepted',
        respondedAt: '2026-09-01T12:00:00Z'
      }
    ])

    vi.spyOn(adminApi, 'fetchAdminUsers').mockResolvedValue({
      items: [
        {
          id: 10,
          firstName: 'Sam',
          lastName: 'Student',
          email: 'student@example.com'
        } as any
      ],
      total: 1,
      page: 1,
      limit: 200,
      hasMore: false
    })

    vi.spyOn(adminApi, 'createAdminEvent').mockResolvedValue({
      id: 103,
      eventName: 'New Test Event'
    } as any)

    vi.spyOn(adminApi, 'updateAdminEvent').mockResolvedValue({
      id: 101,
      eventName: 'Updated Event'
    } as any)

    vi.spyOn(adminApi, 'deleteAdminEvent').mockResolvedValue({
      id: 101
    } as any)
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
    vi.restoreAllMocks()
  })

  const mountPage = async () => {
    wrapper = mount(EventsPage, {
      global: {
        stubs: {
          RouterLink: true
        },
        mocks: {
          $route: { params: {}, name: 'events' },
          $router: { push: vi.fn() }
        }
      },
      attachTo: document.body
    })
    await flushPromises()
    return wrapper
  }

  describe('Student Access View', () => {
    it('does NOT render admin controls (New Event button, card checkboxes, More buttons)', async () => {
      const auth = useAuthStore()
      auth.user = studentUser

      const w = await mountPage()

      // Header should not have New Event button
      expect(w.find('.page-head__actions').exists()).toBe(false)
      expect(w.text()).not.toContain('New Event')

      // Cards should not have select checkboxes or More buttons
      expect(w.find('.event-card-select').exists()).toBe(false)
      expect(w.find('.event-card-more-btn').exists()).toBe(false)
      expect(w.find('.bulk-actions-bar').exists()).toBe(false)
    })
  })

  describe('Admin Access View', () => {
    it('renders admin controls (New Event button, card checkboxes, More buttons)', async () => {
      const auth = useAuthStore()
      auth.user = adminUser

      const w = await mountPage()

      // Header should have New Event button
      const newEventBtn = w.find('.page-head__actions .btn-primary')
      expect(newEventBtn.exists()).toBe(true)
      expect(newEventBtn.text()).toContain('New Event')

      // Cards should have select checkboxes and More buttons
      const checkboxes = w.findAll('.event-card-checkbox')
      expect(checkboxes.length).toBe(2)

      const moreBtns = w.findAll('.event-card-more-btn')
      expect(moreBtns.length).toBe(2)
    })

    it('opens New Event form sheet when clicking New Event button', async () => {
      const auth = useAuthStore()
      auth.user = adminUser

      const w = await mountPage()

      const newEventBtn = w.find('.page-head__actions .btn-primary')
      await newEventBtn.trigger('click')
      await flushPromises()

      // The FormSheet dialog should be mounted to document body
      const dialog = document.body.querySelector('.admin-sheet')
      expect(dialog).not.toBeNull()
      expect(dialog?.textContent).toContain('New Event')
      expect(dialog?.textContent).toContain('Event Name *')
      expect(dialog?.textContent).toContain('Event Format *')
      expect(dialog?.textContent).toContain('Timezone *')
      expect(dialog?.textContent).toContain('Target Groups')
      expect(dialog?.textContent).toContain('Target Roles')
    })

    it('toggles the More actions dropdown on event card', async () => {
      const auth = useAuthStore()
      auth.user = adminUser

      const w = await mountPage()

      const firstMoreBtn = w.findAll('.event-card-more-btn')[0]
      await firstMoreBtn.trigger('click')
      await flushPromises()

      // Dropdown menu should be visible
      const dropdown = w.find('.event-card-dropdown')
      expect(dropdown.exists()).toBe(true)
      expect(dropdown.text()).toContain('View Details')
      expect(dropdown.text()).toContain('See RSVPs')
      expect(dropdown.text()).toContain('Edit')
      expect(dropdown.text()).toContain('Delete')
    })

    it('opens See RSVPs side panel when clicking See RSVPs in dropdown', async () => {
      const auth = useAuthStore()
      auth.user = adminUser

      const w = await mountPage()

      // Open menu
      await w.findAll('.event-card-more-btn')[0].trigger('click')
      await flushPromises()

      // Click 'See RSVPs'
      const rsvpMenuItem = w
        .findAll('.event-card-dropdown-item')
        .find((el) => el.text().includes('See RSVPs'))
      expect(rsvpMenuItem).toBeDefined()
      await rsvpMenuItem?.trigger('click')
      await flushPromises()

      // RSVPs sheet should be rendered
      expect(adminApi.fetchAdminEventRsvps).toHaveBeenCalledWith(101)
      const rsvpsSheet = document.body.querySelector('.admin-event-rsvps')
      expect(rsvpsSheet).not.toBeNull()
      expect(rsvpsSheet?.textContent).toContain('Sam Student')
      expect(rsvpsSheet?.textContent).toContain('student@example.com')
      expect(rsvpsSheet?.textContent).toContain('Going')
    })

    it('opens Edit Event form sheet when clicking Edit in dropdown', async () => {
      const auth = useAuthStore()
      auth.user = adminUser

      const w = await mountPage()

      // Open menu
      await w.findAll('.event-card-more-btn')[0].trigger('click')
      await flushPromises()

      // Click 'Edit'
      const editMenuItem = w
        .findAll('.event-card-dropdown-item')
        .find((el) => el.text().includes('Edit'))
      expect(editMenuItem).toBeDefined()
      await editMenuItem?.trigger('click')
      await flushPromises()

      // Edit sheet should open prefilled
      const editDialog = document.body.querySelector('.admin-sheet')
      expect(editDialog).not.toBeNull()
      expect(editDialog?.textContent).toContain('Edit Event')
      const nameInput = editDialog?.querySelector('#ev-name') as HTMLInputElement
      expect(nameInput?.value).toBe('Biotech Innovation Summit')
    })

    it('opens confirmation dialog when clicking Delete in dropdown', async () => {
      const auth = useAuthStore()
      auth.user = adminUser

      const w = await mountPage()

      // Open menu
      await w.findAll('.event-card-more-btn')[0].trigger('click')
      await flushPromises()

      // Click 'Delete'
      const deleteMenuItem = w
        .findAll('.event-card-dropdown-item')
        .find((el) => el.text().includes('Delete'))
      expect(deleteMenuItem).toBeDefined()
      await deleteMenuItem?.trigger('click')
      await flushPromises()

      // Single delete ConfirmDialog should be visible
      const confirmDialog = document.body.querySelector('.admin-modal--confirm')
      expect(confirmDialog).not.toBeNull()
      expect(confirmDialog?.textContent).toContain('Delete Event')
      expect(confirmDialog?.textContent).toContain('Biotech Innovation Summit')

      // Confirm deletion
      const confirmBtn = confirmDialog?.querySelector('.btn-danger') as HTMLButtonElement
      expect(confirmBtn).not.toBeNull()
      confirmBtn.click()
      await flushPromises()

      expect(adminApi.deleteAdminEvent).toHaveBeenCalledWith(101)
    })

    it('supports bulk selection and bulk delete', async () => {
      const auth = useAuthStore()
      auth.user = adminUser

      const w = await mountPage()

      // Select both events
      const checkboxes = w.findAll('.event-card-checkbox')
      await checkboxes[0].trigger('change')
      await checkboxes[1].trigger('change')
      await flushPromises()

      // BulkActionsBar should appear
      const bulkBar = w.find('.bulk-actions-bar')
      expect(bulkBar.exists()).toBe(true)
      expect(bulkBar.text()).toContain('2 events selected')

      // Click Delete on bulk bar
      const bulkDeleteBtn = bulkBar.find('.btn-danger')
      expect(bulkDeleteBtn.exists()).toBe(true)
      await bulkDeleteBtn.trigger('click')
      await flushPromises()

      // Bulk ConfirmDialog should appear
      const confirmDialog = document.body.querySelector('.admin-modal--confirm')
      expect(confirmDialog).not.toBeNull()
      expect(confirmDialog?.textContent).toContain('Delete Events')
      expect(confirmDialog?.textContent).toContain('Delete 2 events?')

      // Confirm bulk deletion
      const confirmBtn = confirmDialog?.querySelector('.btn-danger') as HTMLButtonElement
      expect(confirmBtn).not.toBeNull()
      confirmBtn.click()
      await flushPromises()

      expect(adminApi.deleteAdminEvent).toHaveBeenCalledWith(101)
      expect(adminApi.deleteAdminEvent).toHaveBeenCalledWith(102)
    })

    it('opens event details modal when clicking View Details in More dropdown', async () => {
      const auth = useAuthStore()
      auth.user = adminUser

      const w = await mountPage()

      // Open menu on first card
      await w.findAll('.event-card-more-btn')[0].trigger('click')
      await flushPromises()

      // Click 'View Details'
      const viewMenuItem = w
        .findAll('.event-card-dropdown-item')
        .find((el) => el.text().includes('View Details'))
      expect(viewMenuItem).toBeDefined()
      await viewMenuItem?.trigger('click')
      await flushPromises()

      // Details modal should open
      const modal = w.find('.modal')
      expect(modal.classes()).toContain('show')
      expect(modal.text()).toContain('Biotech Innovation Summit')
    })

    it('validates required fields and submits in AdminEventFormSheet', async () => {
      const auth = useAuthStore()
      auth.user = adminUser

      const w = await mountPage()

      // Open New Event
      await w.find('.page-head__actions .btn-primary').trigger('click')
      await flushPromises()

      const dialog = document.body.querySelector('.admin-sheet') as HTMLElement
      expect(dialog).not.toBeNull()

      const nameInput = dialog.querySelector('#ev-name') as HTMLInputElement
      const form = dialog.querySelector('form') as HTMLFormElement

      // Submit with empty name
      nameInput.value = ''
      nameInput.dispatchEvent(new Event('input'))
      form.dispatchEvent(new Event('submit'))
      await flushPromises()

      expect(dialog.textContent).toContain('Event name is required.')
      expect(adminApi.createAdminEvent).not.toHaveBeenCalled()

      // Fill in valid name and submit
      nameInput.value = 'Annual Biotech Showcase'
      nameInput.dispatchEvent(new Event('input'))
      form.dispatchEvent(new Event('submit'))
      await flushPromises()

      expect(adminApi.createAdminEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          eventName: 'Annual Biotech Showcase',
          eventFormat: 'in_person'
        })
      )
    })

    it('filters attendees in AdminEventRsvpsSheet via search input', async () => {
      const auth = useAuthStore()
      auth.user = adminUser

      const w = await mountPage()

      // Open menu and RSVPs sheet
      await w.findAll('.event-card-more-btn')[0].trigger('click')
      await flushPromises()

      const rsvpMenuItem = w
        .findAll('.event-card-dropdown-item')
        .find((el) => el.text().includes('See RSVPs'))
      await rsvpMenuItem?.trigger('click')
      await flushPromises()

      const rsvpsSheet = document.body.querySelector('.admin-event-rsvps') as HTMLElement
      expect(rsvpsSheet).not.toBeNull()
      expect(rsvpsSheet.textContent).toContain('Sam Student')

      const searchInput = rsvpsSheet.querySelector('.admin-event-rsvps__search-input') as HTMLInputElement
      expect(searchInput).not.toBeNull()

      // Search for non-matching name
      searchInput.value = 'Nonexistent Person'
      searchInput.dispatchEvent(new Event('input'))
      await flushPromises()

      expect(rsvpsSheet.textContent).toContain('No matching RSVPs found')

      // Clear search
      searchInput.value = ''
      searchInput.dispatchEvent(new Event('input'))
      await flushPromises()

      expect(rsvpsSheet.textContent).toContain('Sam Student')
    })
  })
})
