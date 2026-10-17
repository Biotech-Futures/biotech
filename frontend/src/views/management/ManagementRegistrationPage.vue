<template>
  <!-- Management > Registration: when registration opens and closes, then
       registering students as a supervisor does (an admin's, with no
       supervisor of their own, have none). -->
  <div class="management-registration">
    <RegistrationDatesPage />
    <RegistrationPage mode="supervisor" embedded />
  </div>
</template>

<script setup lang="ts">
import RegistrationPage from '@/views/RegistrationPage.vue'
import RegistrationDatesPage from './RegistrationDatesPage.vue'
</script>

<style scoped>
/* As far apart as Registration Visibility's cards. */
.management-registration {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
</style>
