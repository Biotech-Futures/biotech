import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import AdminAnnouncementFormSheet from '@/components/admin/announcements/AdminAnnouncementFormSheet.vue'
import RichEditor from '@/components/admin/announcements/RichEditor.vue'
import * as adminApi from '@/utils/adminAPI'

let wrapper: VueWrapper | null = null

describe('AdminAnnouncementFormSheet & RichEditor', () => {
  beforeEach(() => {
    vi.spyOn(adminApi, 'fetchAnnouncementRoles').mockResolvedValue([
      { id: 1, name: 'Student' },
      { id: 2, name: 'Mentor' }
    ])
    vi.spyOn(adminApi, 'fetchAnnouncementGroups').mockResolvedValue([
      { id: 10, name: 'Team Alpha' },
      { id: 20, name: 'Team Beta' }
    ])
    vi.spyOn(adminApi, 'createAdminAnnouncement').mockResolvedValue({
      id: 301,
      title: 'Created Announcement',
      body: '<p>Created Body</p>',
      visibilityScope: 'global',
      publishedAt: '2026-05-01T10:00:00Z',
      archivedAt: null,
      authorUserId: 1,
      audiences: []
    })
    vi.spyOn(adminApi, 'updateAdminAnnouncement').mockResolvedValue({
      id: 302,
      title: 'Updated Announcement',
      body: '<p>Updated Body</p>',
      visibilityScope: 'role_based',
      publishedAt: '2026-05-01T10:00:00Z',
      archivedAt: null,
      authorUserId: 1,
      audiences: []
    })
    vi.spyOn(adminApi, 'fetchAdminAnnouncement').mockResolvedValue({
      id: 302,
      title: 'Preloaded Title',
      body: '<p>Preloaded Body HTML</p>',
      visibilityScope: 'role_based',
      publishedAt: '2026-05-01T10:00:00Z',
      archivedAt: null,
      authorUserId: 1,
      audiences: [{ id: 1, roleId: 2, groupId: null, roleName: 'Mentor', groupName: null }]
    })
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    vi.restoreAllMocks()
  })

  it('renders correctly in create mode with empty fields and loaded roles/groups', async () => {
    wrapper = mount(AdminAnnouncementFormSheet, {
      props: {
        modelValue: true,
        announcement: null
      },
      global: {
        stubs: {
          FormSheet: {
            props: ['modelValue', 'title', 'description'],
            template: '<div class="form-sheet-stub"><slot /><slot name="footer" /></div>'
          },
          RichEditor: true,
          ConfirmDialog: true
        }
      }
    })
    await flushPromises()

    const titleInput = wrapper.find<HTMLInputElement>('#ann-title')
    expect(titleInput.exists()).toBe(true)
    expect(titleInput.element.value).toBe('')

    // Check roles and groups checkboxes
    const checkboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    expect(checkboxes.length).toBe(4) // 2 roles + 2 groups

    // Notice for global visibility
    expect(wrapper.text()).toContain('No roles or groups selected — announcement will be visible to all users (Global)')
  })

  it('populates fields in edit mode and fetches full detail if body is missing', async () => {
    wrapper = mount(AdminAnnouncementFormSheet, {
      props: {
        modelValue: true,
        announcement: {
          id: 302,
          title: 'Initial Title',
          visibilityScope: 'role_based',
          publishedAt: '2026-05-01T10:00:00Z',
          archivedAt: null,
          authorUserId: 1,
          audiences: []
        }
      },
      global: {
        stubs: {
          FormSheet: {
            props: ['modelValue', 'title', 'description'],
            template: '<div class="form-sheet-stub"><slot /><slot name="footer" /></div>'
          },
          RichEditor: true,
          ConfirmDialog: true
        }
      }
    })
    await flushPromises()

    expect(adminApi.fetchAdminAnnouncement).toHaveBeenCalledWith(302)
    const titleInput = wrapper.find<HTMLInputElement>('#ann-title')
    expect(titleInput.element.value).toBe('Preloaded Title')
  })

  it('validates required fields before submitting', async () => {
    wrapper = mount(AdminAnnouncementFormSheet, {
      props: {
        modelValue: true,
        announcement: null
      },
      global: {
        stubs: {
          FormSheet: {
            props: ['modelValue', 'title'],
            template: '<div class="form-sheet-stub"><slot /></div>'
          },
          RichEditor: true,
          ConfirmDialog: true
        }
      }
    })
    await flushPromises()

    // Click Publish without title
    const publishBtn = wrapper.findAll('button').find(b => b.text().includes('Publish') && !b.text().includes('& Notify'))
    expect(publishBtn).toBeDefined()
    await publishBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Title is required')
    expect(adminApi.createAdminAnnouncement).not.toHaveBeenCalled()
  })

  it('submits create payload with selected roles and groups', async () => {
    wrapper = mount(AdminAnnouncementFormSheet, {
      props: {
        modelValue: true,
        announcement: null
      },
      global: {
        stubs: {
          FormSheet: {
            props: ['modelValue', 'title'],
            template: '<div class="form-sheet-stub"><slot /></div>'
          },
          RichEditor: {
            name: 'RichEditor',
            props: ['modelValue'],
            emits: ['update:modelValue'],
            template: '<textarea class="rich-editor-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>'
          },
          ConfirmDialog: true
        }
      }
    })
    await flushPromises()

    // Fill title and body
    const titleInput = wrapper.find<HTMLInputElement>('#ann-title')
    await titleInput.setValue('New Tech Initiative')

    const bodyEditor = wrapper.findComponent({ name: 'RichEditor' })
    bodyEditor.vm.$emit('update:modelValue', '<p>Exciting news about tech funding</p>')
    await flushPromises()

    // Toggle a role checkbox (Mentor, id 2)
    const mentorCheckbox = wrapper.findAll('label').find(l => l.text().includes('Mentor'))?.find('input')
    expect(mentorCheckbox).toBeDefined()
    await mentorCheckbox!.trigger('change')
    await flushPromises()

    // Click Publish
    const publishBtn = wrapper.findAll('button').find(b => b.text().trim() === 'Publish')
    expect(publishBtn).toBeDefined()
    await publishBtn!.trigger('click')
    await flushPromises()

    expect(adminApi.createAdminAnnouncement).toHaveBeenCalledWith({
      title: 'New Tech Initiative',
      body: '<p>Exciting news about tech funding</p>',
      role_ids: [2],
      group_ids: undefined,
      send_email: false
    })

    expect(wrapper.emitted('saved')).toBeTruthy()
  })

  it('renders RichEditor toolbar buttons and supports raw mode toggle', async () => {
    const editorWrapper = mount(RichEditor, {
      props: {
        modelValue: '<p>Initial content</p>'
      }
    })
    await flushPromises()

    // Toolbar buttons exist
    const toolbar = editorWrapper.find('.rich-editor-toolbar')
    expect(toolbar.exists()).toBe(true)

    // Bold button
    const boldBtn = editorWrapper.find('button[title*="Bold"]')
    expect(boldBtn.exists()).toBe(true)

    // Table insert button
    const tableBtn = editorWrapper.find('button[title*="Insert table"]')
    expect(tableBtn.exists()).toBe(true)

    // Raw mode button
    const rawBtn = editorWrapper.find('.toggle-raw-btn')
    expect(rawBtn.exists()).toBe(true)
    expect(rawBtn.text()).toContain('HTML')

    // Switch to Raw HTML mode
    await rawBtn.trigger('mousedown')
    await flushPromises()

    expect(editorWrapper.find('.raw-html-textarea').exists()).toBe(true)
    expect(rawBtn.text()).toContain('Visual')

    editorWrapper.unmount()
  })
})
