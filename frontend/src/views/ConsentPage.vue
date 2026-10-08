<template>
  <main class="consent-page">
    <div class="consent-shell">
      <header class="consent-brand">
        <img :src="logo" :alt="BRAND_NAME" class="consent-brand__logo" />
        <span class="consent-brand__name">{{ BRAND_NAME }}</span>
      </header>

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
            We've emailed you a copy. Your reference is <strong>{{ signed.reference }}</strong>.
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

          <button type="submit" class="consent-submit" :disabled="submitting" data-test="consent-submit">
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

import logo from '@/assets/btf-logo.png'
import SignaturePad from '@/components/consent/SignaturePad.vue'
import { BRAND_NAME } from '@/constants/brand'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { fetchConsentForm, signConsentForm } from '@/utils/consentAPI'
import type { ConsentFormData, ConsentSigned } from '@/utils/consentAPI'

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

const expiresLabel = computed(() =>
  data.value
    ? new Date(data.value.expiresAt).toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' })
    : ''
)

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
.consent-page {
  --emerald-700: #1f5d4f;
  --emerald-500: #2fa486;
  --stone-900: #10211d;
  --stone-700: #36514a;
  --stone-500: #648178;
  --border-soft: rgba(16, 33, 29, 0.12);
  min-height: 100vh;
  min-height: 100dvh;
  padding: 32px 16px 48px;
  font-family: Arial, Helvetica, sans-serif;
  color: var(--stone-900);
  background: linear-gradient(180deg, #eef7f2 0%, #e7f3ec 40%, #dcece2 100%);
}

.consent-page,
.consent-page * {
  box-sizing: border-box;
}

.consent-shell {
  max-width: 760px;
  margin: 0 auto;
}

.consent-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

.consent-brand__logo {
  width: 40px;
  height: 40px;
  object-fit: contain;
}

.consent-brand__name {
  font-weight: 700;
  font-size: 1.15rem;
}

.consent-card {
  padding: 32px;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 20px 60px rgba(12, 41, 34, 0.12);
}

h1 {
  margin: 0 0 16px;
  font-size: 1.75rem;
  line-height: 1.2;
}

.consent-kicker {
  margin: 0 0 6px;
  color: var(--emerald-700);
  font-size: 0.78rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.consent-body {
  color: var(--stone-700);
  line-height: 1.65;
}

.consent-body :deep(h2),
.consent-section h2,
.consent-section legend {
  margin: 24px 0 8px;
  padding: 0;
  color: var(--stone-900);
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
  color: var(--emerald-700);
  font-weight: 700;
}

.consent-section {
  margin: 0;
  padding: 0;
  border: 0;
}

.consent-section p {
  color: var(--stone-700);
  line-height: 1.6;
}

.consent-section--invalid .consent-option {
  border-color: rgba(210, 75, 75, 0.5);
}

.consent-option {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-top: 10px;
  padding: 14px 16px;
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  line-height: 1.55;
  cursor: pointer;
}

.consent-option--selected {
  border-color: var(--emerald-500);
  background: rgba(47, 164, 134, 0.07);
}

.consent-option input,
.consent-agree input {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  margin-top: 2px;
  accent-color: var(--emerald-700);
}

.consent-field {
  display: grid;
  gap: 7px;
  margin-top: 16px;
  font-weight: 700;
  font-size: 0.95rem;
}

.consent-field input {
  min-height: 48px;
  padding: 0 14px;
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  font: inherit;
  font-weight: 400;
}

.consent-field input.is-invalid {
  border-color: rgba(210, 75, 75, 0.6);
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
  border: 1px solid rgba(210, 75, 75, 0.2);
  border-radius: 8px;
  background: rgba(255, 245, 245, 0.95);
  color: #9f3030;
}

.consent-submit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  min-height: 52px;
  margin-top: 22px;
  border: 0;
  border-radius: 12px;
  color: #ffffff;
  background: linear-gradient(135deg, var(--emerald-700), var(--emerald-500));
  font-size: 1rem;
  font-weight: 800;
  cursor: pointer;
}

.consent-submit:disabled {
  opacity: 0.72;
  cursor: wait;
}

.consent-muted {
  color: var(--stone-500);
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
  color: var(--stone-700);
  line-height: 1.6;
}

.consent-success-icon {
  display: grid;
  place-items: center;
  width: 58px;
  height: 58px;
  border-radius: 50%;
  background: rgba(39, 132, 109, 0.12);
  color: var(--emerald-700);
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
  border: 2px solid rgba(31, 93, 79, 0.2);
  border-top-color: var(--emerald-700);
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
    padding: 22px 18px;
  }

  h1 {
    font-size: 1.45rem;
  }
}
</style>
