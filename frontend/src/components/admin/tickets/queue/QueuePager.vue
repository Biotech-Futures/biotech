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

    <nav class="queue-pager__nav" aria-label="Pagination">
      <button
        type="button"
        class="queue-pager__btn"
        :disabled="page <= 1 || disabled"
        @click="emit('page-change', page - 1)"
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
          :disabled="disabled"
          @click="emit('page-change', item)"
        >
          {{ item }}
        </button>
      </template>
      <button
        type="button"
        class="queue-pager__btn"
        :disabled="page >= totalPages || disabled"
        @click="emit('page-change', page + 1)"
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
</script>

<style scoped>
.queue-pager {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.queue-pager__left {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1rem;
}

.queue-pager__where {
  margin: 0;
  font-size: 0.875rem;
}

.queue-pager__nav {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.25rem;
}

.queue-pager__btn {
  min-width: 2rem;
  height: 2rem;
  padding: 0 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
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
.queue-pager__btn:hover:not(:disabled) {
  background: var(--accent-green-soft);
  color: var(--charcoal);
}

.queue-pager__btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

/* Literal #fff on the green, 6.03:1: --white turns near-black in the dark
   theme (2.79:1 here). */
.queue-pager__num--current,
.queue-pager__num--current:hover:not(:disabled) {
  border-color: var(--dark-green);
  background: var(--dark-green);
  color: #fff;
}

.queue-pager__gap {
  padding: 0 0.25rem;
}

@media (max-width: 640px) {
  .queue-pager__nav {
    justify-content: flex-start;
  }
}
</style>
