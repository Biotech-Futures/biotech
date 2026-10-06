<template>
  <div class="stat-tile">
    <!-- Not uppercase with letter spacing any more. At 390px "SATISFACTION"
         ran past the edge of its own card and "HAND-OFFS" broke across two
         lines; the capitals bought nothing that weight and colour were not
         already doing. -->
    <p class="stat-tile__label">{{ label }}</p>
    <!-- A duration reads as two numbers when it wraps: "33h" above "58m".
         Kept on one line. -->
    <p class="stat-tile__value">{{ value }}</p>
    <p class="stat-tile__hint">{{ hint }}</p>
  </div>
</template>

<script setup lang="ts">
/** One number, its name, and what it means.
 *
 *  Not a chart: a single quantity has no shape to show, and a one-bar chart is
 *  a number wearing a costume. */
defineProps<{
  label: string
  value: string
  hint: string
}>()
</script>

<style scoped>
/* A grey tile inside the white card since the first redesign round (October
   2026), a step darker than the card in dark too. Muted text is the round's
   #5a6268: 5.89:1 on the tile's #f8f9fa, and it would still clear AA on the
   page ground (--bg-light) where --text-muted is 4.45:1 and fails. Dark takes
   the designer's #a3b3ae, 7.71:1 on the dark tile's #161f1d. */
.stat-tile {
  --stat-muted: #5a6268;
  --stat-ground: #f8f9fa;
  --stat-edge: #e6eae8;

  min-width: 0;
  padding: 0.75rem 0.875rem;
  border: 1px solid var(--stat-edge);
  border-radius: 8px;
  background: var(--stat-ground);
}

:root[data-theme='dark'] .stat-tile {
  --stat-muted: #a3b3ae;
  --stat-ground: #161f1d;
  --stat-edge: #2b3936;
}

.stat-tile__label {
  margin: 0;
  color: var(--stat-muted);
  font-size: 0.8rem;
  font-weight: 600;
}

.stat-tile__value {
  margin: 0.25rem 0 0 0;
  color: var(--charcoal);
  font-size: 1.5rem;
  font-weight: 600;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.stat-tile__hint {
  margin: 0.25rem 0 0 0;
  color: var(--stat-muted);
  font-size: 0.8rem;
  line-height: 1.35;
}
</style>
