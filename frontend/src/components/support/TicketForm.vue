<template>
  <form class="ticket-form" @submit.prevent="submit">
    <h2 class="ticket-form__title">How can we help?</h2>
    <p class="ticket-form__lede">
      Tell us more about your issue and we'll get back to you as soon as possible. You
      will be able to follow the conversation from this page.
    </p>

    <label class="ticket-form__field">
      <span class="ticket-form__label">Issue category</span>
      <select v-model="category" required class="ticket-form__control">
        <!-- Starts unselected on purpose. Defaulting to the first category
             filed every untouched submission under the first category, and
             afterwards nothing could tell those apart from a real choice —
             which is the one thing that would quietly ruin the category
             breakdown the client asked for. The list is the client's own. -->
        <option value="" disabled>Select a category</option>
        <option v-for="option in TICKET_CATEGORIES" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </label>

    <label class="ticket-form__field">
      <span class="ticket-form__label">How urgent is this?</span>
      <select v-model="priority" class="ticket-form__control">
        <option v-for="option in TICKET_PRIORITIES" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
      <!-- Preselected to Normal rather than left blank, unlike the category
           above. The two are not the same question: a blank category is a
           fact we do not have, so asking for it is right, while a blank
           urgency has an obvious and honest default. Making it a required
           choice would also push people towards High, because that is what an
           unanswered question about your own problem feels like. -->
      <!-- The full sentences live here, not in the option labels. A closed
           <select> cannot wrap, so anything long enough to explain itself is
           truncated on a phone — and the default option is the one line a
           student who never opens the dropdown will read. This paragraph
           wraps, so it can carry the explanation the labels had to drop. -->
      <span class="ticket-form__hint">
        Pick the one that is true for you: whether you are stuck right now,
        able to carry on for the time being, or just letting us know. Support
        can change this if they need to.
      </span>
    </label>

    <label class="ticket-form__field">
      <span class="ticket-form__label">Subject</span>
      <input
        v-model="subject"
        type="text"
        required
        maxlength="255"
        placeholder="Enter a short subject"
        class="ticket-form__control"
      />
    </label>

    <label class="ticket-form__field">
      <span class="ticket-form__label">Message</span>
      <textarea
        v-model="body"
        required
        rows="6"
        :maxlength="MAX_BODY_LENGTH"
        placeholder="Describe your issue in detail..."
        class="ticket-form__control ticket-form__control--area"
      ></textarea>
      <span class="ticket-form__counter" :class="{ 'ticket-form__counter--full': body.length >= MAX_BODY_LENGTH }">
        {{ body.length }} / {{ MAX_BODY_LENGTH }}
      </span>
    </label>

    <TicketAttachmentPicker v-model="files" />

    <p v-if="error" class="ticket-form__error" role="alert">{{ error }}</p>

    <button type="submit" class="ticket-form__submit" :disabled="isSubmitting || !canSubmit">
      {{ isSubmitting ? 'Sending…' : 'Submit ticket' }}
    </button>
  </form>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import TicketAttachmentPicker from '@/components/support/TicketAttachmentPicker.vue'
import { apiErrorFromUnknown } from '@/utils/apiError'
import {
  MAX_BODY_LENGTH,
  TICKET_CATEGORIES,
  TICKET_PRIORITIES,
  submitTicket,
  type TicketCategory,
  type TicketDetail,
  type TicketPriority
} from '@/utils/supportAPI'

const emit = defineEmits<{ submitted: [TicketDetail] }>()

const category = ref<TicketCategory | ''>('')
const priority = ref<TicketPriority>('normal')
const subject = ref('')
const body = ref('')
const files = ref<File[]>([])
const isSubmitting = ref(false)
const error = ref('')

const canSubmit = computed(
  () =>
    category.value !== '' &&
    subject.value.trim().length > 0 &&
    body.value.trim().length > 0
)

async function submit() {
  if (isSubmitting.value || !canSubmit.value) return
  isSubmitting.value = true
  error.value = ''

  try {
    const ticket = await submitTicket({
      category: category.value as TicketCategory,
      priority: priority.value,
      subject: subject.value.trim(),
      body: body.value.trim(),
      files: files.value
    })
    category.value = ''
    priority.value = 'normal'
    subject.value = ''
    body.value = ''
    files.value = []
    emit('submitted', ticket)
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'Could not submit your enquiry.').message
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.ticket-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.5rem;
  background: var(--surface-elevated);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  box-shadow: 0 1px 3px var(--shadow);
}

.ticket-form__title {
  margin: 0;
  font-size: 1.3rem;
}

.ticket-form__lede {
  margin: -0.5rem 0 0 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.ticket-form__field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  position: relative;
}

.ticket-form__label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--charcoal);
}

.ticket-form__control {
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--white);
  color: var(--charcoal);
  font-family: inherit;
  font-size: 0.95rem;
}

.ticket-form__control:focus {
  outline: none;
  border-color: var(--dark-green);
  box-shadow: 0 0 0 3px var(--light-green);
}

.ticket-form__control--area {
  resize: vertical;
  min-height: 8rem;
}

.ticket-form__hint {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.ticket-form__counter {
  align-self: flex-end;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.ticket-form__counter--full {
  color: var(--danger);
  font-weight: 600;
}

.ticket-form__error {
  margin: 0;
  color: var(--danger);
  font-size: 0.88rem;
}

.ticket-form__submit {
  align-self: flex-start;
  padding: 0.65rem 1.4rem;
  border: none;
  border-radius: 6px;
  background: var(--dark-green);
  color: var(--white);
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
}

.ticket-form__submit:hover:not(:disabled) {
  background: var(--charcoal);
}

.ticket-form__submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
