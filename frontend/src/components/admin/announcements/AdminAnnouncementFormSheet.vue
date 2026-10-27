<template>
  <FormSheet
    v-model="open"
    :title="isEditing ? 'Edit Announcement' : 'New Announcement'"
    :description="isEditing ? `Update details for announcement #${announcement?.id}` : 'Create a new announcement for students, mentors, or all users.'"
    width="min(100vw, 760px)"
  >
    <form class="admin-ann-form" novalidate :aria-busy="saving" @submit.prevent>
      <p v-if="formError" class="admin-ann-form__error" role="alert">
        <i class="fas fa-triangle-exclamation mr-1.5"></i>
        {{ formError }}
      </p>

      <div class="admin-ann-form__grid">
        <!-- Title -->
        <div class="form-field form-field--full">
          <label class="form-label" for="ann-title">
            Title <span class="required-star">*</span>
          </label>
          <input
            id="ann-title"
            v-model.trim="title"
            type="text"
            class="editor__title app-input app-input--wide"
            placeholder="Announcement title"
            maxlength="255"
            required
          />
        </div>

        <!-- Body with TipTap RichEditor -->
        <div class="form-field form-field--full">
          <label class="form-label">
            Body <span class="required-star">*</span>
          </label>
          <RichEditor
            :key="editorKey"
            ref="richEditorRef"
            v-model="body"
            compact
            placeholder="Write your announcement content…"
          />
          <!-- Merge tags: filled in with each reader's own details. -->
          <div v-if="mergeTags.length" class="admin-ann-form__merge-tags" data-testid="merge-tags">
            <span class="admin-ann-form__merge-tags-label">
              Personalise it. Each tag becomes the reader's own:
            </span>
            <MergeTagPalette :tags="mergeTags" @insert="insertMergeTag" />
          </div>
        </div>

        <!-- Target Roles -->
        <div class="form-field form-field--full">
          <div class="admin-ann-form__section">
            <span class="font-semibold">Target Roles</span>
            <span class="admin-ann-form__section-note">(leave unselected to target all roles)</span>
          </div>
          <div v-if="loadingMeta" class="admin-ann-form__meta-loading">
            <i class="fas fa-spinner fa-spin mr-1.5"></i> Loading roles…
          </div>
          <fieldset v-else-if="roles.length" class="admin-ann-form__checkbox-grid">
            <legend class="sr-only">Target Roles</legend>
            <label
              v-for="r in roles"
              :key="r.id"
              class="admin-ann-form__checkbox-label"
            >
              <input
                type="checkbox"
                :value="r.id"
                :checked="roleIds.includes(r.id)"
                @change="toggleRole(r.id)"
              />
              <span>{{ r.name }}</span>
            </label>
          </fieldset>
          <p v-if="roleIds.length > 0" class="admin-ann-form__count-note">
            {{ roleIds.length }} role{{ roleIds.length > 1 ? 's' : '' }} selected
          </p>
        </div>

        <!-- Target Categories: ticking one selects its groups below. Off until
             the submission deadline has passed and who's in which is settled,
             the whole section greyed out till then. -->
        <div
          class="form-field form-field--full"
          :class="{ 'admin-ann-form__categories--off': !categories?.available }"
          data-testid="target-categories-section"
        >
          <div class="admin-ann-form__section">
            <span class="font-semibold">Target Categories</span>
            <span class="admin-ann-form__section-note">(leave unselected to target all groups)</span>
          </div>
          <fieldset class="admin-ann-form__checkbox-grid" data-testid="target-categories">
            <legend class="sr-only">Target Categories</legend>
            <label
              v-for="c in categoryList"
              :key="c.key"
              class="admin-ann-form__checkbox-label"
            >
              <input
                type="checkbox"
                :checked="categoryChecked(c)"
                :disabled="!categories?.available || !c.group_ids.length"
                @change="toggleCategory(c)"
              />
              <span>{{ c.label }}<template v-if="categories?.available"> ({{ c.group_ids.length }})</template></span>
            </label>
          </fieldset>
          <p v-if="!categories?.available" class="admin-ann-form__categories-reason">
            {{ categories?.reason || 'Available once the submission deadline has passed.' }}
          </p>
        </div>

        <!-- Target Groups -->
        <div class="form-field form-field--full">
          <div class="admin-ann-form__section">
            <span class="font-semibold">Target Groups</span>
            <span class="admin-ann-form__section-note">(leave unselected to target all groups)</span>
          </div>
          <div v-if="loadingMeta" class="admin-ann-form__meta-loading">
            <i class="fas fa-spinner fa-spin mr-1.5"></i> Loading groups…
          </div>
          <fieldset v-else-if="groups.length" class="admin-ann-form__checkbox-grid">
            <legend class="sr-only">Target Groups</legend>
            <label
              v-for="g in groups"
              :key="g.id"
              class="admin-ann-form__checkbox-label"
            >
              <input
                type="checkbox"
                :value="g.id"
                :checked="groupIds.includes(g.id)"
                @change="toggleGroup(g.id)"
              />
              <span>{{ g.name }}</span>
            </label>
          </fieldset>
          <p v-if="groupIds.length > 0" class="admin-ann-form__count-note">
            {{ groupIds.length }} group{{ groupIds.length > 1 ? 's' : '' }} selected
          </p>
        </div>

        <!-- Global audience notice -->
        <div v-if="roleIds.length === 0 && groupIds.length === 0" class="admin-ann-form__notice">
          <i class="fas fa-circle-info"></i>
          <span>No roles or groups selected - announcement will be visible to all users (Global).</span>
        </div>
      </div>

      <!-- Sending progress. The request only returns once every email has
           been attempted (the server sends synchronously), so this stays up
           for exactly as long as sending takes. Kept mounted so screen
           readers hear it change. -->
      <p class="admin-ann-form__progress" role="status" aria-live="polite">
        <template v-if="saving">
          <i class="fas fa-spinner fa-spin" aria-hidden="true"></i>
          <span v-if="pendingEmail">
            Sending emails… This can take a moment for a large audience. Please keep this open.
          </span>
          <span v-else>Saving…</span>
        </template>
      </p>

      <!-- Footer Actions -->
      <div class="admin-ann-form__footer">
        <button
          v-if="isEditing"
          type="button"
          class="btn btn-danger"
          :disabled="saving || busy"
          @click="emit('delete', announcement!)"
        >
          <i class="fas fa-trash-can" aria-hidden="true"></i>
          <span>Delete</span>
        </button>

        <span v-if="isEditing" class="admin-ann-form__footer-spacer"></span>

        <button
          type="button"
          class="btn btn-outline"
          :disabled="saving || busy"
          @click="onDismiss"
        >
          <span>Cancel</span>
        </button>

        <!-- Create Mode Buttons: ONLY Publish & Notify -->
        <template v-if="!isEditing">
          <button
            type="button"
            class="btn btn-primary"
            :disabled="saving || busy"
            @click="promptPublishWithEmail"
          >
            <i v-if="saving && pendingEmail" class="fas fa-spinner fa-spin"></i>
            <i v-else class="fas fa-paper-plane"></i>
            <span>{{ saving && pendingEmail ? 'Sending…' : 'Publish & Notify' }}</span>
          </button>
        </template>

        <!-- Edit Mode Buttons -->
        <template v-else>
          <button
            type="button"
            class="btn btn-outline"
            :disabled="saving || busy"
            @click="handleSubmit(false)"
          >
            <i v-if="saving && !pendingEmail" class="fas fa-spinner fa-spin"></i>
            <span>{{ saving && !pendingEmail ? 'Saving…' : 'Save' }}</span>
          </button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="saving || busy"
            @click="handleSubmit(true)"
          >
            <i v-if="saving && pendingEmail" class="fas fa-spinner fa-spin"></i>
            <i v-else class="fas fa-paper-plane"></i>
            <span>{{ saving && pendingEmail ? 'Sending…' : 'Save & Re-notify' }}</span>
          </button>
        </template>
      </div>
    </form>
  </FormSheet>

  <!-- Publish & Notify confirmation modal -->
  <ConfirmDialog
    v-model="confirmNotifyOpen"
    title="Publish & Notify Announcement?"
    message="This will immediately publish the announcement to the platform and send an email notification to the selected audience."
    confirm-label="Publish & Notify"
    variant="default"
    @confirm="confirmPublishAndNotify"
  />
</template>

<script setup lang="ts">
import { ref, computed, defineAsyncComponent, watch } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import MergeTagPalette from '@/components/admin/emails/MergeTagPalette.vue'
import { mergeTagToken } from '@/utils/systemEmail'

const RichEditor = defineAsyncComponent(
  () => import('@/components/admin/RichEditor.vue')
)
import {
  fetchAdminAnnouncement,
  createAdminAnnouncement,
  updateAdminAnnouncement,
  fetchAnnouncementRoles,
  fetchAnnouncementGroups,
  fetchAnnouncementMergeTags,
  type AdminAnnouncement,
  type AdminAnnouncementDetail,
  type AdminAnnouncementRoleOption,
  type AdminAnnouncementGroupOption,
  type AdminAnnouncementMergeTag
} from '@/utils/adminAPI'
import { fetchAnnouncementCategories, type AnnouncementCategories } from '@/utils/managementAPI'

interface Props {
  modelValue: boolean
  announcement?: AdminAnnouncement | null
  busy?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: false,
  announcement: null,
  busy: false
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  /** `emailed`: notification emails were requested and sending has finished. */
  (e: 'saved', announcement: AdminAnnouncementDetail, emailed: boolean): void
  (e: 'delete', announcement: AdminAnnouncement): void
  (e: 'close'): void
}>()

const open = computed({
  get: () => props.modelValue,
  // Escape, the backdrop and the close button all land here. While a save
  // (and any email send) is in flight the sheet stays open, so the progress
  // indicator can't vanish before sending has finished.
  set: (val: boolean) => {
    if (!val && saving.value) return
    emit('update:modelValue', val)
  }
})

const isEditing = computed(() => Boolean(props.announcement && props.announcement.id))

const title = ref('')
const body = ref('')
const roleIds = ref<number[]>([])
const groupIds = ref<number[]>([])

// The greeting tags a body may use, offered under the editor.
const mergeTags = ref<AdminAnnouncementMergeTag[]>([])
const richEditorRef = ref<{ insertText: (text: string) => void } | null>(null)

const roles = ref<AdminAnnouncementRoleOption[]>([])
const groups = ref<AdminAnnouncementGroupOption[]>([])
const loadingMeta = ref(false)

const saving = ref(false)
const pendingEmail = ref(false)
const formError = ref<string | null>(null)
const confirmNotifyOpen = ref(false)

const editorKey = computed(() => {
  return props.announcement ? `edit-${props.announcement.id}` : 'new-announcement'
})

// Finalist, Nonfinalist and Nonsubmission, each with its groups; shown off
// until they're known.
const categories = ref<AnnouncementCategories | null>(null)
const DEFAULT_CATEGORIES = [
  { key: 'finalists', label: 'Finalist', group_ids: [] },
  { key: 'nonfinalists', label: 'Nonfinalist', group_ids: [] },
  { key: 'nonsubmissions', label: 'Nonsubmission', group_ids: [] }
]
const categoryList = computed(() => categories.value?.categories ?? DEFAULT_CATEGORIES)
type Category = AnnouncementCategories['categories'][number]

// Ticked while every one of its groups is.
const categoryChecked = (c: Category) =>
  c.group_ids.length > 0 && c.group_ids.every((id) => groupIds.value.includes(id))

const toggleCategory = (c: Category) => {
  groupIds.value = categoryChecked(c)
    ? groupIds.value.filter((id) => !c.group_ids.includes(id))
    : [...new Set([...groupIds.value, ...c.group_ids])]
}

async function loadCategories() {
  try {
    categories.value = await fetchAnnouncementCategories()
  } catch {
    // Best effort: without them the categories just stay off.
  }
}

async function loadMeta() {
  void loadCategories()
  void loadMergeTags()
  if (roles.value.length > 0 && groups.value.length > 0) return
  loadingMeta.value = true
  try {
    const [rolesData, groupsData] = await Promise.all([
      fetchAnnouncementRoles(),
      fetchAnnouncementGroups()
    ])
    roles.value = rolesData || []
    groups.value = groupsData || []
  } catch (err) {
    console.error('Failed to load announcement targeting metadata:', err)
  } finally {
    loadingMeta.value = false
  }
}

async function loadMergeTags() {
  try {
    mergeTags.value = await fetchAnnouncementMergeTags()
  } catch {
    // Best effort: without them the palette just stays empty.
  }
}

function insertMergeTag(tag: AdminAnnouncementMergeTag) {
  richEditorRef.value?.insertText(mergeTagToken(tag.name))
}

async function populateFromAnnouncement(item: AdminAnnouncement) {
  applyAnnouncement(item)
  if (item.id) {
    try {
      const fullDetail = await fetchAdminAnnouncement(item.id)
      if (fullDetail) applyAnnouncement(fullDetail)
    } catch (err) {
      console.error('Failed to load announcement details:', err)
    }
  }
}

function applyAnnouncement(item: AdminAnnouncement) {
  title.value = item.title || ''
  body.value = item.body || ''
  roleIds.value = (item.audiences || [])
    .map((a) => a.roleId)
    .filter((id): id is number => id !== null && id !== undefined)
  groupIds.value = (item.audiences || [])
    .map((a) => a.groupId)
    .filter((id): id is number => id !== null && id !== undefined)
}

function resetForm() {
  title.value = ''
  body.value = ''
  roleIds.value = []
  groupIds.value = []
}

watch(
  () => props.modelValue,
  async (isOpen) => {
    confirmNotifyOpen.value = false
    if (!isOpen) return
    formError.value = null
    await loadMeta()
    if (props.announcement) {
      await populateFromAnnouncement(props.announcement)
    } else {
      resetForm()
    }
  },
  { immediate: true }
)

function toggleRole(id: number) {
  if (roleIds.value.includes(id)) {
    roleIds.value = roleIds.value.filter((r) => r !== id)
  } else {
    roleIds.value.push(id)
  }
}

function toggleGroup(id: number) {
  if (groupIds.value.includes(id)) {
    groupIds.value = groupIds.value.filter((g) => g !== id)
  } else {
    groupIds.value.push(id)
  }
}

function onDismiss() {
  if (saving.value) return
  confirmNotifyOpen.value = false
  emit('close')
  open.value = false
}

function validateForm(): boolean {
  formError.value = null
  if (!title.value.trim()) {
    formError.value = 'Title is required.'
    return false
  }
  const strippedBody = body.value.replace(/<[^>]*>/g, '').trim()
  if (!strippedBody && !body.value.includes('<img')) {
    formError.value = 'Body content is required.'
    return false
  }
  return true
}

function promptPublishWithEmail() {
  if (!validateForm()) return
  confirmNotifyOpen.value = true
}

async function confirmPublishAndNotify() {
  confirmNotifyOpen.value = false
  await handleSubmit(true)
}

async function handleSubmit(sendEmail: boolean) {
  // One save (and one batch of emails) at a time, whatever triggered it.
  if (saving.value) return
  if (!validateForm()) return

  saving.value = true
  pendingEmail.value = sendEmail
  formError.value = null

  let result: AdminAnnouncementDetail | null = null
  try {
    const payload = {
      title: title.value.trim(),
      body: body.value,
      role_ids: roleIds.value.length > 0 ? roleIds.value : undefined,
      group_ids: groupIds.value.length > 0 ? groupIds.value : undefined,
      send_email: sendEmail
    }

    if (isEditing.value && props.announcement?.id) {
      result = await updateAdminAnnouncement(props.announcement.id, payload)
    } else {
      result = await createAdminAnnouncement(payload)
    }
  } catch (err: unknown) {
    console.error('Failed to save announcement:', err)
    formError.value = err instanceof Error ? err.message : 'Failed to save announcement. Please try again.'
  } finally {
    saving.value = false
    pendingEmail.value = false
  }

  // Closed only once saving has cleared, so the close guard lets it through.
  if (result) {
    emit('saved', result, sendEmail)
    confirmNotifyOpen.value = false
    open.value = false
  }
}
</script>

<!-- The title box shared with the other editor forms. -->
<style scoped src="../editorForm.css"></style>

<style scoped>
.admin-ann-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding: 0.25rem 0;
}

.admin-ann-form__error {
  display: flex;
  align-items: center;
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  padding: 0.625rem 0.875rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
}

.admin-ann-form__grid {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.form-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
}

.required-star {
  color: #dc2626;
}

.admin-ann-form__section {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: #374151;
  margin-bottom: 0.25rem;
}

.admin-ann-form__section-note {
  font-size: 0.75rem;
  color: #6b7280;
}

.admin-ann-form__meta-loading {
  font-size: 0.8125rem;
  color: #6b7280;
  padding: 0.5rem 0;
}

.admin-ann-form__checkbox-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem 1rem;
  border: 1px solid #e5e7eb;
  border-radius: 0.375rem;
  padding: 0.75rem;
  background-color: #f9fafb;
}

@media (max-width: 640px) {
  .admin-ann-form__checkbox-grid {
    grid-template-columns: 1fr;
  }
}

.admin-ann-form__checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: #374151;
  cursor: pointer;
  user-select: none;
}

.admin-ann-form__checkbox-label input[type='checkbox'] {
  width: 1rem;
  height: 1rem;
  accent-color: var(--dark-green);
  cursor: pointer;
}

.admin-ann-form__count-note {
  font-size: 0.75rem;
  color: #6b7280;
  margin-top: 0.25rem;
}

/* Target Categories before submissions close: all of it greyed out. */
.admin-ann-form__categories--off {
  opacity: 0.5;
}

.admin-ann-form__categories--off .admin-ann-form__checkbox-label {
  cursor: not-allowed;
}

/* When they open. */
.admin-ann-form__categories-reason {
  font-size: 0.75rem;
  font-style: italic;
  color: #6b7280;
  margin-top: 0.25rem;
}

.admin-ann-form__notice {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  font-size: 0.84rem;
  color: var(--teal);
  background-color: var(--light-green);
  border: 1px solid rgba(1, 113, 81, 0.25);
  border-radius: 0.375rem;
  padding: 0.625rem 0.875rem;
  line-height: 1.4;
}

.admin-ann-form__merge-tags {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  margin-top: 0.5rem;
}

.admin-ann-form__merge-tags-label {
  font-size: 0.75rem;
  color: #6b7280;
}

.admin-ann-form__notice i {
  font-size: 1rem;
  color: var(--dark-green);
  flex-shrink: 0;
}

.admin-ann-form__progress {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 1rem 0 0;
  color: var(--text-muted);
  font-size: 0.875rem;
}

/* Collapses while idle; the live region itself stays mounted. */
.admin-ann-form__progress:empty {
  display: none;
}

.admin-ann-form__footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 0.65rem;
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-light);
}

.admin-ann-form__footer-spacer {
  flex: 1;
}

.btn-danger {
  background-color: var(--danger);
  color: var(--white);
}

.btn-danger:hover:not(:disabled) {
  background-color: #b91c1c;
}
</style>
