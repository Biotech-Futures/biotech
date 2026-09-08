<template>
  <div class="card by-group">
    <div class="card-header">
      <h3 class="card-title">Mark by Group</h3>
    </div>
    <p class="by-group__hint">
      Every component for a single group. Search by group name or ID.
    </p>
    <form class="by-group__form" @submit.prevent="open">
      <GroupSearchInput ref="picker" v-model="query" class="by-group__picker" @select="goTo" />
      <button type="submit" class="btn btn-primary btn-sm">Open</button>
    </form>
    <p v-if="error" class="by-group__error">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import GroupSearchInput from '@/components/grading/GroupSearchInput.vue'

const router = useRouter()
const picker = ref<InstanceType<typeof GroupSearchInput> | null>(null)
const query = ref('')
const error = ref('')

const goTo = ({ id }: { id: number }) => {
  void router.push(`/grading/groups/${id}`)
}

const open = () => {
  error.value = ''
  const id = picker.value?.resolveId() ?? null
  if (id == null) {
    error.value = 'No group matches that name or ID.'
    return
  }
  void router.push(`/grading/groups/${id}`)
}
</script>

<style scoped>
.by-group {
  max-width: 36rem;
}

.by-group__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.by-group__form {
  display: flex;
  gap: 0.5rem;
}

.by-group__picker {
  flex: 1;
}

.by-group__error {
  color: var(--danger);
  font-size: 0.85rem;
  margin: 0.5rem 0 0;
}
</style>
