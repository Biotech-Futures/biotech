<template>
  <article
    class="announcement-skeleton"
    :class="{ 'announcement-skeleton--with-media': withMedia }"
    aria-hidden="true"
  >
    <div v-if="withMedia" class="announcement-skeleton__media skeleton-block"></div>
    <div class="announcement-skeleton__body">
      <div class="announcement-skeleton__heading">
        <div class="skeleton-block announcement-skeleton__title"></div>
        <div class="skeleton-block announcement-skeleton__badge"></div>
      </div>
      <div class="skeleton-block announcement-skeleton__meta"></div>
      <div class="skeleton-block announcement-skeleton__line"></div>
      <div class="skeleton-block announcement-skeleton__line"></div>
      <div class="skeleton-block announcement-skeleton__line announcement-skeleton__line--short"></div>
    </div>
  </article>
</template>

<script setup lang="ts">
defineProps<{ withMedia?: boolean }>()
</script>

<style scoped>
.announcement-skeleton {
  background: var(--white);
  border: 1px solid rgba(1, 113, 81, 0.08);
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(7, 17, 15, 0.04);
  overflow: hidden;
  padding: 1.5rem;
}

.announcement-skeleton--with-media {
  display: grid;
  grid-template-columns: minmax(260px, 38%) minmax(0, 1fr);
  padding: 0;
  min-height: 240px;
}

.announcement-skeleton--with-media .announcement-skeleton__body {
  padding: 1.5rem;
}

.announcement-skeleton__media {
  min-height: 240px;
  border-radius: 0;
}

.announcement-skeleton__heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.9rem;
}

.announcement-skeleton__title {
  width: min(420px, 70%);
  height: 22px;
}

.announcement-skeleton__badge {
  width: 90px;
  height: 22px;
  border-radius: 999px;
}

.announcement-skeleton__meta {
  width: 200px;
  height: 12px;
  margin-bottom: 1.1rem;
}

.announcement-skeleton__line {
  width: 100%;
  height: 12px;
  margin-bottom: 0.7rem;
}

.announcement-skeleton__line--short {
  width: 60%;
  margin-bottom: 0;
}

.skeleton-block {
  position: relative;
  overflow: hidden;
  border-radius: 8px;
  background: #eef2f0;
}

.skeleton-block::after {
  position: absolute;
  inset: 0;
  content: '';
  transform: translateX(-100%);
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.72),
    transparent
  );
  animation: announcement-shimmer 1.35s ease-in-out infinite;
}

@keyframes announcement-shimmer {
  100% {
    transform: translateX(100%);
  }
}

@media (max-width: 720px) {
  .announcement-skeleton--with-media {
    grid-template-columns: 1fr;
  }
  .announcement-skeleton__media {
    min-height: 180px;
  }
}
</style>
