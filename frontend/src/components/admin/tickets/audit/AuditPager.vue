<template>
  <div class="audit-pager">
    <div class="audit-pager__left">
      <div class="audit-pager__size">
        <label :for="sizeId" class="audit-pager__size-label">Rows per page</label>
        <!-- None of the three size controls is disabled while a page loads,
             unlike the React ones. Disabling the control that has focus drops
             keyboard focus to the top of the document, and a size picked
             mid-load only starts a fresh load: the page's stale-response
             token throws the older answer away. -->
        <select
          v-if="!customMode"
          :id="sizeId"
          ref="selectEl"
          :value="pageSize"
          class="audit-pager__select"
          @change="pick"
        >
          <option v-for="option in sizeOptions" :key="option" :value="option">
            {{ option }} / page
          </option>
          <option :value="CUSTOM">Custom…</option>
        </select>
        <template v-else>
          <input
            :id="sizeId"
            ref="inputEl"
            :value="draft"
            type="number"
            inputmode="numeric"
            :min="MIN_PAGE_SIZE"
            :max="MAX_PAGE_SIZE"
            class="audit-pager__custom"
            @input="typed"
            @blur="applyCustom"
            @keydown.enter.prevent="applyCustom"
          />
          <button type="button" class="audit-pager__btn" @click="backToPresets">Presets</button>
        </template>
      </div>
      <p class="audit-pager__info">Page {{ page }} of {{ totalPages }}</p>
    </div>

    <!-- aria-disabled rather than disabled, for the same reason as the select
         above: pressing Previous onto page 1, or Next while the page loads,
         would otherwise switch off the very button that has focus. The
         buttons stay focusable and do nothing while they are marked. -->
    <nav class="audit-pager__nav" aria-label="Pagination">
      <button
        type="button"
        class="audit-pager__btn"
        :aria-disabled="page <= 1 || disabled ? 'true' : undefined"
        @click="go(page - 1, page <= 1)"
      >
        Previous
      </button>
      <template v-for="(item, index) in items" :key="item === 'ellipsis' ? `ellipsis-${index}` : item">
        <span v-if="item === 'ellipsis'" class="audit-pager__ellipsis" aria-hidden="true">…</span>
        <button
          v-else
          type="button"
          class="audit-pager__btn audit-pager__btn--number"
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
        class="audit-pager__btn"
        :aria-disabled="page >= totalPages || disabled ? 'true' : undefined"
        @click="go(page + 1, page >= totalPages)"
      >
        Next
      </button>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, useId, watch } from 'vue'
import '@/components/support/ticketControls.css'

import { pageItems } from './pageItems'

// The React control, presets and custom box both
// (adminweb/src/components/user/PageSizeSelect.tsx): 25/50/100/200, and
// "Custom…" for any whole number from 1 to 500. The portal's AdminDataTable
// has presets only; this keeps the React one because the audit page is a
// port of that page. 200 and everything past 100 are offered although the
// server clamps every page to 100: once the answer lands, the page feeds this
// control the size the server served, so after asking for 200 it reads 100
// rather than claiming a size nobody is honouring.
const PAGE_SIZE_PRESETS = [25, 50, 100, 200]
const MIN_PAGE_SIZE = 1
const MAX_PAGE_SIZE = 500
const CUSTOM = 'custom'

const isPreset = (value: number) => PAGE_SIZE_PRESETS.includes(value)

// As React clamped it. An emptied box reads as 0 and so as 1 row per page,
// which is what the React control did too.
function clampPageSize(value: number): number {
  if (!Number.isFinite(value)) return PAGE_SIZE_PRESETS[0]!
  return Math.min(MAX_PAGE_SIZE, Math.max(MIN_PAGE_SIZE, Math.floor(value)))
}

const props = withDefaults(
  defineProps<{
    page: number
    totalPages: number
    pageSize: number
    disabled?: boolean
  }>(),
  { disabled: false }
)

const emit = defineEmits<{
  (e: 'page-change', page: number): void
  (e: 'page-size-change', size: number): void
}>()

const sizeId = useId()
const selectEl = ref<HTMLSelectElement | null>(null)
const inputEl = ref<HTMLInputElement | null>(null)

// A size that is not a preset opens on the number box, the one control that
// can name it, as React's did.
const customMode = ref(!isPreset(props.pageSize))
const draft = ref(String(props.pageSize))

// A size in force that is not a preset, met while the presets are showing,
// still gets an option of its own, so the select names it instead of going
// blank. The React Select had no item to show for such a value.
const sizeOptions = computed(() =>
  isPreset(props.pageSize)
    ? PAGE_SIZE_PRESETS
    : [...PAGE_SIZE_PRESETS, props.pageSize].sort((a, b) => a - b)
)

// Keep the box in step when the size changes from outside, and go back to the
// presets whenever the size in force is one of them: a custom 300 comes back
// from the server as 100. When that swap takes away the box the reader was
// typing in, focus goes to the select that replaces it, not to the top of the
// document.
watch(
  () => props.pageSize,
  async (value) => {
    draft.value = String(value)
    if (!customMode.value || !isPreset(value)) return
    const hadFocus = inputEl.value !== null && document.activeElement === inputEl.value
    customMode.value = false
    if (!hadFocus) return
    await nextTick()
    selectEl.value?.focus()
  }
)

async function pick(event: Event) {
  const choice = (event.target as HTMLSelectElement).value
  if (choice === CUSTOM) {
    customMode.value = true
    await nextTick()
    inputEl.value?.focus()
    inputEl.value?.select()
    return
  }
  emit('page-size-change', Number(choice))
  // Controlled, the way the React Select was: the select names the size the
  // page says is in force, not the option last clicked. They differ when the
  // pick changes nothing on the page. Asking for 200 again while the server
  // serves 100 starts no load and so no re-render, and without this the
  // select would sit on 200 over a page of 100 rows.
  await nextTick()
  if (selectEl.value) selectEl.value.value = String(props.pageSize)
}

function typed(event: Event) {
  draft.value = (event.target as HTMLInputElement).value
}

function applyCustom() {
  const next = clampPageSize(Number(draft.value))
  draft.value = String(next)
  if (next !== props.pageSize) emit('page-size-change', next)
}

async function backToPresets() {
  customMode.value = false
  // The box may hold a size the presets cannot show, so going back to them
  // goes back to the first of them, as React did.
  if (!isPreset(props.pageSize)) emit('page-size-change', PAGE_SIZE_PRESETS[0]!)
  await nextTick()
  selectEl.value?.focus()
}

const items = computed(() => pageItems(props.page, props.totalPages))

function go(target: number, atEdge: boolean) {
  if (atEdge || props.disabled) return
  emit('page-change', target)
}
</script>

<style scoped>
/* The footer sits straight on the page's ground, --bg-light, where
   --text-muted is 4.45:1 and under AA. Since the first redesign round
   (October 2026) it looks the same as the queue's pager (QueuePager.vue):
   36px buttons, an edge you can see, and a disabled button that stays solid
   and goes grey instead of fading. Measured (WCAG AA):
     light  Page N of M #5a6268 on #f8f9fa 5.89   edge #84938f on white 3.21
     dark   Page N of M --text-muted 6.19 on the dark page
            edge #70827d on the #161f1d button 4.15 (--border-light was 1.16) */
.audit-pager {
  --audit-muted: #5a6268;
  --audit-edge: #84938f;
  --audit-quiet-edge: #e6eae8;

  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

:root[data-theme='dark'] .audit-pager {
  --audit-muted: var(--text-muted);
  --audit-edge: #70827d;
  --audit-quiet-edge: var(--border-light);
}

.audit-pager__left {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.audit-pager__size {
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
}

.audit-pager__size-label {
  margin: 0;
  color: var(--charcoal);
  font-size: 0.875rem;
}

.audit-pager__info {
  margin: 0;
  color: var(--audit-muted);
  font-size: 0.875rem;
}

.audit-pager__select,
.audit-pager__custom {
  height: 2.25rem;
  padding: 0.25rem 0.7rem;
  border: 1px solid var(--audit-edge);
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
  font: inherit;
  font-size: 0.875rem;
}

/* The thin chevron from ticketControls.css in place of the browser's. */
.audit-pager__select {
  width: 7rem;
  appearance: none;
  padding-right: 2rem;
  background-image: var(--ticket-select-chevron);
  background-repeat: no-repeat;
  background-position: right 0.75rem center;
}

.audit-pager__custom {
  width: 5rem;
}

.audit-pager__nav {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.375rem;
}

.audit-pager__btn {
  min-width: 2.25rem;
  height: 2.25rem;
  padding: 0 0.625rem;
  border: 1px solid var(--audit-edge);
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
  font: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
}

.audit-pager__btn--number {
  font-variant-numeric: tabular-nums;
}

/* Hover sets background AND colour so no global rule can combine into
   green-on-green. */
.audit-pager__btn:hover:not([aria-disabled='true']):not([aria-current='page']) {
  background: var(--accent-green-soft);
  color: var(--charcoal);
}

/* Literal #fff, not var(--white): --white is a surface colour and turns dark
   green-black in the dark theme, 2.79:1 on this green. #fff is 6.03:1. */
.audit-pager__btn[aria-current='page'] {
  background: var(--dark-green);
  border-color: var(--dark-green);
  color: #fff;
}

.audit-pager__btn[aria-disabled='true'] {
  border-color: var(--audit-quiet-edge);
  color: var(--audit-muted);
  cursor: not-allowed;
}

.audit-pager__ellipsis {
  padding: 0 0.25rem;
  color: var(--charcoal);
  font-weight: 600;
}

/* The global focus ring is --dark-green, which the dark theme does not
   redefine: 2.79:1 on the dark surface, under the 3:1 a focus indicator
   needs. --mint-green is 6.13:1 there. */
:root[data-theme='dark'] .audit-pager__btn:focus-visible,
:root[data-theme='dark'] .audit-pager__select:focus-visible,
:root[data-theme='dark'] .audit-pager__custom:focus-visible {
  outline-color: var(--mint-green);
}
</style>
