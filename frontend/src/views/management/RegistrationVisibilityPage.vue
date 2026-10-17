<template>
  <!-- Registration Visibility: late links and the supervisors who register
       after registration closes (its dates are on Registration); then what
       supervisors see. -->
  <div class="registration-visibility">
    <LateLinksPage />
    <SupervisorsAfterClosePage />
    <SupervisorPagesPage />
  </div>
</template>

<script setup lang="ts">
import LateLinksPage from './LateLinksPage.vue'
import SupervisorPagesPage from './SupervisorPagesPage.vue'
import SupervisorsAfterClosePage from './SupervisorsAfterClosePage.vue'
</script>

<style scoped>
.registration-visibility {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
</style>
