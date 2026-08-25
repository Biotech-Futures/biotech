<template>
  <div class="attach">
    <label class="attach__button">
      <input
        ref="input"
        type="file"
        multiple
        :accept="ACCEPT"
        class="attach__input"
        @change="onPick"
      />
      <i class="fas fa-paperclip"></i>
      <span>Attach files</span>
    </label>
    <span class="attach__hint">{{ ATTACHMENT_HINT }}</span>

    <ul v-if="modelValue.length" class="attach__list">
      <li v-for="(file, index) in modelValue" :key="`${file.name}-${index}`" class="attach__item">
        <span class="attach__name">{{ file.name }}</span>
        <span class="attach__size">{{ readableSize(file.size) }}</span>
        <button type="button" class="attach__remove" :aria-label="`Remove ${file.name}`" @click="remove(index)">
          &times;
        </button>
      </li>
    </ul>

    <p v-if="error" class="attach__error">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ATTACHMENT_HINT, MAX_ATTACHMENTS, MAX_ATTACHMENT_BYTES } from '@/utils/supportAPI'

const ACCEPT = '.pdf,.png,.jpg,.jpeg,.docx'

const props = defineProps<{ modelValue: File[] }>()
const emit = defineEmits<{ 'update:modelValue': [File[]] }>()

const input = ref<HTMLInputElement | null>(null)
const error = ref('')

function readableSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// Checked here as well as on the server. The server is the one that decides,
// but telling someone their 40 MB file is too big before they wait for it to
// upload is the difference between a hint and a rejection.
function onPick(event: Event) {
  const picked = Array.from((event.target as HTMLInputElement).files || [])
  if (!picked.length) return
  error.value = ''

  const tooBig = picked.find((file) => file.size > MAX_ATTACHMENT_BYTES)
  if (tooBig) {
    error.value = `${tooBig.name} is larger than 10 MB.`
  }

  const accepted = picked.filter((file) => file.size <= MAX_ATTACHMENT_BYTES)
  const combined = [...props.modelValue, ...accepted]
  if (combined.length > MAX_ATTACHMENTS) {
    error.value = `You can attach up to ${MAX_ATTACHMENTS} files to one message.`
  }

  emit('update:modelValue', combined.slice(0, MAX_ATTACHMENTS))
  if (input.value) input.value.value = ''
}

function remove(index: number) {
  const next = [...props.modelValue]
  next.splice(index, 1)
  emit('update:modelValue', next)
  error.value = ''
}
</script>

<style scoped>
.attach {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
}

.attach__button {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.85rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--surface-elevated);
  color: var(--charcoal);
  font-size: 0.88rem;
  cursor: pointer;
}

.attach__button:hover {
  border-color: var(--dark-green);
  color: var(--dark-green);
}

.attach__input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.attach__hint {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.attach__list {
  flex-basis: 100%;
  list-style: none;
  margin: 0.25rem 0 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.attach__item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.35rem 0.6rem;
  background: var(--bg-light);
  border-radius: 6px;
  font-size: 0.85rem;
}

.attach__name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attach__size {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.attach__remove {
  border: none;
  background: none;
  color: var(--text-muted);
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
}

.attach__remove:hover {
  color: var(--danger);
}

.attach__error {
  flex-basis: 100%;
  margin: 0;
  color: var(--danger);
  font-size: 0.84rem;
}
</style>
