<template>
  <FormSheet
    v-model="open"
    :title="isEditing ? 'Edit Resource' : 'Upload Resource'"
    :description="isEditing ? `Update details for resource #${resource?.id}` : 'Add a new file, attachment, or page to the resource library.'"
    width="min(100vw, 680px)"
  >
    <form class="admin-resource-form" novalidate @submit.prevent="submitForm">
      <p v-if="formError" class="admin-resource-form__error" role="alert">
        {{ formError }}
      </p>

      <div class="admin-resource-form__grid">
        <!-- Resource Kind -->
        <div class="form-field form-field--full">
          <label class="form-label" for="res-kind">Resource Kind *</label>
          <select
            id="res-kind"
            v-model="form.kind"
            class="form-input filter-select"
            :disabled="isEditing"
          >
            <option value="file">File Upload</option>
            <option value="attachment">Attachment</option>
            <option value="page">Rich Content Page</option>
          </select>
          <p v-if="isEditing" class="admin-resource-form__hint">
            Resource kind cannot be changed after creation.
          </p>
        </div>

        <!-- Resource Name -->
        <div class="form-field form-field--full">
          <label class="form-label" for="res-name">Resource Name *</label>
          <input
            id="res-name"
            v-model.trim="form.name"
            type="text"
            class="form-input"
            placeholder="e.g. Mentor Handbook 2026"
            required
            maxlength="255"
          />
        </div>

        <!-- Description -->
        <div class="form-field form-field--full">
          <label class="form-label" for="res-desc">Description *</label>
          <textarea
            id="res-desc"
            v-model.trim="form.description"
            class="form-input"
            rows="3"
            placeholder="Short description for admins and users."
            required
          ></textarea>
        </div>

        <!-- Visibility -->
        <div class="form-field form-field--full">
          <label class="form-label" for="res-visibility">Visibility *</label>
          <select
            id="res-visibility"
            v-model="form.visibilityScope"
            class="form-input filter-select"
          >
            <option value="global">Global (All Users)</option>
            <option value="role_based">Role-based</option>
          </select>
        </div>

        <!-- Visible Roles (if role_based) -->
        <div v-if="form.visibilityScope === 'role_based'" class="form-field form-field--full">
          <label class="form-label">Visible Roles *</label>
          <fieldset class="admin-resource-form__checkbox-grid">
            <legend class="sr-only">Select visible roles</legend>
            <label
              v-for="role in availableRoles"
              :key="role.id"
              class="admin-resource-form__checkbox-label"
            >
              <input
                type="checkbox"
                :value="role.id"
                :checked="form.roleIds.includes(role.id)"
                @change="toggleRole(role.id)"
              />
              <span>{{ formatRoleName(role) }}</span>
            </label>
          </fieldset>
          <p class="admin-resource-form__hint">
            Only users with the selected role(s) will be able to view and access this resource.
          </p>
        </div>

        <!-- Resource Labels -->
        <div class="form-field form-field--full">
          <label class="form-label" for="res-labels">Resource Labels</label>
          <input
            id="res-labels"
            v-model.trim="form.labelInput"
            type="text"
            class="form-input"
            placeholder="e.g. Do's and Don'ts, Group tips"
          />
          <p class="admin-resource-form__hint">
            Enter comma-separated labels (e.g. Do's and Don'ts, Group tips).
          </p>
        </div>

        <!-- Type -->
        <div class="form-field form-field--full">
          <label class="form-label" for="res-type">Type</label>
          <select
            id="res-type"
            v-model="form.typeId"
            class="form-input filter-select"
          >
            <option :value="null">Uncategorized</option>
            <option
              v-for="typeItem in resourceTypes"
              :key="typeItem.id"
              :value="typeItem.id"
            >
              {{ typeItem.type_name }}
            </option>
          </select>
        </div>
      </div>

      <!-- File Upload section for file/attachment kinds -->
      <div v-if="form.kind !== 'page'" class="admin-resource-form__section-wrap">
        <div class="admin-resource-form__section">File Attachment</div>
        <div class="admin-resource-file-upload">
          <div class="admin-resource-file-upload__controls">
            <input
              ref="fileInputRef"
              type="file"
              class="admin-resource-file-input"
              @change="onFileChange"
            />
            <button
              type="button"
              class="btn btn-outline btn-sm"
              @click="triggerFileInput"
            >
              <i class="fas fa-folder-open" aria-hidden="true"></i>
              <span>{{ selectedFile || currentFileName ? 'Change File' : 'Browse Files' }}</span>
            </button>
            <button
              v-if="selectedFile"
              type="button"
              class="btn btn-outline btn-sm"
              @click="clearSelectedFile"
            >
              <i class="fas fa-times" aria-hidden="true"></i>
              <span>Clear</span>
            </button>
          </div>

          <div v-if="selectedFile" class="admin-resource-file-badge">
            <i class="fas fa-file" aria-hidden="true"></i>
            <span class="admin-resource-file-name">{{ selectedFile.name }}</span>
            <span class="admin-resource-file-size">({{ formatFileSize(selectedFile.size) }})</span>
          </div>
          <div v-else-if="currentFileName" class="admin-resource-file-badge admin-resource-file-badge--existing">
            <i class="fas fa-file-check" aria-hidden="true"></i>
            <span class="admin-resource-file-name">Current: {{ currentFileName }}</span>
            <span v-if="currentFileSize" class="admin-resource-file-size">({{ formatFileSize(currentFileSize) }})</span>
          </div>

          <p class="admin-resource-form__hint">
            Accepted: PDF, Word, Excel, PowerPoint, Images, Videos, Text &bull; Max 25 MB
          </p>
        </div>
      </div>

      <!-- Rich Page Content for page kind -->
      <div v-else class="admin-resource-form__section-wrap">
        <div class="admin-resource-form__section">Page Content *</div>
        <div class="form-field form-field--full">
          <textarea
            id="res-page-content"
            v-model="form.contentHtml"
            class="form-input"
            rows="8"
            placeholder="Write resource page content (HTML or plain text)..."
            required
          ></textarea>
          <p class="admin-resource-form__hint">
            Content will be displayed directly when users view this resource page.
          </p>
        </div>
      </div>

      <!-- Footer Actions -->
      <div class="admin-resource-form__footer">
        <button
          v-if="isEditing"
          type="button"
          class="btn btn-danger"
          :disabled="saving || busy"
          @click="emit('delete')"
        >
          <i class="fas fa-trash-can" aria-hidden="true"></i>
          Delete
        </button>
        <span v-if="isEditing" class="admin-resource-form__footer-spacer"></span>
        <button
          type="button"
          class="btn btn-outline"
          :disabled="saving || busy"
          @click="onCancel"
        >
          Cancel
        </button>
        <button
          type="submit"
          class="btn btn-primary"
          :disabled="saving || busy"
        >
          <span v-if="saving" class="admin-resource-form__spinner" aria-hidden="true"></span>
          {{ isEditing ? 'Save Changes' : 'Upload Resource' }}
        </button>
      </div>
    </form>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import type {
  AdminResourceDetail,
  AdminResourceRoleItem,
  CreateAdminResourcePayload,
  UpdateAdminResourcePayload
} from '@/utils/adminAPI'
import {
  createAdminResource,
  fetchAdminResourceRoles,
  replaceAdminResourceFile,
  updateAdminResource,
  uploadAdminResource
} from '@/utils/adminAPI'
import type { Resource, ResourceKind, ResourceType } from '@/utils/resourcesAPI'
import { fetchResourceTypes } from '@/utils/resourcesAPI'

const props = defineProps<{
  modelValue: boolean
  resource?: Resource | AdminResourceDetail | null
  busy?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'close'): void
  (e: 'saved'): void
  (e: 'delete'): void
}>()

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value)
})

const isEditing = computed(() => Boolean(props.resource?.id))

interface ResourceFormState {
  name: string
  description: string
  kind: ResourceKind
  visibilityScope: 'global' | 'role_based'
  typeId: number | null
  roleIds: number[]
  labelInput: string
  contentHtml: string
}

const defaultFormState = (): ResourceFormState => ({
  name: '',
  description: '',
  kind: 'file',
  visibilityScope: 'global',
  typeId: null,
  roleIds: [],
  labelInput: '',
  contentHtml: ''
})

const form = reactive<ResourceFormState>(defaultFormState())
const formError = ref('')
const saving = ref(false)

const availableRoles = ref<AdminResourceRoleItem[]>([])
const resourceTypes = ref<ResourceType[]>([])

const fileInputRef = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)

const currentFileName = computed(() => {
  if (!props.resource) return null
  const raw = props.resource as any
  return raw.file_name || null
})

const currentFileSize = computed(() => {
  if (!props.resource) return null
  const raw = props.resource as any
  return raw.file_size || null
})

const formatRoleName = (role: AdminResourceRoleItem): string => {
  if (role.type_name) return role.type_name
  if (role.slug) {
    return role.slug
      .split(/[-_]+/)
      .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
      .join(' ')
  }
  return `Role #${role.id}`
}

const formatFileSize = (bytes?: number | null): string => {
  if (!bytes || bytes <= 0) return '-'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let idx = 0
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024
    idx++
  }
  return `${size.toFixed(size >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`
}

const loadLookups = async () => {
  try {
    const [rolesData, typesData] = await Promise.all([
      fetchAdminResourceRoles(),
      fetchResourceTypes()
    ])
    // Filter out 'admin' role because admins always have access
    availableRoles.value = (rolesData || []).filter((r) => r.slug !== 'admin')
    resourceTypes.value = typesData || []
  } catch (err) {
    console.warn('Failed to load resource metadata:', err)
  }
}

const parseLabels = (labelInput: string): string[] => {
  return labelInput
    .split(',')
    .map((l) => l.trim())
    .filter(Boolean)
}

const initForm = async (currentResource?: Resource | AdminResourceDetail | null) => {
  formError.value = ''
  selectedFile.value = null
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }

  await loadLookups()

  if (!currentResource) {
    Object.assign(form, defaultFormState())
    return
  }

  const raw = currentResource as any

  // Extract role IDs from audiences or visible_roles
  let roleIds: number[] = []
  if (Array.isArray(raw.audiences)) {
    roleIds = raw.audiences.map((a: any) => a.role_id || a.role?.id).filter(Boolean)
  } else if (Array.isArray(raw.visible_roles)) {
    roleIds = raw.visible_roles.map((r: any) => r.id).filter(Boolean)
  }

  // Extract label names
  let labelStr = ''
  if (Array.isArray(raw.labels)) {
    labelStr = raw.labels.map((l: any) => l.name).filter(Boolean).join(', ')
  }

  const rawTypeId = raw.type_id ?? raw.resource_type_id ?? raw.resource_type_detail?.id ?? null

  const isRoleBased =
    raw.visibility_scope === 'role_based' ||
    raw.visibility_scope === 'role' ||
    roleIds.length > 0

  Object.assign(form, {
    name: raw.name || raw.resource_name || '',
    description: raw.description || raw.resource_description || '',
    kind: raw.kind || raw.resource_kind || 'file',
    visibilityScope: isRoleBased ? 'role_based' : 'global',
    typeId: rawTypeId,
    roleIds,
    labelInput: labelStr,
    contentHtml: raw.content_html || ''
  })
}

watch(
  () => props.modelValue,
  (isOpening) => {
    if (isOpening) {
      void initForm(props.resource)
    }
  },
  { immediate: true }
)

const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const onFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  if (file.size > 25 * 1024 * 1024) {
    formError.value = 'File is too large. Maximum allowed size is 25 MB.'
    return
  }

  selectedFile.value = file
  formError.value = ''
}

const clearSelectedFile = () => {
  selectedFile.value = null
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

const toggleRole = (roleId: number) => {
  const idx = form.roleIds.indexOf(roleId)
  if (idx > -1) {
    form.roleIds.splice(idx, 1)
  } else {
    form.roleIds.push(roleId)
  }
}

const onCancel = () => {
  open.value = false
  emit('close')
}

const validateForm = (): boolean => {
  if (!form.name.trim()) {
    formError.value = 'Resource name is required.'
    return false
  }
  if (!form.description.trim()) {
    formError.value = 'Description is required.'
    return false
  }
  if (form.visibilityScope === 'role_based' && form.roleIds.length === 0) {
    formError.value = 'Please select at least one visible role for role-based visibility.'
    return false
  }
  if (!isEditing.value && form.kind !== 'page' && !selectedFile.value) {
    formError.value = 'Please select a file to upload.'
    return false
  }
  if (form.kind === 'page' && !form.contentHtml.trim()) {
    formError.value = 'Page content is required for page resources.'
    return false
  }
  return true
}

const submitForm = async () => {
  formError.value = ''
  if (!validateForm()) return

  saving.value = true
  const labelsList = parseLabels(form.labelInput)

  try {
    if (!isEditing.value) {
      // -------------------------------------------------------------
      // Create Workflow
      // -------------------------------------------------------------
      if (form.kind === 'page') {
        const payload: CreateAdminResourcePayload = {
          resource_name: form.name.trim(),
          resource_description: form.description.trim(),
          resource_kind: 'page',
          visibility_scope: form.visibilityScope,
          role_ids: form.visibilityScope === 'role_based' ? form.roleIds : [],
          resource_type_id: form.typeId,
          label_names: labelsList,
          content_html: form.contentHtml
        }
        await createAdminResource(payload)
      } else {
        // Multipart upload for file / attachment
        const formData = new FormData()
        if (selectedFile.value) {
          formData.append('file', selectedFile.value)
        }
        formData.append('name', form.name.trim())
        formData.append('description', form.description.trim())
        formData.append('kind', form.kind)
        formData.append('visibility_scope', form.visibilityScope)

        if (form.typeId) {
          formData.append('resource_type_id', String(form.typeId))
        }

        if (form.visibilityScope === 'role_based') {
          for (const roleId of form.roleIds) {
            formData.append('role_ids', String(roleId))
          }
        }

        for (const label of labelsList) {
          formData.append('label_names', label)
        }

        await uploadAdminResource(formData)
      }
    } else if (props.resource?.id) {
      // -------------------------------------------------------------
      // Edit Workflow
      // -------------------------------------------------------------
      const updatePayload: UpdateAdminResourcePayload = {
        resource_name: form.name.trim(),
        resource_description: form.description.trim(),
        visibility_scope: form.visibilityScope,
        role_ids: form.visibilityScope === 'role_based' ? form.roleIds : [],
        resource_type_id: form.typeId,
        label_names: labelsList,
        content_html: form.kind === 'page' ? form.contentHtml : null
      }

      await updateAdminResource(props.resource.id, updatePayload)

      // If a new physical file was chosen in edit mode for a file resource, replace it
      if (selectedFile.value && form.kind !== 'page') {
        await replaceAdminResourceFile(props.resource.id, selectedFile.value)
      }
    }

    open.value = false
    emit('saved')
  } catch (err: any) {
    console.error('Failed to save resource:', err)
    formError.value = err?.message || 'Failed to save resource. Please check your inputs.'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.admin-resource-form {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.admin-resource-form__grid {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-field--full {
  width: 100%;
}

.form-label {
  display: block;
  margin-bottom: 0.35rem;
  font-size: 0.825rem;
  font-weight: 600;
  color: var(--charcoal);
}

.form-input {
  width: 100%;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
  font: inherit;
  font-size: 0.92rem;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.form-input:focus {
  outline: none;
  border-color: var(--dark-green);
  box-shadow: 0 0 0 3px rgba(1, 113, 81, 0.15);
}

.filter-select {
  appearance: none;
  -webkit-appearance: none;
  background-image: linear-gradient(45deg, transparent 50%, var(--text-muted) 50%),
                    linear-gradient(135deg, var(--text-muted) 50%, transparent 50%);
  background-position: calc(100% - 18px) 50%, calc(100% - 13px) 50%;
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
  padding-right: 2rem;
  cursor: pointer;
}

.admin-resource-form__section-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.admin-resource-form__section {
  margin: 0.5rem 0 0.2rem;
  padding-bottom: 0.35rem;
  border-bottom: 1px solid var(--border-light);
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--dark-green);
}

.admin-resource-form__checkbox-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 0.55rem;
  border: none;
  padding: 0;
  margin: 0.25rem 0 0;
}

.admin-resource-form__checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--charcoal);
  cursor: pointer;
}

.admin-resource-form__checkbox-label input {
  accent-color: var(--dark-green);
  width: 16px;
  height: 16px;
}

.admin-resource-file-upload {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.admin-resource-file-upload__controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.admin-resource-file-input {
  display: none;
}

.admin-resource-file-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 0.75rem;
  background-color: var(--bg-light);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  font-size: 0.85rem;
  color: var(--charcoal);
  width: fit-content;
  max-width: 100%;
}

.admin-resource-file-badge--existing {
  background-color: rgba(1, 113, 81, 0.06);
  border-color: rgba(1, 113, 81, 0.2);
  color: var(--dark-green);
}

.admin-resource-file-name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-resource-file-size {
  color: var(--text-muted);
  font-size: 0.78rem;
}

.admin-resource-form__hint {
  margin: 0.25rem 0 0;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.admin-resource-form__error {
  margin: 0 0 0.5rem;
  padding: 0.65rem 0.85rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.875rem;
}

.admin-resource-form__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.65rem;
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-light);
}

.admin-resource-form__footer-spacer {
  flex: 1;
}

.admin-resource-form__spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  margin-right: 0.4rem;
  vertical-align: -2px;
  border: 2px solid rgba(255, 255, 255, 0.5);
  border-top-color: var(--white);
  border-radius: 50%;
  animation: admin-spin 0.8s linear infinite;
}

@keyframes admin-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
