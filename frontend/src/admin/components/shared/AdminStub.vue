<!-- Placeholder body for admin screens that haven't been ported yet. -->
<script setup lang="ts">
defineProps<{
  title: string
}>()
</script>

<template>
  <div>
    <h1 class="mb-4">{{ title }}</h1>
    <v-alert
      type="info"
      variant="tonal"
      text="This screen is being migrated from the admin portal."
    />
  </div>
</template>
