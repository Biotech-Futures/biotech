<template>
  <div class="card">
    <div class="card-header">
      <h3 class="card-title">Component: {{ code }}</h3>
    </div>
    <p>Coming soon — the cohort table for this component.</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const code = computed(() => String(route.params.code || ''))
</script>
