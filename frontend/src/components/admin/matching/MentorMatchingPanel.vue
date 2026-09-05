<template>
  <div class="mentor-matching">
    <div class="mentor-matching__header">
      <div class="mentor-matching__title">
        <h2>Mentor Matching</h2>
        <span v-if="hasRun" class="mentor-matching__badge">
          {{ matchableRecommendations.length }} matchable
        </span>
        <span
          v-if="hasRun && unmatchedRecommendations.length > 0"
          class="mentor-matching__badge mentor-matching__badge--warn"
        >
          <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
          {{ unmatchedRecommendations.length }} unmatched
        </span>
      </div>

      <div class="mentor-matching__actions">
        <label class="mentor-matching__toggle">
          <input v-model="showFullMentors" type="checkbox" />
          <span>Show mentors at capacity</span>
        </label>
        <button type="button" class="btn btn-sm btn-primary" :disabled="loading" @click="run">
          <i class="fas fa-link" aria-hidden="true"></i>
          <span>{{ loading ? 'Matching...' : 'Run match' }}</span>
        </button>
        <button
          type="button"
          class="btn btn-sm btn-outline"
          :disabled="!hasRun || confirming || selectedCount === 0"
          @click="onConfirm"
        >
          <i class="fas fa-check" aria-hidden="true"></i>
          <span>{{ confirming ? 'Confirming...' : `Confirm ${selectedCount || ''}`.trim() }}</span>
        </button>
      </div>
    </div>

    <!-- Mode selector -->
    <fieldset class="mentor-matching__modes">
      <legend class="mentor-matching__modes-legend">Matching mode</legend>
      <div class="mentor-matching__mode-buttons" role="radiogroup" aria-label="Matching mode">
        <button
          v-for="entry in modes"
          :key="entry.value"
          type="button"
          role="radio"
          :aria-checked="mode === entry.value"
          class="mentor-matching__mode"
          :class="{ 'mentor-matching__mode--active': mode === entry.value }"
          :disabled="loading"
          @click="setMode(entry.value)"
        >
          {{ entry.label }}
        </button>
      </div>
      <p class="mentor-matching__muted">{{ modeDescription }}</p>
    </fieldset>

    <p
      v-if="capacityShortage"
      class="mentor-matching__warning"
      role="status"
    >
      <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
      <span>
        Not enough mentor capacity: {{ unmatchedRecommendations.length }} group<template
          v-if="unmatchedRecommendations.length !== 1"
        >s</template>
        still need a mentor but only {{ capacityShortage.totalCapacity }} place<template
          v-if="capacityShortage.totalCapacity !== 1"
        >s</template>
        remain. Changing mode will not resolve this.
      </span>
    </p>

    <p v-if="error" class="mentor-matching__error" role="alert">
      <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
      <span>{{ error }}</span>
      <button type="button" class="btn btn-sm btn-outline" @click="run">Retry</button>
    </p>

    <p v-if="loading" class="mentor-matching__loading">
      <span class="mentor-matching__spinner" aria-hidden="true"></span>
      Running the matcher...
    </p>

    <p v-else-if="!hasRun" class="mentor-matching__empty">
      Choose a mode and click <strong>Run match</strong>. Nothing is saved until you confirm.
    </p>

    <p v-else-if="recommendations.length === 0" class="mentor-matching__empty">
      No recommendations returned. Every group may already have a mentor.
    </p>

    <div v-else class="mentor-matching__table-wrap">
      <table class="mentor-matching__table">
        <thead>
          <tr>
            <th class="mentor-matching__check-col">
              <input
                type="checkbox"
                :checked="allSelected"
                :disabled="matchableRecommendations.length === 0"
                aria-label="Select all matchable recommendations"
                @change="toggleAll"
              />
            </th>
            <th>Group</th>
            <th>Country</th>
            <th>Students</th>
            <th>Recommended mentor</th>
            <th>Capacity</th>
            <th>Score</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="entry in recommendations"
            :key="entry.group.groupId"
            :class="{ 'mentor-matching__row--unmatched': !entry.recommendedMentor }"
          >
            <td class="mentor-matching__check-col">
              <input
                v-if="entry.recommendedMentor"
                type="checkbox"
                :checked="selectedGroupIds.has(entry.group.groupId)"
                :aria-label="`Select ${entry.group.groupName}`"
                @change="toggleOne(entry.group.groupId)"
              />
            </td>
            <td>
              <span class="mentor-matching__group-name">{{ entry.group.groupName }}</span>
              <span v-if="entry.group.studentInterests.length" class="mentor-matching__muted">
                {{ entry.group.studentInterests.join(', ') }}
              </span>
            </td>
            <td>{{ entry.group.countryName || 'Unknown' }}</td>
            <td>{{ entry.group.studentCount }}</td>
            <td>
              <template v-if="entry.recommendedMentor">
                <span>{{ entry.recommendedMentor.name }}</span>
                <span v-if="entry.recommendedMentor.institution" class="mentor-matching__muted">
                  {{ entry.recommendedMentor.institution }}
                </span>
              </template>
              <span v-else class="mentor-matching__muted">
                {{ entry.reason || 'No compatible mentor' }}
              </span>
            </td>
            <td>
              <span v-if="entry.recommendedMentor">
                {{ entry.recommendedMentor.remainingCapacity }}
              </span>
              <span v-else class="mentor-matching__muted">—</span>
            </td>
            <td>
              <span v-if="entry.recommendedMentor" class="mentor-matching__score">
                {{ Math.round(entry.score) }}
              </span>
              <span v-else class="mentor-matching__muted">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="hasRun" class="mentor-matching__muted">
      {{ availableMentors.length }} mentor<template v-if="availableMentors.length !== 1">s</template>
      shown<template v-if="!showFullMentors"> (mentors at capacity hidden)</template>.
    </p>
  </div>
</template>

<script setup lang="ts">
import {
  MENTOR_MATCH_MODES,
  useMentorMatching
} from '@/composables/admin/useMentorMatching'

const modes = MENTOR_MATCH_MODES

const {
  loading,
  confirming,
  error,
  hasRun,
  mode,
  modeDescription,
  recommendations,
  matchableRecommendations,
  unmatchedRecommendations,
  availableMentors,
  showFullMentors,
  capacityShortage,
  selectedGroupIds,
  selectedCount,
  allSelected,
  toggleOne,
  toggleAll,
  run,
  setMode,
  confirm
} = useMentorMatching()

const onConfirm = () => {
  void confirm()
}
</script>

<style scoped>
.mentor-matching {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.mentor-matching__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.mentor-matching__title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.mentor-matching__title h2 {
  margin: 0;
}

.mentor-matching__badge {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background-color: var(--light-green);
  color: var(--dark-green);
  font-size: 0.75rem;
  font-weight: 600;
}

.mentor-matching__badge--warn {
  background-color: rgba(255, 193, 7, 0.15);
  color: #8a6100;
}

.mentor-matching__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.mentor-matching__toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.mentor-matching__modes {
  margin: 0;
  padding: 0.75rem 0.85rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--bg-light);
}

.mentor-matching__modes-legend {
  padding: 0 0.35rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-muted);
}

.mentor-matching__mode-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-bottom: 0.5rem;
}

.mentor-matching__mode {
  padding: 0.3rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background-color: var(--surface-elevated);
  color: var(--charcoal);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
}

.mentor-matching__mode--active {
  border-color: var(--dark-green);
  background-color: var(--light-green);
  color: var(--dark-green);
}

.mentor-matching__mode:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mentor-matching__warning,
.mentor-matching__error {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  padding: 0.6rem 0.85rem;
  border-radius: 8px;
  font-size: 0.9rem;
}

.mentor-matching__warning {
  border: 1px solid var(--warning);
  color: #8a6100;
}

.mentor-matching__error {
  border: 1px solid var(--danger);
  color: var(--danger);
}

.mentor-matching__loading,
.mentor-matching__empty {
  margin: 0;
  padding: 2rem;
  border: 1px dashed var(--border-light);
  border-radius: 8px;
  color: var(--text-muted);
  text-align: center;
}

.mentor-matching__spinner {
  display: inline-block;
  width: 0.9rem;
  height: 0.9rem;
  margin-right: 0.4rem;
  border: 2px solid var(--border-light);
  border-top-color: var(--dark-green);
  border-radius: 50%;
  animation: mentor-matching-spin 0.7s linear infinite;
}

@keyframes mentor-matching-spin {
  to {
    transform: rotate(360deg);
  }
}

.mentor-matching__table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border-light);
  border-radius: 8px;
}

.mentor-matching__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.mentor-matching__table th,
.mentor-matching__table td {
  padding: 0.5rem 0.65rem;
  text-align: left;
  border-bottom: 1px solid var(--border-light);
  vertical-align: top;
}

.mentor-matching__table th {
  background-color: var(--bg-light);
  font-size: 0.8rem;
  color: var(--text-muted);
}

.mentor-matching__table tbody tr:last-child td {
  border-bottom: none;
}

.mentor-matching__check-col {
  width: 38px;
}

.mentor-matching__row--unmatched {
  background-color: rgba(220, 53, 69, 0.04);
}

.mentor-matching__group-name {
  display: block;
  font-weight: 600;
}

.mentor-matching__score {
  padding: 0 0.4rem;
  border-radius: 999px;
  background-color: var(--light-green);
  color: var(--dark-green);
  font-weight: 600;
}

.mentor-matching__muted {
  display: block;
  color: var(--text-muted);
  font-size: 0.8rem;
}
</style>
