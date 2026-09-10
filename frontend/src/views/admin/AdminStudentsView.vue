<template>
  <AdminUsersView ref="usersView" title="Students" noun="student" role-filter="student" />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import AdminUsersView from '@/views/admin/AdminUsersView.vue'

const usersView = ref<InstanceType<typeof AdminUsersView> | null>(null)

defineExpose({
  openCreate: () => usersView.value?.openCreate(),
  openStudentImport: () => usersView.value?.openStudentImport(),
  loading: computed(() => usersView.value?.loading ?? false)
})
</script>