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
/* Muted text sits on the card (--white), where --text-muted would pass in
   light (4.69:1); #616970 is used anyway so the tile reads the same on the
   page ground (--bg-light), where --text-muted is 4.45:1 and fails. Dark
   hands it back to the theme's #8a9a96, 5.72:1 on the dark card. */
.stat-tile {
  --stat-muted: #616970;

  min-width: 0;
  padding: 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
}

:root[data-theme='dark'] .stat-tile {
  --stat-muted: #8a9a96;
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
