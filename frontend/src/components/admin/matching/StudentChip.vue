<template>
  <div
    ref="triggerRef"
    class="student-chip"
    :class="{
      'student-chip--fixed': fixed,
      'student-chip--recommended': !fixed && !moved
    }"
    :tabindex="fixed ? -1 : 0"
    @mouseenter="openCard"
    @mouseleave="closeCard"
    @focus="openCard"
    @blur="closeCard"
  >
    <span class="student-chip__name">{{ student.name }}</span>
    <span
      v-if="entry"
      class="student-chip__score"
      :class="{ 'student-chip__score--moved': moved }"
    >
      {{ Math.round(displayScore) }}
    </span>

    <!--
      Teleported to <body> so the card escapes the board's `overflow-y: auto`
      scroll container and the waiting area, both of which clipped it when
      positioned inside the chip. Position is computed from the trigger's
      viewport rect, which also lets it flip above/below near an edge.

      Nested inside the root element on purpose: vuedraggable needs each item to
      have a single root node, and a top-level <Teleport> sibling makes this a
      fragment, which silently breaks dragging. The content still renders on
      <body> from here.
    -->
    <Teleport to="body">
    <div
      v-if="open"
      ref="cardRef"
      class="student-chip-card"
      role="tooltip"
      :style="cardStyle"
    >
      <section class="student-chip-card__section">
        <p class="student-chip-card__heading">Student</p>
        <dl class="student-chip-card__facts">
          <div>
            <dt>Country</dt>
            <dd>{{ student.country || 'N/A' }}</dd>
          </div>
          <div>
            <dt>Year level</dt>
            <dd>{{ student.yearLevel ?? 'N/A' }}</dd>
          </div>
        </dl>
        <template v-if="student.interests.length">
          <p class="student-chip-card__heading student-chip-card__heading--sub">Interests</p>
          <div class="student-chip-card__chips">
            <span
              v-for="interest in student.interests"
              :key="interest"
              class="student-chip-card__chip"
            >
              {{ interest }}
            </span>
          </div>
        </template>
      </section>

      <!-- Reason and score only exist for a recommendation; an existing group
           member was never scored against the group they are already in. -->
      <section v-if="entry?.reason" class="student-chip-card__section">
        <p class="student-chip-card__heading">Reason</p>
        <p class="student-chip-card__reason">{{ entry.reason }}</p>
      </section>

      <section v-if="entry" class="student-chip-card__section">
        <p v-if="moved" class="student-chip-card__stale">
          <i class="fas fa-circle-info" aria-hidden="true"></i>
          <span>
            Score is for
            <strong>{{ recommendedGroupName ?? 'the originally suggested group' }}</strong
            >, not this one.
          </span>
        </p>

        <div class="student-chip-card__row student-chip-card__row--total">
          <span>Match score</span>
          <span>{{ displayScore.toFixed(2) }}</span>
        </div>

        <template v-if="entry.scoreBreakdown">
          <div class="student-chip-card__row">
            <span>Base</span>
            <span>{{ entry.scoreBreakdown.baseScore.toFixed(2) }}</span>
          </div>
          <div class="student-chip-card__row">
            <span>Year penalty</span>
            <span class="student-chip-card__negative">
              {{ signed(-entry.scoreBreakdown.yearPenalty) }}
            </span>
          </div>
          <div class="student-chip-card__row">
            <span>Location penalty</span>
            <span class="student-chip-card__negative">
              {{ signed(-entry.scoreBreakdown.countryPenalty) }}
            </span>
          </div>
          <div class="student-chip-card__row">
            <span>Timezone penalty</span>
            <span class="student-chip-card__negative">
              {{ signed(-entry.scoreBreakdown.timezonePenalty) }}
            </span>
          </div>
          <div class="student-chip-card__row">
            <span>Size bonus</span>
            <span class="student-chip-card__positive">
              {{ signed(entry.scoreBreakdown.sizeBonus) }}
            </span>
          </div>
          <div class="student-chip-card__row student-chip-card__row--total">
            <span>Total</span>
            <span>{{ entry.scoreBreakdown.objectiveScore.toFixed(2) }}</span>
          </div>
        </template>
      </section>
    </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import type { MatchStudent, RecommendedStudent } from '@/utils/adminMatching'

const props = withDefaults(
  defineProps<{
    student: MatchStudent
    /** Present only for recommended/moved students — drives score and reason. */
    entry?: RecommendedStudent | null
    /** Existing group members: not draggable, no score. */
    fixed?: boolean
    /** Hides the card entirely while a drag is in progress. */
    suppressed?: boolean
    /** True when the student is no longer in the group the matcher proposed. */
    moved?: boolean
    recommendedGroupName?: string | null
  }>(),
  {
    entry: null,
    fixed: false,
    suppressed: false,
    moved: false,
    recommendedGroupName: null
  }
)

/**
 * The algorithm returns two numbers (algorithms/student.py):
 *   score          = BASE_SCORE - totalPenalty, clamped 0-100 (no size bonus)
 *   objectiveScore = score + sizeBonus, clamped 0-106
 * `objectiveScore` is what the matcher ranks by and what the breakdown totals
 * to, so showing `score` made the badge disagree with its own breakdown.
 */
const displayScore = computed(
  () => props.entry?.scoreBreakdown?.objectiveScore ?? props.entry?.score ?? 0
)

const CARD_WIDTH = 272
const EDGE_GAP = 8

const triggerRef = ref<HTMLElement | null>(null)
const cardRef = ref<HTMLElement | null>(null)
const open = ref(false)
const cardStyle = ref<Record<string, string>>({})

const place = () => {
  const trigger = triggerRef.value
  if (!trigger) return

  const rect = trigger.getBoundingClientRect()
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight
  // Falls back to a typical height on the first frame, before the card exists.
  const cardHeight = cardRef.value?.offsetHeight ?? 280

  const centred = rect.left + rect.width / 2 - CARD_WIDTH / 2
  const left = Math.max(
    EDGE_GAP,
    Math.min(centred, viewportWidth - CARD_WIDTH - EDGE_GAP)
  )

  // Prefer above the chip; flip below when there isn't room.
  const above = rect.top - EDGE_GAP - cardHeight
  const top =
    above >= EDGE_GAP
      ? above
      : Math.max(EDGE_GAP, Math.min(rect.bottom + EDGE_GAP, viewportHeight - cardHeight - EDGE_GAP))

  cardStyle.value = {
    left: `${left}px`,
    top: `${top}px`,
    width: `${CARD_WIDTH}px`
  }
}

const openCard = async () => {
  if (props.suppressed) return
  open.value = true
  // First pass positions blind, second corrects once the card has a height.
  await nextTick()
  place()
}

const closeCard = () => {
  open.value = false
}

// A drag can start while the card is open; hide it so it can't cover the drop
// zones, and so SortableJS never clones it into the drag preview.
watch(
  () => props.suppressed,
  (isSuppressed) => {
    if (isSuppressed) closeCard()
  }
)

// The chip can move under the cursor when an ancestor scrolls, so follow it.
// `capture` is required to catch scrolls on the board's inner container.
const onViewportChange = () => {
  if (open.value) place()
}

window.addEventListener('scroll', onViewportChange, { passive: true, capture: true })
window.addEventListener('resize', onViewportChange, { passive: true })

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onViewportChange, { capture: true })
  window.removeEventListener('resize', onViewportChange)
})

/** "-12.00" / "+5.00" — matches the reference app's signed breakdown rows. */
const signed = (value: number): string =>
  `${value > 0 ? '+' : '-'}${Math.abs(value).toFixed(2)}`
</script>

<style scoped>
.student-chip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background-color: var(--surface-elevated);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: grab;
}

.student-chip:active {
  cursor: grabbing;
}

/* Sitting where the matcher put them. A tint derived from --dark-green rather
   than --light-green, which is a cream in light mode and reads as unhighlighted. */
.student-chip--recommended {
  border-color: var(--dark-green);
  background-color: rgba(1, 113, 81, 0.12);
  color: var(--dark-green);
}

.student-chip--fixed {
  cursor: default;
}

/* Applied by SortableJS (drag-class) to the element under the cursor. The node
   keeps its source styling until the drop commits, so a student dragged out of
   their recommended group would otherwise stay green all the way across. */
.student-chip--dragging {
  border-color: var(--border-light);
  background-color: var(--surface-elevated);
  color: var(--charcoal);
}

.student-chip__score {
  flex-shrink: 0;
  padding: 0.05rem 0.45rem;
  border-radius: 999px;
  background-color: var(--dark-green);
  color: var(--white);
  font-size: 0.75rem;
  font-weight: 700;
}

/* Moved out of the recommended group: the number is stale, so it is shown as
   an outline rather than a solid badge. */
.student-chip__score--moved {
  background-color: transparent;
  border: 1px solid var(--border-light);
  color: var(--text-muted);
}
</style>

<style>
/* Unscoped: the card is teleported to <body>, outside this component's scope. */
.student-chip-card {
  position: fixed;
  z-index: 1000;
  padding: 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background-color: var(--surface-elevated);
  box-shadow: 0 8px 24px var(--shadow);
  color: var(--charcoal);
  font-size: 0.8rem;
  font-weight: 400;
  pointer-events: none;
}

.student-chip-card__section + .student-chip-card__section {
  margin-top: 0.6rem;
  padding-top: 0.6rem;
  border-top: 1px solid var(--border-light);
}

.student-chip-card__heading {
  margin: 0 0 0.35rem;
  color: var(--text-muted);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.student-chip-card__heading--sub {
  margin-top: 0.5rem;
}

.student-chip-card__facts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.35rem;
  margin: 0;
}

.student-chip-card__facts dt {
  color: var(--text-muted);
  font-size: 0.7rem;
}

.student-chip-card__facts dd {
  margin: 0;
  font-size: 0.8rem;
  font-weight: 600;
}

.student-chip-card__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.student-chip-card__chip {
  padding: 0.05rem 0.4rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  font-size: 0.7rem;
}

.student-chip-card__reason {
  margin: 0;
  font-size: 0.8rem;
  line-height: 1.4;
}

.student-chip-card__stale {
  display: flex;
  gap: 0.35rem;
  margin: 0 0 0.5rem;
  padding: 0.35rem 0.5rem;
  border-radius: 6px;
  background-color: rgba(255, 193, 7, 0.15);
  color: #8a6100;
  font-size: 0.72rem;
  line-height: 1.35;
}

.student-chip-card__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.78rem;
}

.student-chip-card__row + .student-chip-card__row {
  margin-top: 0.15rem;
}

.student-chip-card__row--total {
  padding-top: 0.25rem;
  font-weight: 700;
}

.student-chip-card__row--total + .student-chip-card__row {
  margin-top: 0.3rem;
}

.student-chip-card__negative {
  color: var(--danger);
}

.student-chip-card__positive {
  color: var(--success);
}
</style>
