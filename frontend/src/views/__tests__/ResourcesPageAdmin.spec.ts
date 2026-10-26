import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import ResourcesPage from '@/views/ResourcesPage.vue'
import AdminResourceFormSheet from '@/components/admin/resources/AdminResourceFormSheet.vue'
import { useAuthStore } from '@/stores/auth'
import * as resourcesApi from '@/utils/resourcesAPI'
import * as adminApi from '@/utils/adminAPI'
import * as managementApi from '@/utils/managementAPI'
import { useRoute } from 'vue-router'
import { pickAppSelect } from '@/__tests__/appSelect'

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: vi.fn(() => ({ params: {}, query: {}, name: 'resources' })),
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

// When each is released (what Release Resources had): the handbook hidden and
// never released, the rules shown and released last February. By last year's
// release, the rules come first, as by latest modified.
const release = (
  id: number,
  name: string,
  extra: Partial<managementApi.ResourceReleaseRow> = {},
): managementApi.ResourceReleaseRow => ({
  id, name, shown: true, release_on: null, released: true, last_released_at: null, ...extra,
})
const releases = () => [
  release(101, 'Mentor Handbook 2026', { shown: false, released: false }),
  release(102, 'Biotech Competition Rules', { last_released_at: '2025-02-12T12:00:00+11:00' }),
]

let wrapper: VueWrapper | null = null

// The shared table's rows, and a row's own button by its text.
const tableRows = () => wrapper!.findAll('tr.data-table-row')
const rowButton = (rowIndex: number, label: string) =>
  tableRows()[rowIndex].findAll('button').find((button) => button.text() === label)

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
    vi.spyOn(managementApi, 'fetchResourceReleases').mockResolvedValue(releases())
    vi.spyOn(managementApi, 'saveResourceRelease').mockResolvedValue(release(102, 'Biotech Competition Rules'))
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    vi.restoreAllMocks()
  })

  describe('Student Access View', () => {
    it('does NOT render admin controls (Upload button, Actions columns, tick boxes)', async () => {
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
      expect(wrapper.text()).not.toContain('Add Resource')
      expect(wrapper.text()).not.toContain("Show Others' View")

      // No action columns or tick boxes, and no Kind: the name has the room.
      expect(wrapper.find('.data-table-actions-col').exists()).toBe(false)
      expect(wrapper.find('.data-table-check-col').exists()).toBe(false)
      expect(wrapper.findAll('thead th').map((th) => th.text()).filter(Boolean)).toEqual([
        'Icon', 'Name', 'Type', 'Labels', 'Modified',
      ])
      expect(wrapper.find('.resource-name-cell--wide').exists()).toBe(true)
      expect(managementApi.fetchResourceReleases).not.toHaveBeenCalled()

      // Rows are still rendered for student
      const rows = tableRows()
      expect(rows).toHaveLength(2)

      // Clicking a name calls router.push
      await rows[1].find('.data-table-cell--primary').trigger('click')
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

    it('renders elevated admin controls (Add Resource on the table, Edit, release columns, Checkboxes)', () => {
      // Add Resource beside the table's search; Show Others' View where it was.
      expect(wrapper!.get('.data-table-search-side').text()).toContain('Add Resource')
      expect(wrapper!.get('.resource-header__actions').text()).toBe("Show Others' View")
      expect(wrapper?.text()).not.toContain('Batch Mode')
      expect(wrapper?.find('th.data-table-check-col').exists()).toBe(true)
      expect(wrapper?.findAll('td.data-table-check-col')).toHaveLength(2)
      expect(wrapper!.findAll('thead th').map((th) => th.text()).filter(Boolean)).toEqual([
        'Icon', 'Name', 'Type', 'Labels', 'Modified', 'Edit', 'Show/Hide', 'Release At', 'Last Released',
      ])
      // What Release Resources said, now here.
      expect(wrapper!.text()).toContain('is released automatically at the start of its Release At date (Sydney time)')

      expect(rowButton(0, 'Edit')).toBeDefined()
      expect(rowButton(1, 'Edit')).toBeDefined()
    })

    it('opens Add Resource side panel when clicking Add Resource button', async () => {
      const uploadBtn = wrapper?.findAll('button').find((b) => b.text().includes('Add Resource'))
      expect(uploadBtn).toBeDefined()

      await uploadBtn?.trigger('click')
      await flushPromises()

      const formSheet = wrapper?.findComponent({ name: 'AdminResourceFormSheet' })
      expect(formSheet?.exists()).toBe(true)
      expect(formSheet?.props('modelValue')).toBe(true)
      expect(formSheet?.props('resource')).toBeNull()
    })

    it('shows Edit on each row, and no Delete, View or Download (Delete is in its panel, or for ticked rows)', () => {
      for (const row of [0, 1]) {
        expect(rowButton(row, 'Edit')).toBeDefined()
        expect(rowButton(row, 'Delete')).toBeUndefined()
        expect(rowButton(row, 'View')).toBeUndefined()
        expect(rowButton(row, 'Download')).toBeUndefined()
      }
    })

    it('opens a resource by its name, but not elsewhere on its row', async () => {
      await rowButton(1, 'Edit')?.trigger('click')
      await tableRows()[1].trigger('click')
      await flushPromises()
      expect(mockPush).not.toHaveBeenCalled()

      await tableRows()[1].find('.data-table-cell--primary').trigger('click')
      await flushPromises()
      expect(mockPush).toHaveBeenCalledWith({
        name: 'resource-detail',
        params: { id: 101 }
      })
    })

    it('lists each by when it was released last year, those never released last, and sorts by Modified and Name', async () => {
      const names = () => tableRows().map((row) => row.find('.resource-name-cell').text())
      const sortBy = async (label: string) => {
        await wrapper!.findAll('.data-table-sort-btn').find((button) => button.text() === label)?.trigger('click')
        await flushPromises()
      }

      expect(names()).toEqual(['Biotech Competition Rules', 'Mentor Handbook 2026'])
      // As the other admin tables write a date.
      expect(tableRows()[0]!.text()).toContain('12/02/25')

      await sortBy('Modified')
      expect(names()).toEqual(['Mentor Handbook 2026', 'Biotech Competition Rules'])

      await sortBy('Name')
      expect(names()).toEqual(['Biotech Competition Rules', 'Mentor Handbook 2026'])

      expect(wrapper!.findAll('.data-table-sort-btn').map((button) => button.text())).toEqual([
        'Name', 'Modified', 'Last Released',
      ])
    })

    it('hides one and sets its release date, each saved as it changes', async () => {
      const lastYear = { last_released_at: '2025-02-12T12:00:00+11:00' }
      vi.mocked(managementApi.saveResourceRelease)
        .mockResolvedValueOnce(release(102, 'Biotech Competition Rules', { ...lastYear, shown: false, released: false }))
        .mockResolvedValueOnce(
          release(102, 'Biotech Competition Rules', { ...lastYear, shown: false, released: false, release_on: '2026-11-30' }),
        )
        .mockResolvedValueOnce(release(102, 'Biotech Competition Rules', { ...lastYear, shown: false, released: false }))

      // The rules' row is first.
      wrapper!.findAllComponents({ name: 'HideShowSwitch' })[0]!.vm.$emit('change', false)
      await flushPromises()
      expect(managementApi.saveResourceRelease).toHaveBeenLastCalledWith(102, { shown: false })

      // No × on the date.
      const date = () => wrapper!.findAllComponents({ name: 'AppDatePicker' })[0]!
      expect(date().props('clearable')).toBe(false)
      date().vm.$emit('update:modelValue', '2026-11-30')
      await flushPromises()
      expect(managementApi.saveResourceRelease).toHaveBeenLastCalledWith(102, { release_on: '2026-11-30' })
      expect(date().props('modelValue')).toBe('2026-11-30')

      date().vm.$emit('update:modelValue', '')
      await flushPromises()
      expect(managementApi.saveResourceRelease).toHaveBeenLastCalledWith(102, { release_on: null })
    })

    it("shows others' view: their table, with the resources released to them, and back", async () => {
      const names = () => tableRows().map((row) => row.find('.resource-name-cell').text())
      await wrapper!.get('[data-test="others-view"]').trigger('click')
      await flushPromises()

      expect(wrapper!.findAll('thead th').map((th) => th.text()).filter(Boolean)).toEqual([
        'Icon', 'Name', 'Type', 'Labels', 'Modified',
      ])
      // The hidden handbook isn't theirs to see; no ticks, Edit or Add Resource.
      expect(names()).toEqual(['Biotech Competition Rules'])
      expect(wrapper!.find('.data-table-check-col').exists()).toBe(false)
      expect(wrapper!.text()).not.toContain('Add Resource')
      expect(wrapper!.get('[data-test="others-view-note"]').text()).toContain('released to them now')
      expect(wrapper!.get('[data-test="others-view"]').text()).toBe('Show Admin View')

      await wrapper!.get('[data-test="others-view"]').trigger('click')
      await flushPromises()
      expect(names()).toEqual(['Biotech Competition Rules', 'Mentor Handbook 2026'])
      expect(wrapper!.text()).toContain('Add Resource')
    })

    it('opens Edit Resource form sheet when clicking Edit', async () => {
      const editBtn = rowButton(1, 'Edit')
      expect(editBtn).toBeDefined()

      await editBtn?.trigger('click')
      await flushPromises()

      const formSheet = wrapper?.findComponent({ name: 'AdminResourceFormSheet' })
      expect(formSheet?.props('modelValue')).toBe(true)
      expect(formSheet?.props('resource')).toEqual(mockResource1)
    })

    it("opens ConfirmDialog from its Edit panel's Delete and executes delete", async () => {
      await rowButton(1, 'Edit')?.trigger('click')
      await flushPromises()
      wrapper!.findComponent({ name: 'AdminResourceFormSheet' }).vm.$emit('delete')
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

  describe('Back from a resource', () => {
    it('turns to the page with its row and brings it into view', async () => {
      const scrollIntoView = vi.fn()
      Element.prototype.scrollIntoView = scrollIntoView
      const many = Array.from({ length: 20 }, (_, i) => ({
        ...mockResource1, id: i + 1, name: `Resource ${String(i + 1).padStart(2, '0')}`,
      }))
      vi.mocked(resourcesApi.fetchResources).mockResolvedValue({ results: many, count: 20 })
      vi.mocked(managementApi.fetchResourceReleases).mockResolvedValue(many.map((item) => release(item.id, item.name)))
      vi.mocked(useRoute).mockReturnValueOnce({ params: {}, query: { resource: '16' }, name: 'resources' } as never)
      const auth = useAuthStore()
      auth.user = adminUser
      auth.initialized = true

      wrapper = mount(ResourcesPage, { global: { stubs: { AdminResourceFormSheet: true, ConfirmDialog: true } } })
      await flushPromises()
      await flushPromises()

      expect(wrapper.get('tr.data-table-row--focused').attributes('data-row-key')).toBe('16')
      expect(scrollIntoView).toHaveBeenCalledWith({ block: 'center' })
    })
  })

  describe('AdminResourceFormSheet Component', () => {
    it('validates required fields and always shows visible roles (no global option)', async () => {
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

      expect(sheetWrapper.text()).toContain('Add Resource')
      expect(sheetWrapper.find('#res-kind').exists()).toBe(true)
      expect(sheetWrapper.find('#res-name').exists()).toBe(true)
      expect(sheetWrapper.find('#res-desc').exists()).toBe(true)
      // Visibility is role-based only: no Global/Role-based dropdown
      expect(sheetWrapper.find('#res-visibility').exists()).toBe(false)
      expect(sheetWrapper.text()).not.toContain('Global')

      // Submit empty form -> shows validation error
      await sheetWrapper.find('form').trigger('submit')
      await flushPromises()
      expect(sheetWrapper.find('.admin-resource-form__error').text()).toContain('Resource name is required')

      // Fill name & description
      await sheetWrapper.find('#res-name').setValue('New Handbook')
      await sheetWrapper.find('#res-desc').setValue('Handbook description')

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

    it('fetches admin resource detail and preserves role-based visibility and assigned roles when editing', async () => {
      const mockDetail: adminApi.AdminResourceDetail = {
        id: 101,
        resource_name: 'Mentor Handbook 2026',
        resource_description: 'Official mentor onboarding handbook.',
        resource_kind: 'file',
        resource_type: 'Guide',
        resource_type_id: 1,
        visibility_scope: 'role_based',
        uploaded_at: '2026-03-01T10:00:00Z',
        deleted_at: null,
        file_name: 'mentor_handbook.pdf',
        file_mime_type: 'application/pdf',
        file_size: 102400,
        audiences: [
          {
            id: 1,
            role_id: 1,
            role: { id: 1, slug: 'student', type_name: 'Student' }
          }
        ],
        labels: [{ id: 1, name: 'Mentorship' }]
      }
      vi.spyOn(adminApi, 'fetchAdminResource').mockResolvedValue(mockDetail)

      const sheetWrapper = mount(AdminResourceFormSheet, {
        props: {
          modelValue: true,
          resource: mockResource1
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

      expect(adminApi.fetchAdminResource).toHaveBeenCalledWith(101)
      expect(sheetWrapper.find('#res-visibility').exists()).toBe(false)

      // Checkbox for student (value "1") should be checked
      const studentCheckbox = sheetWrapper
        .findAll('fieldset input[type="checkbox"]')
        .find((c) => (c.element as HTMLInputElement).value === '1')
      expect((studentCheckbox?.element as HTMLInputElement).checked).toBe(true)

      // Checkbox for mentor (value "2") should NOT be checked
      const mentorCheckbox = sheetWrapper
        .findAll('fieldset input[type="checkbox"]')
        .find((c) => (c.element as HTMLInputElement).value === '2')
      expect((mentorCheckbox?.element as HTMLInputElement).checked).toBe(false)

      sheetWrapper.unmount()
    })

    it('submits a page resource created via RichEditor', async () => {
      const sheetWrapper = mount(AdminResourceFormSheet, {
        props: {
          modelValue: true,
          resource: null
        },
        global: {
          stubs: {
            FormSheet: {
              template: '<div><slot /></div>'
            },
            RichEditor: {
              name: 'RichEditor',
              props: ['modelValue'],
              emits: ['update:modelValue'],
              template: '<div class="stub-rich-editor"><textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" /></div>'
            }
          }
        }
      })
      await flushPromises()

      // Set kind to 'page'
      await pickAppSelect(sheetWrapper, '#res-kind', 'Rich Content Page')
      await sheetWrapper.find('#res-name').setValue('Competition Rules')
      await sheetWrapper.find('#res-desc').setValue('Rules description')

      // Set page content in RichEditor
      const richTextarea = sheetWrapper.find('.stub-rich-editor textarea')
      expect(richTextarea.exists()).toBe(true)
      await richTextarea.setValue('<p>Official Rules Content</p>')

      // Pick the Student role (value "1")
      const studentCheckbox = sheetWrapper
        .findAll('fieldset input[type="checkbox"]')
        .find((c) => (c.element as HTMLInputElement).value === '1')
      await studentCheckbox?.setValue(true)

      await sheetWrapper.find('form').trigger('submit')
      await flushPromises()

      expect(adminApi.createAdminResource).toHaveBeenCalledWith(
        expect.objectContaining({
          resource_name: 'Competition Rules',
          resource_description: 'Rules description',
          resource_kind: 'page',
          content_html: '<p>Official Rules Content</p>',
          visibility_scope: 'role_based',
          role_ids: [1]
        })
      )

      sheetWrapper.unmount()
    })

    it('renders role checkboxes without a select-all control', async () => {
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

      const roleBoxes = () =>
        sheetWrapper.findAll('fieldset input[type="checkbox"]').map((c) => c.element as HTMLInputElement)
      expect(sheetWrapper.find('#res-roles-all').exists()).toBe(false)
      expect(roleBoxes()).toHaveLength(2) // Student and Mentor; Admin is never listed

      sheetWrapper.unmount()
    })
  })

  describe('AdminResourceFormSheet large files', () => {
    const makeFile = (name: string, sizeBytes: number) => {
      const file = new File(['%PDF-1.4'], name, { type: 'application/pdf' })
      // jsdom can't cheaply hold a real 30 MB file; the form only reads .size.
      Object.defineProperty(file, 'size', { value: sizeBytes })
      return file
    }
    const LARGE = 30 * 1024 * 1024
    const SMALL = 1024

    const mountSheet = async (resource: resourcesApi.Resource | null = null) => {
      const sheetWrapper = mount(AdminResourceFormSheet, {
        props: { modelValue: true, resource },
        global: { stubs: { FormSheet: { template: '<div><slot /></div>' } } }
      })
      await flushPromises()
      return sheetWrapper
    }

    const pickFile = async (sheetWrapper: VueWrapper, file: File) => {
      const input = sheetWrapper.find('input[type="file"]')
      Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
      await input.trigger('change')
    }

    const fillRequiredFields = async (sheetWrapper: VueWrapper) => {
      await sheetWrapper.find('#res-name').setValue('Big Recording')
      await sheetWrapper.find('#res-desc').setValue('A large file')
      await sheetWrapper.findAll('fieldset input[type="checkbox"]')[0].setValue(true)
    }

    const submitButton = (sheetWrapper: VueWrapper) =>
      sheetWrapper.find('button[type="submit"]').element as HTMLButtonElement

    const uploadedFormData = () =>
      vi.mocked(adminApi.uploadAdminResource).mock.calls[0][0] as FormData

    it('warns about a large file and only uploads once it is acknowledged', async () => {
      const sheetWrapper = await mountSheet()
      await fillRequiredFields(sheetWrapper)
      await pickFile(sheetWrapper, makeFile('big.pdf', LARGE))

      expect(sheetWrapper.text()).toContain('over the 25 MB guideline')
      expect(sheetWrapper.find('#res-oversize-ack').exists()).toBe(true)
      expect(submitButton(sheetWrapper).disabled).toBe(true)

      await sheetWrapper.find('#res-oversize-ack').setValue(true)
      expect(submitButton(sheetWrapper).disabled).toBe(false)

      await sheetWrapper.find('form').trigger('submit')
      await flushPromises()

      expect(adminApi.uploadAdminResource).toHaveBeenCalledTimes(1)
      expect(uploadedFormData().get('acknowledged_oversized')).toBe('true')

      sheetWrapper.unmount()
    })

    it('resets the acknowledgement when a different file is chosen', async () => {
      const sheetWrapper = await mountSheet()
      await pickFile(sheetWrapper, makeFile('big.pdf', LARGE))
      await sheetWrapper.find('#res-oversize-ack').setValue(true)

      await pickFile(sheetWrapper, makeFile('other-big.pdf', LARGE))

      const ack = sheetWrapper.find('#res-oversize-ack').element as HTMLInputElement
      expect(ack.checked).toBe(false)
      expect(submitButton(sheetWrapper).disabled).toBe(true)

      sheetWrapper.unmount()
    })

    it('shows no warning for a normal-size file and sends acknowledged_oversized=false', async () => {
      const sheetWrapper = await mountSheet()
      await fillRequiredFields(sheetWrapper)
      await pickFile(sheetWrapper, makeFile('small.pdf', SMALL))

      expect(sheetWrapper.find('#res-oversize-ack').exists()).toBe(false)
      expect(submitButton(sheetWrapper).disabled).toBe(false)

      await sheetWrapper.find('form').trigger('submit')
      await flushPromises()

      expect(uploadedFormData().get('acknowledged_oversized')).toBe('false')

      sheetWrapper.unmount()
    })

    const editDetail: adminApi.AdminResourceDetail = {
      id: 101,
      resource_name: 'Mentor Handbook 2026',
      resource_description: 'Official mentor onboarding handbook.',
      resource_kind: 'file',
      resource_type: 'Guide',
      resource_type_id: 1,
      visibility_scope: 'role_based',
      uploaded_at: '2026-03-01T10:00:00Z',
      deleted_at: null,
      file_name: 'mentor_handbook.pdf',
      file_mime_type: 'application/pdf',
      file_size: 102400,
      audiences: [{ id: 1, role_id: 1, role: { id: 1, slug: 'student', type_name: 'Student' } }]
    }

    it('passes the acknowledgement when replacing a file on edit', async () => {
      vi.spyOn(adminApi, 'fetchAdminResource').mockResolvedValue(editDetail)
      const replaceSpy = vi
        .spyOn(adminApi, 'replaceAdminResourceFile')
        .mockResolvedValue(editDetail)

      const sheetWrapper = await mountSheet(mockResource1)
      const file = makeFile('new-handbook.pdf', LARGE)
      await pickFile(sheetWrapper, file)
      await sheetWrapper.find('#res-oversize-ack').setValue(true)
      await sheetWrapper.find('form').trigger('submit')
      await flushPromises()

      expect(adminApi.updateAdminResource).toHaveBeenCalled()
      expect(replaceSpy).toHaveBeenCalledWith(101, file, true)
      expect(sheetWrapper.emitted('update:modelValue')?.at(-1)).toEqual([false])

      sheetWrapper.unmount()
    })

    it('says the details were saved when the replacement file is rejected', async () => {
      vi.spyOn(adminApi, 'fetchAdminResource').mockResolvedValue(editDetail)
      vi.spyOn(adminApi, 'replaceAdminResourceFile').mockRejectedValue(
        new Error('Resource file must use an allowed file extension.')
      )

      const sheetWrapper = await mountSheet(mockResource1)
      await pickFile(sheetWrapper, makeFile('new-handbook.pdf', SMALL))
      await sheetWrapper.find('form').trigger('submit')
      await flushPromises()

      expect(adminApi.updateAdminResource).toHaveBeenCalled()
      expect(sheetWrapper.find('.admin-resource-form__error').text()).toContain(
        'Details were saved, but the new file was rejected: Resource file must use an allowed file extension.'
      )
      // The list refreshes, but the sheet stays open for another file.
      expect(sheetWrapper.emitted('saved')).toHaveLength(1)
      expect(sheetWrapper.emitted('update:modelValue')).toBeUndefined()

      sheetWrapper.unmount()
    })

    it('replaces video or slides on edit for a recorded session resource', async () => {
      const recordedSessionDetail: adminApi.AdminResourceDetail = {
        id: 105,
        resource_name: 'Workshop Session 1',
        resource_description: 'Recorded session video and slides.',
        resource_kind: 'file',
        resource_type: 'Recorded Session',
        resource_type_id: 10,
        visibility_scope: 'role_based',
        uploaded_at: '2026-03-01T10:00:00Z',
        deleted_at: null,
        file_name: 'session1.mp4',
        file_mime_type: 'video/mp4',
        file_size: 1024 * 1024 * 5,
        slides_file_name: 'session1_slides.pdf',
        slides_file_size: 50000,
        audiences: [{ id: 1, role_id: 1, role: { id: 1, slug: 'student', type_name: 'Student' } }]
      }

      vi.spyOn(resourcesApi, 'fetchResourceTypes').mockResolvedValue([
        { id: 10, type_name: 'Recorded Session', type_description: 'Recordings' }
      ])
      vi.spyOn(adminApi, 'fetchAdminResource').mockResolvedValue(recordedSessionDetail)
      const replaceSpy = vi.spyOn(adminApi, 'replaceAdminResourceFile').mockResolvedValue(recordedSessionDetail)
      const updateSpy = vi.spyOn(adminApi, 'updateAdminResource').mockResolvedValue(recordedSessionDetail)

      const recResource: resourcesApi.Resource = {
        id: 105,
        name: 'Workshop Session 1',
        description: 'Recorded session video and slides.',
        kind: 'file',
        type_name: 'Recorded Session',
        file_name: 'session1.mp4',
        file_mime_type: 'video/mp4',
        file_size: 1024 * 1024 * 5,
        uploaded_at: '2026-03-01T10:00:00Z',
        labels: []
      }

      const sheetWrapper = await mountSheet(recResource)
      await flushPromises()

      // The recorded session component should be rendered
      expect(sheetWrapper.findComponent({ name: 'AdminRecordedSessionFields' }).exists()).toBe(true)

      // Test updating video file
      const newVideo = new File(['fake video'], 'new_session.mp4', { type: 'video/mp4' })
      const videoInput = sheetWrapper.find('#admin-resource-video-file')
      Object.defineProperty(videoInput.element, 'files', { value: [newVideo], configurable: true })
      await videoInput.trigger('change')
      await flushPromises()

      expect(sheetWrapper.text()).toContain('new_session.mp4')

      // Click Save Changes
      await sheetWrapper.find('form').trigger('submit')
      await flushPromises()

      expect(updateSpy).toHaveBeenCalledWith(105, expect.objectContaining({
        resource_name: 'Workshop Session 1',
        resource_type_id: 10,
        role_ids: [1]
      }))
      expect(replaceSpy).toHaveBeenCalledWith(105, newVideo, false)

      sheetWrapper.unmount()
    })

    it('replaces only slides on edit when video is not changed', async () => {
      const recordedSessionDetail: adminApi.AdminResourceDetail = {
        id: 106,
        resource_name: 'Workshop Session 2',
        resource_description: 'Recorded session video only initially.',
        resource_kind: 'file',
        resource_type: 'Recorded Session',
        resource_type_id: 10,
        visibility_scope: 'role_based',
        uploaded_at: '2026-03-01T10:00:00Z',
        deleted_at: null,
        file_name: 'session2.mp4',
        file_mime_type: 'video/mp4',
        file_size: 1024 * 1024 * 5,
        slides_file_name: null,
        slides_file_size: null,
        audiences: [{ id: 1, role_id: 1, role: { id: 1, slug: 'student', type_name: 'Student' } }]
      }

      vi.spyOn(resourcesApi, 'fetchResourceTypes').mockResolvedValue([
        { id: 10, type_name: 'Recorded Session', type_description: 'Recordings' }
      ])
      vi.spyOn(adminApi, 'fetchAdminResource').mockResolvedValue(recordedSessionDetail)
      const replaceSpy = vi.spyOn(adminApi, 'replaceAdminResourceFile').mockResolvedValue(recordedSessionDetail)
      const updateSpy = vi.spyOn(adminApi, 'updateAdminResource').mockResolvedValue(recordedSessionDetail)

      const recResource: resourcesApi.Resource = {
        id: 106,
        name: 'Workshop Session 2',
        description: 'Recorded session video only initially.',
        kind: 'file',
        type_name: 'Recorded Session',
        file_name: 'session2.mp4',
        file_mime_type: 'video/mp4',
        file_size: 1024 * 1024 * 5,
        uploaded_at: '2026-03-01T10:00:00Z',
        labels: []
      }

      const sheetWrapper = await mountSheet(recResource)
      await flushPromises()

      // Test updating slides file
      const newSlides = new File(['%PDF-1.4 fake slides'], 'slides.pdf', { type: 'application/pdf' })
      const slidesInput = sheetWrapper.find('#admin-resource-slides-file')
      Object.defineProperty(slidesInput.element, 'files', { value: [newSlides], configurable: true })
      await slidesInput.trigger('change')
      await flushPromises()

      expect(sheetWrapper.text()).toContain('slides.pdf')

      // Click Save Changes
      await sheetWrapper.find('form').trigger('submit')
      await flushPromises()

      expect(updateSpy).toHaveBeenCalledWith(106, expect.objectContaining({
        resource_name: 'Workshop Session 2',
        resource_type_id: 10,
        role_ids: [1]
      }))
      expect(replaceSpy).toHaveBeenCalledWith(106, null, false, newSlides)

      sheetWrapper.unmount()
    })

    it('enables submit when large video is acknowledged in AdminRecordedSessionFields', async () => {
      const recordedSessionDetail: adminApi.AdminResourceDetail = {
        id: 107,
        resource_name: 'Workshop Session 3',
        resource_description: 'Recorded session.',
        resource_kind: 'file',
        resource_type: 'Recorded Session',
        resource_type_id: 10,
        visibility_scope: 'role_based',
        uploaded_at: '2026-03-01T10:00:00Z',
        deleted_at: null,
        file_name: 'session3.mp4',
        file_mime_type: 'video/mp4',
        file_size: 1024 * 1024 * 5,
        audiences: [{ id: 1, role_id: 1, role: { id: 1, slug: 'student', type_name: 'Student' } }]
      }

      vi.spyOn(resourcesApi, 'fetchResourceTypes').mockResolvedValue([
        { id: 10, type_name: 'Recorded Session', type_description: 'Recordings' }
      ])
      vi.spyOn(adminApi, 'fetchAdminResource').mockResolvedValue(recordedSessionDetail)

      const recResource: resourcesApi.Resource = {
        id: 107,
        name: 'Workshop Session 3',
        description: 'Recorded session.',
        kind: 'file',
        type_name: 'Recorded Session',
        file_name: 'session3.mp4',
        file_mime_type: 'video/mp4',
        file_size: 1024 * 1024 * 5,
        uploaded_at: '2026-03-01T10:00:00Z',
        labels: []
      }

      const sheetWrapper = await mountSheet(recResource)
      await flushPromises()

      const bigVideo = makeFile('big_session.mp4', LARGE)
      const videoInput = sheetWrapper.find('#admin-resource-video-file')
      Object.defineProperty(videoInput.element, 'files', { value: [bigVideo], configurable: true })
      await videoInput.trigger('change')
      await flushPromises()

      // Submit button should be disabled until acknowledged
      const submitBtn = sheetWrapper.find('button[type="submit"]').element as HTMLButtonElement
      expect(submitBtn.disabled).toBe(true)

      // Acknowledge large video
      const ackBox = sheetWrapper.find('#res-video-oversize-ack')
      expect(ackBox.exists()).toBe(true)
      await ackBox.setValue(true)
      await flushPromises()

      expect(submitBtn.disabled).toBe(false)

      sheetWrapper.unmount()
    })
  })

  describe('Multi-Select & Bulk Actions', () => {
    it('renders selection checkboxes for admin and hides them for student', async () => {
      const auth = useAuthStore()
      auth.user = studentUser
      auth.initialized = true

      wrapper = mount(ResourcesPage)
      await flushPromises()

      expect(wrapper.find('th.data-table-check-col').exists()).toBe(false)
      expect(wrapper.findAll('td.data-table-check-col')).toHaveLength(0)
      expect(wrapper.text()).not.toContain('Batch Mode')

      auth.user = adminUser
      await flushPromises()

      expect(wrapper.find('th.data-table-check-col').exists()).toBe(true)
      expect(wrapper.findAll('td.data-table-check-col')).toHaveLength(2)
      expect(wrapper.text()).not.toContain('Batch Mode')
    })

    it('selects rows via checkbox and triggers bulk actions', async () => {
      const auth = useAuthStore()
      auth.user = adminUser
      auth.initialized = true

      wrapper = mount(ResourcesPage)
      await flushPromises()

      const rows = tableRows()
      const firstCheckbox = rows[0].find('td.data-table-check-col input[type="checkbox"]')
      expect(firstCheckbox.exists()).toBe(true)

      await firstCheckbox.setValue(true)
      await flushPromises()

      // Bulk bar appears showing 1 selected
      expect(wrapper.find('.bulk-actions-bar').exists()).toBe(true)
      expect(wrapper.find('.bulk-actions-bar__count').text()).toContain('1 resource selected')

      // Click master checkbox to select all
      const selectAll = wrapper.find('th.data-table-check-col input[type="checkbox"]')
      await selectAll.setValue(true)
      await flushPromises()

      expect(wrapper.find('.bulk-actions-bar__count').text()).toContain('2 resources selected')

      // Clear selection
      const clearBtn = wrapper.find('.bulk-actions-bar__clear')
      await clearBtn.trigger('click')
      await flushPromises()

      expect(wrapper.find('.bulk-actions-bar').exists()).toBe(false)
    })

    it('opens Batch Edit Access modal and applies visibility and role changes to selected resources', async () => {
      const auth = useAuthStore()
      auth.user = adminUser
      auth.initialized = true

      wrapper = mount(ResourcesPage, {
        attachTo: document.body
      })
      await flushPromises()

      // Select all via master checkbox
      await wrapper.find('th.data-table-check-col input[type="checkbox"]').setValue(true)
      await flushPromises()

      // Click Edit Access in BulkActionsBar
      const editAccessBtn = wrapper.findAll('.bulk-actions-bar .btn').find((b) => b.text().includes('Edit Access'))
      expect(editAccessBtn).toBeDefined()
      await editAccessBtn?.trigger('click')
      await flushPromises()

      const sheet = document.body.querySelector('.admin-sheet') as HTMLElement
      expect(sheet).not.toBeNull()
      expect(sheet.textContent).toContain('Batch Edit Access')
      expect(sheet.textContent).toContain('2 selected resources')

      // Select student role checkbox
      const roleCheckboxes = sheet.querySelectorAll('fieldset input[type="checkbox"]')
      expect(roleCheckboxes.length).toBeGreaterThan(0)
      ;(roleCheckboxes[0] as HTMLInputElement).checked = true
      roleCheckboxes[0].dispatchEvent(new Event('change'))
      await flushPromises()

      // Click Apply
      const applyBtn = Array.from(sheet.querySelectorAll('.btn')).find((el) =>
        el.textContent?.includes('Apply Access Changes')
      ) as HTMLButtonElement
      expect(applyBtn).toBeDefined()
      applyBtn.click()
      await flushPromises()

      expect(adminApi.updateAdminResource).toHaveBeenCalledWith(101, {
        visibility_scope: 'role_based',
        role_ids: [1]
      })
      expect(adminApi.updateAdminResource).toHaveBeenCalledWith(102, {
        visibility_scope: 'role_based',
        role_ids: [1]
      })
    })

    const openBatchAccessSheet = async () => {
      const auth = useAuthStore()
      auth.user = adminUser
      auth.initialized = true

      wrapper = mount(ResourcesPage, {
        attachTo: document.body
      })
      await flushPromises()

      await wrapper.find('th.data-table-check-col input[type="checkbox"]').setValue(true)
      await flushPromises()

      const editAccessBtn = wrapper.findAll('.bulk-actions-bar .btn').find((b) => b.text().includes('Edit Access'))
      await editAccessBtn?.trigger('click')
      await flushPromises()

      const sheet = document.body.querySelector('.admin-sheet') as HTMLElement
      const applyBtn = Array.from(sheet.querySelectorAll('.btn')).find((el) =>
        el.textContent?.includes('Apply Access Changes')
      ) as HTMLButtonElement
      return { sheet, applyBtn }
    }

    it('Batch Edit Access has no global option and blocks Apply when no roles are selected', async () => {
      const { sheet, applyBtn } = await openBatchAccessSheet()

      expect(sheet.querySelector('#batch-visibility-scope')).toBeNull()
      expect(sheet.textContent).not.toContain('Global')

      applyBtn.click()
      await flushPromises()

      expect(sheet.querySelector('.admin-batch-access-form__error')?.textContent).toContain(
        'Please select at least one role'
      )
      expect(adminApi.updateAdminResource).not.toHaveBeenCalled()
    })

    it('Batch Edit Access renders role checkboxes without a select-all control and applies selected roles', async () => {
      const { sheet, applyBtn } = await openBatchAccessSheet()

      expect(sheet.querySelector('#batch-roles-all')).toBeNull()
      expect(sheet.textContent).not.toContain('Select all roles')

      const roleBoxes = Array.from(sheet.querySelectorAll('fieldset input[type="checkbox"]')) as HTMLInputElement[]
      expect(roleBoxes.length).toBeGreaterThan(0)
      for (const box of roleBoxes) {
        box.checked = true
        box.dispatchEvent(new Event('change'))
      }
      await flushPromises()

      applyBtn.click()
      await flushPromises()

      expect(adminApi.updateAdminResource).toHaveBeenCalledWith(101, {
        visibility_scope: 'role_based',
        role_ids: [1, 2]
      })
    })

    it('prompts confirmation and deletes all selected resources in bulk', async () => {
      const auth = useAuthStore()
      auth.user = adminUser
      auth.initialized = true

      wrapper = mount(ResourcesPage, {
        attachTo: document.body
      })
      await flushPromises()

      // Select both
      await wrapper.find('th.data-table-check-col input[type="checkbox"]').setValue(true)
      await flushPromises()

      // Click Delete in BulkActionsBar
      const deleteBtn = wrapper.findAll('.bulk-actions-bar .btn').find((b) => b.text().includes('Delete'))
      expect(deleteBtn).toBeDefined()
      await deleteBtn?.trigger('click')
      await flushPromises()

      const confirmDialog = document.body.querySelector('.admin-modal--confirm') as HTMLElement
      expect(confirmDialog).not.toBeNull()
      expect(confirmDialog.textContent).toContain('Delete Resources')
      expect(confirmDialog.textContent).toContain('Are you sure you want to delete 2 selected resources?')

      // Confirm deletion
      const confirmActionBtn = confirmDialog.querySelector('.btn-danger') as HTMLButtonElement
      expect(confirmActionBtn).toBeDefined()
      confirmActionBtn.click()
      await flushPromises()

      expect(adminApi.deleteAdminResource).toHaveBeenCalledWith(101)
      expect(adminApi.deleteAdminResource).toHaveBeenCalledWith(102)
    })
  })
})
