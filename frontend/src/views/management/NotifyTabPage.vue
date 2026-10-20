<template>
  <!-- Management > Notify Finalists: the finalists' email, then the emails to
       the teams that weren't (and those that didn't submit). -->
  <div class="notify-tab">
    <NotifyFinalistsPage />
    <NonFinalistPage />
  </div>
</template>

<script setup lang="ts">
import NonFinalistPage from './NonFinalistPage.vue'
import NotifyFinalistsPage from './NotifyFinalistsPage.vue'
</script>

<style scoped>
/* As far apart as the cards within each. */
.notify-tab {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
</style>
