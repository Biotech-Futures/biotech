<template>
  <div class="queue-pager">
    <div class="queue-pager__left">
      <PageSizeControl
        :value="pageSize"
        :disabled="disabled"
        @change="(size) => emit('page-size-change', size)"
      />
      <p class="queue-pager__where">Page {{ page }} of {{ totalPages }}</p>
    </div>

    <!-- aria-disabled rather than disabled, as on the audit tab's pager
         (AuditPager.vue). Pressing Next while a page loads, or Next onto the
         last page, would otherwise switch off the very button that has
         focus, and the browser drops focus to the top of the document. The
         buttons stay focusable and do nothing while they are marked. -->
    <nav class="queue-pager__nav" aria-label="Pagination">
      <button
        type="button"
        class="queue-pager__btn"
        :aria-disabled="page <= 1 || disabled ? 'true' : undefined"
        @click="go(page - 1, page <= 1)"
      >
        Previous
      </button>
      <template v-for="(item, index) in items" :key="item === 'ellipsis' ? `gap-${index}` : item">
        <span v-if="item === 'ellipsis'" class="queue-pager__gap" aria-hidden="true">…</span>
        <button
          v-else
          type="button"
          class="queue-pager__btn queue-pager__num"
          :class="{ 'queue-pager__num--current': item === page }"
          :aria-label="`Go to page ${item}`"
          :aria-current="item === page ? 'page' : undefined"
          :aria-disabled="disabled ? 'true' : undefined"
          @click="go(item, false)"
        >
          {{ item }}
        </button>
      </template>
      <button
        type="button"
        class="queue-pager__btn"
        :aria-disabled="page >= totalPages || disabled ? 'true' : undefined"
        @click="go(page + 1, page >= totalPages)"
      >
        Next
      </button>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import PageSizeControl from './PageSizeControl.vue'
import { pageItems } from './queueRules'

/** The queue's footer: rows per page, "Page N of M", and numbered navigation
 *  with the first and last page pinned. It only reports what was clicked;
 *  which clicks continue the walk and which start a fresh read is the
 *  page's business (useTicketQueue goToPage). */
const props = defineProps<{
  page: number
  totalPages: number
  /** The size that was asked for. Never the size the server served: that
   *  one only feeds totalPages (see servedPageCount). React fed its control
   *  the asked size for a reason specific to its Select; here the control
   *  offers nothing over the server's cap, so the two only differ if that
   *  cap is lowered. */
  pageSize: number
  disabled: boolean
}>()

const emit = defineEmits<{
  'page-change': [page: number]
  'page-size-change': [size: number]
}>()

const items = computed(() => pageItems(props.page, props.totalPages))

// A marked button ignores the press; Enter and Space arrive here as a click
// too. The page makes the same check on live state (useTicketQueue
// goToPage), because two presses in one tick both land before this prop has
// caught up.
function go(target: number, atEdge: boolean) {
  if (atEdge || props.disabled) return
  emit('page-change', target)
}
</script>

<style scoped>
/* The first redesign round (October 2026): 36px buttons a little further
   apart, an edge you can see, and a disabled button that stays solid and
   goes grey instead of fading. Measured (WCAG AA):
     light  edge #84938f on white 3.21:1   disabled words #5a6268 6.21:1
            Page N of M #5a6268 on the #f8f9fa page 5.89:1
     dark   edge #70827d on the #161f1d button 4.15:1   (--border-light was 1.16:1)
            disabled words and Page N of M take --text-muted, 5.72:1 and 6.19:1 */
.queue-pager {
  --pager-edge: #84938f;
  --pager-muted: #5a6268;
  --pager-quiet-edge: #e6eae8;

  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

:root[data-theme='dark'] .queue-pager {
  --pager-edge: #70827d;
  --pager-muted: var(--text-muted);
  --pager-quiet-edge: var(--border-light);
}

.queue-pager__left {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.85rem;
}

.queue-pager__where {
  margin: 0;
  color: var(--pager-muted);
  font-size: 0.9rem;
}

.queue-pager__nav {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.375rem;
}

.queue-pager__btn {
  min-width: 2.25rem;
  height: 2.25rem;
  padding: 0 0.625rem;
  border: 1px solid var(--pager-edge);
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
  font: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
}

/* Background and colour both set, so no global rule can combine into
   green-on-green. */
.queue-pager__btn:hover:not([aria-disabled='true']) {
  background: var(--accent-green-soft);
  color: var(--charcoal);
}

.queue-pager__btn[aria-disabled='true'] {
  border-color: var(--pager-quiet-edge);
  color: var(--pager-muted);
  cursor: not-allowed;
}

/* Literal #fff on the green, 6.03:1: --white turns near-black in the dark
   theme (2.79:1 here). */
.queue-pager__num--current,
.queue-pager__num--current:hover:not([aria-disabled='true']) {
  border-color: var(--dark-green);
  background: var(--dark-green);
  color: #fff;
}

.queue-pager__gap {
  padding: 0 0.25rem;
  font-weight: 600;
}

@media (max-width: 640px) {
  .queue-pager__nav {
    justify-content: flex-start;
  }
}
</style>
