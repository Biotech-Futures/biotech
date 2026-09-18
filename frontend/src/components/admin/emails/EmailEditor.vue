<template>
  <section class="email-editor" aria-label="Email editor">
    <header class="email-editor__header">
      <div class="email-editor__title-block">
        <h2 class="email-editor__title">
          {{ emailTemplate.name }}
          <i
            v-if="emailTemplate.locked"
            class="fas fa-lock email-editor__lock"
            title="This email is required and cannot be switched off"
            aria-hidden="true"
          ></i>
        </h2>
        <p class="email-editor__description">{{ emailTemplate.description }}</p>
      </div>

      <label class="email-editor__switch">
        <input
          type="checkbox"
          class="sr-only"
          role="switch"
          :checked="emailTemplate.enabled"
          :disabled="emailTemplate.locked || busy"
          :aria-label="`Send ${emailTemplate.name}`"
          @change="onToggleEnabled(($event.target as HTMLInputElement).checked)"
        />
        <span class="email-editor__switch-track" aria-hidden="true">
          <span class="email-editor__switch-knob"></span>
        </span>
        <span class="email-editor__switch-label">
          {{ emailTemplate.enabled ? 'Sending' : 'Paused' }}
        </span>
      </label>
    </header>

    <p v-if="emailTemplate.locked" class="email-editor__note">
      <i class="fas fa-shield-halved" aria-hidden="true"></i>
      Account sign-in would break if this email were paused, so it always sends.
    </p>

    <p
      v-if="!emailTemplate.usingSavedContent"
      class="email-editor__note email-editor__note--muted"
    >
      <i class="fas fa-wand-magic-sparkles" aria-hidden="true"></i>
      These are the current built-in contents. Save to switch to your custom wording.
    </p>

    <div class="email-editor__field">
      <label class="email-editor__label" for="email-subject">Subject</label>
      <input
        id="email-subject"
        ref="subjectInput"
        type="text"
        class="email-editor__subject"
        :value="subject"
        :placeholder="emailTemplate.defaultSubject"
        :disabled="busy"
        maxlength="255"
        @focus="activeField = 'subject'"
        @input="emit('update:subject', ($event.target as HTMLInputElement).value)"
      />
    </div>

    <div class="email-editor__field">
      <label class="email-editor__label">Body</label>
      <MergeTagPalette :tags="emailTemplate.mergeTags" @insert="onInsertTag" />
      <div class="email-editor__body" @focusin="activeField = 'body'">
        <RichEditor
          ref="bodyEditor"
          :model-value="body"
          email-mode
          compact
          :read-only="busy"
          @update:model-value="emit('update:body', $event)"
          @focus="activeField = 'body'"
        />
      </div>
    </div>

    <footer class="email-editor__actions">
      <div class="email-editor__actions-primary">
        <button
          type="button"
          class="btn btn-primary"
          :disabled="!dirty || busy"
          @click="emit('save')"
        >
          <i v-if="saving" class="fas fa-spinner fa-spin" aria-hidden="true"></i>
          <i v-else class="fas fa-floppy-disk" aria-hidden="true"></i>
          <span>{{ saving ? 'Saving…' : 'Save changes' }}</span>
        </button>
        <button
          type="button"
          class="btn btn-outline"
          :disabled="!emailTemplate.usingSavedContent || busy"
          @click="emit('restore')"
        >
          <i v-if="restoring" class="fas fa-spinner fa-spin" aria-hidden="true"></i>
          <i v-else class="fas fa-rotate-left" aria-hidden="true"></i>
          <span>{{ restoring ? 'Restoring…' : 'Restore default' }}</span>
        </button>
      </div>

      <div class="email-editor__actions-secondary">
        <button type="button" class="btn btn-outline" :disabled="busy" @click="emit('test-send')">
          <i v-if="testing" class="fas fa-spinner fa-spin" aria-hidden="true"></i>
          <i v-else class="fas fa-paper-plane" aria-hidden="true"></i>
          <span>{{ testing ? 'Sending…' : 'Send test' }}</span>
        </button>
      </div>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { defineAsyncComponent, nextTick, ref } from 'vue'
import MergeTagPalette from '@/components/admin/emails/MergeTagPalette.vue'
import { mergeTagToken, type SystemEmailMergeTag, type SystemEmailTemplate } from '@/utils/systemEmail'

const RichEditor = defineAsyncComponent(() => import('@/components/admin/RichEditor.vue'))

const props = defineProps<{
  emailTemplate: SystemEmailTemplate
  subject: string
  body: string
  dirty: boolean
  busy: boolean
  saving: boolean
  testing: boolean
  restoring: boolean
}>()

const emit = defineEmits<{
  (e: 'update:subject', value: string): void
  (e: 'update:body', value: string): void
  (e: 'toggle-enabled', enabled: boolean): void
  (e: 'save'): void
  (e: 'restore'): void
  (e: 'test-send'): void
}>()

type EditableField = 'subject' | 'body'

const activeField = ref<EditableField>('body')
const subjectInput = ref<HTMLInputElement | null>(null)
const bodyEditor = ref<{ insertText: (text: string) => void } | null>(null)

const onToggleEnabled = (enabled: boolean) => {
  if (props.emailTemplate.locked && !enabled) return
  emit('toggle-enabled', enabled)
}

const onInsertTag = (tag: SystemEmailMergeTag) => {
  const token = mergeTagToken(tag.name)
  if (activeField.value === 'subject') {
    insertIntoSubject(token)
  } else {
    bodyEditor.value?.insertText(token)
  }
}

/** Insert at the caret (or append) so tags land where the admin is typing. */
const insertIntoSubject = (token: string) => {
  const input = subjectInput.value
  if (!input) {
    emit('update:subject', `${props.subject}${token}`)
    return
  }
  const start = input.selectionStart ?? input.value.length
  const end = input.selectionEnd ?? start
  const next = `${input.value.slice(0, start)}${token}${input.value.slice(end)}`
  emit('update:subject', next)
  void nextTick(() => {
    input.focus()
    const caret = start + token.length
    input.setSelectionRange(caret, caret)
  })
}
</script>

<style scoped>
.email-editor {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 0;
}

.email-editor__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.email-editor__title {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0 0 0.25rem;
  font-size: 1.0625rem;
  font-weight: 600;
  color: #111827;
}

.email-editor__lock {
  font-size: 0.75rem;
  color: #6b7280;
}

.email-editor__description {
  margin: 0;
  font-size: 0.8125rem;
  color: #6b7280;
}

.email-editor__switch {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
  cursor: pointer;
}

.email-editor__switch input:disabled + .email-editor__switch-track {
  opacity: 0.5;
  cursor: not-allowed;
}

.email-editor__switch-track {
  position: relative;
  display: inline-block;
  width: 2.5rem;
  height: 1.375rem;
  border-radius: 999px;
  background: #d1d5db;
  transition: background-color 0.15s ease;
}

.email-editor__switch input:checked + .email-editor__switch-track {
  background: #2563eb;
}

.email-editor__switch-knob {
  position: absolute;
  top: 0.1875rem;
  left: 0.1875rem;
  width: 1rem;
  height: 1rem;
  border-radius: 50%;
  background: #ffffff;
  transition: transform 0.15s ease;
}

.email-editor__switch input:checked + .email-editor__switch-track .email-editor__switch-knob {
  transform: translateX(1.125rem);
}

.email-editor__switch-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #4b5563;
  min-width: 3.5rem;
}

.email-editor__note {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  padding: 0.5rem 0.75rem;
  border-radius: 0.375rem;
  background: #eff6ff;
  font-size: 0.75rem;
  color: #1e40af;
}

.email-editor__note--muted {
  background: #f9fafb;
  color: #6b7280;
}

.email-editor__field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.email-editor__label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #6b7280;
}

.email-editor__subject {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  color: #111827;
}

.email-editor__subject:focus {
  outline: none;
  border-color: #2563eb;
}

.email-editor__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding-top: 0.5rem;
  border-top: 1px solid #e5e7eb;
}

.email-editor__actions-primary,
.email-editor__actions-secondary {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
</style>
