<template>
  <p
    v-if="UNDER_CONSTRUCTION"
    style="background: #fff8e1; border: 1px solid #f5d97e; border-radius: 8px; color: #8a6d1a; font-size: 0.85rem; padding: 0.6rem 0.85rem; margin: 0 0 0.75rem"
  >
    <i class="fas fa-hammer" aria-hidden="true"></i>
    The backend for this page is still being built.
  </p>
  <div class="release">
    <p v-if="isLoading" class="release__hint">Loading…</p>

    <div v-else-if="loadError" class="card release__load-error">
      <p>Failed to load release status.</p>
      <p class="release__error-detail">{{ loadError }}</p>
      <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
    </div>

    <div v-else-if="status" class="card release__panel">
      <div class="card-header">
        <h3 class="card-title">Release Certificates</h3>
      </div>

      <p class="release__headline" :class="released ? 'release__state--ok' : 'release__state--warn'">
        <i :class="released ? 'fas fa-eye' : 'fas fa-eye-slash'" aria-hidden="true"></i>
        {{ released ? 'Certificates are released' : 'Certificates are not released' }}
      </p>
      <p v-if="released" class="release__detail">
        Last Released at {{ releasedAtLabel }}<template v-if="status.released_by"> by {{ status.released_by }}</template>.
      </p>

      <p v-if="actionError" class="release__banner release__banner--error">{{ actionError }}</p>

      <p class="release__hint">
        Releasing gives certificates only to students whose group made a submission.
      </p>

      <div class="release__finalists">
        <label class="release__finalists-toggle">
          <input
            type="checkbox"
            :checked="excludeFinalists"
            :disabled="isTogglingExclusion"
            @change="onExclusionChange"
          />
          <span>Exclude finalists from this release</span>
        </label>
      </div>
      <p v-if="!released && submissionsOpen" class="release__banner release__banner--warn">
        Submissions are still open (including extensions) — certificates can be released
        once the window has closed.
      </p>

      <div class="release__actions">
        <button
          type="button"
          class="btn btn-primary btn-sm"
          :disabled="isToggling || released || submissionsOpen"
          @click="showConfirm = true"
        >
          Release
        </button>
        <button
          v-if="released"
          type="button"
          class="btn btn-outline btn-sm"
          :disabled="isToggling"
          @click="unrelease"
        >
          {{ isToggling ? 'Unreleasing…' : 'Unrelease' }}
        </button>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="showConfirm" class="release__overlay" @click.self="showConfirm = false">
        <div class="release__dialog" role="dialog" aria-modal="true" aria-label="Release certificates">
          <h3 class="release__dialog-title">
            <i class="fas fa-award" aria-hidden="true"></i> Release certificates?
          </h3>
          <p class="release__dialog-text">
            Students will immediately be able to download their participation certificates.
          </p>
          <div class="release__dialog-actions">
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="isToggling"
              @click="showConfirm = false"
            >
              Cancel
            </button>
            <button
              type="button"
              class="btn btn-primary btn-sm"
              :disabled="isToggling"
              @click="confirmRelease"
            >
              {{ isToggling ? 'Releasing…' : 'Release' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  fetchCertificatesRelease,
  setCertificatesFinalistExclusion,
  toggleCertificatesRelease,
  type ReleaseStatus
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

// Flip to false once the backend flow is signed off.
const UNDER_CONSTRUCTION = true

const status = ref<ReleaseStatus | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const isToggling = ref(false)

const released = computed(() => status.value?.released_at != null)

// While any team can still submit, the button is disabled outright — the
// confirm dialog must not even open for a release the server would refuse.
const submissionsOpen = computed(() => status.value?.submissions_open === true)

const excludeFinalists = computed(() => status.value?.exclude_finalists === true)
const isTogglingExclusion = ref(false)

const onExclusionChange = async (event: Event) => {
  const exclude = (event.target as HTMLInputElement).checked
  isTogglingExclusion.value = true
  actionError.value = ''
  try {
    status.value = await setCertificatesFinalistExclusion(exclude)
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    isTogglingExclusion.value = false
  }
}

const releasedAtLabel = computed(() =>
  status.value?.released_at ? new Date(status.value.released_at).toLocaleString() : ''
)

const load = async () => {
  isLoading.value = true
  loadError.value = ''
  try {
    status.value = await fetchCertificatesRelease()
  } catch (err) {
    status.value = null
    loadError.value = apiErrorFromUnknown(err).message
  } finally {
    isLoading.value = false
  }
}

onMounted(load)

const showConfirm = ref(false)

const unrelease = async () => {
  isToggling.value = true
  actionError.value = ''
  try {
    status.value = await toggleCertificatesRelease(false)
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    isToggling.value = false
  }
}

const confirmRelease = async () => {
  isToggling.value = true
  actionError.value = ''
  try {
    status.value = await toggleCertificatesRelease(true)
    showConfirm.value = false
  } catch (err) {
    showConfirm.value = false
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    isToggling.value = false
  }
}
</script>

<style scoped>
.release {
  max-width: 36rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.release__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.release__panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* The panel's flex gap already spaces the content below the heading — the
   header's own margin would double it. */
.release__panel .card-header {
  margin-bottom: 0;
}

.release__load-error p {
  margin: 0 0 0.5rem;
}

.release__error-detail {
  color: var(--text-muted);
  font-size: 0.85rem;
}

/* Same look as the deadline page's "Submissions open/closed" state line. */
.release__state--ok {
  color: var(--dark-green);
}

.release__state--warn {
  color: #eab308;
}

.release__headline {
  font-weight: 600;
  font-size: 0.9rem;
  margin: 0 0 0.2rem;
}

.release__detail {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0;
}

.release__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
}

.release__banner--error {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.release__banner--warn {
  background: color-mix(in srgb, #ff8c00 12%, transparent);
  color: #ff8c00;
}

.release__finalists {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 0.85rem 1rem;
}

.release__finalists-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  cursor: pointer;
}

.release__finalists-toggle input {
  accent-color: var(--dark-green);
  width: 1.1rem;
  height: 1.1rem;
}

.release__actions {
  display: flex;
  gap: 0.5rem;
}

.release__actions .btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.release__overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 2000;
}

.release__dialog {
  background: var(--surface-elevated);
  color: var(--charcoal);
  border-radius: 10px;
  box-shadow: 0 10px 40px var(--shadow);
  width: 100%;
  max-width: 26rem;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.release__dialog-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.15rem;
  margin: 0;
}

.release__dialog-title i {
  color: var(--dark-green);
}

.release__dialog-text {
  color: var(--text-muted);
  font-size: 0.92rem;
  margin: 0;
}

.release__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style>
