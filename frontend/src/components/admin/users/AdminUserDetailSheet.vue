<template>
  <FormSheet
    :model-value="open"
    :title="detailTitle"
    description="Account details"
    width="min(100vw, 620px)"
    @update:model-value="onDismiss"
    @close="onDismiss"
  >
    <AdminUserDetailContent :user="user" @updated="(u) => emit('updated', u)" />

    <div class="admin-users-detail__footer">
      <button type="button" class="btn btn-outline" @click="onDismiss">Close</button>
      <button v-if="user" type="button" class="btn btn-primary" @click="emit('edit', user)">Edit</button>
    </div>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import AdminUserDetailContent from '@/components/admin/users/AdminUserDetailContent.vue'
import type { AdminUser } from '@/utils/adminAPI'
import { userName } from '@/utils/userFormat'

const props = defineProps<{
  open: boolean
  user: AdminUser | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'edit', user: AdminUser): void
  (e: 'updated', user: AdminUser): void
}>()

const detailTitle = computed(() => userName(props.user) || 'User details')

const onDismiss = () => {
  emit('close')
}
</script>

<style scoped>
.admin-users-detail__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 1.5rem;
}
</style>