<template>
  <!-- Management > Submission Deadline: the deadline for every group, then
       extending it for some. -->
  <div class="submission-deadline-tab">
    <SetDeadlinePage />
    <DeadlineExtensionPage />
  </div>
</template>

<script setup lang="ts">
import DeadlineExtensionPage from './DeadlineExtensionPage.vue'
import SetDeadlinePage from './SetDeadlinePage.vue'
</script>

<style scoped>
/* As far apart as the cards within each. */
.submission-deadline-tab {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
</style>
