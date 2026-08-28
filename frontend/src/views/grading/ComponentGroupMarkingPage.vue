<template>
  <div class="card">
    <div class="card-header">
      <h3 class="card-title">Mark {{ code }} — group {{ groupId }}</h3>
    </div>
    <p>Coming soon — single-component marking with prev/next navigation.</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const code = computed(() => String(route.params.code || ''))
const groupId = computed(() => String(route.params.groupId || ''))
</script>
