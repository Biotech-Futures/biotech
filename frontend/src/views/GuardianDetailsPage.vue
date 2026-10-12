<template>
  <main class="details-page">
    <!-- Under the site's top bar, which shows the logo. -->
    <div class="details-shell">
      <section class="details-card">
        <div v-if="loading" class="details-state" role="status" aria-live="polite">
          <span class="details-spinner" aria-hidden="true"></span>
          <p>Loading…</p>
        </div>

        <div v-else-if="linkError" class="details-state" role="alert" data-test="details-link-error">
          <h1>{{ linkErrorCode === 'done' ? 'Already given' : "This link can't be used" }}</h1>
          <p>{{ linkError }}</p>
        </div>

        <div v-else-if="saved" class="details-state" role="status" data-test="details-saved">
          <div class="details-success-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" focusable="false"><path d="M20 6 9 17l-5-5" /></svg>
          </div>
          <h1>Thank you</h1>
          <p>The consent form for {{ saved.studentName }} has been emailed to {{ saved.email }}.</p>
        </div>

        <form v-else-if="studentName" novalidate @submit.prevent="submit">
          <h1>Guardian Details of {{ studentName }}</h1>

          <label class="details-field" for="details-first-name">
            <span>First name</span>
            <input
              id="details-first-name"
              v-model="firstName"
              type="text"
              autocomplete="given-name"
              maxlength="255"
              :class="{ 'is-invalid': badFields.includes('firstName') }"
              data-test="details-first-name"
            />
          </label>
          <label class="details-field" for="details-last-name">
            <span>Last name</span>
            <input
              id="details-last-name"
              v-model="lastName"
              type="text"
              autocomplete="family-name"
              maxlength="255"
              :class="{ 'is-invalid': badFields.includes('lastName') }"
              data-test="details-last-name"
            />
          </label>
          <label class="details-field" for="details-email">
            <span>Email</span>
            <input
              id="details-email"
              v-model="email"
              type="email"
              autocomplete="email"
              maxlength="254"
              :class="{ 'is-invalid': badFields.includes('email') }"
              data-test="details-email"
            />
          </label>

          <p v-if="submitError" class="details-error" role="alert" data-test="details-error">{{ submitError }}</p>

          <button type="submit" class="btn btn-primary details-submit" :disabled="submitting" data-test="details-submit">
            <span v-if="submitting" class="details-spinner details-spinner--light" aria-hidden="true"></span>
            {{ submitting ? 'Saving…' : 'Save' }}
          </button>
          <p class="details-muted">The guardian will then be emailed the consent form.</p>
        </form>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { apiErrorFromUnknown } from '@/utils/apiError'
import {
  fetchGuardianDetailsForm,
  saveGuardianDetailsForm,
  type GuardianDetailsSaved,
} from '@/utils/guardianDetailsAPI'

const route = useRoute()
const token = computed(() => String(route.params.token || ''))

const loading = ref(true)
const studentName = ref('')
const linkError = ref('')
const linkErrorCode = ref('')
const saved = ref<GuardianDetailsSaved | null>(null)

const firstName = ref('')
const lastName = ref('')
const email = ref('')
const submitting = ref(false)
const submitError = ref('')
// The boxes the message is about, outlined in red.
const badFields = ref<string[]>([])

const FIELD_LABELS: Record<string, string> = { firstName: 'first name', lastName: 'last name', email: 'email' }
const looksLikeEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)

// What's wrong before sending, naming the field: empty boxes first, then an
// email that isn't a full address.
const formProblem = (): { fields: string[]; message: string } | null => {
  const values: Record<string, string> = {
    firstName: firstName.value.trim(),
    lastName: lastName.value.trim(),
    email: email.value.trim(),
  }
  const empty = Object.keys(values).filter((field) => !values[field])
  if (empty.length) {
    return { fields: empty, message: `Please enter the ${empty.map((field) => FIELD_LABELS[field]).join(' and ')}.` }
  }
  if (!looksLikeEmail(values.email!)) {
    return { fields: ['email'], message: 'Enter a full email address, like name@example.com.' }
  }
  return null
}

function showLinkError(error: unknown) {
  const apiError = apiErrorFromUnknown(error, 'This link could not be opened.')
  linkErrorCode.value = String(apiError.code || '').replace(/^details_link_/, '')
  linkError.value = apiError.message
}

async function submit() {
  if (submitting.value) return
  const problem = formProblem()
  badFields.value = problem?.fields ?? []
  submitError.value = problem?.message ?? ''
  if (problem) return

  submitting.value = true
  try {
    saved.value = await saveGuardianDetailsForm(token.value, {
      firstName: firstName.value.trim(),
      lastName: lastName.value.trim(),
      email: email.value.trim(),
    })
  } catch (error) {
    const apiError = apiErrorFromUnknown(error, 'The details could not be saved. Please try again.')
    if (String(apiError.code || '').startsWith('details_link_')) {
      showLinkError(error)
    } else {
      submitError.value = apiError.message
      const fields = apiError.body.badFields
      badFields.value = Array.isArray(fields) ? fields.map(String) : []
    }
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    studentName.value = (await fetchGuardianDetailsForm(token.value)).studentName
  } catch (error) {
    showLinkError(error)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* The platform's card, fields, button and colours, on the site's background
   under its top bar (64px). */
.details-page {
  min-height: calc(100vh - 64px);
  min-height: calc(100dvh - 64px);
  padding: 32px 16px 48px;
  color: var(--teal);
  background: var(--bg-light);
}

.details-page,
.details-page * {
  box-sizing: border-box;
}

.details-shell {
  max-width: 560px;
  margin: 0 auto;
}

.details-card {
  padding: 1.5rem;
  border-radius: 8px;
  background: var(--white);
  box-shadow: 0 2px 4px var(--shadow);
}

h1 {
  margin: 0 0 8px;
  font-size: 1.6rem;
  line-height: 1.2;
}

.details-field {
  display: grid;
  gap: 7px;
  margin-top: 16px;
  font-weight: 700;
  font-size: 0.95rem;
}

.details-field input {
  width: 100%;
  padding: 0.625rem;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  background: var(--white);
  color: var(--teal);
  font: inherit;
  font-size: 1rem;
  font-weight: 400;
  transition: border-color 0.3s ease;
}

.details-field input:focus {
  outline: none;
  border-color: var(--dark-green);
  box-shadow: 0 0 0 3px rgba(1, 113, 81, 0.1);
}

.details-field input.is-invalid {
  border-color: var(--danger);
}

.details-error {
  margin: 18px 0 0;
  padding: 12px 14px;
  border: 1px solid rgba(220, 53, 69, 0.25);
  border-radius: 4px;
  background: rgba(220, 53, 69, 0.06);
  color: var(--danger);
}

.details-submit {
  width: 100%;
  margin-top: 22px;
}

.details-submit:disabled {
  opacity: 0.72;
  cursor: wait;
}

.details-muted {
  margin: 14px 0 0;
  color: var(--text-muted);
  font-size: 0.9rem;
  text-align: center;
}

.details-state {
  display: grid;
  justify-items: center;
  gap: 8px;
  padding: 24px 0;
  text-align: center;
}

.details-state p {
  margin: 0;
  max-width: 480px;
  line-height: 1.6;
}

.details-success-icon {
  display: grid;
  place-items: center;
  width: 58px;
  height: 58px;
  border-radius: 50%;
  background: var(--light-green);
  color: var(--dark-green);
}

.details-success-icon svg {
  width: 26px;
  height: 26px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.4;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.details-spinner {
  width: 22px;
  height: 22px;
  border: 2px solid rgba(1, 113, 81, 0.2);
  border-top-color: var(--dark-green);
  border-radius: 50%;
  animation: details-spin 0.8s linear infinite;
}

.details-spinner--light {
  width: 18px;
  height: 18px;
  border-color: rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
}

@keyframes details-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 620px) {
  .details-page {
    padding: 20px 16px 36px;
  }

  .details-card {
    padding: 22px 18px;
  }

  h1 {
    font-size: 1.35rem;
  }
}
</style>
