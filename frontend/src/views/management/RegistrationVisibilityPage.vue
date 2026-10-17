<template>
  <!-- Registration Visibility: whether registration is open, first, then what
       supervisors see (their pages and their Registration page). -->
  <div class="registration-visibility">
    <RegistrationOpenPage />
    <SupervisorPagesPage />
  </div>
</template>

<script setup lang="ts">
import RegistrationOpenPage from './RegistrationOpenPage.vue'
import SupervisorPagesPage from './SupervisorPagesPage.vue'
</script>

<style scoped>
.registration-visibility {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
</style>
