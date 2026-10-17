<template>
  <!-- Late Registration: late links, what supervisors see, and the
       supervisors who register after registration closes (its dates are on
       Registration). -->
  <div class="late-registration">
    <LateLinksPage />
    <SupervisorPagesPage />
    <SupervisorsAfterClosePage />
  </div>
</template>

<script setup lang="ts">
import LateLinksPage from './LateLinksPage.vue'
import SupervisorPagesPage from './SupervisorPagesPage.vue'
import SupervisorsAfterClosePage from './SupervisorsAfterClosePage.vue'
</script>

<style scoped>
.late-registration {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
</style>
