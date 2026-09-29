<template>
  <!-- The landing page of an account whose role is support but who cannot
       work the queue: access revoked on the roster, or never granted. The
       sidebar has nothing to offer them, and an empty app reads as broken
       rather than as "this is not for you" (adminweb AdminHomePage.tsx). The
       way out is the account menu in the header, which has Log out. -->
  <div class="content-area support-access">
    <div class="card support-access__card">
      <i class="fas fa-headset support-access__icon" aria-hidden="true"></i>
      <h1 class="support-access__title">Support queue</h1>
      <p class="support-access__text">
        Your account does not have access to the support queue. If you think it
        should, ask an administrator to grant you support access.
      </p>
      <p v-if="auth.user?.email" class="support-access__account">
        Signed in as {{ auth.user.email }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { landingPath, SUPPORT_ACCESS_PATH } from '@/utils/landing'

const router = useRouter()
const auth = useAuthStore()

// Only one account belongs here. Anyone else who opens the address (an agent
// whose access has since been granted, a student following an old link) is
// sent to their own start page, the way SetPasswordPage sends away someone
// with no password left to set.
onMounted(async () => {
  const target = landingPath(auth)
  if (target !== SUPPORT_ACCESS_PATH) {
    await router.replace(target)
  }
})
</script>

<style scoped>
.support-access__card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  max-width: 560px;
  margin: 2rem auto 0;
  padding: 3rem 1.5rem;
  text-align: center;
}

.support-access__icon {
  font-size: 2rem;
  color: var(--eucalypt);
  margin-bottom: 0.5rem;
}

.support-access__title {
  margin: 0;
  font-size: 1.5rem;
}

.support-access__text {
  margin: 0;
  max-width: 420px;
  color: var(--charcoal);
  line-height: 1.6;
}

/* On the card's --white, --text-muted is 4.69:1 and passes AA; it would not
   on the page ground (--bg-light, 4.45:1). */
.support-access__account {
  margin: 0.5rem 0 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}
</style>
