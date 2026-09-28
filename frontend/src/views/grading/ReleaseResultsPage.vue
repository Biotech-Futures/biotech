<template>
  <p
    v-if="UNDER_CONSTRUCTION"
    style="background: #fff8e1; border: 1px solid #f5d97e; border-radius: 8px; color: #8a6d1a; font-size: 0.85rem; padding: 0.6rem 0.85rem; margin: 0 0 0.75rem"
  >
    <i class="fas fa-hammer" aria-hidden="true"></i>
    The backend for this page is still being built.
  </p>
  <!-- Separate cards, as on the other Management tabs: the title card, then
       one each for marks and certificates. -->
  <div class="release-results">
    <section class="card release-results__intro">
      <div class="card-header">
        <h3 class="card-title">Release Results</h3>
      </div>
      <p class="release-results__hint">
        Releasing shows results only to students whose group made a submission.
      </p>
      <div>
        <button type="button" class="btn btn-outline btn-sm" @click="showPreview = true">
          Preview Email
        </button>
      </div>
    </section>
    <ReleasePage />
    <ReleaseCertificatesPage />
  </div>

  <!-- No results email is sent yet, so there is nothing real to preview. -->
  <Teleport to="body">
    <div v-if="showPreview" class="release-results__overlay" @click.self="showPreview = false">
      <div class="release-results__dialog" role="dialog" aria-modal="true" aria-label="Preview email">
        <h3 class="release-results__dialog-title">
          <i class="fas fa-envelope" aria-hidden="true"></i> Preview Email
        </h3>
        <p class="release-results__dialog-text">
          The email sent when results are released hasn't been set up yet. Its preview will
          show here.
        </p>
        <div class="release-results__dialog-actions">
          <button type="button" class="btn btn-primary btn-sm" @click="showPreview = false">
            Close
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ReleaseCertificatesPage from '@/views/grading/ReleaseCertificatesPage.vue'
import ReleasePage from '@/views/grading/ReleasePage.vue'

// Flip to false once the backend flow is signed off.
const UNDER_CONSTRUCTION = true

const showPreview = ref(false)
</script>

<style scoped>
.release-results {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 48rem;
}

.release-results__intro {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* The card's flex gap spaces the parts; the header's own margin would double it. */
.release-results__intro .card-header {
  margin-bottom: 0;
}

.release-results__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0;
}

/* As the release confirmation dialogs. */
.release-results__overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 2000;
}

.release-results__dialog {
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

.release-results__dialog-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.15rem;
  margin: 0;
}

.release-results__dialog-title i {
  color: var(--dark-green);
}

.release-results__dialog-text {
  color: var(--text-muted);
  font-size: 0.92rem;
  margin: 0;
}

.release-results__dialog-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
