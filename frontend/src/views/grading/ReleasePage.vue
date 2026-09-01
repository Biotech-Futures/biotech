<template>
  <div class="release">
    <p v-if="isLoading" class="release__hint">Loading…</p>

    <div v-else-if="loadError" class="card release__load-error">
      <p>Failed to load release status.</p>
      <p class="release__error-detail">{{ loadError }}</p>
      <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
    </div>

    <template v-else-if="status">
      <div class="release__card" :class="released ? 'release__card--ok' : 'release__card--warn'">
        <i v-if="released" class="fas fa-circle-check release__icon--ok" aria-hidden="true"></i>
        <div>
          <p class="release__headline">
            {{ released ? 'Marks are released' : 'Marks are NOT released' }}
          </p>
          <p class="release__detail">
            <template v-if="released">
              Released at {{ releasedAtLabel }}<template v-if="status.released_by"> by {{ status.released_by }}</template>.
            </template>
            <template v-else>
              Students and supervisors cannot see their grades until you release.
            </template>
          </p>
        </div>
      </div>

      <p v-if="actionError" class="release__banner release__banner--error">{{ actionError }}</p>

      <div class="release__actions">
        <button
          type="button"
          class="btn btn-primary btn-sm"
          :disabled="isToggling || released"
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
    </template>

    <Teleport to="body">
      <div v-if="showConfirm" class="release__overlay" @click.self="showConfirm = false">
        <div class="release__dialog" role="dialog" aria-modal="true" aria-label="Release marks">
          <h3 class="release__dialog-title">
            <i class="fas fa-unlock" aria-hidden="true"></i> Release marks?
          </h3>
          <p class="release__dialog-text">
            Students and supervisors will immediately be able to see their grades, download
            their marks summary and certificate.
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
import { fetchRelease, toggleRelease, type ReleaseStatus } from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const status = ref<ReleaseStatus | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const isToggling = ref(false)

const released = computed(() => status.value?.released_at != null)

const releasedAtLabel = computed(() =>
  status.value?.released_at ? new Date(status.value.released_at).toLocaleString() : ''
)

const load = async () => {
  isLoading.value = true
  loadError.value = ''
  try {
    status.value = await fetchRelease()
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
    status.value = await toggleRelease(false)
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
    status.value = await toggleRelease(true)
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

.release__load-error p {
  margin: 0 0 0.5rem;
}

.release__error-detail {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.release__card {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  border-radius: 8px;
  padding: 1rem;
  border: 1px solid;
}

.release__card--ok {
  background: var(--surface-elevated);
  border-color: var(--border-light);
}

.release__card--warn {
  background: var(--surface-elevated);
  border-color: var(--border-light);
}

.release__card--warn .release__detail {
  color: #d97706;
}

.release__icon--ok {
  color: var(--dark-green);
  margin-top: 0.2rem;
}

.release__headline {
  font-weight: 600;
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
