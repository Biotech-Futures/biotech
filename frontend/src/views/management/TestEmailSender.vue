<template>
  <!-- Beside an email's preview: send it, exactly as the chosen group or
       supervisor would get it, to any address. Nothing is recorded as sent. -->
  <div class="test-email">
    <button
      type="button"
      class="btn btn-outline btn-sm"
      :disabled="sending || !recipient || !to.trim()"
      @click="send"
    >
      {{ sending ? 'Sending…' : 'Send Test Email' }}
    </button>
    <span class="test-email__word">of</span>
    <select
      v-model="recipient"
      class="test-email__select"
      aria-label="Send it as"
      :disabled="!recipients.length"
    >
      <option v-if="!recipients.length" value="">
        {{ loadError ? "Couldn't load the list" : 'Nobody yet' }}
      </option>
      <option v-for="option in recipients" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>
    <span class="test-email__word">to</span>
    <!-- Password managers leave this box alone. -->
    <input
      v-model="to"
      type="email"
      class="test-email__to"
      placeholder="Email address"
      aria-label="Send the test to"
      autocomplete="off"
      data-bwignore
      data-1p-ignore
      data-lpignore="true"
      @keydown.enter.prevent="send"
    />
    <span
      v-if="result"
      class="test-email__result"
      :class="result.ok ? 'test-email__result--ok' : 'test-email__result--error'"
      role="status"
    >
      {{ result.text }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  fetchTestEmailRecipients,
  sendTestEmail,
  type TestEmailKind,
  type TestEmailRecipient
} from '@/utils/managementAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const props = defineProps<{
  kind: TestEmailKind
  /** The page's unsaved details, sent as its preview sends them. */
  fields?: () => object
}>()

const recipients = ref<TestEmailRecipient[]>([])
// Shared with the page (v-model:recipient), so its preview shows the email
// as the one picked here gets it.
const recipient = defineModel<string>('recipient', { default: '' })
const loadError = ref(false)
const to = ref('')
const sending = ref(false)
const result = ref<{ ok: boolean; text: string } | null>(null)

onMounted(async () => {
  try {
    recipients.value = (await fetchTestEmailRecipients(props.kind)).recipients
    recipient.value = recipients.value[0]?.value ?? ''
  } catch {
    loadError.value = true
  }
})

const send = async () => {
  if (sending.value || !recipient.value || !to.value.trim()) return
  sending.value = true
  result.value = null
  try {
    const sent = await sendTestEmail(props.kind, recipient.value, to.value.trim(), props.fields?.() ?? {})
    // A test can take a few minutes too, and bounces like the real thing.
    const note = sent.sent_from
      ? ` It can take a few minutes to arrive. If it can't be delivered, it comes back to ${sent.sent_from}.`
      : ''
    result.value = { ok: true, text: `Test sent to ${sent.sent_to}.${note}` }
  } catch (err) {
    result.value = { ok: false, text: apiErrorFromUnknown(err).message }
  } finally {
    sending.value = false
  }
}
</script>

<style scoped>
.test-email {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  /* The rest of its row: it never drops below the button beside it. */
  flex: 1 1 0;
}

.test-email__word {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.test-email__select,
.test-email__to {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.3rem 0.5rem;
  font-size: 0.85rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--charcoal);
}

.test-email__select {
  max-width: 14rem;
}

.test-email__to {
  /* At least 13rem, taking the room there is up to 17rem. */
  flex: 1 1 13rem;
  min-width: 13rem;
  max-width: 17rem;
}

.test-email__select:focus,
.test-email__to:focus {
  outline: none;
  border-color: var(--dark-green);
}

.test-email__result {
  font-size: 0.85rem;
  /* Its own line, so it never pushes the address box down. */
  flex-basis: 100%;
}

.test-email__result--ok {
  color: var(--dark-green);
}

.test-email__result--error {
  color: var(--danger);
}
</style>
