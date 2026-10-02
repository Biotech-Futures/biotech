<template>
  <div class="non-finalist">
    <SymposiumEmailCard
      email="nonfinalists"
      button-label="Email All Nonfinalists"
      newly-added
      confirm-title="Email non-finalist teams?"
    >
      <div class="card-header">
        <h3 class="card-title">Email Nonfinalist</h3>
      </div>
      <!-- Laid out like Notify Finalists: the page title over a divider, then
           a section heading. -->
      <h3 class="non-finalist__section-title">Email Nonfinalist</h3>
      <p class="non-finalist__hint">
        For teams that submitted but weren't selected as finalists.
      </p>
      <p class="non-finalist__hint">
        Students, mentors and supervisors in these groups each get the email. Anyone in multiple groups gets multiple emails, one for each group.
      </p>
      <p class="non-finalist__hint">
        The Symposium date and registration link come from Email Details on
        <RouterLink to="/management/notify-finalists">Notify Finalists</RouterLink>.
      </p>
    </SymposiumEmailCard>

    <SymposiumEmailCard
      email="nonsubmissions"
      button-label="Email All Nonsubmissions"
      confirm-title="Email teams without a submission?"
    >
      <h3 class="non-finalist__section-title">Email Nonsubmission</h3>
      <p class="non-finalist__hint">For teams that didn't make a submission.</p>
      <p class="non-finalist__hint">
        Students, mentors and supervisors in these groups each get the email. Anyone in multiple groups gets multiple emails, one for each group.
      </p>
      <p class="non-finalist__hint">
        The Symposium date and registration link come from Email Details on
        <RouterLink to="/management/notify-finalists">Notify Finalists</RouterLink>.
      </p>
    </SymposiumEmailCard>
  </div>
</template>

<script setup lang="ts">
import SymposiumEmailCard from '@/views/management/SymposiumEmailCard.vue'
</script>

<style scoped>
/* As on Notify Finalists. */
.non-finalist {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* As "Change Deadline". */
.non-finalist__section-title {
  font-size: 1.05rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}

.non-finalist__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.non-finalist__hint a {
  color: var(--dark-green);
}
</style>
