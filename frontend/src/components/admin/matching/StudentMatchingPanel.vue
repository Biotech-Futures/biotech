<template>
  <div class="student-matching">
    <div class="student-matching__header">
      <div class="student-matching__title">
        <h2>Student Matching</h2>
        <span v-if="hasRun" class="student-matching__badge">
          {{ recommendedCount }} proposed
        </span>
        <span
          v-if="hasRun && unmatchedStudents.length > 0"
          class="student-matching__badge student-matching__badge--warn"
        >
          <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
          {{ unmatchedStudents.length }} unmatched
        </span>
      </div>

      <div class="student-matching__actions">
        <button type="button" class="btn btn-sm btn-primary" :disabled="loading" @click="run">
          <i class="fas fa-shuffle" aria-hidden="true"></i>
          <span>{{ loading ? 'Matching...' : 'Run match' }}</span>
        </button>
        <button
          type="button"
          class="btn btn-sm btn-outline"
          :disabled="!hasRun || confirming || assignmentCount === 0"
          @click="onConfirm"
        >
          <i class="fas fa-check" aria-hidden="true"></i>
          <span>{{ confirming ? 'Confirming...' : `Confirm ${assignmentCount || ''}`.trim() }}</span>
        </button>
        <button
          type="button"
          class="btn btn-sm btn-outline"
          :disabled="!hasRun || loading || confirming"
          @click="reset"
        >
          <i class="fas fa-rotate-left" aria-hidden="true"></i>
          <span>Reset board</span>
        </button>
      </div>
    </div>

    <p v-if="error" class="student-matching__error" role="alert">
      <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
      <span>{{ error }}</span>
      <button type="button" class="btn btn-sm btn-outline" @click="run">Retry</button>
    </p>

    <p v-if="loading" class="student-matching__loading">
      <span class="student-matching__spinner" aria-hidden="true"></span>
      Running the matcher...
    </p>

    <!-- Distinct from "no results": an unrun matcher must never look like a
         finished one with nothing left to do. -->
    <p v-else-if="!hasRun" class="student-matching__empty">
      Click <strong>Run match</strong> to generate group suggestions. Nothing is saved
      until you confirm.
    </p>

    <p v-else-if="isEmpty" class="student-matching__empty">
      The matcher returned no suggestions. Every student may already be grouped.
    </p>

    <template v-else>
      <!-- Proposed groups -->
      <section v-if="recommendations.length" class="student-matching__section">
        <h3 class="student-matching__section-title">Proposed groups</h3>
        <div class="student-matching__grid">
          <article
            v-for="group in recommendations"
            :key="group.id"
            class="student-matching__group"
          >
            <header class="student-matching__group-head">
              <span class="student-matching__group-name">{{ group.groupName }}</span>
              <span class="student-matching__muted">
                {{ group.existingStudents.length + group.recommendStudents.length }}<template
                  v-if="group.maxSize"
                >/{{ group.maxSize }}</template>
              </span>
            </header>

            <p v-if="group.tutor" class="student-matching__muted">
              Mentor: {{ group.tutor.name }}
            </p>

            <ul class="student-matching__students">
              <li
                v-for="student in group.existingStudents"
                :key="`existing-${student.id}`"
                class="student-matching__student student-matching__student--existing"
              >
                <span>{{ student.name }}</span>
                <span class="student-matching__muted">already in group</span>
              </li>

              <li
                v-for="entry in group.recommendStudents"
                :key="`proposed-${entry.student.id}`"
                class="student-matching__student"
              >
                <div class="student-matching__student-main">
                  <span>{{ entry.student.name }}</span>
                  <span class="student-matching__score">{{ Math.round(entry.score) }}</span>
                </div>
                <span v-if="entry.reason" class="student-matching__muted">{{ entry.reason }}</span>
                <span v-if="entry.student.interests.length" class="student-matching__muted">
                  {{ entry.student.interests.join(', ') }}
                </span>
              </li>
            </ul>
          </article>
        </div>
      </section>

      <!-- Unmatched -->
      <section v-if="unmatchedStudents.length" class="student-matching__section">
        <h3 class="student-matching__section-title">
          Unmatched students ({{ unmatchedStudents.length }})
        </h3>
        <ul class="student-matching__list">
          <li v-for="entry in unmatchedStudents" :key="entry.student.id" class="student-matching__row">
            <span>{{ entry.student.name }}</span>
            <span class="student-matching__muted">
              {{ entry.reason || 'No compatible group found.' }}
            </span>
          </li>
        </ul>
      </section>

      <!-- Groups with spare seats -->
      <section v-if="notFullGroups.length" class="student-matching__section">
        <h3 class="student-matching__section-title">
          Groups with spare seats ({{ notFullGroups.length }})
        </h3>
        <ul class="student-matching__list">
          <li v-for="group in notFullGroups" :key="group.id" class="student-matching__row">
            <span>{{ group.groupName }}</span>
            <span class="student-matching__muted">
              {{ group.studentCount }} member<template v-if="group.studentCount !== 1">s</template>
              · {{ group.availableSeats }} seat<template v-if="group.availableSeats !== 1">s</template>
              free
            </span>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { useStudentMatching } from '@/composables/admin/useStudentMatching'

// Drag-to-reassign is not wired up yet — the board currently confirms the
// algorithm's proposal as-is. `assignStudent()` on the composable is the hook
// the drag layer will call once a library is agreed.
const {
  loading,
  confirming,
  error,
  hasRun,
  recommendations,
  unmatchedStudents,
  notFullGroups,
  recommendedCount,
  assignmentCount,
  isEmpty,
  run,
  reset,
  confirm
} = useStudentMatching()

const onConfirm = () => {
  void confirm()
}
</script>

<style scoped>
.student-matching {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.student-matching__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.student-matching__title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.student-matching__title h2 {
  margin: 0;
}

.student-matching__badge {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background-color: var(--light-green);
  color: var(--dark-green);
  font-size: 0.75rem;
  font-weight: 600;
}

.student-matching__badge--warn {
  background-color: rgba(255, 193, 7, 0.15);
  color: #8a6100;
}

.student-matching__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.student-matching__error {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  padding: 0.6rem 0.85rem;
  border: 1px solid var(--danger);
  border-radius: 8px;
  color: var(--danger);
  font-size: 0.9rem;
}

.student-matching__loading,
.student-matching__empty {
  margin: 0;
  padding: 2rem;
  border: 1px dashed var(--border-light);
  border-radius: 8px;
  color: var(--text-muted);
  text-align: center;
}

.student-matching__spinner {
  display: inline-block;
  width: 0.9rem;
  height: 0.9rem;
  margin-right: 0.4rem;
  border: 2px solid var(--border-light);
  border-top-color: var(--dark-green);
  border-radius: 50%;
  animation: student-matching-spin 0.7s linear infinite;
}

@keyframes student-matching-spin {
  to {
    transform: rotate(360deg);
  }
}

.student-matching__section {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.student-matching__section-title {
  margin: 0;
  font-size: 1rem;
}

.student-matching__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 0.75rem;
}

.student-matching__group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.85rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--surface-elevated);
}

.student-matching__group-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
}

.student-matching__group-name {
  font-weight: 600;
}

.student-matching__students,
.student-matching__list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.student-matching__student {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.45rem 0.55rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background-color: var(--bg-light);
  font-size: 0.85rem;
}

.student-matching__student--existing {
  flex-direction: row;
  justify-content: space-between;
  opacity: 0.75;
}

.student-matching__student-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.student-matching__score {
  padding: 0 0.4rem;
  border-radius: 999px;
  background-color: var(--light-green);
  color: var(--dark-green);
  font-size: 0.75rem;
  font-weight: 600;
}

.student-matching__row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.5rem 0.65rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  font-size: 0.85rem;
}

.student-matching__muted {
  color: var(--text-muted);
  font-size: 0.8rem;
}
</style>
