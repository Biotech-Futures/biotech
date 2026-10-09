<template>
  <AdminUsersView ref="usersView" title="Supervisors" noun="supervisor" role-filter="supervisor" />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import AdminUsersView from '@/views/admin/AdminUsersView.vue'

const usersView = ref<InstanceType<typeof AdminUsersView> | null>(null)

defineExpose({
  openCreate: () => usersView.value?.openCreate(),
  loading: computed(() => usersView.value?.loading ?? false)
})
</script>