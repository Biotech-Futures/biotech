<template>
  <form class="ticket-form" @submit.prevent="submit">
    <h2 class="ticket-form__title">How can we help?</h2>
    <p class="ticket-form__lede">
      Tell us more about your issue and we'll get back to you as soon as possible. You
      will be able to follow the conversation from this page.
    </p>

    <!-- Side by side once there is room for both, one above the other when
         there is not. The hint under them is about the urgency, and says so
         to a screen reader through aria-describedby now that it is no longer
         inside that label. -->
    <div class="ticket-form__pair">
      <label class="ticket-form__field">
        <span class="ticket-form__label">Issue category</span>
        <select v-model="category" required class="ticket-form__control ticket-form__select">
          <!-- Starts unselected on purpose. Defaulting to the first category
               filed every untouched submission under the first category, and
               afterwards nothing could tell those apart from a real choice.
               That is the one thing that would quietly ruin the category
               breakdown the client asked for. The list is the client's own. -->
          <option value="" disabled>Select a category</option>
          <option v-for="option in TICKET_CATEGORIES" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>

      <label class="ticket-form__field">
        <span class="ticket-form__label">How urgent is this?</span>
        <select
          v-model="priority"
          class="ticket-form__control ticket-form__select"
          :aria-describedby="urgencyHintId"
        >
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
      </label>
    </div>
    <!-- The full sentences live here, not in the option labels. A closed
         <select> cannot wrap, so anything long enough to explain itself is
         truncated on a phone, and the default option is the one line a
         student who never opens the dropdown will read. This paragraph
         wraps, so it can carry the explanation the labels had to drop. -->
    <p :id="urgencyHintId" class="ticket-form__hint">
      Pick the one that is true for you: whether you are stuck right now,
      able to carry on for the time being, or just letting us know. Support
      can change this if they need to.
    </p>

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
        rows="3"
        :maxlength="MAX_BODY_LENGTH"
        placeholder="Describe your issue in detail..."
        class="ticket-form__control ticket-form__control--area"
      ></textarea>
      <span class="ticket-form__counter" :class="{ 'ticket-form__counter--full': body.length >= MAX_BODY_LENGTH }">
        {{ body.length }} / {{ MAX_BODY_LENGTH }}
      </span>
    </label>

    <TicketAttachmentPicker v-model="files" class="ticket-form__attach" />

    <p v-if="error" class="ticket-form__error" role="alert">{{ error }}</p>

    <button type="submit" class="ticket-form__submit" :disabled="isSubmitting || !canSubmit">
      {{ isSubmitting ? 'Sending…' : 'Submit ticket' }}
    </button>
  </form>
</template>

<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import TicketAttachmentPicker from '@/components/support/TicketAttachmentPicker.vue'
import '@/components/support/ticketControls.css'
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
const urgencyHintId = useId()

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
/* The first redesign round (October 2026): taller, rounder controls with an
   edge you can see, a brand green top on the card, quieter greys. Colours are
   this component's own so main.css stays every other team's.

   Measured (WCAG AA: 4.5:1 for text, 3:1 for a control's edge):
     light  muted #5a6268 on #ffffff 6.21:1   placeholder #6c757d 4.69:1
            control edge #84938f on #ffffff 3.21:1
     dark   muted #a3b3ae on the #1d2826 card 6.95:1
            placeholder #93a39e on the #161f1d field 6.39:1
            control edge #70827d on #161f1d 4.15:1, on the card 3.74:1
   The old edge, --border-light, was 1.32:1 in light and 1.16:1 in dark. */
.ticket-form {
  --form-muted: #5a6268;
  --form-placeholder: #6c757d;
  --form-control-edge: #84938f;
  --form-focus-edge: var(--dark-green);
  --form-card-edge: #e3e7e5;
  --form-card-shadow: 0 1px 2px rgba(23, 66, 67, 0.06), 0 4px 12px rgba(23, 66, 67, 0.05);

  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.5rem 1.75rem 1.625rem;
  background: var(--surface-elevated);
  border: 1px solid var(--form-card-edge);
  border-top: 3px solid var(--dark-green);
  border-radius: 12px;
  box-shadow: var(--form-card-shadow);
}

/* The dark focus edge is the designer's dark link colour: brand green on the
   dark field was 2.79:1, darker than the edge it replaces. */
:root[data-theme='dark'] .ticket-form {
  --form-muted: #a3b3ae;
  --form-placeholder: #93a39e;
  --form-control-edge: #70827d;
  --form-focus-edge: #6dbfb1;
  --form-card-edge: #2b3936;
  --form-card-shadow: 0 1px 3px var(--shadow);
}

.ticket-form__title {
  margin: 0;
  font-size: 1.3rem;
  line-height: 1.25;
}

.ticket-form__lede {
  margin: -0.5rem 0 0 0;
  color: var(--form-muted);
  font-size: 0.9rem;
  line-height: 1.5;
}

.ticket-form__pair {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15.5rem, 1fr));
  gap: 1rem 1.25rem;
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
  min-height: 2.75rem;
  padding: 0.6rem 0.875rem;
  border: 1px solid var(--form-control-edge);
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
  font-family: inherit;
  font-size: 0.95rem;
}

.ticket-form__control::placeholder {
  color: var(--form-placeholder);
  opacity: 1;
}

.ticket-form__control:focus {
  outline: none;
  border-color: var(--form-focus-edge);
  box-shadow: 0 0 0 3px var(--light-green);
}

/* The browser's arrow is switched off for the thin chevron from
   ticketControls.css, with room kept clear of it on the right. Until a
   category is picked the required select is :invalid, and it reads as a
   placeholder; the open list keeps the normal text colour. */
.ticket-form__select {
  appearance: none;
  padding-right: 2.5rem;
  background-image: var(--ticket-select-chevron);
  background-repeat: no-repeat;
  background-position: right 1.05rem center;
}

.ticket-form__select:invalid {
  color: var(--form-placeholder);
}

.ticket-form__select option {
  color: var(--charcoal);
}

.ticket-form__control--area {
  resize: vertical;
  min-height: 5.75rem;
  line-height: 1.45;
}

.ticket-form__hint {
  margin: -0.5rem 0 0 0;
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--form-muted);
}

.ticket-form__counter {
  align-self: flex-end;
  font-size: 0.8rem;
  color: var(--form-muted);
}

.ticket-form__counter--full {
  color: var(--danger);
  font-weight: 600;
}

/* The attachments read as part of the message above them: the button sits
   about 7px under the counter. The picker's own negative margin (room for its
   drop highlight) is folded in; the extra class outranks the picker's rule. */
.ticket-form > .ticket-form__attach {
  margin-top: calc(-0.6rem - 1px - 0.55rem);
}

/* Here the hint takes a line of its own under the button, however wide the
   form is; in the reply box it stays beside the button. */
.ticket-form__attach :deep(.attach__hint) {
  flex-basis: 100%;
}

.ticket-form__error {
  margin: 0;
  color: var(--danger);
  font-size: 0.88rem;
}

/* White in both themes. var(--white) is the dark page colour in dark, which
   put dark text on the green at 2.79:1. The hover ground is fixed for the same
   reason: var(--charcoal) turns pale in dark, under white text. */
.ticket-form__submit {
  align-self: flex-start;
  min-height: 2.75rem;
  padding: 0.65rem 1.5rem;
  border: none;
  border-radius: 8px;
  background: var(--dark-green);
  color: #ffffff;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
}

.ticket-form__submit:hover:not(:disabled) {
  background: #174243;
}

.ticket-form__submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
