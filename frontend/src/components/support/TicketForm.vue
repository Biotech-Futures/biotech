<template>
  <form class="ticket-form" @submit.prevent="submit">
    <!-- The second redesign round moves the client's p48 question, "How can
         we help?", up into the page header and names the form for what it
         does. -->
    <h2 class="ticket-form__title">Raise an enquiry</h2>
    <p class="ticket-form__lede">
      Tell us more about your issue and we'll get back to you as soon as possible.
    </p>

    <!-- Side by side once there is room for both, one above the other when
         there is not. -->
    <div class="ticket-form__pair">
      <!-- The platform's own dropdown (AppSelect) since the 2026-10-22 client
           meeting (C-29: "Team 3 has implemented a styling for the dropdowns
           ... if you can adopt that as well"). A label beside it rather than
           around it, as the platform's forms pair theirs. -->
      <div class="ticket-form__field">
        <label class="ticket-form__label" for="ticket-category">Issue category</label>
        <!-- Starts unselected on purpose. Defaulting to the first category
             filed every untouched submission under the first category, and
             afterwards nothing could tell those apart from a real choice.
             That is the one thing that would quietly ruin the category
             breakdown the client asked for. The list is the client's own. -->
        <AppSelect
          id="ticket-category"
          :model-value="category"
          required
          class="ticket-form__control ticket-form__select"
          placeholder="Select a category"
          :options="CATEGORY_OPTIONS"
          @update:model-value="(value) => (category = value as TicketCategory)"
        />
      </div>

      <div class="ticket-form__field">
        <label class="ticket-form__label" for="ticket-urgency">Urgency</label>
        <!-- Starts unselected, like the category, because the client asked
             for it at the 8 October meeting (C-22): "Can you make that not
             default to anything? I would want them to select that." A
             preselected answer is one a student never reads, and it used to
             be "I can keep working", so every untouched enquiry said so.
             The server still falls back to Normal for a caller that sends
             nothing; this form always sends a choice. -->
        <AppSelect
          id="ticket-urgency"
          :model-value="priority"
          required
          class="ticket-form__control ticket-form__select"
          placeholder="Select how urgent this is"
          :options="URGENCY_OPTIONS"
          @update:model-value="(value) => (priority = value as TicketPriority)"
        />
      </div>
    </div>

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
import { computed, ref } from 'vue'
import AppSelect, { type AppSelectOption } from '@/components/AppSelect.vue'
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

const CATEGORY_OPTIONS: AppSelectOption[] = TICKET_CATEGORIES.map(({ value, label }) => ({ value, label }))
const URGENCY_OPTIONS: AppSelectOption[] = TICKET_PRIORITIES.map(({ value, label }) => ({ value, label }))

const category = ref<TicketCategory | ''>('')
const priority = ref<TicketPriority | ''>('')
const subject = ref('')
const body = ref('')
const files = ref<File[]>([])
const isSubmitting = ref(false)
const error = ref('')

const canSubmit = computed(
  () =>
    category.value !== '' &&
    priority.value !== '' &&
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
      priority: priority.value as TicketPriority,
      subject: subject.value.trim(),
      body: body.value.trim(),
      files: files.value
    })
    category.value = ''
    priority.value = ''
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
   edge you can see, quieter greys. Colours are this component's own so
   main.css stays every other team's. The round also put a 3px brand green
   strip along the card's top; the client asked for it to go at the
   2026-10-22 meeting (C-24: "very commonly associated with AI designs"), so
   the card has the same 1px edge all round.

   Measured (WCAG AA: 4.5:1 for text, 3:1 for a control's edge):
     light  muted #5a6268 on #ffffff 6.21:1   placeholder #6c757d 4.69:1
            control edge #84938f on #ffffff 3.21:1
     dark   muted #a3b3ae on the #1d2826 card 6.95:1
            placeholder #93a39e on the #161f1d field 6.39:1
            control edge #70827d on #161f1d 4.15:1, on the card 3.74:1
   The old edge, --border-light, was 1.32:1 in light and 1.16:1 in dark.
   The glow round a focused field was the global --light-green, the peach the
   client asked us to drop (C-20); it takes the designer's pale green until he
   draws one, and dark keeps the token, which is already a green there. */
.ticket-form {
  --form-muted: #5a6268;
  --form-placeholder: #6c757d;
  --form-control-edge: #84938f;
  --form-focus-edge: var(--dark-green);
  --form-focus-glow: #d3ece0;
  --form-card-edge: #e3e7e5;
  --form-card-shadow: 0 1px 2px rgba(23, 66, 67, 0.06), 0 4px 12px rgba(23, 66, 67, 0.05);

  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.5625rem 1.75rem 1.625rem;
  background: var(--surface-elevated);
  border: 1px solid var(--form-card-edge);
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
  --form-focus-glow: var(--light-green);
  --form-card-edge: #2b3936;
  --form-card-shadow: 0 1px 3px var(--shadow);
}

.ticket-form__title {
  margin: 0;
  font-size: 1.3rem;
  line-height: 1.25;
}

.ticket-form__lede {
  margin: -0.55rem 0 0.125rem 0;
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
  line-height: 1.5;
  color: var(--teal);
}

.ticket-form__control {
  min-height: 2.75rem;
  padding: 0.6rem 0.875rem;
  border: 1px solid var(--form-control-edge);
  border-radius: 8px;
  background: var(--white);
  color: var(--teal);
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
  box-shadow: 0 0 0 3px var(--form-focus-glow);
}

/* AppSelect draws its own chevron and placeholder; the box keeps the form's
   edge, corners and height through .ticket-form__control. At AppSelect's own
   line height the 2.75rem floor decides the height, as it does for the
   subject box below (44px both); its "large" size took the form's taller
   line and came out 1.5px over. */
.ticket-form__select {
  display: block;
  width: 100%;
}

.ticket-form__control--area {
  resize: vertical;
  min-height: 5.75rem;
  line-height: 1.45;
}

.ticket-form__counter {
  align-self: flex-end;
  font-size: 0.8rem;
  line-height: 1.2;
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

.ticket-form__error {
  margin: 0;
  color: var(--danger);
  font-size: 0.88rem;
}

/* White in both themes. var(--white) is the dark page colour in dark, which
   put dark text on the green at 2.79:1. The hover ground is fixed for the same
   reason: var(--teal) turns pale in dark, under white text. */
.ticket-form__submit {
  align-self: flex-start;
  min-height: 2.75rem;
  margin-top: 0.125rem;
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

/* AppSelect rings its box in --dark-green when its field has keyboard focus,
   which the dark theme does not redefine: about 2.8:1 on the dark grounds,
   under the 3:1 a focus indicator needs. The student pages' dark ring (SupportCentrePage.vue), 7.04:1 on the card. */
:root[data-theme='dark'] .ticket-form__select:has(:focus-visible) {
  outline-color: #6dbfb1;
}
</style>
