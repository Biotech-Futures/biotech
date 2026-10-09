<template>
  <div class="student-matching">
    <!-- Toolbar -->
    <div class="student-matching__header">
      <div class="student-matching__title">
        <h2>Student Matching</h2>
        <span v-if="hasRun" class="student-matching__badge">
          {{ assignmentCount }} proposed
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
          <span>{{ confirming ? 'Confirming...' : 'Confirm assignments' }}</span>
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

    <!-- Stat tiles -->
    <div v-if="hasRun" class="student-matching__stats">
      <div class="student-matching__stat">
        <p class="student-matching__stat-label">Total groups</p>
        <p class="student-matching__stat-value">{{ totalGroups }}</p>
      </div>
      <div class="student-matching__stat">
        <p class="student-matching__stat-label">Visible groups</p>
        <p class="student-matching__stat-value">{{ visibleGroupCount }}</p>
      </div>
      <div class="student-matching__stat">
        <p class="student-matching__stat-label">Open seats</p>
        <p class="student-matching__stat-value">{{ totalOpenSeats }}</p>
      </div>
      <div class="student-matching__stat">
        <p class="student-matching__stat-label">Waiting students</p>
        <p class="student-matching__stat-value">{{ waitingCount }}</p>
      </div>
    </div>

    <p v-if="error" class="student-matching__error" role="alert">
      <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
      <span>{{ error }}</span>
      <button type="button" class="btn btn-sm btn-outline" @click="run">Retry</button>
    </p>

    <p v-if="loading" class="student-matching__placeholder">
      <span class="student-matching__spinner" aria-hidden="true"></span>
      Running the matcher...
    </p>

    <!-- An unrun board must not read as a finished one with nothing to do. -->
    <p v-else-if="!hasRun" class="student-matching__placeholder">
      Click <strong>Run match</strong> to load recommended groups. Nothing is saved
      until you confirm.
    </p>

    <p v-else-if="isEmpty" class="student-matching__placeholder">
      The matcher returned no groups. Every student may already be placed.
    </p>

    <template v-else>
      <!-- Search + filter -->
      <div class="student-matching__filters">
        <input
          v-model="search"
          type="search"
          class="student-matching__search"
          placeholder="Search by group or tutor"
          aria-label="Search by group or tutor"
        />
        <select v-model="groupFilter" class="student-matching__select" aria-label="Filter groups">
          <option v-for="option in groupFilters" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </div>

      <!-- Waiting area -->
      <section class="student-matching__waiting">
        <div class="student-matching__section-head">
          <h3 class="student-matching__section-title">Waiting Area</h3>
          <span class="student-matching__badge">{{ waitingCount }} students</span>
        </div>
        <!-- The hint sits outside the sortable container, not in a #footer slot:
             a footer renders a real sibling node that SortableJS will happily
             insert the dragged chip *after*, so the chip jumped to the right
             mid-drag and snapped left once Vue re-rendered the list. -->
        <div class="student-matching__dropzone-wrap">
          <p v-if="waiting.length === 0" class="student-matching__dropzone-hint">
            Drop students here to keep them waiting.
          </p>
          <draggable
            v-model="waiting"
            :group="DRAG_GROUP"
            :item-key="studentKey"
            drag-class="student-chip--dragging"
            class="student-matching__dropzone student-matching__dropzone--waiting"
            @start="isDragging = true"
            @end="isDragging = false"
          >
          <!-- `moved` is hardcoded: anyone in the waiting area is by definition
               out of their recommended group. Keep comments outside #item —
               vuedraggable requires that slot to render exactly one node, and
               dev builds retain comment nodes. -->
          <template #item="{ element }">
            <StudentChip
              :student="element.student"
              :entry="element"
              :suppressed="isDragging"
              moved
              :recommended-group-name="recommendedGroupOf(element.student.id)?.groupName ?? null"
            />
          </template>
          </draggable>
        </div>
      </section>

      <!-- Group cards -->
      <div class="student-matching__board">
        <article
          v-for="group in visibleGroups"
          :key="group.id"
          class="student-matching__group"
        >
          <header class="student-matching__group-head">
            <div>
              <p class="student-matching__group-name">{{ group.groupName }}</p>
              <p class="student-matching__muted">{{ group.tutor?.name ?? 'Unassigned' }}</p>
            </div>
            <span class="student-matching__capacity">
              {{ seatsUsed(group) }}/{{ group.maxSize }}
            </span>
          </header>

          <div v-if="group.sharedInterests.length" class="student-matching__interests">
            <p class="student-matching__label">Shared interests</p>
            <div class="student-matching__chips">
              <span v-for="interest in group.sharedInterests" :key="interest" class="student-matching__chip">
                {{ interest }}
              </span>
            </div>
          </div>

          <div v-if="group.existingStudents.length" class="student-matching__existing">
            <p class="student-matching__label">Existing students</p>
            <!-- Outside any draggable list, so these can't be picked up. They
                 still get a detail card, minus score/reason — an existing member
                 was never scored against the group they are already in. -->
            <StudentChip
              v-for="student in group.existingStudents"
              :key="student.id"
              :student="student"
              fixed
              :suppressed="isDragging"
              class="student-matching__existing-chip"
            />
          </div>

          <div class="student-matching__proposed">
            <p class="student-matching__label">Recommended / moved</p>
            <div class="student-matching__dropzone-wrap">
              <p
                v-if="(buckets[String(group.id)] ?? []).length === 0"
                class="student-matching__dropzone-hint"
              >
                Drop students here
              </p>
              <draggable
                v-model="buckets[String(group.id)]"
                :group="DRAG_GROUP"
                :item-key="studentKey"
                drag-class="student-chip--dragging"
                class="student-matching__dropzone"
                @start="isDragging = true"
                @end="isDragging = false"
              >
              <template #item="{ element }">
                <StudentChip
                  :student="element.student"
                  :entry="element"
                  :suppressed="isDragging"
                  :moved="!isInRecommendedGroup(element.student.id, group.id)"
                  :recommended-group-name="recommendedGroupOf(element.student.id)?.groupName ?? null"
                />
              </template>
              </draggable>
            </div>
          </div>
        </article>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import draggable from 'vuedraggable'
import { GROUP_FILTERS, useStudentMatching } from '@/composables/admin/useStudentMatching'
import StudentChip from '@/components/admin/matching/StudentChip.vue'
import type { RecommendedStudent } from '@/utils/adminMatching'

// Shared name means students can move between any bucket and the waiting area.
const DRAG_GROUP = { name: 'matching-students' }

const groupFilters = GROUP_FILTERS

const studentKey = (entry: RecommendedStudent) => String(entry.student.id)

// Hover cards are hidden mid-drag so they can't cover the drop zones you're
// aiming at (the reference app does the same via `suppressTooltip`).
const isDragging = ref(false)

const {
  loading,
  confirming,
  error,
  hasRun,
  buckets,
  waiting,
  search,
  groupFilter,
  visibleGroups,
  totalGroups,
  visibleGroupCount,
  totalOpenSeats,
  waitingCount,
  assignmentCount,
  isEmpty,
  seatsUsed,
  recommendedGroupOf,
  isInRecommendedGroup,
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
  gap: 1rem;
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

.student-matching__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

/* The shared .btn class doesn't space an icon from its label. */
.student-matching .btn {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}

.student-matching__badge {
  padding: 0.15rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 600;
}

/* Stats */
.student-matching__stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.6rem;
}

.student-matching__stat {
  padding: 0.6rem 0.8rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--bg-light);
}

.student-matching__stat-label {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.75rem;
}

.student-matching__stat-value {
  margin: 0.15rem 0 0;
  font-size: 1.1rem;
  font-weight: 700;
}

/* Filters */
.student-matching__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

/* Form controls don't inherit font-family from body. */
.student-matching__search,
.student-matching__select {
  font-family: inherit;
}

.student-matching__search {
  flex: 1 1 260px;
  min-width: 0;
  padding: 0.45rem 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--surface-elevated);
  color: var(--charcoal);
  font-size: 0.9rem;
}

.student-matching__select {
  padding: 0.45rem 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--surface-elevated);
  color: var(--charcoal);
  font-size: 0.9rem;
}

/* Sections */
.student-matching__section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.4rem;
}

.student-matching__section-title {
  margin: 0;
  font-size: 1rem;
}

.student-matching__label {
  margin: 0 0 0.3rem;
  color: var(--text-muted);
  font-size: 0.75rem;
}

/* Drop zones */
.student-matching__dropzone {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-height: 3rem;
  padding: 0.5rem;
  border: 1px dashed var(--border-light);
  border-radius: 8px;
  background-color: var(--bg-light);
}

.student-matching__dropzone--waiting {
  flex-direction: row;
  flex-wrap: wrap;
  min-height: 4.5rem;
  align-items: flex-start;
}

/* The hint is overlaid rather than being a sibling inside the sortable list,
   so SortableJS has no non-chip node to position the dragged item against. */
.student-matching__dropzone-wrap {
  position: relative;
}

.student-matching__dropzone-hint {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  color: var(--text-muted);
  font-size: 0.8rem;
  text-align: center;
  pointer-events: none;
}

/* Board */
.student-matching__board {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
  max-height: 70vh;
  overflow-y: auto;
  /* Matches the inter-card gap so the inset reads as deliberate rather than as
     a hairline crack between the card border and the container border. */
  padding: 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--bg-light);
}

.student-matching__group {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.85rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--surface-elevated);
}

.student-matching__group-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
}

.student-matching__group-name {
  margin: 0;
  font-weight: 700;
}

.student-matching__capacity {
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  background-color: var(--charcoal);
  color: var(--white);
  font-size: 0.75rem;
  font-weight: 700;
}

.student-matching__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.student-matching__chip {
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  background-color: var(--light-green);
  color: var(--dark-green);
  font-size: 0.75rem;
  font-weight: 600;
}

.student-matching__student {
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background-color: var(--surface-elevated);
  font-size: 0.85rem;
  font-weight: 600;
}

.student-matching__existing-chip {
  margin-bottom: 0.35rem;
}

/* States */
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

.student-matching__placeholder {
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

.student-matching__muted {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.8rem;
}
</style>
