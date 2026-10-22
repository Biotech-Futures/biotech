<template>
  <div class="non-finalist">
    <SymposiumEmailCard
      email="nonfinalists"
      button-label="Email All Nonfinalists"
      newly-added
      confirm-title="Email non-finalist teams?"
    >
      <!-- Below Notify Finalists on its tab: headed as the cards after a
           page's first are, with no title of its own over a divider. -->
      <h3 class="non-finalist__section-title">Notify Nonfinalist</h3>
      <p class="non-finalist__hint">
        For teams that submitted but weren't selected as finalists.
      </p>
      <p class="non-finalist__hint">
        The Symposium date and registration link come from Set Details above.
      </p>
      <p class="non-finalist__hint">
        Each group gets one email: its students in To, and its mentors and supervisors in CC. Resending emails only those who missed it, with mentors and supervisors in To if no student is left. Anyone in multiple groups gets one email for each group.
      </p>
    </SymposiumEmailCard>

    <SymposiumEmailCard
      email="nonsubmissions"
      button-label="Email All Nonsubmissions"
      confirm-title="Email teams without a submission?"
    >
      <h3 class="non-finalist__section-title">Notify Nonsubmission</h3>
      <p class="non-finalist__hint">For teams that didn't make a submission.</p>
      <p class="non-finalist__hint">
        The Symposium date and registration link come from Set Details above.
      </p>
      <p class="non-finalist__hint">
        Each group gets one email: its students in To, and its mentors and supervisors in CC. Resending emails only those who missed it, with mentors and supervisors in To if no student is left. Anyone in multiple groups gets one email for each group.
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
