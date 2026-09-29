<template>
  <!-- The group's released results: its marks and marks summary, and its
       students' and mentors' certificates, as the results email carries them. -->
  <div class="group-results">
    <p v-if="actionError" class="group-results__error" role="alert">{{ actionError }}</p>

    <section v-if="!results.has_submission" class="card group-results__card">
      <h2 class="card-title">Results</h2>
      <p class="group-results__muted">
        This group didn't make a submission, so there are no results to show.
      </p>
    </section>

    <template v-else>
      <section class="card group-results__card" data-testid="results-marks">
        <header class="group-results__head">
          <h2 class="card-title">Marks</h2>
          <button
            v-if="results.marks_released"
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="downloading === 'summary'"
            @click="downloadSummary"
          >
            {{ downloading === 'summary' ? 'Preparing…' : 'Download Marks Summary' }}
          </button>
        </header>
        <p v-if="!results.marks_released" class="group-results__muted">
          Marks haven't been released yet.
        </p>
        <article v-for="component in markedComponents" :key="component.code" class="group-results__component">
          <h3 class="group-results__component-name">{{ component.name }}</h3>
          <p v-if="!component.submitted" class="group-results__muted">Not submitted.</p>
          <div v-else class="group-results__scroll">
            <table class="group-results__table">
              <!-- The same columns in every part's table, so they line up. -->
              <colgroup>
                <col class="group-results__col-criterion" />
                <col class="group-results__col-mark" />
                <col />
              </colgroup>
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
                  <td class="group-results__mark">
                    <span v-if="criterion.mark">{{ criterion.mark }}</span>
                    <span v-else class="group-results__muted">—</span>
                    <span class="group-results__muted"> / {{ criterion.max_mark }}</span>
                  </td>
                  <td class="group-results__comment">{{ criterion.comment }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </section>

      <section class="card group-results__card" data-testid="results-certificates">
        <h2 class="card-title">Certificates</h2>
        <p v-if="!results.certificates_released" class="group-results__muted">
          Certificates haven't been released yet.
        </p>
        <p v-else-if="results.certificates_withheld" class="group-results__muted">
          As a finalist team, your certificates are handed out at the Symposium.
        </p>
        <p v-else-if="!results.certificates.length" class="group-results__muted">
          No certificates for this group.
        </p>
        <ul v-else class="group-results__certificates">
          <li v-for="certificate in results.certificates" :key="certificate.user_id">
            <span>
              {{ certificate.name }}
              <span class="group-results__muted">
                · {{ certificate.kind === 'student' ? 'Student' : 'Mentor' }} Certificate
              </span>
            </span>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="downloading === certificate.user_id"
              @click="downloadCertificate(certificate)"
            >
              {{ downloading === certificate.user_id ? 'Preparing…' : 'Download' }}
            </button>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  downloadGroupCertificate,
  downloadGroupSummary,
  type GroupCertificate,
  type GroupResults
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const props = defineProps<{ groupId: string; results: GroupResults }>()

// The parts that carry marks; one without criteria has nothing to show.
const markedComponents = computed(() =>
  props.results.components.filter((component) => component.criteria.length)
)

const downloading = ref<'summary' | number | null>(null)
const actionError = ref('')

const download = async (which: 'summary' | number, run: () => Promise<void>) => {
  downloading.value = which
  actionError.value = ''
  try {
    await run()
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    downloading.value = null
  }
}

const downloadSummary = () =>
  download('summary', () => downloadGroupSummary(props.groupId, props.results.summary_file_name))

const downloadCertificate = (certificate: GroupCertificate) =>
  download(certificate.user_id, () => downloadGroupCertificate(props.groupId, certificate))
</script>

<style scoped>
.group-results {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.group-results__card {
  height: auto;
  min-height: 0;
  padding: 1.25rem 1.5rem;
  overflow: visible;
}

.group-results__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
}

.group-results__muted {
  color: var(--text-muted);
}

.group-results__error {
  color: var(--danger);
  margin: 0;
}

.group-results__component + .group-results__component {
  margin-top: 1.25rem;
}

.group-results__component-name {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 0.5rem;
}

.group-results__scroll {
  overflow-x: auto;
  border: 1px solid var(--border-light);
  border-radius: 8px;
}

.group-results__table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.group-results__col-criterion {
  width: 30%;
}

.group-results__col-mark {
  width: 9rem;
}

.group-results__table th,
.group-results__table td {
  padding: 0.55rem 0.75rem;
  text-align: left;
  vertical-align: top;
  border-bottom: 1px solid var(--border-light);
}

.group-results__table thead th {
  color: var(--text-muted);
  font-weight: 600;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.group-results__table tbody tr:last-child td {
  border-bottom: none;
}

.group-results__mark {
  white-space: nowrap;
}

.group-results__comment {
  white-space: pre-line;
}

.group-results__certificates {
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0;
}

.group-results__certificates li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.55rem 0;
  border-bottom: 1px solid var(--border-light);
}

.group-results__certificates li:last-child {
  border-bottom: none;
}
</style>
