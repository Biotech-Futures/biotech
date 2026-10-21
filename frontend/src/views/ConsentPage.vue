<template>
  <main class="consent-page">
    <!-- Under the site's top bar, which shows the logo. -->
    <div class="consent-shell">
      <section class="consent-card">
        <div v-if="loading" class="consent-state" role="status" aria-live="polite">
          <span class="consent-spinner" aria-hidden="true"></span>
          <p>Loading the consent form…</p>
        </div>

        <div v-else-if="linkError" class="consent-state" role="alert" data-test="consent-link-error">
          <h1>{{ linkErrorTitle }}</h1>
          <p>{{ linkError }}</p>
          <p v-if="linkErrorCode !== 'used'">
            Email <a :href="`mailto:${supportEmail}`">{{ supportEmail }}</a> if you need help.
          </p>
        </div>

        <div v-else-if="signed" class="consent-state" role="status" data-test="consent-signed">
          <div class="consent-success-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" focusable="false"><path d="M20 6 9 17l-5-5" /></svg>
          </div>
          <h1>Thank you</h1>
          <p>
            Your consent for {{ data?.studentName }} has been recorded
            {{ signed.mediaConsent ? 'with' : 'without' }} media consent.
          </p>
          <p class="consent-muted">
            Your reference is <strong>{{ signed.reference }}</strong>.
            To withdraw consent later, email <a :href="`mailto:${supportEmail}`">{{ supportEmail }}</a>.
          </p>
        </div>

        <form v-else-if="data" class="consent-form" novalidate @submit.prevent="submit">
          <p class="consent-kicker">Parent / guardian consent</p>
          <h1>{{ greeting }}</h1>

          <!-- Wording is rendered by the backend from its own template; names are escaped there. -->
          <div class="consent-body" data-test="consent-body" v-html="data.form.body_html"></div>

          <fieldset class="consent-section" :class="{ 'consent-section--invalid': showErrors && mediaConsent === null }">
            <legend>Media consent: please select one option</legend>
            <label class="consent-option" :class="{ 'consent-option--selected': mediaConsent === true }">
              <input v-model="mediaConsent" type="radio" name="media" :value="true" data-test="media-yes" />
              <span>{{ data.form.media_yes }}</span>
            </label>
            <label class="consent-option" :class="{ 'consent-option--selected': mediaConsent === false }">
              <input v-model="mediaConsent" type="radio" name="media" :value="false" data-test="media-no" />
              <span>{{ data.form.media_no }}</span>
            </label>
          </fieldset>

          <section class="consent-section">
            <h2>Declaration</h2>
            <p>{{ data.form.declaration }}</p>

            <label class="consent-field" for="consent-name">
              <span>Your full name</span>
              <input
                id="consent-name"
                v-model="fullName"
                type="text"
                autocomplete="name"
                maxlength="255"
                :class="{ 'is-invalid': showErrors && !fullName.trim() }"
                data-test="consent-name"
              />
            </label>

            <div class="consent-field">
              <span id="consent-signature-label">Your signature</span>
              <SignaturePad
                aria-labelledby="consent-signature-label"
                :disabled="submitting"
                :invalid="showErrors && !signature"
                @change="signature = $event"
              />
            </div>

            <label class="consent-agree">
              <input v-model="agreed" type="checkbox" data-test="consent-agree" />
              <span>I am {{ data.studentName }}'s parent, guardian or authorised consent provider, and I agree to the above.</span>
            </label>
          </section>

          <p v-if="showErrors && missing.length" class="consent-error" role="alert" data-test="consent-missing">
            Please {{ missing.join(', ') }}.
          </p>
          <p v-if="submitError" class="consent-error" role="alert" data-test="consent-submit-error">{{ submitError }}</p>

          <button type="submit" class="btn btn-primary consent-submit" :disabled="submitting" data-test="consent-submit">
            <span v-if="submitting" class="consent-spinner consent-spinner--light" aria-hidden="true"></span>
            {{ submitting ? 'Signing…' : 'Sign consent form' }}
          </button>
          <p class="consent-muted consent-footnote">
            This link is just for you and works until {{ expiresLabel }}. Questions? Email
            <a :href="`mailto:${supportEmail}`">{{ supportEmail }}</a>.
          </p>
        </form>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import SignaturePad from '@/components/consent/SignaturePad.vue'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { fetchConsentForm, signConsentForm } from '@/utils/consentAPI'
import type { ConsentFormData, ConsentSigned } from '@/utils/consentAPI'
import { formatDayMonthTime } from '@/utils/date'

const DEFAULT_SUPPORT_EMAIL = 'support@biotechfutures.org'

const route = useRoute()
const token = computed(() => String(route.params.token || ''))

const loading = ref(true)
const data = ref<ConsentFormData | null>(null)
const linkError = ref('')
const linkErrorCode = ref('')
const signed = ref<ConsentSigned | null>(null)

const mediaConsent = ref<boolean | null>(null)
const fullName = ref('')
const signature = ref<string | null>(null)
const agreed = ref(false)
const showErrors = ref(false)
const submitting = ref(false)
const submitError = ref('')

const supportEmail = computed(() => data.value?.supportEmail || DEFAULT_SUPPORT_EMAIL)

const greeting = computed(() =>
  data.value?.guardianFirstName ? `Hi ${data.value.guardianFirstName}` : 'Hello'
)

const linkErrorTitle = computed(() =>
  linkErrorCode.value === 'used' ? 'Already signed' : "This link can't be used"
)

// "22 Oct, 11:00 am", in the set time.
const expiresLabel = computed(() => (data.value ? formatDayMonthTime(data.value.expiresAt) : ''))

const missing = computed(() => {
  const items: string[] = []
  if (mediaConsent.value === null) items.push('choose a media consent option')
  if (!fullName.value.trim()) items.push('enter your full name')
  if (!signature.value) items.push('sign in the signature box')
  if (!agreed.value) items.push('tick the box to confirm')
  return items
})

function showLinkError(error: unknown) {
  const apiError = apiErrorFromUnknown(error, 'This consent link could not be opened.')
  linkErrorCode.value = String(apiError.code || '').replace(/^consent_link_/, '')
  linkError.value = apiError.message
}

async function submit() {
  if (submitting.value || !data.value) return
  showErrors.value = true
  submitError.value = ''
  if (missing.value.length) return

  submitting.value = true
  try {
    signed.value = await signConsentForm(token.value, {
      guardianFullName: fullName.value.trim(),
      mediaConsent: mediaConsent.value as boolean,
      signature: signature.value as string,
      agreed: agreed.value,
      consentVersion: data.value.form.version
    })
    window.scrollTo?.({ top: 0 })
  } catch (error) {
    const apiError = apiErrorFromUnknown(error, 'Could not record your consent. Please try again.')
    if (String(apiError.code || '').startsWith('consent_link_')) showLinkError(apiError)
    else submitError.value = apiError.message
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    data.value = await fetchConsentForm(token.value)
    fullName.value = [data.value.guardianFirstName, data.value.guardianLastName].filter(Boolean).join(' ')
  } catch (error) {
    showLinkError(error)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* The platform's card, fields, button and colours, on the site's background
   under its top bar (64px), as the Guardian Details form. */
.consent-page {
  min-height: calc(100vh - 64px);
  min-height: calc(100dvh - 64px);
  padding: 32px 16px 48px;
  color: var(--teal);
  background: var(--bg-light);
}

.consent-page,
.consent-page * {
  box-sizing: border-box;
}

.consent-shell {
  max-width: 1100px;
  margin: 0 auto;
}

/* As .card. */
.consent-card {
  padding: 1.5rem;
  border-radius: 8px;
  background: var(--white);
  box-shadow: 0 2px 4px var(--shadow);
}

h1 {
  margin: 0 0 16px;
  font-size: 1.75rem;
  line-height: 1.2;
}

.consent-kicker {
  margin: 0 0 6px;
  color: var(--dark-green);
  font-size: 0.78rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.consent-body {
  line-height: 1.65;
}

.consent-body :deep(h2),
.consent-section h2,
.consent-section legend {
  margin: 24px 0 8px;
  padding: 0;
  color: var(--teal);
  font-size: 1.1rem;
  font-weight: 700;
}

.consent-body :deep(p) {
  margin: 0 0 12px;
}

.consent-body :deep(ul),
.consent-body :deep(ol) {
  margin: 0 0 14px;
  padding-left: 1.4rem;
}

.consent-body :deep(li + li) {
  margin-top: 6px;
}

.consent-body :deep(a),
.consent-card a {
  color: var(--dark-green);
  font-weight: 700;
}

.consent-section {
  margin: 0;
  padding: 0;
  border: 0;
}

.consent-section p {
  line-height: 1.6;
}

.consent-section--invalid .consent-option {
  border-color: var(--danger);
}

/* A media consent choice: the site's border, dark green when picked. */
.consent-option {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-top: 10px;
  padding: 14px 16px;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  line-height: 1.55;
  cursor: pointer;
}

.consent-option--selected {
  border-color: var(--dark-green);
  background: rgba(1, 113, 81, 0.06);
}

.consent-option input,
.consent-agree input {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  /* Centred on the first line of the text beside it, 1.55 lines tall; the
     text's own size, so em measures that line. */
  margin: calc((1.55em - 18px) / 2) 0 0;
  font-size: inherit;
  accent-color: var(--dark-green);
}

/* The agree box, bigger. */
.consent-agree input {
  width: 22px;
  height: 22px;
  margin-top: calc((1.55em - 22px) / 2);
}

.consent-field {
  display: grid;
  gap: 7px;
  margin-top: 16px;
  font-weight: 700;
  font-size: 0.95rem;
}

/* As .form-control. */
.consent-field input {
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

.consent-field input:focus {
  outline: none;
  border-color: var(--dark-green);
  box-shadow: 0 0 0 3px rgba(1, 113, 81, 0.1);
}

.consent-field input.is-invalid {
  border-color: var(--danger);
}

.consent-agree {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-top: 18px;
  line-height: 1.55;
  cursor: pointer;
}

.consent-error {
  margin: 18px 0 0;
  padding: 12px 14px;
  border: 1px solid rgba(220, 53, 69, 0.25);
  border-radius: 4px;
  background: rgba(220, 53, 69, 0.06);
  color: var(--danger);
}

/* .btn .btn-primary does the rest. */
.consent-submit {
  width: 100%;
  margin-top: 22px;
}

.consent-submit:disabled {
  opacity: 0.72;
  cursor: wait;
}

.consent-muted {
  color: var(--text-muted);
  font-size: 0.9rem;
  line-height: 1.6;
}

.consent-footnote {
  margin: 14px 0 0;
  text-align: center;
}

.consent-state {
  display: grid;
  justify-items: center;
  gap: 8px;
  padding: 24px 0;
  text-align: center;
}

.consent-state p {
  margin: 0;
  max-width: 520px;
  line-height: 1.6;
}

.consent-success-icon {
  display: grid;
  place-items: center;
  width: 58px;
  height: 58px;
  border-radius: 50%;
  background: var(--light-green);
  color: var(--dark-green);
}

.consent-success-icon svg {
  width: 26px;
  height: 26px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.4;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.consent-spinner {
  width: 22px;
  height: 22px;
  border: 2px solid rgba(1, 113, 81, 0.2);
  border-top-color: var(--dark-green);
  border-radius: 50%;
  animation: consent-spin 0.8s linear infinite;
}

.consent-spinner--light {
  width: 18px;
  height: 18px;
  border-color: rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
}

@keyframes consent-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 620px) {
  .consent-page {
    padding: 20px 16px 36px;
  }

  .consent-card {
    padding: 1.25rem 1rem;
  }

  h1 {
    font-size: 1.45rem;
  }
}
</style>
