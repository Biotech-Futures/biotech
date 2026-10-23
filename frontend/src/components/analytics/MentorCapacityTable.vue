<template>
  <section class="mentor-capacity-table-card" aria-labelledby="mentor-capacity-table-title">
    <div class="mentor-capacity-table-heading">
      <div>
        <h2 id="mentor-capacity-table-title">Mentors with Available Capacity</h2>
        <p>
          {{ availableMentors.length }} activated
          {{ availableMentors.length === 1 ? 'mentor has' : 'mentors have' }} room for additional groups.
        </p>
      </div>
      <button
        type="button"
        class="mentor-capacity-table-toggle"
        :aria-expanded="expanded"
        aria-controls="mentor-capacity-table-content"
        @click="expanded = !expanded"
      >
        {{ expanded ? 'Hide table' : 'View mentors' }}
        <span aria-hidden="true">{{ expanded ? '⌃' : '⌄' }}</span>
      </button>
    </div>

    <div v-if="expanded" id="mentor-capacity-table-content" class="mentor-capacity-table-content">
      <div v-if="availableMentors.length" class="mentor-capacity-table-scroll">
        <table>
          <thead>
            <tr>
              <th>Mentor</th>
              <th>Region</th>
              <th>Areas of Interest</th>
              <th>Background</th>
              <th class="numeric-column">Groups</th>
              <th class="numeric-column">Remaining Capacity</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="mentor in availableMentors"
              :key="mentor.id"
              class="mentor-capacity-row"
              role="link"
              tabindex="0"
              :aria-label="`Open ${mentor.name} in Admin mentors`"
              @click="emit('select', mentor)"
              @keydown.enter="emit('select', mentor)"
              @keydown.space.prevent="emit('select', mentor)"
            >
              <td>
                <strong>{{ mentor.name }}</strong>
                <small>{{ mentor.email || 'No email provided' }}</small>
              </td>
              <td>{{ mentor.region || 'Not provided' }}</td>
              <td>{{ mentor.interests.length ? mentor.interests.join(', ') : 'Not provided' }}</td>
              <td>{{ backgroundLabel(mentor.background) }}</td>
              <td class="numeric-column">{{ mentor.groupIds.length }} / {{ mentor.capacity }}</td>
              <td class="numeric-column remaining-capacity">{{ remainingCapacity(mentor) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="mentor-capacity-empty">No activated mentors currently have available capacity.</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { DemoMentor, MentorBackground } from '@/types/analytics'

const props = defineProps<{
  mentors: DemoMentor[]
}>()

const emit = defineEmits<{
  select: [mentor: DemoMentor]
}>()

const expanded = ref(false)

const availableMentors = computed(() =>
  props.mentors
    .filter((mentor) => (mentor.accountActive ?? mentor.status === 'active') && remainingCapacity(mentor) > 0)
    .sort((a, b) =>
      remainingCapacity(b) - remainingCapacity(a) || a.name.localeCompare(b.name),
    ),
)

function remainingCapacity(mentor: DemoMentor) {
  return Math.max(mentor.capacity - new Set(mentor.groupIds).size, 0)
}

function backgroundLabel(background: MentorBackground) {
  if (background === 'hdr') return 'HDR'
  if (background === 'unknown') return 'Not provided'
  return background.charAt(0).toUpperCase() + background.slice(1)
}

function open() {
  expanded.value = true
}

defineExpose({ open })
</script>

<style scoped>
.mentor-capacity-table-card {
  margin-top: 14px;
  border: 1px solid var(--analytics-ui-border, #dce8e4);
  border-radius: 14px;
  background: var(--analytics-ui-surface, #fff);
  box-shadow: 0 3px 12px rgba(20, 64, 60, 0.04);
  overflow: hidden;
}

.mentor-capacity-table-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 18px 20px;
}

.mentor-capacity-table-heading h2 {
  margin: 0;
  color: var(--analytics-ui-text, #174243);
  font-size: 18px;
}

.mentor-capacity-table-heading p {
  margin: 5px 0 0;
  color: var(--analytics-ui-muted, #687a76);
  font-size: 13px;
}

.mentor-capacity-table-toggle {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 9px;
  min-height: 38px;
  padding: 0 16px;
  border: 1px solid var(--analytics-ui-control-border, #9fd8c7);
  border-radius: 9px;
  background: var(--analytics-ui-surface, #fff);
  color: var(--analytics-ui-accent, #017151);
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.mentor-capacity-table-toggle:hover,
.mentor-capacity-table-toggle:focus-visible {
  background: var(--analytics-ui-selected, #ecf8f4);
}

.mentor-capacity-table-content {
  padding: 0 20px 20px;
}

.mentor-capacity-table-scroll {
  max-height: 410px;
  border: 1px solid var(--analytics-ui-border, #e0e9e7);
  border-radius: 11px;
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  color: var(--analytics-ui-text, #294f4a);
  font-size: 13px;
}

th,
td {
  padding: 13px 14px;
  border-bottom: 1px solid var(--analytics-ui-border, #e5ece9);
  text-align: left;
  vertical-align: middle;
}

th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--analytics-ui-soft, #eef5f2);
  color: var(--analytics-ui-text, #174243);
  font-size: 12px;
  white-space: nowrap;
}

tbody tr:last-child td {
  border-bottom: 0;
}

tbody tr:hover {
  background: var(--analytics-ui-surface, #f7fbf9);
}

.mentor-capacity-row {
  cursor: pointer;
}

.mentor-capacity-row:focus-visible {
  outline: 2px solid #017151;
  outline-offset: -2px;
  background: var(--analytics-ui-soft, #eef8f4);
}

td strong,
td small {
  display: block;
}

td strong {
  color: var(--analytics-ui-text, #174243);
}

td small {
  margin-top: 3px;
  color: var(--analytics-ui-muted, #71817d);
  font-size: 11px;
}

.numeric-column {
  text-align: center;
  white-space: nowrap;
}

.remaining-capacity {
  color: var(--analytics-ui-accent, #017151);
  font-size: 15px;
  font-weight: 800;
}

.mentor-capacity-empty {
  margin: 0;
  padding: 30px 16px;
  border: 1px dashed var(--analytics-ui-border, #d7e2de);
  border-radius: 10px;
  color: var(--analytics-ui-muted, #687a76);
  text-align: center;
}

@media (max-width: 760px) {
  .mentor-capacity-table-heading {
    align-items: stretch;
    flex-direction: column;
  }

  .mentor-capacity-table-toggle {
    width: 100%;
  }

  .mentor-capacity-table-content {
    padding-inline: 12px;
  }

  table {
    min-width: 850px;
  }
}
</style>
