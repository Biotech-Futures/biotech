<template>
  <FormSheet
    :model-value="open"
    :title="detailTitle"
    description="Account details"
    width="min(100vw, 620px)"
    @update:model-value="onDismiss"
    @close="onDismiss"
  >
    <p v-if="loading" class="admin-users-detail__muted">Loading details...</p>
    <p v-else-if="error" class="admin-users-detail__error" role="alert">{{ error }}</p>
    <AdminUserDetailContent
      v-else-if="user"
      :user="user"
      :editable="showEdit"
      @updated="(u) => emit('updated', u)"
    />

    <!-- A student's or mentor's parts each have their own Edit, and the x closes. -->
    <div v-if="user?.role !== 'student' && user?.role !== 'mentor'" class="admin-users-detail__footer">
      <button type="button" class="btn btn-outline" @click="onDismiss">Close</button>
      <button v-if="user && showEdit" type="button" class="btn btn-primary" @click="emit('edit', user)">Edit</button>
    </div>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import AdminUserDetailContent from '@/components/admin/users/AdminUserDetailContent.vue'
import type { AdminUser } from '@/utils/adminAPI'
import { userName } from '@/utils/userFormat'

const props = withDefaults(
  defineProps<{
    open: boolean
    user: AdminUser | null
    loading?: boolean
    error?: string
    fallbackName?: string
    showEdit?: boolean
  }>(),
  {
    loading: false,
    error: '',
    fallbackName: '',
    showEdit: true
  }
)

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'edit', user: AdminUser): void
  (e: 'updated', user: AdminUser): void
}>()

const detailTitle = computed(() => userName(props.user) || props.fallbackName || 'User details')

const onDismiss = () => {
  emit('close')
}
</script>

<style scoped>
.admin-users-detail__muted {
  color: var(--text-muted);
  font-size: 0.875rem;
}

.admin-users-detail__error {
  color: var(--danger);
  font-size: 0.875rem;
}

.admin-users-detail__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 1.5rem;
}
</style>