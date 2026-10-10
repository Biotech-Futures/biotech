<template>
  <div class="email-type-list">
    <div class="email-type-list__search">
      <i class="fas fa-magnifying-glass" aria-hidden="true"></i>
      <input
        v-model="query"
        type="search"
        class="email-type-list__search-input"
        placeholder="Search emails"
        aria-label="Search email types"
        autocomplete="off"
        data-bwignore
        data-1p-ignore
        data-lpignore="true"
      />
    </div>

    <!-- On the Log, every email at once, above them all. -->
    <button
      v-if="withAll"
      type="button"
      class="email-type-list__item"
      :class="{ 'is-selected': selectedKey === '' }"
      :aria-current="selectedKey === '' ? 'true' : undefined"
      data-test="all-emails"
      @click="emit('select', '')"
    >
      <span class="email-type-list__name">All emails</span>
    </button>

    <p v-if="!filtered.length" class="email-type-list__empty">
      No emails match “{{ query }}”.
    </p>

    <ul v-else class="email-type-list__items">
      <template v-for="(template, index) in filtered" :key="template.key">
        <!-- The group's heading, above the first of its emails shown. -->
        <li
          v-if="index === 0 || groupOf(template.key) !== groupOf(filtered[index - 1]!.key)"
          class="email-type-list__heading"
          role="presentation"
          data-test="email-group"
        >
          {{ groupOf(template.key) }}
        </li>
        <li>
          <button
            type="button"
            class="email-type-list__item"
            :class="{ 'is-selected': template.key === selectedKey }"
            :aria-current="template.key === selectedKey ? 'true' : undefined"
            @click="emit('select', template.key)"
          >
            <span class="email-type-list__copy">
              <span class="email-type-list__name">
                <span>
                  {{ nameParts(template.name).title }}
                  <span v-if="nameParts(template.name).to" class="email-type-list__to">
                    {{ nameParts(template.name).to }}
                  </span>
                </span>
                <i
                  v-if="template.locked"
                  class="fas fa-lock email-type-list__lock"
                  :title="`${template.name} is required and cannot be switched off`"
                  aria-hidden="true"
                ></i>
              </span>
            </span>
            <span
              class="email-type-list__status"
              :class="template.enabled ? 'is-on' : 'is-off'"
              :title="template.enabled ? 'Enabled' : 'Disabled'"
            >
              {{ template.enabled ? 'On' : 'Off' }}
            </span>
          </button>
        </li>
      </template>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { nameParts, type SystemEmailTemplate } from '@/utils/systemEmail'

const props = defineProps<{
  templates: SystemEmailTemplate[]
  /** '' for All emails, when ``withAll``. */
  selectedKey: string | null
  withAll?: boolean
}>()

const emit = defineEmits<{
  (e: 'select', key: string): void
}>()

const query = ref('')

// Each email's group, with a heading above it, in the order the list shows them.
const GROUPS: [string, string[]][] = [
  ['Sign-in', ['login_code', 'password_reset', 'password_changed']],
  [
    'Guardians',
    [
      'guardian_details_request',
      'guardian_details_received',
      'guardian_consent_student_notice',
      'guardian_consent_request',
      'guardian_consent_received'
    ]
  ],
  ['Messages and events', ['unread_messages', 'rsvp_reminder', 'event_promotion', 'announcement']],
  ['Submissions', ['submission_reminder', 'submission_confirmation']],
  ['Symposium', ['finalist_notification', 'nonfinalist_invitation', 'nonsubmission_notice']],
  ['Results', ['results_team', 'results_supervisor']]
]
const GROUP_OF = new Map(GROUPS.flatMap(([heading, keys]) => keys.map((key) => [key, heading] as const)))
// An email not placed in a group yet still gets a heading.
const groupOf = (key: string) => GROUP_OF.get(key) ?? 'Other'


const filtered = computed(() => {
  const term = query.value.trim().toLowerCase()
  if (!term) return props.templates
  return props.templates.filter(
    (template) =>
      template.name.toLowerCase().includes(term) ||
      template.description.toLowerCase().includes(term)
  )
})
</script>

<style scoped>
.email-type-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-width: 0;
}

.email-type-list__search {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  background: #ffffff;
  color: #9ca3af;
}

.email-type-list__search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  font-size: 0.875rem;
  color: #111827;
  background: transparent;
}

.email-type-list__empty {
  margin: 0;
  padding: 0.75rem;
  font-size: 0.8125rem;
  color: #6b7280;
}

.email-type-list__items {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.email-type-list__heading {
  margin: 0.25rem 0 -0.2rem;
  padding: 0 0.25rem;
  font-size: 0.65rem;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.email-type-list__heading:first-child {
  margin-top: 0;
}

.email-type-list__item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  width: 100%;
  padding: 0.625rem 0.75rem;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  background: #ffffff;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.email-type-list__item:hover {
  border-color: rgba(1, 113, 81, 0.4);
  background: rgba(1, 113, 81, 0.06);
}

.email-type-list__item.is-selected {
  border-color: var(--dark-green);
  background: var(--accent-green-soft);
}

.email-type-list__copy {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  min-width: 0;
}

.email-type-list__name {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: #000;
}

/* Who it goes to, as in "(to student)": not bold, and lighter. */
.email-type-list__to {
  font-weight: 400;
  color: var(--text-muted);
}

.email-type-list__lock {
  font-size: 0.6875rem;
  color: var(--eucalypt);
}

.email-type-list__status {
  flex-shrink: 0;
  padding: 0.125rem 0.5rem;
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.email-type-list__status.is-on {
  color: #047857;
  background: #d1fae5;
}

.email-type-list__status.is-off {
  color: #b91c1c;
  background: #fee2e2;
}

/* Dark theme: grey boxes with light text, as other pages' inputs. */
:root[data-theme='dark'] .email-type-list__search,
:root[data-theme='dark'] .email-type-list__item:not(.is-selected):not(:hover) {
  background: var(--surface-elevated);
  border-color: var(--border-light);
}

:root[data-theme='dark'] .email-type-list__search-input,
:root[data-theme='dark'] .email-type-list__name {
  color: var(--charcoal);
}
</style>
