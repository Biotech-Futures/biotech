<template>
  <!-- Late Registration: late links, and the supervisors who register after
       registration closes (its dates are on Registration). What supervisors
       see is on Challenge Start. -->
  <div class="late-registration">
    <LateLinksPage />
    <SupervisorsAfterClosePage />
  </div>
</template>

<script setup lang="ts">
import LateLinksPage from './LateLinksPage.vue'
import SupervisorsAfterClosePage from './SupervisorsAfterClosePage.vue'
</script>

<style scoped>
.late-registration {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
</style>
