<template>
  <section class="results-tab" :aria-busy="isLoading">
    <div v-if="isLoading" class="results-loading">Loading results…</div>

    <div v-else-if="loadError" class="results-error" role="alert">
      {{ loadError }}
    </div>

    <template v-else-if="payload">
      <header class="results-header">
        <h3>Your marks</h3>
        <p class="results-subtitle">
          {{ payload.group.group_name }} · {{ payload.year }}
        </p>
        <div class="results-actions">
          <button
            type="button"
            class="btn btn-primary"
            :disabled="downloadingSummary"
            @click="onDownloadSummary"
          >
            {{ downloadingSummary ? 'Preparing…' : 'Download PDF/DOCX summary' }}
          </button>
          <button
            type="button"
            class="btn"
            :disabled="downloadingCert"
            @click="onDownloadCert"
          >
            {{ downloadingCert ? 'Preparing…' : 'Download participation certificate' }}
          </button>
        </div>
      </header>

      <div class="results-components">
        <article
          v-for="component in payload.components"
          :key="component.code"
          class="results-component"
        >
          <h4>{{ component.name }}</h4>
          <p v-if="!component.submitted" class="results-empty">
            No submission uploaded.
          </p>
          <table v-else class="results-table">
            <thead>
              <tr>
                <th>Criterion</th>
                <th>Mark</th>
                <th>Comment</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="criterion in component.criteria" :key="criterion.name">
                <td>{{ criterion.name }}</td>
                <td>
                  <span v-if="criterion.mark">{{ criterion.mark }}</span>
                  <span v-else class="results-pending">—</span>
                  <span class="results-max"> / {{ criterion.max_mark }}</span>
                </td>
                <td>{{ criterion.comment }}</td>
              </tr>
            </tbody>
          </table>
        </article>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  downloadMyCertificate,
  downloadMySummary,
  fetchMyGrades,
  type MyGradesPayload,
} from '@/utils/gradingAPI'

const payload = ref<MyGradesPayload | null>(null)
const isLoading = ref(true)
const loadError = ref<string | null>(null)
const downloadingSummary = ref(false)
const downloadingCert = ref(false)

async function load() {
  isLoading.value = true
  loadError.value = null
  try {
    payload.value = await fetchMyGrades()
  } catch (err) {
    // The release gate raises 403 pre-release. Surface a friendly message
    // instead of the raw error so the tab (if rendered by mistake) still
    // reads well.
    const status = (err as { response?: Response }).response?.status
    if (status === 403) {
      loadError.value = 'Marks have not been released yet.'
    } else {
      loadError.value = (err as Error).message || 'Failed to load marks.'
    }
  } finally {
    isLoading.value = false
  }
}

async function onDownloadSummary() {
  if (!payload.value) return
  downloadingSummary.value = true
  try {
    await downloadMySummary(payload.value.group.group_name)
  } catch (err) {
    loadError.value = `Download failed: ${(err as Error).message}`
  } finally {
    downloadingSummary.value = false
  }
}

async function onDownloadCert() {
  if (!payload.value) return
  downloadingCert.value = true
  try {
    await downloadMyCertificate(payload.value.group.group_name)
  } catch (err) {
    loadError.value = `Download failed: ${(err as Error).message}`
  } finally {
    downloadingCert.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.results-tab {
  padding: 1rem;
  display: grid;
  gap: 1rem;
}
.results-header {
  display: grid;
  gap: 0.25rem;
}
.results-subtitle {
  color: var(--color-text-muted, #666);
  font-size: 0.9rem;
}
.results-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.5rem;
}
.btn {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 6px;
  background: white;
  cursor: pointer;
}
.btn:disabled {
  opacity: 0.6;
  cursor: default;
}
.btn-primary {
  background: var(--color-primary, #1f6feb);
  color: white;
  border-color: var(--color-primary, #1f6feb);
}
.results-component {
  border: 1px solid var(--color-border, #eee);
  border-radius: 8px;
  padding: 0.75rem 1rem;
}
.results-component h4 {
  margin: 0 0 0.5rem 0;
}
.results-table {
  width: 100%;
  border-collapse: collapse;
}
.results-table th,
.results-table td {
  padding: 0.4rem 0.5rem;
  text-align: left;
  border-bottom: 1px solid var(--color-border, #eee);
  vertical-align: top;
}
.results-max {
  color: var(--color-text-muted, #888);
  font-size: 0.85rem;
}
.results-pending {
  color: var(--color-text-muted, #888);
}
.results-empty {
  color: var(--color-text-muted, #888);
  font-style: italic;
}
.results-error {
  padding: 1rem;
  border: 1px solid #f0c;
  border-radius: 8px;
  background: #fff0f3;
}
</style>
