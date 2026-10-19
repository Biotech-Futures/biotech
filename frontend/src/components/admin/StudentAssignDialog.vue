<template>
  <FormSheet
    :model-value="open"
    :title="single ? 'Assign Student to Group' : 'Assign students to a group'"
    :description="
      single
        ? `Select a group for ${studentLabel}.${stateSuffix}`
        : `Assigning ${assignStudents.length} ${assignStudents.length === 1 ? 'student' : 'students'} to the selected group.`
    "
    width="min(100vw, 520px)"
    @update:model-value="onDismiss"
    @close="onDismiss"
  >
    <p v-if="error" class="assign-dialog__error" role="alert">{{ error }}</p>

    <div class="form-field">
      <label class="form-label" for="assign-group-select">Group</label>
      <select
        id="assign-group-select"
        v-model="selectedGroupId"
        class="form-input"
        :disabled="loadingGroups || busy"
      >
        <option value="">{{ loadingGroups ? 'Loading groups...' : 'Select a group' }}</option>
        <option v-for="group in groups" :key="group.id" :value="String(group.id)">
          {{ group.name }} · {{ group.studentCount }}/{{ DEFAULT_GROUP_MAX_SIZE }}
          ({{ group.remaining }} left)
        </option>
      </select>
      <p v-if="!loadingGroups && groups.length === 0" class="assign-dialog__hint">
        No groups with available space. Students can be assigned once a group has free seats.
      </p>
      <p v-if="overflow > 0" class="assign-dialog__overflow">
        This group has only {{ selectedGroup?.remaining }} seat{{ selectedGroup?.remaining === 1 ? '' : 's' }}
        left. Deselect {{ overflow }} student{{ overflow === 1 ? '' : 's' }} or pick a group with more room.
      </p>
    </div>

    <template #footer>
      <button
        type="button"
        class="btn btn-outline"
        :disabled="busy"
        @click="onDismiss"
      >
        Cancel
      </button>
      <button
        type="button"
        class="btn btn-primary"
        :disabled="!selectedGroupId || overflow > 0 || groups.length === 0 || busy"
        @click="confirm"
      >
        <span v-if="busy" class="assign-dialog__spinner" aria-hidden="true"></span>
        {{ busy ? 'Assigning...' : 'Confirm assignment' }}
      </button>
    </template>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import {
  type AdminUser,
  confirmStudentAssignments,
  fetchAdminGroupList
} from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import { DEFAULT_GROUP_MAX_SIZE, groupsWithFreeSeats, type GroupWithCapacity } from '@/utils/groupCapacity'

const props = defineProps<{
  open: boolean
  students: AdminUser[]
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'confirmed', assignedCount: number): void
}>()

const assignStudents = computed(() => props.students)
const single = computed(() => assignStudents.value.length === 1)

const studentLabel = computed(() => {
  const student = assignStudents.value[0]
  if (!student) return ''
  return [student.firstName, student.lastName].filter(Boolean).join(' ') || student.email || ''
})

const stateSuffix = computed(() => {
  const student = assignStudents.value[0]
  return student?.state?.stateName ? ` (${student.state.stateName})` : ''
})

const loadingGroups = ref(false)
const busy = ref(false)
const error = ref('')
const groups = ref<GroupWithCapacity[]>([])
const selectedGroupId = ref('')

const selectedGroup = computed(() => groups.value.find((g) => String(g.id) === selectedGroupId.value))
const overflow = computed(() =>
  selectedGroup.value ? Math.max(0, assignStudents.value.length - selectedGroup.value.remaining) : 0
)

const loadGroups = async () => {
  loadingGroups.value = true
  error.value = ''
  try {
    const data = await fetchAdminGroupList({ page: 1, limit: 100 })
    groups.value = groupsWithFreeSeats(data.items)
  } catch (loadError) {
    logApiError('admin.students.assign-groups', loadError)
    error.value =
      loadError instanceof Error
        ? loadError.message
        : 'Groups could not be loaded right now.'
    groups.value = []
  } finally {
    loadingGroups.value = false
  }
}

const onDismiss = () => {
  if (busy.value) return
  selectedGroupId.value = ''
  error.value = ''
  emit('update:open', false)
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      selectedGroupId.value = ''
      error.value = ''
      void loadGroups()
    }
  }
)

const confirm = async () => {
  const groupId = Number(selectedGroupId.value)
  if (!assignStudents.value.length || !Number.isFinite(groupId) || groupId <= 0) return
  busy.value = true
  error.value = ''
  try {
    const result = await confirmStudentAssignments(
      assignStudents.value.map((student) => ({ studentId: student.id, groupId }))
    )
    selectedGroupId.value = ''
    emit('update:open', false)
    emit('confirmed', result.assignedCount)
  } catch (submitError) {
    logApiError('admin.students.assign', submitError)
    error.value =
      submitError instanceof Error
        ? submitError.message
        : 'Unable to assign the student right now.'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.assign-dialog__error {
  margin: 0 0 1rem;
  padding: 0.7rem 0.9rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.875rem;
}

.assign-dialog__hint {
  margin: 0.5rem 0 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.assign-dialog__overflow {
  margin: 0.5rem 0 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: #b45309;
}

.assign-dialog__spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  margin-right: 0.5rem;
  vertical-align: -2px;
  border: 2px solid rgba(255, 255, 255, 0.5);
  border-top-color: var(--white);
  border-radius: 50%;
  animation: assign-dialog-spin 0.8s linear infinite;
}

@keyframes assign-dialog-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .assign-dialog__spinner {
    animation: none;
  }
}
</style>