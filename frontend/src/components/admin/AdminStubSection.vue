<template>
  <div class="content-area admin-stub">
    <div class="admin-stub__header">
      <h1 class="admin-stub__title">{{ title }}</h1>
      <p v-if="subtitle" class="admin-stub__subtitle">{{ subtitle }}</p>
    </div>

    <div class="card admin-stub__card">
      <i class="fas admin-stub__icon" :class="icon" aria-hidden="true"></i>
      <h2 class="admin-stub__heading">{{ heading }}</h2>
      <p class="admin-stub__text">{{ description }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    subtitle?: string
    icon?: string
    heading?: string
    description: string
  }>(),
  {
    subtitle: '',
    icon: 'fa-spinner',
    heading: 'Coming soon'
  }
)
</script>

<style scoped>
.admin-stub__header {
  margin-bottom: 1.5rem;
}

.admin-stub__title {
  margin: 0 0 0.25rem;
}

.admin-stub__subtitle {
  margin: 0;
  color: var(--text-muted);
}

.admin-stub__card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 0.5rem;
  padding: 3rem 1.5rem;
}

.admin-stub__icon {
  font-size: 2rem;
  color: var(--eucalypt);
  margin-bottom: 0.5rem;
}

.admin-stub__heading {
  margin: 0;
}

.admin-stub__text {
  margin: 0;
  max-width: 420px;
  color: var(--text-muted);
  line-height: 1.6;
}
</style>
