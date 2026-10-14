import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import AdminAnnouncementFormSheet from '@/components/admin/announcements/AdminAnnouncementFormSheet.vue'
import RichEditor from '@/components/admin/RichEditor.vue'
import * as adminApi from '@/utils/adminAPI'
import * as managementApi from '@/utils/managementAPI'

let wrapper: VueWrapper | null = null

describe('AdminAnnouncementFormSheet & RichEditor', () => {
  beforeEach(() => {
    // Until submissions close, the categories stay off.
    vi.spyOn(managementApi, 'fetchAnnouncementCategories').mockResolvedValue({
      available: false,
      reason: 'Available once submissions close, on Friday, 17 October 2026, 11:59 PM (Sydney time).',
      categories: [
        { key: 'finalists', label: 'Finalist', group_ids: [] },
        { key: 'nonfinalists', label: 'Nonfinalist', group_ids: [] },
        { key: 'nonsubmissions', label: 'Nonsubmission', group_ids: [] }
      ]
    })
    vi.spyOn(adminApi, 'fetchAnnouncementRoles').mockResolvedValue([
      { id: 1, name: 'Student' },
      { id: 2, name: 'Mentor' }
    ])
    vi.spyOn(adminApi, 'fetchAnnouncementGroups').mockResolvedValue([
      { id: 10, name: 'Team Alpha' },
      { id: 20, name: 'Team Beta' }
    ])
    vi.spyOn(adminApi, 'fetchAnnouncementMergeTags').mockResolvedValue([
      { name: 'first_name', description: "Reader's first name", sample: 'Alex', html: false },
      { name: 'name', description: "Reader's full name", sample: 'Alex Chen', html: false }
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
    expect(checkboxes.length).toBe(7) // 2 roles + 3 categories + 2 groups

    // Notice for global visibility
    expect(wrapper.text()).toContain('No roles or groups selected - announcement will be visible to all users (Global)')
  })

  const mountCreate = async () => {
    wrapper = mount(AdminAnnouncementFormSheet, {
      props: { modelValue: true, announcement: null },
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
    return wrapper
  }

  it('puts Target Categories before Target Groups, off until submissions close', async () => {
    const w = await mountCreate()
    const sections = w.findAll('.admin-ann-form__section .font-semibold').map((s) => s.text())
    expect(sections.indexOf('Target Categories')).toBe(sections.indexOf('Target Groups') - 1)
    const boxes = w.find('[data-testid="target-categories"]').findAll('input')
    expect(w.find('[data-testid="target-categories"]').findAll('label').map((l) => l.text())).toEqual([
      'Finalist',
      'Nonfinalist',
      'Nonsubmission'
    ])
    for (const box of boxes) expect(box.attributes('disabled')).toBeDefined()
    expect(w.text()).toContain('Available once submissions close, on Friday, 17 October 2026')
    // The whole section greyed out, its reason in small italics.
    expect(w.find('[data-testid="target-categories-section"]').classes()).toContain('admin-ann-form__categories--off')
    expect(w.find('.admin-ann-form__categories-reason').exists()).toBe(true)
  })

  it('ticking a category selects its groups, and unticking clears them', async () => {
    vi.spyOn(managementApi, 'fetchAnnouncementCategories').mockResolvedValue({
      available: true,
      reason: '',
      categories: [
        { key: 'finalists', label: 'Finalist', group_ids: [10] },
        { key: 'nonfinalists', label: 'Nonfinalist', group_ids: [20] },
        { key: 'nonsubmissions', label: 'Nonsubmission', group_ids: [] }
      ]
    })
    const w = await mountCreate()
    const category = (label: string) =>
      w.find('[data-testid="target-categories"]').findAll('label').find((l) => l.text().startsWith(label))!
    const groupBox = (name: string) =>
      w.findAll('label').find((l) => l.text() === name)!.find<HTMLInputElement>('input').element
    expect(category('Finalist').text()).toBe('Finalist (1)')
    // None in it, so nothing to tick.
    expect(category('Nonsubmission').find('input').attributes('disabled')).toBeDefined()

    await category('Finalist').find('input').trigger('change')
    expect(groupBox('Team Alpha').checked).toBe(true)
    expect(groupBox('Team Beta').checked).toBe(false)
    expect(category('Finalist').find<HTMLInputElement>('input').element.checked).toBe(true)

    await category('Finalist').find('input').trigger('change')
    expect(groupBox('Team Alpha').checked).toBe(false)
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

    // Click Publish & Notify without title
    const publishNotifyBtn = wrapper.findAll('button').find(b => b.text().includes('Publish & Notify'))
    expect(publishNotifyBtn).toBeDefined()
    await publishNotifyBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Title is required')
    expect(adminApi.createAdminAnnouncement).not.toHaveBeenCalled()
  })

  it('submits create payload with selected roles and groups via Publish & Notify', async () => {
    wrapper = mount(AdminAnnouncementFormSheet, {
      props: {
        modelValue: true,
        announcement: null
      },
      global: {
        stubs: {
          FormSheet: {
            props: ['modelValue', 'title'],
            template: '<div class="form-sheet-stub"><slot /><slot name="footer" /></div>'
          },
          RichEditor: {
            name: 'RichEditor',
            props: ['modelValue'],
            emits: ['update:modelValue'],
            template: '<textarea class="rich-editor-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>'
          },
          ConfirmDialog: {
            name: 'ConfirmDialog',
            props: ['modelValue', 'title', 'message'],
            emits: ['update:modelValue', 'confirm', 'cancel'],
            template: '<div v-if="modelValue" class="confirm-dialog-stub"><button class="confirm-btn" @click="$emit(\'confirm\')">Confirm</button></div>'
          }
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

    // Click Publish & Notify
    const publishNotifyBtn = wrapper.findAll('button').find(b => b.text().includes('Publish & Notify'))
    expect(publishNotifyBtn).toBeDefined()
    await publishNotifyBtn!.trigger('click')
    await flushPromises()

    // Confirm dialog
    const confirmBtn = wrapper.find('.confirm-btn')
    expect(confirmBtn.exists()).toBe(true)
    await confirmBtn.trigger('click')
    await flushPromises()

    expect(adminApi.createAdminAnnouncement).toHaveBeenCalledWith({
      title: 'New Tech Initiative',
      body: '<p>Exciting news about tech funding</p>',
      role_ids: [2],
      group_ids: undefined,
      send_email: true
    })

    expect(wrapper.emitted('saved')).toBeTruthy()
  })

  it('prompts confirmation on Publish & Notify and closes dialog after confirming publication', async () => {
    wrapper = mount(AdminAnnouncementFormSheet, {
      props: {
        modelValue: true,
        announcement: null
      },
      global: {
        stubs: {
          FormSheet: {
            props: ['modelValue', 'title'],
            template: '<div class="form-sheet-stub"><slot /><slot name="footer" /></div>'
          },
          RichEditor: {
            name: 'RichEditor',
            props: ['modelValue'],
            emits: ['update:modelValue'],
            template: '<textarea class="rich-editor-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>'
          },
          ConfirmDialog: {
            name: 'ConfirmDialog',
            props: ['modelValue', 'title', 'message'],
            emits: ['update:modelValue', 'confirm', 'cancel'],
            template: '<div v-if="modelValue" class="confirm-dialog-stub"><button class="confirm-btn" @click="$emit(\'confirm\')">Confirm</button></div>'
          }
        }
      }
    })
    await flushPromises()

    // Fill title and body
    const titleInput = wrapper.find<HTMLInputElement>('#ann-title')
    await titleInput.setValue('Company Update')

    const bodyEditor = wrapper.findComponent({ name: 'RichEditor' })
    bodyEditor.vm.$emit('update:modelValue', '<p>Important update details</p>')
    await flushPromises()

    // Click Publish & Notify button
    const publishNotifyBtn = wrapper.findAll('button').find(b => b.text().includes('Publish & Notify'))
    expect(publishNotifyBtn).toBeDefined()
    await publishNotifyBtn!.trigger('click')
    await flushPromises()

    // Confirm dialog is open
    const confirmDialog = wrapper.findComponent({ name: 'ConfirmDialog' })
    expect(confirmDialog.props('modelValue')).toBe(true)

    // Click confirm on dialog
    const confirmBtn = wrapper.find('.confirm-btn')
    expect(confirmBtn.exists()).toBe(true)
    await confirmBtn.trigger('click')
    await flushPromises()

    // Api was called with send_email: true
    expect(adminApi.createAdminAnnouncement).toHaveBeenCalledWith({
      title: 'Company Update',
      body: '<p>Important update details</p>',
      role_ids: undefined,
      group_ids: undefined,
      send_email: true
    })

    // Dialog is closed
    expect(confirmDialog.props('modelValue')).toBe(false)
    expect(wrapper.emitted('saved')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
  })

  it('offers merge tags under the body and inserts the chosen one', async () => {
    const insertText = vi.fn()
    wrapper = mount(AdminAnnouncementFormSheet, {
      props: { modelValue: true, announcement: null },
      global: {
        stubs: {
          FormSheet: {
            props: ['modelValue', 'title', 'description'],
            template: '<div class="form-sheet-stub"><slot /><slot name="footer" /></div>'
          },
          RichEditor: {
            name: 'RichEditor',
            props: ['modelValue'],
            emits: ['update:modelValue'],
            template: '<div class="rich-editor-stub"></div>',
            methods: { insertText }
          },
          ConfirmDialog: true
        }
      }
    })
    await flushPromises()

    const palette = wrapper.find('[data-testid="merge-tags"]')
    expect(palette.exists()).toBe(true)

    const firstNameTag = palette
      .findAll('.merge-tags__tag')
      .find((tag) => tag.text().includes('first_name'))
    expect(firstNameTag).toBeTruthy()

    await firstNameTag!.trigger('click')
    expect(insertText).toHaveBeenCalledWith('{{ first_name }}')
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
  describe('sending progress (AM7)', () => {
    const existing = {
      id: 302,
      title: 'Preloaded Title',
      bodyHtml: '<p>Preloaded Body HTML</p>',
      bodyText: 'Preloaded Body HTML',
      visibilityScope: 'role_based'
    } as unknown as adminApi.AdminAnnouncement

    const saved = {
      id: 301,
      title: 'Created Announcement',
      body: '<p>Created Body</p>',
      visibilityScope: 'global',
      publishedAt: '2026-05-01T10:00:00Z',
      archivedAt: null,
      authorUserId: 1,
      audiences: []
    } as adminApi.AdminAnnouncementDetail

    /** A request the test settles itself, to look at the in-flight state. */
    const deferred = () => {
      let resolve!: (value: adminApi.AdminAnnouncementDetail) => void
      let reject!: (error: Error) => void
      const promise = new Promise<adminApi.AdminAnnouncementDetail>((res, rej) => {
        resolve = res
        reject = rej
      })
      return { promise, resolve, reject }
    }

    // The real FormSheet, so Escape / backdrop / close button are the real ones.
    const mountSheet = async (announcement: adminApi.AdminAnnouncement | null = null) => {
      wrapper = mount(AdminAnnouncementFormSheet, {
        props: {
          modelValue: true,
          announcement,
          'onUpdate:modelValue': (value: boolean) => wrapper!.setProps({ modelValue: value })
        },
        global: {
          stubs: {
            teleport: true,
            RichEditor: {
              name: 'RichEditor',
              props: ['modelValue'],
              emits: ['update:modelValue'],
              template: '<textarea class="rich-editor-stub" :value="modelValue"></textarea>'
            },
            ConfirmDialog: {
              name: 'ConfirmDialog',
              props: ['modelValue'],
              emits: ['update:modelValue', 'confirm'],
              template: '<div v-if="modelValue"><button class="confirm-btn" @click="$emit(\'confirm\')">Confirm</button></div>'
            }
          }
        }
      })
      await flushPromises()
      await wrapper.find('#ann-title').setValue('Term dates')
      wrapper.findComponent({ name: 'RichEditor' }).vm.$emit('update:modelValue', '<p>Body</p>')
      await flushPromises()
      return wrapper
    }

    const button = (label: string) => wrapper!.findAll('button').find((b) => b.text().includes(label))
    const progress = () => wrapper!.find('[role="status"]')
    const footerButtons = () => wrapper!.findAll('.admin-ann-form__footer button')

    /** Publish & Notify through its confirmation, leaving the request in flight. */
    const publishAndNotify = async () => {
      await button('Publish & Notify')!.trigger('click')
      await wrapper!.find('.confirm-btn').trigger('click')
      await flushPromises()
    }

    it('shows "Sending emails…" and locks the form while Publish & Notify is in flight', async () => {
      const request = deferred()
      vi.mocked(adminApi.createAdminAnnouncement).mockReturnValue(request.promise)
      await mountSheet()

      await publishAndNotify()

      expect(progress().text()).toContain('Sending emails…')
      expect(progress().find('.fa-spinner').exists()).toBe(true)
      expect(wrapper!.find('form').attributes('aria-busy')).toBe('true')
      expect(button('Sending…')).toBeDefined()
      expect(footerButtons().every((b) => b.attributes('disabled') !== undefined)).toBe(true)

      request.resolve(saved)
      await flushPromises()
    })

    it('shows "Saving…", not sending, for a save without email', async () => {
      const request = deferred()
      vi.mocked(adminApi.updateAdminAnnouncement).mockReturnValue(request.promise)
      await mountSheet(existing)

      await button('Save')!.trigger('click')
      await flushPromises()

      expect(progress().text()).toBe('Saving…')
      expect(progress().text()).not.toContain('Sending')
      expect(button('Saving…')).toBeDefined()

      request.resolve(saved)
      await flushPromises()
    })

    it('shows "Sending emails…" for Save & Re-notify', async () => {
      const request = deferred()
      vi.mocked(adminApi.updateAdminAnnouncement).mockReturnValue(request.promise)
      await mountSheet(existing)

      await button('Save & Re-notify')!.trigger('click')
      await flushPromises()

      expect(progress().text()).toContain('Sending emails…')
      expect(vi.mocked(adminApi.updateAdminAnnouncement).mock.calls[0][1]).toMatchObject({ send_email: true })

      request.resolve(saved)
      await flushPromises()
    })

    it('cannot be closed by Escape, the backdrop or the close button while sending', async () => {
      const request = deferred()
      vi.mocked(adminApi.createAdminAnnouncement).mockReturnValue(request.promise)
      await mountSheet()
      await publishAndNotify()

      await wrapper!.find('.admin-sheet').trigger('keydown', { key: 'Escape' })
      await wrapper!.find('.admin-sheet__backdrop').trigger('mousedown')
      await wrapper!.find('.admin-sheet__close').trigger('click')
      await flushPromises()

      expect(wrapper!.emitted('update:modelValue')).toBeUndefined()
      expect(wrapper!.find('.admin-sheet').exists()).toBe(true)
      expect(progress().text()).toContain('Sending emails…')

      request.resolve(saved)
      await flushPromises()
    })

    it('clears the indicator and closes once sending has finished', async () => {
      const request = deferred()
      vi.mocked(adminApi.createAdminAnnouncement).mockReturnValue(request.promise)
      await mountSheet()
      await publishAndNotify()

      request.resolve(saved)
      await flushPromises()

      expect(wrapper!.emitted('saved')).toEqual([[saved, true]])
      expect(wrapper!.emitted('update:modelValue')).toEqual([[false]])
      expect(wrapper!.find('.admin-sheet').exists()).toBe(false)
    })

    it('reports a plain save without claiming emails were sent', async () => {
      vi.mocked(adminApi.updateAdminAnnouncement).mockResolvedValue(saved)
      await mountSheet(existing)

      await button('Save')!.trigger('click')
      await flushPromises()

      expect(wrapper!.emitted('saved')).toEqual([[saved, false]])
    })

    it('clears the indicator and keeps the form open with the error when sending fails', async () => {
      const request = deferred()
      vi.mocked(adminApi.createAdminAnnouncement).mockReturnValue(request.promise)
      await mountSheet()
      await publishAndNotify()

      request.reject(new Error('Mail server unavailable'))
      await flushPromises()

      expect(progress().text()).toBe('')
      expect(wrapper!.find('form').attributes('aria-busy')).toBe('false')
      expect(wrapper!.find('[role="alert"]').text()).toContain('Mail server unavailable')
      expect(footerButtons().every((b) => b.attributes('disabled') === undefined)).toBe(true)
      expect(button('Publish & Notify')).toBeDefined()
      expect(wrapper!.find<HTMLInputElement>('#ann-title').element.value).toBe('Term dates')
      expect(wrapper!.emitted('saved')).toBeUndefined()
      expect(wrapper!.find('.admin-sheet').exists()).toBe(true)

      // Once settled it can be dismissed again.
      await wrapper!.find('.admin-sheet__close').trigger('click')
      expect(wrapper!.emitted('update:modelValue')).toEqual([[false]])
    })

    it('sends only once when Confirm is double-clicked', async () => {
      const request = deferred()
      vi.mocked(adminApi.createAdminAnnouncement).mockReturnValue(request.promise)
      await mountSheet()

      await button('Publish & Notify')!.trigger('click')
      // Two clicks before Vue re-renders: the dialog's button is still there
      // for the second one, so only the re-entry guard stops a second send.
      const confirm = wrapper!.find('.confirm-btn').element as HTMLButtonElement
      confirm.click()
      confirm.click()
      await flushPromises()

      expect(adminApi.createAdminAnnouncement).toHaveBeenCalledTimes(1)

      request.resolve(saved)
      await flushPromises()
    })
  })
})
