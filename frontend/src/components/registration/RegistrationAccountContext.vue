<template>
  <section class="account-context" aria-labelledby="registration-account-heading">
    <div>
      <p>Signed-in account</p>
      <h3 id="registration-account-heading">{{ displayName }}</h3>
      <span>{{ roleLabel }}</span>
    </div>
    <dl>
      <div>
        <dt>Email</dt>
        <dd>{{ email || 'Available from the authenticated session' }}</dd>
      </div>
      <div>
        <dt>School or organisation</dt>
        <dd>{{ organization || 'Available from the authenticated session' }}</dd>
      </div>
    </dl>
    <p class="account-context__note">
      This context is display-only. The registration service identifies the submitting account from
      the authenticated session.
    </p>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  displayName: string
  roleLabel: string
  email?: string
  organization?: string
}>()
</script>

<style scoped>
.account-context {
  display: grid;
  gap: 22px;
  padding: 24px;
  border: 1px solid var(--registration-line);
  border-radius: 16px;
  background: #f7faf7;
}

.account-context p,
.account-context h3,
.account-context dl,
.account-context dd {
  margin: 0;
}

.account-context > div:first-child {
  display: grid;
  gap: 4px;
}

.account-context > div:first-child p,
dt {
  color: var(--registration-muted);
  font-size: 0.78rem;
  font-weight: 700;
}

.account-context h3 {
  font-size: 1.2rem;
}

.account-context > div:first-child span {
  color: var(--registration-green-dark);
  font-size: 0.86rem;
  font-weight: 750;
}

.account-context dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.account-context dl > div {
  min-width: 0;
  display: grid;
  gap: 5px;
}

dd {
  overflow-wrap: anywhere;
  color: var(--registration-ink);
  font-size: 0.92rem;
}

.account-context__note {
  max-width: 70ch;
  color: var(--registration-muted);
  font-size: 0.82rem;
  line-height: 1.5;
}

@media (max-width: 620px) {
  .account-context dl {
    grid-template-columns: 1fr;
  }
}
</style>
