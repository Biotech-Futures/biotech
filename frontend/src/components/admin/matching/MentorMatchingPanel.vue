<template>
  <div class="mentor-matching">
    <!-- Header -->
    <div class="mentor-matching__head">
      <h2 class="mentor-matching__title">Mentor Assignment</h2>
      <p class="mentor-matching__subtitle">
        Run the algorithm, review recommendations, then confirm selected assignments.
      </p>
    </div>

    <!-- Matching mode + actions -->
    <div class="mentor-matching__controls">
      <div class="mentor-matching__modes" role="radiogroup" aria-label="Matching mode">
        <span v-for="entry in modes" :key="entry.value" class="mentor-matching__mode-wrap">
          <button
            type="button"
            role="radio"
            :aria-checked="mode === entry.value"
            :aria-describedby="`mode-desc-${entry.value}`"
            class="mentor-matching__mode"
            :class="{ 'mentor-matching__mode--active': mode === entry.value }"
            :disabled="loading"
            @click="setMode(entry.value)"
          >
            {{ entry.label }}
          </button>
          <!-- Description on hover/focus rather than a permanent line of copy
               under the controls. -->
          <span :id="`mode-desc-${entry.value}`" class="mentor-matching__mode-tip" role="tooltip">
            {{ entry.description }}
          </span>
        </span>
      </div>

      <button type="button" class="btn btn-sm btn-primary" :disabled="loading" @click="run">
        <i class="fas fa-shuffle" aria-hidden="true"></i>
        <span>{{ loading ? 'Matching...' : 'Run match' }}</span>
      </button>
      <button
        type="button"
        class="btn btn-sm btn-outline"
        :disabled="!hasRun || confirming || selectedCount === 0"
        @click="onConfirm"
      >
        <i class="fas fa-check" aria-hidden="true"></i>
        <span>{{ confirming ? 'Confirming...' : `Confirm selected (${selectedCount})` }}</span>
      </button>
    </div>

    <!-- Statistics -->
    <div class="mentor-matching__stats">
      <div class="mentor-matching__stat">
        <p class="mentor-matching__stat-label">Unmatched groups</p>
        <p class="mentor-matching__stat-value">{{ unmatchedGroups.length }}</p>
      </div>
      <div class="mentor-matching__stat">
        <p class="mentor-matching__stat-label">Recommendations</p>
        <p class="mentor-matching__stat-value">{{ matchableRecommendations.length }}</p>
      </div>
      <div class="mentor-matching__stat">
        <p class="mentor-matching__stat-label">No mentor found</p>
        <p class="mentor-matching__stat-value">{{ unmatchedRecommendations.length }}</p>
      </div>
      <div class="mentor-matching__stat">
        <p class="mentor-matching__stat-label">Selected</p>
        <p class="mentor-matching__stat-value">{{ selectedCount }}</p>
      </div>
    </div>

    <p v-if="capacityShortage" class="mentor-matching__warning" role="status">
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

    <!-- Reference tables: shown only until a match is run, at which point the
         recommendations table below takes their place. -->
    <div v-if="!hasRun && !loading" class="mentor-matching__columns">
      <!-- Unmatched groups -->
      <section class="mentor-matching__panel">
        <header class="mentor-matching__panel-head">
          <h3>Unmatched Groups</h3>
          <span class="mentor-matching__count">{{ unmatchedGroups.length }}</span>
        </header>

        <p v-if="loadingLists" class="mentor-matching__empty">Loading groups...</p>
        <p v-else-if="unmatchedGroups.length === 0" class="mentor-matching__empty">
          Every group has a mentor.
        </p>
        <ul v-else class="mentor-matching__list">
          <li v-for="group in unmatchedGroups" :key="group.groupId">
            <button
              type="button"
              class="mentor-matching__row"
              :aria-expanded="expandedGroupIds.has(group.groupId)"
              @click="toggleGroupExpanded(group.groupId)"
            >
              <i
                class="fas mentor-matching__chevron"
                :class="expandedGroupIds.has(group.groupId) ? 'fa-chevron-down' : 'fa-chevron-right'"
                aria-hidden="true"
              ></i>
              <span class="mentor-matching__row-name">{{ group.groupName }}</span>
              <span class="mentor-matching__pill">{{ group.countryName || 'Unknown' }}</span>
            </button>

            <div v-if="expandedGroupIds.has(group.groupId)" class="mentor-matching__detail">
              <p class="mentor-matching__detail-label">Students: {{ group.studentCount }}</p>

              <div v-if="group.students?.length" class="mentor-matching__cards">
                <!-- Same shape as the student-matching cards: name, then the
                     interests the matcher scores on. -->
                <div
                  v-for="student in group.students"
                  :key="student.name"
                  class="mentor-matching__student-card"
                >
                  <span class="mentor-matching__student-name">{{ student.name }}</span>
                  <div v-if="student.interests.length" class="mentor-matching__chips">
                    <span
                      v-for="interest in student.interests"
                      :key="interest"
                      class="mentor-matching__chip"
                    >
                      {{ interest }}
                    </span>
                  </div>
                  <span v-else class="mentor-matching__muted">No interests recorded</span>
                </div>
              </div>
              <p v-else class="mentor-matching__muted">No student details available.</p>
            </div>
          </li>
        </ul>
      </section>

      <!-- Mentors -->
      <section class="mentor-matching__panel">
        <header class="mentor-matching__panel-head">
          <h3>Mentors</h3>
          <span class="mentor-matching__count">{{ mentors.length }}</span>
          <span class="mentor-matching__available">
            <span class="mentor-matching__dot" aria-hidden="true"></span>
            Available
          </span>
          <label class="mentor-matching__toggle">
            <input v-model="showFullMentors" type="checkbox" />
            <span>Show mentors at capacity</span>
          </label>
        </header>

        <p v-if="loadingLists" class="mentor-matching__empty">Loading mentors...</p>
        <p v-else-if="availableMentors.length === 0" class="mentor-matching__empty">
          No mentors with remaining capacity.
        </p>
        <ul v-else class="mentor-matching__list">
          <li v-for="mentor in availableMentors" :key="mentor.mentorId">
            <button
              type="button"
              class="mentor-matching__row"
              :aria-expanded="expandedMentorIds.has(mentor.mentorId)"
              @click="toggleMentorExpanded(mentor.mentorId)"
            >
              <span
                class="mentor-matching__dot"
                :class="{ 'mentor-matching__dot--full': mentor.remainingCapacity === 0 }"
                aria-hidden="true"
              ></span>
              <i
                class="fas mentor-matching__chevron"
                :class="
                  expandedMentorIds.has(mentor.mentorId) ? 'fa-chevron-down' : 'fa-chevron-right'
                "
                aria-hidden="true"
              ></i>
              <span class="mentor-matching__row-main">
                <span class="mentor-matching__row-name">{{ mentor.name }}</span>
                <span class="mentor-matching__muted">{{ mentor.institution || '—' }}</span>
              </span>
              <span class="mentor-matching__pill">{{ mentor.countryName || 'Unknown' }}</span>
              <span class="mentor-matching__capacity">
                {{ mentor.currentAssignedCount }}/{{ mentor.maxGroupCount }}
              </span>
            </button>

            <div v-if="expandedMentorIds.has(mentor.mentorId)" class="mentor-matching__detail">
              <p class="mentor-matching__detail-label">
                Remaining capacity: {{ mentor.remainingCapacity }}
              </p>
              <div v-if="mentor.interests.length" class="mentor-matching__chips">
                <span
                  v-for="interest in mentor.interests"
                  :key="interest"
                  class="mentor-matching__chip"
                >
                  {{ interest }}
                </span>
              </div>
              <p v-else class="mentor-matching__muted">No interests recorded.</p>
            </div>
          </li>
        </ul>
      </section>
    </div>

    <!-- Recommendations -->
    <p v-if="loading" class="mentor-matching__placeholder">
      <span class="mentor-matching__spinner" aria-hidden="true"></span>
      Running the matcher...
    </p>

    <p v-else-if="!hasRun" class="mentor-matching__placeholder">
      Click <strong>Run match</strong> to generate recommendations. Nothing is saved
      until you confirm.
    </p>

    <p v-else-if="recommendations.length === 0" class="mentor-matching__placeholder">
      No recommendations returned. Every group may already have a mentor.
    </p>

    <template v-else>
      <div class="mentor-matching__filters">
        <input
          v-model="recSearch"
          type="search"
          class="mentor-matching__search"
          placeholder="Search by group, mentor, or country"
          aria-label="Search by group, mentor, or country"
        />
        <select v-model="recCountry" class="mentor-matching__select" aria-label="Filter by country">
          <option value="all">All countries</option>
          <option v-for="country in recCountries" :key="country" :value="country">
            {{ country }}
          </option>
        </select>
      </div>

      <div class="mentor-matching__table-wrap">
        <table class="mentor-matching__table">
          <thead>
            <tr>
              <th class="mentor-matching__expand-col"></th>
              <th class="mentor-matching__check-col">
                <input
                  type="checkbox"
                  :checked="allSelected"
                  :disabled="matchableRecommendations.length === 0"
                  aria-label="Select all matchable recommendations"
                  @change="toggleAll"
                />
              </th>
              <th v-for="column in columns" :key="column.key">
                <button
                  type="button"
                  class="mentor-matching__sort-btn"
                  @click="setRecSort(column.key)"
                >
                  <span>{{ column.label }}</span>
                  <i class="fas" :class="recSortIcon(column.key)" aria-hidden="true"></i>
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            <template v-for="entry in sortedRecommendations" :key="entry.group.groupId">
              <tr
                :class="{
                  'mentor-matching__table-row--unmatched': !effectiveMentorFor(entry)
                }"
              >
                <td class="mentor-matching__expand-col">
                  <button
                    type="button"
                    class="mentor-matching__expand-btn"
                    :aria-expanded="expandedRecIds.has(entry.group.groupId)"
                    :aria-label="`Details for ${entry.group.groupName}`"
                    @click="toggleRecExpanded(entry.group.groupId)"
                  >
                    <i
                      class="fas"
                      :class="
                        expandedRecIds.has(entry.group.groupId)
                          ? 'fa-chevron-down'
                          : 'fa-chevron-right'
                      "
                      aria-hidden="true"
                    ></i>
                  </button>
                </td>
                <td class="mentor-matching__check-col">
                  <input
                    v-if="effectiveMentorFor(entry)"
                    type="checkbox"
                    :checked="selectedGroupIds.has(entry.group.groupId)"
                    :aria-label="`Select ${entry.group.groupName}`"
                    @change="toggleOne(entry.group.groupId)"
                  />
                </td>
                <td class="mentor-matching__group-cell">{{ entry.group.groupName }}</td>
                <td>
                  <span class="mentor-matching__country-badge">
                    {{ entry.group.countryName || 'Unknown' }}
                  </span>
                </td>
                <td>{{ entry.group.studentCount }}</td>
                <td>
                  <template v-if="changingGroupId === entry.group.groupId">
                    <select
                      class="mentor-matching__select mentor-matching__select--inline"
                      :aria-label="`Choose a mentor for ${entry.group.groupName}`"
                      @change="onMentorPicked(entry.group.groupId, $event)"
                    >
                      <option value="">Keep recommendation</option>
                      <option
                        v-for="candidate in availableMentors"
                        :key="candidate.mentorId"
                        :value="candidate.mentorId"
                        :selected="effectiveMentorFor(entry)?.mentorId === candidate.mentorId"
                      >
                        {{ candidate.name }} ({{ candidate.remainingCapacity }} left)
                      </option>
                    </select>
                  </template>
                  <template v-else-if="effectiveMentorFor(entry)">
                    <span class="mentor-matching__mentor-name">
                      {{ effectiveMentorFor(entry)?.name }}
                    </span>
                    <button
                      type="button"
                      class="mentor-matching__change"
                      @click="changingGroupId = entry.group.groupId"
                    >
                      Change
                    </button>
                    <span v-if="isOverridden(entry.group.groupId)" class="mentor-matching__muted">
                      Changed from {{ entry.recommendedMentor?.name ?? 'no mentor' }}
                    </span>
                  </template>
                  <template v-else>
                    <span class="mentor-matching__muted">
                      {{ entry.reason || 'No compatible mentor' }}
                    </span>
                    <button
                      type="button"
                      class="mentor-matching__change"
                      @click="changingGroupId = entry.group.groupId"
                    >
                      Assign
                    </button>
                  </template>
                </td>
                <td>{{ effectiveMentorFor(entry)?.institution || '—' }}</td>
                <td>{{ effectiveMentorFor(entry)?.remainingCapacity ?? '—' }}</td>
                <td>
                  <span v-if="effectiveMentorFor(entry)" class="mentor-matching__score">
                    {{ Math.round(entry.score) }}
                  </span>
                  <span v-else class="mentor-matching__muted">—</span>
                </td>
              </tr>

              <tr v-if="expandedRecIds.has(entry.group.groupId)">
                <td :colspan="columns.length + 2" class="mentor-matching__expanded-cell">
                  <div class="mentor-matching__detail-grid">
                    <!-- Group -->
                    <div class="mentor-matching__detail-col">
                      <p class="mentor-matching__detail-heading">Group</p>
                      <p class="mentor-matching__detail-strong">{{ entry.group.groupName }}</p>
                      <p class="mentor-matching__detail-line">
                        Country:
                        <span>{{ entry.group.countryName || 'Unknown' }}</span>
                      </p>
                      <p class="mentor-matching__detail-line">
                        Students: <span>{{ entry.group.studentCount }}</span>
                      </p>

                      <template v-if="entry.group.students?.length">
                        <p class="mentor-matching__detail-heading">Students</p>
                        <div
                          v-for="student in entry.group.students"
                          :key="student.name"
                          class="mentor-matching__detail-card"
                        >
                          <p class="mentor-matching__detail-strong">{{ student.name }}</p>
                          <div v-if="student.interests.length" class="mentor-matching__chips">
                            <span
                              v-for="interest in student.interests"
                              :key="interest"
                              class="mentor-matching__chip"
                            >
                              {{ interest }}
                            </span>
                          </div>
                        </div>
                      </template>

                      <template v-else-if="entry.group.studentInterests.length">
                        <p class="mentor-matching__detail-heading">Student interests</p>
                        <div class="mentor-matching__chips">
                          <span
                            v-for="interest in uniqueInterests(entry.group.studentInterests)"
                            :key="interest"
                            class="mentor-matching__chip"
                          >
                            {{ interest }}
                          </span>
                        </div>
                      </template>
                    </div>

                    <!-- Score breakdown -->
                    <div class="mentor-matching__detail-col">
                      <p class="mentor-matching__detail-heading">Score breakdown</p>
                      <div class="mentor-matching__detail-card">
                        <div class="mentor-matching__score-row mentor-matching__score-row--head">
                          <span>Match score</span>
                          <span class="mentor-matching__score-total">
                            {{ Math.round(entry.score) }}
                          </span>
                        </div>

                        <template v-if="entry.scoreBreakdown">
                          <div class="mentor-matching__score-row">
                            <span>Base</span>
                            <span>{{ entry.scoreBreakdown.baseScore }}</span>
                          </div>
                          <!-- Zero-value contributions are omitted so the card
                               shows only what actually moved the score. -->
                          <div
                            v-if="entry.scoreBreakdown.countryPenalty > 0"
                            class="mentor-matching__score-row"
                          >
                            <span>Country mismatch</span>
                            <span class="mentor-matching__negative">
                              −{{ entry.scoreBreakdown.countryPenalty }}
                            </span>
                          </div>
                          <div
                            v-if="entry.scoreBreakdown.interestBonus > 0"
                            class="mentor-matching__score-row"
                          >
                            <span>Interest overlap</span>
                            <span class="mentor-matching__positive">
                              +{{ entry.scoreBreakdown.interestBonus }}
                            </span>
                          </div>
                          <div
                            v-if="entry.scoreBreakdown.timezonePenalty > 0"
                            class="mentor-matching__score-row"
                          >
                            <span>Timezone penalty</span>
                            <span class="mentor-matching__negative">
                              −{{ entry.scoreBreakdown.timezonePenalty }}
                            </span>
                          </div>
                          <div
                            v-if="entry.scoreBreakdown.capacityBonus > 0"
                            class="mentor-matching__score-row"
                          >
                            <span>Capacity bonus</span>
                            <span class="mentor-matching__positive">
                              +{{ entry.scoreBreakdown.capacityBonus }}
                            </span>
                          </div>
                          <div class="mentor-matching__score-row mentor-matching__score-row--foot">
                            <span>Total</span>
                            <span>{{ entry.scoreBreakdown.objectiveScore }}</span>
                          </div>
                        </template>
                      </div>

                      <div class="mentor-matching__detail-card">
                        <p class="mentor-matching__detail-heading">Reason</p>
                        <p
                          v-for="(sentence, index) in reasonSentences(entry.reason)"
                          :key="index"
                          class="mentor-matching__reason"
                        >
                          {{ sentence }}
                        </p>
                      </div>
                    </div>

                    <!-- Mentor -->
                    <div class="mentor-matching__detail-col">
                      <p class="mentor-matching__detail-heading">Mentor</p>
                      <div v-if="effectiveMentorFor(entry)" class="mentor-matching__detail-card">
                        <p class="mentor-matching__detail-strong">
                          {{ effectiveMentorFor(entry)?.name }}
                        </p>
                        <p
                          v-if="effectiveMentorFor(entry)?.institution"
                          class="mentor-matching__muted"
                        >
                          {{ effectiveMentorFor(entry)?.institution }}
                        </p>
                        <p class="mentor-matching__detail-line">
                          Country:
                          <span>{{ effectiveMentorFor(entry)?.countryName || 'Unknown' }}</span>
                        </p>
                        <p class="mentor-matching__detail-line">
                          Remaining capacity:
                          <span>{{ effectiveMentorFor(entry)?.remainingCapacity }}</span>
                        </p>

                        <p class="mentor-matching__detail-heading">Mentor interests</p>
                        <div
                          v-if="effectiveMentorFor(entry)?.interests.length"
                          class="mentor-matching__chips"
                        >
                          <span
                            v-for="interest in effectiveMentorFor(entry)?.interests"
                            :key="interest"
                            class="mentor-matching__chip"
                          >
                            {{ interest }}
                          </span>
                        </div>
                        <span v-else class="mentor-matching__muted">None listed</span>
                      </div>
                      <p v-else class="mentor-matching__muted">No mentor assigned.</p>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  MENTOR_MATCH_MODES,
  type RecommendationSortKey,
  useMentorMatching
} from '@/composables/admin/useMentorMatching'

const modes = MENTOR_MATCH_MODES

const columns: { key: RecommendationSortKey; label: string }[] = [
  { key: 'group', label: 'Group' },
  { key: 'country', label: 'Country' },
  { key: 'students', label: 'Students' },
  { key: 'mentor', label: 'Recommended Mentor' },
  { key: 'institution', label: 'Institution' },
  { key: 'capacity', label: 'Capacity left' },
  { key: 'score', label: 'Score' }
]

/** Group whose mentor picker is currently open, if any. */
const changingGroupId = ref<number | null>(null)

const {
  loading,
  loadingLists,
  confirming,
  error,
  hasRun,
  mode,
  modeDescription,
  recommendations,
  matchableRecommendations,
  unmatchedRecommendations,
  mentors,
  availableMentors,
  unmatchedGroups,
  expandedGroupIds,
  expandedMentorIds,
  showFullMentors,
  capacityShortage,
  selectedGroupIds,
  selectedCount,
  allSelected,
  toggleOne,
  toggleAll,
  toggleGroupExpanded,
  toggleMentorExpanded,
  recSearch,
  recCountry,
  recCountries,
  setRecSort,
  recSortIcon,
  sortedRecommendations,
  expandedRecIds,
  toggleRecExpanded,
  effectiveMentorFor,
  isOverridden,
  setMentorOverride,
  loadLists,
  run,
  setMode,
  confirm
} = useMentorMatching()

const uniqueInterests = (interests: string[]) => [...new Set(interests)]

/** The reason arrives as one string; split it so each clause gets its own line. */
const reasonSentences = (reason: string): string[] => {
  const trimmed = reason?.trim()
  if (!trimmed) return ['No reason provided.']
  return trimmed
    .split('. ')
    .filter(Boolean)
    .map((sentence) => (sentence.endsWith('.') ? sentence : `${sentence}.`))
}

const onMentorPicked = (groupId: number, event: Event) => {
  const raw = (event.target as HTMLSelectElement).value
  setMentorOverride(groupId, raw === '' ? null : Number(raw))
  changingGroupId.value = null
}

// The two reference tables are visible before any match is run, so they load on
// mount. Running the matcher itself stays a deliberate action.
onMounted(() => {
  void loadLists()
})

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

.mentor-matching__title {
  margin: 0;
}

.mentor-matching__subtitle {
  margin: 0.15rem 0 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.mentor-matching__controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

/* The shared .btn class doesn't space an icon from its label. */
.mentor-matching .btn {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}

/* Segmented mode pills */
.mentor-matching__modes {
  display: inline-flex;
  padding: 0.15rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--bg-light);
}

.mentor-matching__mode {
  padding: 0.3rem 0.85rem;
  border: none;
  border-radius: 6px;
  background-color: transparent;
  color: var(--text-muted);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
}

.mentor-matching__mode--active {
  background-color: var(--charcoal);
  color: var(--white);
}

.mentor-matching__mode:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Mode description tooltip */
.mentor-matching__mode-wrap {
  position: relative;
  display: inline-flex;
}

.mentor-matching__mode-tip {
  position: absolute;
  top: calc(100% + 0.5rem);
  left: 0;
  z-index: 30;
  display: none;
  width: 17rem;
  padding: 0.5rem 0.65rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--surface-elevated);
  box-shadow: 0 8px 24px var(--shadow);
  color: var(--charcoal);
  font-size: 0.75rem;
  font-weight: 400;
  line-height: 1.4;
  white-space: normal;
}

.mentor-matching__mode-wrap:hover .mentor-matching__mode-tip,
.mentor-matching__mode-wrap:focus-within .mentor-matching__mode-tip {
  display: block;
}

/* Recommendations filters */
.mentor-matching__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.mentor-matching__search {
  flex: 1 1 260px;
  min-width: 0;
  padding: 0.45rem 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--surface-elevated);
  color: var(--charcoal);
  font-size: 0.9rem;
}

.mentor-matching__select {
  padding: 0.45rem 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--surface-elevated);
  color: var(--charcoal);
  font-size: 0.9rem;
}

.mentor-matching__select--inline {
  padding: 0.25rem 0.4rem;
  font-size: 0.8rem;
}

/* Statistics */
.mentor-matching__stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.6rem;
}

.mentor-matching__stat {
  padding: 0.6rem 0.8rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--surface-elevated);
}

.mentor-matching__stat-label {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.75rem;
}

.mentor-matching__stat-value {
  margin: 0.15rem 0 0;
  font-size: 1.1rem;
  font-weight: 700;
}

/* Two tables */
.mentor-matching__columns {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(330px, 1fr));
  gap: 0.75rem;
}

.mentor-matching__panel {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--surface-elevated);
  overflow: hidden;
}

.mentor-matching__panel-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 0.85rem;
  border-bottom: 1px solid var(--border-light);
}

.mentor-matching__panel-head h3 {
  margin: 0;
  font-size: 0.95rem;
}

.mentor-matching__count {
  padding: 0.05rem 0.5rem;
  border-radius: 999px;
  background-color: var(--bg-light);
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 600;
}

.mentor-matching__available {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  color: var(--text-muted);
  font-size: 0.75rem;
}

.mentor-matching__dot {
  display: inline-block;
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 50%;
  background-color: var(--success);
  flex-shrink: 0;
}

.mentor-matching__dot--full {
  background-color: var(--text-muted);
}

.mentor-matching__toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-left: auto;
  color: var(--text-muted);
  font-size: 0.75rem;
  white-space: nowrap;
}

.mentor-matching__list {
  max-height: 24rem;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  list-style: none;
}

.mentor-matching__list > li + li {
  border-top: 1px solid var(--border-light);
}

/* form controls don't inherit font-family, so a <button> row and everything
   inside it (country pills included) would otherwise render in the browser's
   UI font instead of the body's Arial. */
.mentor-matching__row,
.mentor-matching__mode,
.mentor-matching__expand-btn,
.mentor-matching__change,
.mentor-matching__search,
.mentor-matching__select {
  font-family: inherit;
}

.mentor-matching__row {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 0.85rem;
  border: none;
  background-color: transparent;
  color: var(--charcoal);
  font-size: 0.85rem;
  text-align: left;
  cursor: pointer;
}

.mentor-matching__row:hover {
  background-color: var(--bg-light);
}

.mentor-matching__row-main {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.mentor-matching__row-name {
  display: block;
  font-weight: 600;
}

.mentor-matching__chevron {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.mentor-matching__pill {
  margin-left: auto;
  padding: 0.05rem 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  font-size: 0.72rem;
  white-space: nowrap;
}

.mentor-matching__capacity {
  color: var(--text-muted);
  font-size: 0.78rem;
  white-space: nowrap;
}

/* Expanded detail */
.mentor-matching__detail {
  padding: 0 0.85rem 0.7rem 2rem;
}

.mentor-matching__detail-label {
  margin: 0 0 0.4rem;
  font-size: 0.8rem;
  font-weight: 600;
}

.mentor-matching__cards {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.mentor-matching__student-card {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background-color: var(--bg-light);
}

.mentor-matching__student-name {
  font-size: 0.82rem;
  font-weight: 600;
}

.mentor-matching__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.mentor-matching__chip {
  padding: 0.05rem 0.4rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background-color: var(--surface-elevated);
  font-size: 0.7rem;
}

.mentor-matching__empty {
  margin: 0;
  padding: 1.5rem 0.85rem;
  color: var(--text-muted);
  font-size: 0.82rem;
  text-align: center;
}

/* Recommendations table */
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

.mentor-matching__expand-col {
  width: 32px;
}

/* Cells are top-aligned so multi-line rows read well, which leaves the checkbox
   and chevron floating above the first line of text. Nudge them down onto it. */
.mentor-matching__check-col input,
.mentor-matching__expand-btn {
  margin-top: 0.25rem;
}

.mentor-matching__expand-btn {
  padding: 0;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.75rem;
  cursor: pointer;
}

/* Matches .matched-groups__sort-btn so both admin tables sort identically. */
.mentor-matching__sort-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0;
  border: none;
  background: transparent;
  font: inherit;
  font-weight: 600;
  color: inherit;
  cursor: pointer;
}

/* Deliberately identical to .matched-groups__country-badge — the two admin
   tables sit on the same page and the pills were visibly inconsistent. */
.mentor-matching__country-badge {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  border: 1px solid var(--border-light);
  font-size: 0.75rem;
  color: var(--text-muted);
}

.mentor-matching__group-cell {
  font-weight: 600;
}

.mentor-matching__mentor-name {
  margin-right: 0.4rem;
}

.mentor-matching__change {
  padding: 0;
  border: none;
  background: transparent;
  color: var(--dark-green);
  font-size: 0.78rem;
  font-weight: 600;
  text-decoration: underline;
  cursor: pointer;
}

/* Extra top padding plus a rule so the detail reads as a panel below the row
   rather than crowding straight up against it. */
.mentor-matching__expanded-cell {
  padding: 1.1rem 1rem;
  border-top: 1px solid var(--border-light);
  background-color: var(--bg-light);
}

.mentor-matching__detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0.85rem;
  align-items: start;
}

.mentor-matching__detail-col {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
}

.mentor-matching__detail-heading {
  margin: 0.2rem 0 0;
  color: var(--text-muted);
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.mentor-matching__detail-strong {
  margin: 0;
  font-size: 0.8rem;
  font-weight: 600;
}

/* "Country: Australia" — label muted, value in body colour. */
.mentor-matching__detail-line {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.78rem;
}

.mentor-matching__detail-line span {
  color: var(--charcoal);
}

.mentor-matching__detail-card {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 0.5rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background-color: var(--surface-elevated);
}

.mentor-matching__score-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  color: var(--text-muted);
  font-size: 0.78rem;
}

.mentor-matching__score-row--head {
  padding-bottom: 0.35rem;
  border-bottom: 1px solid var(--border-light);
  font-weight: 600;
}

.mentor-matching__score-row--foot {
  padding-top: 0.35rem;
  border-top: 1px solid var(--border-light);
  color: var(--charcoal);
  font-weight: 700;
}

.mentor-matching__score-total {
  color: var(--charcoal);
  font-size: 0.9rem;
  font-weight: 700;
}

.mentor-matching__reason {
  margin: 0;
  font-size: 0.78rem;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.mentor-matching__negative {
  color: var(--danger);
}

.mentor-matching__positive {
  color: var(--success);
}

.mentor-matching__table-row--unmatched {
  background-color: rgba(220, 53, 69, 0.04);
}

.mentor-matching__score {
  padding: 0 0.4rem;
  border-radius: 999px;
  background-color: rgba(1, 113, 81, 0.12);
  color: var(--dark-green);
  font-weight: 700;
}

/* States */
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

.mentor-matching__placeholder {
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

.mentor-matching__muted {
  display: block;
  color: var(--text-muted);
  font-size: 0.78rem;
}
</style>
