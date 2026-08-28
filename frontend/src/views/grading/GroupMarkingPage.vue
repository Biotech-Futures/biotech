<template>
  <div class="card">
    <div class="card-header">
      <h3 class="card-title">Mark group {{ groupId }}</h3>
    </div>
    <p>Coming soon — every component for this group, with submission previews.</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const groupId = computed(() => String(route.params.groupId || ''))
</script>
