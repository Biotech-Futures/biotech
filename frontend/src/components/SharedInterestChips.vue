<template>
  <!-- A group's areas of interest, each with small circles at its top right:
       the count of students who have it, or, numbered, which of them do. -->
  <ul class="shared-interests">
    <li
      v-for="interest in shown"
      :key="interest.name"
      class="shared-interest"
      :title="
        numbered
          ? `${interest.students.length === 1 ? 'Student' : 'Students'} ${interest.students.join(', ')}`
          : `${interest.count} of ${total} ${total === 1 ? 'student' : 'students'}`
      "
    >
      {{ interest.name }}
      <span class="shared-interest__counts" aria-hidden="true">
        <template v-if="numbered">
          <span v-for="number in interest.students" :key="number" class="shared-interest__count">{{ number }}</span>
        </template>
        <span v-else class="shared-interest__count">{{ interest.count }}</span>
      </span>
      <span v-if="numbered" class="sr-only">
        , {{ interest.students.length === 1 ? 'student' : 'students' }} {{ interest.students.join(', ') }}
      </span>
      <span v-else class="sr-only">, {{ interest.count }} of {{ total }} students</span>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { SharedInterest } from '@/utils/groupInterests'

const props = defineProps<{
  interests: SharedInterest[]
  /** How many students the counts are out of. */
  total: number
  /** Shows which students have each area, by their numbers in the list. */
  numbered?: boolean
}>()

// Numbered: the areas more students share first, then in the students'
// order, student 1's first, and so on.
const byStudents = (a: SharedInterest, b: SharedInterest) => {
  if (a.students.length !== b.students.length) return b.students.length - a.students.length
  for (let i = 0; i < a.students.length; i += 1) {
    if (a.students[i] !== b.students[i]) return a.students[i] - b.students[i]
  }
  return a.name.localeCompare(b.name)
}
const shown = computed(() => (props.numbered ? [...props.interests].sort(byStudents) : props.interests))
</script>

<style scoped>
/* Room above for the circles, which sit over each chip's top edge. */
.shared-interests {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem 0.6rem;
  margin: 0;
  padding: 0.4rem 0.4rem 0 0;
  list-style: none;
}

.shared-interest {
  position: relative;
  display: inline-flex;
  align-items: center;
  min-height: 1.75rem;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  background: var(--accent-green-soft);
  color: var(--dark-green);
  font-size: 0.85rem;
}

.shared-interest__counts {
  position: absolute;
  top: -0.45rem;
  right: -0.2rem;
  display: flex;
  gap: 0.15rem;
}

.shared-interest__count {
  display: grid;
  place-items: center;
  /* 12px across. */
  min-width: 0.75rem;
  height: 0.75rem;
  padding: 0 0.14rem;
  border-radius: 999px;
  background: #000;
  color: #fff;
  font-size: 0.5rem;
  font-weight: 700;
  line-height: 1;
}
</style>
