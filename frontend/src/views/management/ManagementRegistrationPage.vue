<template>
  <!-- Management > Registration: when registration opens and closes, then
       registering students as a supervisor does (an admin's, with no
       supervisor of their own, have none). -->
  <div class="management-registration">
    <RegistrationDatesPage />
    <!-- In a card of its own, headed as the cards below a page's first. -->
    <section class="card">
      <RegistrationPage mode="supervisor" embedded />
    </section>
  </div>
</template>

<script setup lang="ts">
import RegistrationPage from '@/views/RegistrationPage.vue'
import RegistrationDatesPage from './RegistrationDatesPage.vue'
</script>

<style scoped>
/* As far apart as Late Registration's cards. */
.management-registration {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
</style>
