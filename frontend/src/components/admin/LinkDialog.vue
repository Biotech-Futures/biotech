<template>
  <ConfirmDialog
    :model-value="modelValue"
    :title="title"
    :message="message"
    :confirm-label="adding ? (kind === 'button' ? 'Add button' : 'Add link') : 'Save link'"
    @update:model-value="emit('update:modelValue', $event)"
    @confirm="submit"
    @cancel="emit('cancel')"
  >
    <div class="link-dialog">
      <div v-if="placeholders.length" class="link-dialog__options">
        <button
          v-for="token in placeholders"
          :key="token"
          type="button"
          class="link-dialog__option"
          :class="{ 'link-dialog__option--chosen': link.trim() === token }"
          @click="choose(token)"
        >
          <code>{{ token }}</code>
        </button>
      </div>
      <label class="link-dialog__label" :for="inputId">Link</label>
      <input
        :id="inputId"
        ref="input"
        v-model="link"
        type="text"
        class="link-dialog__input"
        :class="{ 'link-dialog__input--invalid': error }"
        placeholder="https://biotechfutures.org"
        autocomplete="off"
        spellcheck="false"
        @input="error = ''"
        @keydown.enter.prevent="submit"
      />
      <p v-if="error" class="link-dialog__error" role="alert">{{ error }}</p>
      <button
        v-if="kind === 'link' && !adding"
        type="button"
        class="link-dialog__remove"
        @click="remove"
      >
        <i class="fas fa-link-slash" aria-hidden="true"></i>
        Remove link
      </button>
    </div>
  </ConfirmDialog>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import { linkHref } from '@/utils/linkHref'

/**
 * Asks where a link or an email button should go, in place of the browser's
 * prompt: one of the email's link placeholders, or a web or email address.
 */
const props = withDefaults(
  defineProps<{
    modelValue: boolean
    kind?: 'link' | 'button'
    /** Adding a new link or button, rather than changing an existing one. */
    adding?: boolean
    /** The current link, when changing one. */
    initialLink?: string
    /** Email placeholders that hold a link, e.g. `{{ registration_url }}`. */
    placeholders?: string[]
    /** Accept site paths like `/events` (not for emails, where they don't work). */
    allowRelative?: boolean
  }>(),
  { kind: 'link', adding: true, initialLink: '', placeholders: () => [], allowRelative: false }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'confirm', href: string): void
  (e: 'remove'): void
  (e: 'cancel'): void
}>()

const inputId = `link-dialog-${Math.random().toString(36).slice(2, 8)}`
const input = ref<HTMLInputElement | null>(null)
const link = ref('')
const error = ref('')

const title = computed(() => {
  if (props.kind === 'button') return props.adding ? 'Add a button' : 'Change the button link'
  return props.adding ? 'Add a link' : 'Change the link'
})

const message = computed(() => {
  const question = `Where should the ${props.kind} take people?`
  return props.placeholders.length
    ? `${question} Pick a link from this email, or enter a web address.`
    : `${question} Enter a web address.`
})

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    link.value = props.initialLink
    error.value = ''
    await nextTick()
    // After ConfirmDialog has focused its own button.
    window.setTimeout(() => input.value?.select(), 0)
  }
)

const choose = (token: string) => {
  link.value = token
  error.value = ''
  input.value?.focus()
}

const submit = () => {
  const href = linkHref(link.value, { allowRelative: props.allowRelative })
  if (!href) {
    error.value = link.value.trim()
      ? 'That isn’t a link. Enter a web address like https://biotechfutures.org' +
        (props.placeholders.length ? ', or pick one of the links above.' : '.')
      : `Enter where the ${props.kind} should go.`
    input.value?.focus()
    return
  }
  emit('confirm', href)
  emit('update:modelValue', false)
}

const remove = () => {
  emit('remove')
  emit('update:modelValue', false)
}
</script>

<style scoped>
.link-dialog {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 1rem;
}

.link-dialog__options {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin-bottom: 0.25rem;
}

.link-dialog__option {
  padding: 0.25rem 0.5rem;
  border: 1px solid rgba(1, 113, 81, 0.35);
  border-radius: 0.375rem;
  background: var(--accent-green-soft);
  color: var(--dark-green);
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.link-dialog__option:hover,
.link-dialog__option--chosen {
  background: rgba(1, 113, 81, 0.18);
  border-color: var(--dark-green);
}

.link-dialog__option code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.75rem;
}

.link-dialog__label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #6b7280;
}

.link-dialog__input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  color: #111827;
  background: #ffffff;
}

.link-dialog__input:focus {
  outline: none;
  border-color: var(--dark-green);
  box-shadow: 0 0 0 3px rgba(1, 113, 81, 0.15);
}

.link-dialog__input--invalid,
.link-dialog__input--invalid:focus {
  border-color: #dc2626;
  box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.15);
}

.link-dialog__error {
  margin: 0;
  font-size: 0.8125rem;
  color: #b91c1c;
}

.link-dialog__remove {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  margin-top: 0.25rem;
  padding: 0.25rem 0;
  border: none;
  background: none;
  font-size: 0.8125rem;
  color: #b91c1c;
  cursor: pointer;
}

.link-dialog__remove:hover {
  text-decoration: underline;
}
</style>
