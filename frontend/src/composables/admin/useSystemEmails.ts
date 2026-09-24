import { computed, ref, watch } from 'vue'
import {
  fetchSystemEmailSettings,
  fetchSystemEmailTemplates,
  previewSystemEmailTemplate,
  restoreSystemEmailTemplate,
  testSendSystemEmailTemplate,
  updateSystemEmailSettings,
  updateSystemEmailTemplate
} from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import type {
  SystemEmailPreview,
  SystemEmailSettings,
  SystemEmailTemplate
} from '@/utils/systemEmail'

export interface SystemEmailDraft {
  subject: string
  body: string
}

/**
 * State and behaviour for the admin system-emails page: load the registry with
 * its saved overrides, edit one type at a time, preview the exact rendered
 * email, send a test to yourself, restore defaults, and flip the per-type and
 * global toggles.
 *
 * Edits are held in a local draft rather than written on every keystroke, so a
 * half-typed merge tag is never saved (and never rejected mid-typing). The
 * draft is compared against the saved row to drive the dirty state.
 */
export function useSystemEmails() {
  const loading = ref(true)
  const error = ref('')
  const notice = ref('')

  const saving = ref(false)
  const previewing = ref(false)
  const testing = ref(false)
  const restoring = ref(false)
  const togglingGlobal = ref(false)
  const togglingKey = ref<string | null>(null)

  const templates = ref<SystemEmailTemplate[]>([])
  const settings = ref<SystemEmailSettings | null>(null)
  const selectedKey = ref<string | null>(null)
  const draft = ref<SystemEmailDraft>({ subject: '', body: '' })
  const preview = ref<SystemEmailPreview | null>(null)

  const previewQueued = ref(false)
  let previewTimer: number | null = null
  const PREVIEW_DEBOUNCE_MS = 500

  const selected = computed<SystemEmailTemplate | null>(
    () => templates.value.find((template) => template.key === selectedKey.value) ?? null
  )

  /** The wording recipients actually get: saved overrides, else the built-in. */
  const currentContent = computed<SystemEmailDraft>(() => {
    const template = selected.value
    if (!template) return { subject: '', body: '' }
    return template.usingSavedContent
      ? { subject: template.subject, body: template.body }
      : { subject: template.defaultSubject, body: template.defaultBody }
  })

  const dirty = computed(() => {
    const template = selected.value
    if (!template) return false
    return (
      draft.value.subject !== currentContent.value.subject ||
      draft.value.body !== currentContent.value.body
    )
  })

  const busy = computed(
    () =>
      saving.value ||
      testing.value ||
      restoring.value ||
      togglingGlobal.value ||
      togglingKey.value !== null
  )

  const emailsEnabled = computed(() => settings.value?.emailsEnabled ?? true)

  // -- Helpers ----------------------------------------------------------------

  const applyTemplate = (template: SystemEmailTemplate | null) => {
    draft.value = template?.usingSavedContent
      ? { subject: template.subject, body: template.body }
      : { subject: template?.defaultSubject ?? '', body: template?.defaultBody ?? '' }
  }

  const replaceTemplate = (updated: SystemEmailTemplate) => {
    const exists = templates.value.some((template) => template.key === updated.key)
    templates.value = exists
      ? templates.value.map((template) => (template.key === updated.key ? updated : template))
      : [...templates.value, updated]
  }

  const clearMessages = () => {
    error.value = ''
    notice.value = ''
  }

  const messageFrom = (fallback: string, caught: unknown): string =>
    caught instanceof Error && caught.message ? caught.message : fallback

  // -- Loading ----------------------------------------------------------------

  const load = async () => {
    loading.value = true
    clearMessages()
    try {
      const [list, loadedSettings] = await Promise.all([
        fetchSystemEmailTemplates(),
        fetchSystemEmailSettings()
      ])
      templates.value = list
      settings.value = loadedSettings

      const stillPresent = list.some((template) => template.key === selectedKey.value)
      if (!stillPresent) selectedKey.value = list[0]?.key ?? null
      applyTemplate(selected.value)
    } catch (loadError) {
      logApiError('admin.system-emails.load', loadError)
      error.value = messageFrom('Unable to load system emails.', loadError)
      templates.value = []
      settings.value = null
    } finally {
      loading.value = false
    }
  }

  // -- Selection / draft ------------------------------------------------------

  const select = (key: string) => {
    if (key === selectedKey.value) return
    selectedKey.value = key
    applyTemplate(selected.value)
    preview.value = null
    clearMessages()
  }

  const setSubject = (value: string) => {
    draft.value = { ...draft.value, subject: value }
  }

  const setBody = (value: string) => {
    draft.value = { ...draft.value, body: value }
  }

  // -- Preview / test / save --------------------------------------------------

  const refreshPreview = async (options?: { quiet?: boolean }) => {
    const template = selected.value
    if (!template) return
    previewing.value = true
    if (options?.quiet) previewQueued.value = false
    else error.value = ''
    try {
      preview.value = await previewSystemEmailTemplate(template.key, {
        subject: draft.value.subject,
        body: draft.value.body
      })
    } catch (previewError) {
      logApiError('admin.system-emails.preview', previewError)
      if (!options?.quiet) {
        error.value = messageFrom('Unable to render the preview.', previewError)
        preview.value = null
      }
    } finally {
      previewing.value = false
      if (previewQueued.value) {
        previewQueued.value = false
        window.setTimeout(runLivePreview, 0)
      }
    }
  }

  /**
 * The preview updates automatically as the admin edits, after a short pause.
 * Quiet failures keep the last good render instead of flashing an error
 * mid-typing (e.g. while a merge tag is half-typed).
 */
const runLivePreview = () => {
  if (!selected.value) return
  if (previewing.value) {
    previewQueued.value = true
    return
  }
  void refreshPreview({ quiet: true })
}

watch(
  draft,
  () => {
    if (!selected.value) return
    if (previewTimer) window.clearTimeout(previewTimer)
    previewTimer = window.setTimeout(runLivePreview, PREVIEW_DEBOUNCE_MS)
  },
  { flush: 'pre' }
)

const testSend = async () => {
    const template = selected.value
    if (!template) return
    testing.value = true
    clearMessages()
    try {
      const result = await testSendSystemEmailTemplate(template.key, {
        subject: draft.value.subject,
        body: draft.value.body
      })
      notice.value = `Test email sent to ${result.sentTo}.`
    } catch (testError) {
      logApiError('admin.system-emails.test-send', testError)
      error.value = messageFrom('Unable to send the test email.', testError)
    } finally {
      testing.value = false
    }
  }

  const save = async () => {
    const template = selected.value
    if (!template) return
    saving.value = true
    clearMessages()
    try {
      const updated = await updateSystemEmailTemplate(template.key, {
        subject: draft.value.subject,
        body: draft.value.body
      })
      replaceTemplate(updated)
      applyTemplate(updated)
      notice.value = `${updated.name} saved.`
      await refreshPreview()
    } catch (saveError) {
      logApiError('admin.system-emails.save', saveError)
      error.value = messageFrom('Unable to save this email.', saveError)
    } finally {
      saving.value = false
    }
  }

  const restore = async () => {
    const template = selected.value
    if (!template) return
    restoring.value = true
    clearMessages()
    try {
      const updated = await restoreSystemEmailTemplate(template.key)
      replaceTemplate(updated)
      applyTemplate(updated)
      notice.value = `${updated.name} restored to its default wording.`
      await refreshPreview()
    } catch (restoreError) {
      logApiError('admin.system-emails.restore', restoreError)
      error.value = messageFrom('Unable to restore this email.', restoreError)
    } finally {
      restoring.value = false
    }
  }

  // -- Toggles ----------------------------------------------------------------

  const toggleEnabled = async (template: SystemEmailTemplate, enabled: boolean) => {
    if (template.locked && !enabled) return
    togglingKey.value = template.key
    clearMessages()
    try {
      replaceTemplate(await updateSystemEmailTemplate(template.key, { enabled }))
    } catch (toggleError) {
      logApiError('admin.system-emails.toggle', toggleError)
      error.value = messageFrom('Unable to update this email.', toggleError)
    } finally {
      togglingKey.value = null
    }
  }

  const toggleGlobal = async (enabled: boolean) => {
    togglingGlobal.value = true
    clearMessages()
    try {
      settings.value = await updateSystemEmailSettings(enabled)
      notice.value = enabled
        ? 'System emails are now being sent.'
        : 'System emails are now paused.'
    } catch (toggleError) {
      logApiError('admin.system-emails.toggle-global', toggleError)
      error.value = messageFrom('Unable to update the global setting.', toggleError)
    } finally {
      togglingGlobal.value = false
    }
  }

  return {
    loading,
    error,
    notice,
    saving,
    previewing,
    testing,
    restoring,
    togglingGlobal,
    togglingKey,
    templates,
    settings,
    selectedKey,
    draft,
    preview,
    selected,
    dirty,
    busy,
    emailsEnabled,
    load,
    select,
    setSubject,
    setBody,
    refreshPreview,
    testSend,
    save,
    restore,
    toggleEnabled,
    toggleGlobal
  }
}
