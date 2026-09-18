<template>
  <div class="content-area admin-emails">
    <div class="admin-emails__header">
      <div>
        <h1 class="admin-emails__title">System Emails</h1>
        <p class="admin-emails__subtitle">
          Edit the wording of the emails the platform sends, preview them with sample data, and
          pause the ones you do not want going out.
        </p>
      </div>

      <label class="admin-emails__global">
        <input
          type="checkbox"
          class="sr-only"
          role="switch"
          :checked="emailsEnabled"
          :disabled="loading || togglingGlobal"
          aria-label="Send system emails"
          @change="toggleGlobal(($event.target as HTMLInputElement).checked)"
        />
        <span class="admin-emails__global-track" aria-hidden="true">
          <span class="admin-emails__global-knob"></span>
        </span>
        <span class="admin-emails__global-label">
          {{ emailsEnabled ? 'Emails on' : 'Emails paused' }}
        </span>
      </label>
    </div>

    <p v-if="!emailsEnabled && !loading" class="admin-emails__banner" role="status">
      <i class="fas fa-circle-pause" aria-hidden="true"></i>
      <span>
        All system emails are paused, except sign-in emails, which always send. Turn the switch
        back on to resume them.
      </span>
    </p>

    <p v-if="error" class="admin-emails__error" role="alert">
      <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
      <span>{{ error }}</span>
    </p>

    <p v-if="notice" class="admin-emails__notice" role="status">
      <i class="fas fa-circle-check" aria-hidden="true"></i>
      <span>{{ notice }}</span>
    </p>

    <div v-if="loading" class="admin-emails__state" role="status">
      <i class="fas fa-spinner fa-spin" aria-hidden="true"></i>
      <span>Loading system emails…</span>
    </div>

    <div v-else-if="!templates.length" class="admin-emails__state">
      <i class="fas fa-inbox" aria-hidden="true"></i>
      <span>No system emails are registered.</span>
    </div>

    <div v-else class="admin-emails__layout">
      <aside class="admin-emails__sidebar">
        <EmailTypeList
          :templates="templates"
          :selected-key="selectedKey"
          @select="onSelect"
        />
      </aside>

      <div class="admin-emails__main" v-if="selected">
        <EmailEditor
          :email-template="selected"
          :subject="draft.subject"
          :body="draft.body"
          :dirty="dirty"
          :busy="busy"
          :saving="saving"
          :testing="testing"
          :restoring="restoring"
          @update:subject="setSubject"
          @update:body="setBody"
          @toggle-enabled="onToggleEnabled"
          @save="save"
          @restore="restoreConfirmOpen = true"
          @test-send="testSend"
        />

        <EmailPreview :preview="preview" :loading="previewing" />
      </div>
    </div>

    <ConfirmDialog
      v-model="restoreConfirmOpen"
      title="Restore default wording?"
      :message="`This removes your edits to ${selected?.name ?? 'this email'} and uses the built-in design again. Its on/off setting is kept.`"
      confirm-label="Restore default"
      variant="warning"
      :busy="restoring"
      @confirm="onRestoreConfirmed"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import EmailEditor from '@/components/admin/emails/EmailEditor.vue'
import EmailPreview from '@/components/admin/emails/EmailPreview.vue'
import EmailTypeList from '@/components/admin/emails/EmailTypeList.vue'
import { useSystemEmails } from '@/composables/admin/useSystemEmails'

const {
  loading,
  error,
  notice,
  saving,
  previewing,
  testing,
  restoring,
  togglingGlobal,
  templates,
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
  testSend,
  save,
  restore,
  toggleEnabled,
  toggleGlobal
} = useSystemEmails()

const restoreConfirmOpen = ref(false)

const onSelect = (key: string) => {
  select(key)
}

const onToggleEnabled = (enabled: boolean) => {
  if (selected.value) void toggleEnabled(selected.value, enabled)
}

const onRestoreConfirmed = async () => {
  await restore()
  restoreConfirmOpen.value = false
}

onMounted(async () => {
  await load()
})
</script>

<style scoped>
.admin-emails {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.admin-emails__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1rem;
}

.admin-emails__title {
  margin: 0 0 0.25rem;
  font-size: 1.5rem;
  font-weight: 700;
  color: #111827;
}

.admin-emails__subtitle {
  margin: 0;
  max-width: 46rem;
  font-size: 0.875rem;
  color: #6b7280;
}

.admin-emails__global {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.admin-emails__global input:disabled + .admin-emails__global-track {
  opacity: 0.5;
  cursor: not-allowed;
}

.admin-emails__global-track {
  position: relative;
  display: inline-block;
  width: 2.75rem;
  height: 1.5rem;
  border-radius: 999px;
  background: #d1d5db;
  transition: background-color 0.15s ease;
}

.admin-emails__global input:checked + .admin-emails__global-track {
  background: #2563eb;
}

.admin-emails__global-knob {
  position: absolute;
  top: 0.1875rem;
  left: 0.1875rem;
  width: 1.125rem;
  height: 1.125rem;
  border-radius: 50%;
  background: #ffffff;
  transition: transform 0.15s ease;
}

.admin-emails__global input:checked + .admin-emails__global-track .admin-emails__global-knob {
  transform: translateX(1.25rem);
}

.admin-emails__global-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: #374151;
}

.admin-emails__banner,
.admin-emails__error,
.admin-emails__notice {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  padding: 0.625rem 0.875rem;
  border-radius: 0.5rem;
  font-size: 0.8125rem;
}

.admin-emails__banner {
  background: #fffbeb;
  color: #92400e;
}

.admin-emails__error {
  background: #fef2f2;
  color: #b91c1c;
}

.admin-emails__notice {
  background: #ecfdf5;
  color: #047857;
}

.admin-emails__state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  min-height: 16rem;
  border: 1px dashed #d1d5db;
  border-radius: 0.5rem;
  color: #6b7280;
  font-size: 0.875rem;
}

.admin-emails__layout {
  display: grid;
  grid-template-columns: minmax(15rem, 20rem) minmax(0, 1fr);
  gap: 1.5rem;
  align-items: start;
}

.admin-emails__sidebar {
  position: sticky;
  top: 1rem;
}

.admin-emails__main {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  min-width: 0;
}

@media (max-width: 1024px) {
  .admin-emails__layout {
    grid-template-columns: 1fr;
  }

  .admin-emails__sidebar {
    position: static;
  }
}
</style>
