<template>
  <section class="email-log" aria-label="Failed sending emails">
    <p v-if="loading" class="email-log__state" role="status">
      <i class="fas fa-spinner fa-spin" aria-hidden="true"></i>
      Loading the log…
    </p>

    <p v-else-if="error" class="email-log__error" role="alert">{{ error }}</p>

    <!-- One email: when it last went, where bounces go, and who it missed,
         as Notify Finalists shows them. -->
    <template v-else-if="email">
      <p class="email-log__line" data-test="log-last-emailed">{{ lastEmailed(email) }}</p>
      <p class="email-log__note">{{ deliveryNote(email.sentFrom, email.toGroups) }}</p>
      <div v-if="email.missed.length" class="email-log__missed" data-test="log-missed">
        <p class="email-log__missed-title">Couldn't be emailed:</p>
        <div v-for="send in email.missed" :key="send.at" class="email-log__send">
          <p class="email-log__when">{{ formatWhen(send.at) }}</p>
          <ul>
            <li v-for="(person, i) in send.people" :key="i">
              <MissedPerson :who="person.who" /><span v-if="person.reason" class="email-log__reason"> · {{ person.reason }}</span>
            </li>
          </ul>
        </div>
      </div>
    </template>

    <!-- All emails: who each one's latest sends couldn't reach. They go from
         different mailboxes, so the note names none, and comes first. -->
    <template v-else>
      <p class="email-log__note" data-test="log-all-note">
        Any that can't be delivered, such as a mistyped address or one a school's mail server refuses, come back
        to the email address they were sent from.
      </p>
      <p class="email-log__missed-title">Couldn't be emailed:</p>
      <p v-if="!withMissed.length" class="email-log__line" data-test="log-none-missed">
        Every email reached everyone it was sent to.
      </p>
      <div v-for="item in withMissed" :key="item.key" class="email-log__email" data-test="log-email">
        <h3 class="email-log__name">
          {{ nameParts(item.name).title }}
          <span v-if="nameParts(item.name).to" class="email-log__to">{{ nameParts(item.name).to }}</span>
          <!-- One send: its time beside the name, else above each send. -->
          <span v-if="item.missed.length === 1" class="email-log__when">{{ formatWhen(item.missed[0].at) }}</span>
        </h3>
        <div v-for="send in item.missed" :key="send.at" class="email-log__send">
          <p v-if="item.missed.length > 1" class="email-log__when">{{ formatWhen(send.at) }}</p>
          <ul>
            <li v-for="(person, i) in send.people" :key="i">
              <MissedPerson :who="person.who" /><span v-if="person.reason" class="email-log__reason"> · {{ person.reason }}</span>
            </li>
          </ul>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { deliveryNote } from '@/composables/useEmailRun'
import { nameParts, type SystemEmailLogEntry } from '@/utils/systemEmail'
import MissedPerson from '@/views/management/MissedPerson.vue'

const props = defineProps<{
  emails: SystemEmailLogEntry[]
  /** '' for All emails. */
  selectedKey: string
  loading: boolean
  error: string
}>()

const email = computed(() => props.emails.find((item) => item.key === props.selectedKey) ?? null)

const withMissed = computed(() => props.emails.filter((item) => item.missed.length))

/** "29/09/2026 23:58", as Notify Finalists shows when it last emailed. */
const formatWhen = (iso: string) => {
  const at = new Date(iso)
  return `${at.toLocaleDateString('en-GB')} ${at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}`
}

const lastEmailed = (item: SystemEmailLogEntry) => {
  if (!item.lastSentAt) return 'Not emailed yet.'
  const by = item.lastSentBy ? ` by ${item.lastSentBy}` : ''
  return `Last Emailed at ${formatWhen(item.lastSentAt)}${by}.`
}
</script>

<style scoped>
.email-log {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  font-size: 0.85rem;
}

.email-log p {
  margin: 0;
}

.email-log__state,
.email-log__line {
  color: var(--text-muted);
}

.email-log__error {
  color: var(--danger);
}

/* The amber Notify Finalists gives its delivery note. */
.email-log__note {
  color: #b8860b;
}

.email-log__missed {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.email-log__missed-title {
  font-weight: 600;
  color: var(--danger);
}

.email-log__email {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.email-log__name {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.375rem;
  margin: 0;
  font-size: 0.875rem;
  font-weight: 500;
  color: #000;
}

.email-log__to {
  font-weight: 400;
  color: var(--text-muted);
}

.email-log__when,
.email-log__reason {
  font-weight: 400;
  color: var(--text-muted);
}

.email-log ul {
  margin: 0;
  padding-left: 1.2rem;
}

:root[data-theme='dark'] .email-log__name {
  color: var(--charcoal);
}
</style>
