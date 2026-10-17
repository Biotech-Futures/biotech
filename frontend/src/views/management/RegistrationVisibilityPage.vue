<template>
  <!-- Registration Visibility: when registration is open, first, then late
       links and the supervisors who register after it closes; then what
       supervisors see (their pages and their Registration page). -->
  <div class="registration-visibility">
    <RegistrationDatesPage />
    <LateLinksPage />
    <SupervisorsAfterClosePage />
    <SupervisorPagesPage />
  </div>
</template>

<script setup lang="ts">
import LateLinksPage from './LateLinksPage.vue'
import RegistrationDatesPage from './RegistrationDatesPage.vue'
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
