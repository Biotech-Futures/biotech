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
      <div
        v-if="email.missed.length || bouncedOf(email).length || waitingOf(email).length"
        class="email-log__missed"
        data-test="log-missed"
      >
        <p class="email-log__missed-title">Couldn't be emailed:</p>
        <!-- Kept until the mail server can be reached, each with when it's given up on. -->
        <template v-if="waitingOf(email).length">
          <p class="email-log__subtitle" data-test="log-waiting">Waiting to send:</p>
          <p class="email-log__when">{{ WAITING_HINT }}</p>
          <ul>
            <li v-for="(person, i) in waitingOf(email)" :key="i">
              <MissedPerson :who="person.who" /><span class="email-log__reason"> · until {{ formatWhen(person.until) }}</span>
            </li>
          </ul>
        </template>
        <!-- Bounced back after the mail server took it, by when each was found. -->
        <template v-if="bouncedOf(email).length">
          <p class="email-log__subtitle" data-test="log-bounced">Bounced emails:</p>
          <div v-for="found in bouncedOf(email)" :key="`bounced-${found.at}`" class="email-log__send">
            <p class="email-log__when">{{ formatWhen(found.at) }}</p>
            <ul>
              <li v-for="(person, i) in found.people" :key="i">
                <MissedPerson :who="person.who" /><span v-if="person.reason" class="email-log__reason"> · {{ person.reason }}</span>
              </li>
            </ul>
          </div>
        </template>
        <template v-if="email.missed.length">
          <p class="email-log__subtitle" data-test="log-failed">Failed emails:</p>
          <div v-for="send in email.missed" :key="send.at" class="email-log__send">
            <p class="email-log__when">{{ formatWhen(send.at) }}</p>
            <ul>
              <li v-for="(person, i) in send.people" :key="i">
                <MissedPerson :who="person.who" /><span v-if="person.reason" class="email-log__reason"> · {{ person.reason }}</span>
              </li>
            </ul>
          </div>
        </template>
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
          <!-- When it was sent. -->
          <span v-if="sentAt(item)" class="email-log__when">{{ formatWhen(sentAt(item)!) }}</span>
        </h3>
        <!-- Kept until the mail server can be reached, each with when it's given up on. -->
        <template v-if="waitingOf(item).length">
          <p class="email-log__subtitle" data-test="log-waiting">Waiting to send:</p>
          <p class="email-log__when">{{ WAITING_HINT }}</p>
          <ul>
            <li v-for="(person, i) in waitingOf(item)" :key="i">
              <MissedPerson :who="person.who" /><span class="email-log__reason"> · until {{ formatWhen(person.until) }}</span>
            </li>
          </ul>
        </template>
        <!-- Bounced back after the mail server took it, by when each was found. -->
        <template v-if="bouncedOf(item).length">
          <p class="email-log__subtitle" data-test="log-bounced">Bounced emails:</p>
          <div v-for="found in bouncedOf(item)" :key="`bounced-${found.at}`" class="email-log__send">
            <p class="email-log__when">{{ formatWhen(found.at) }}</p>
            <ul>
              <li v-for="(person, i) in found.people" :key="i">
                <MissedPerson :who="person.who" /><span v-if="person.reason" class="email-log__reason"> · {{ person.reason }}</span>
              </li>
            </ul>
          </div>
        </template>
        <!-- Its sends that couldn't reach someone: a send's time above it,
             unless it's the one beside the name. -->
        <template v-if="item.missed.length">
          <p class="email-log__subtitle" data-test="log-failed">Failed emails:</p>
          <div v-for="send in item.missed" :key="send.at" class="email-log__send">
            <p v-if="send.at !== sentAt(item) || item.missed.length > 1" class="email-log__when">
              {{ formatWhen(send.at) }}
            </p>
            <ul>
              <li v-for="(person, i) in send.people" :key="i">
                <MissedPerson :who="person.who" /><span v-if="person.reason" class="email-log__reason"> · {{ person.reason }}</span>
              </li>
            </ul>
          </div>
        </template>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { deliveryNote } from '@/composables/useEmailRun'
import { formatShortDateTime, formatStatementTime } from '@/utils/date'
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

// Its bounces, grouped by when they were found (none from an older server).
const bouncedOf = (item: SystemEmailLogEntry) => item.bounced ?? []

// Who it's waiting to reach while the mail server can't be reached.
const waitingOf = (item: SystemEmailLogEntry) => item.waiting ?? []
const WAITING_HINT =
  "The mail server couldn't be reached. Each is tried again every 10 minutes until the time beside it."

const withMissed = computed(() =>
  props.emails.filter((item) => item.missed.length || bouncedOf(item).length || waitingOf(item).length),
)

// When it was sent: its last send, else its latest that missed someone.
const sentAt = (item: SystemEmailLogEntry) => item.lastSentAt ?? item.missed[0]?.at ?? null

/** Each send's time: "29/09/26 23:58". */
const formatWhen = (iso: string) => formatShortDateTime(iso)

// "Last Emailed at 29/09/2026 at 23:58", as Notify Finalists writes it.
const lastEmailed = (item: SystemEmailLogEntry) => {
  if (!item.lastSentAt) return 'Not emailed yet.'
  const by = item.lastSentBy ? ` by ${item.lastSentBy}` : ''
  return `Last Emailed at ${formatStatementTime(item.lastSentAt)}${by}.`
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

/* "Bounced emails:", "Failed emails:": under the email's name, in italics. */
.email-log__subtitle {
  font-weight: 400;
  font-style: italic;
  color: var(--text-primary);
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
  color: var(--teal);
}
</style>
