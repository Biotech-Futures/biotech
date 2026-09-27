<template>
  <section class="group-add">
    <p class="group-detail__muted">
      {{
        remaining > 0
          ? `${remaining} seat${remaining === 1 ? '' : 's'} left. Select ungrouped students to add.`
          : 'This group is full.'
      }}
    </p>

    <div class="group-add__search">
      <i class="fas fa-magnifying-glass group-add__search-icon" aria-hidden="true"></i>
      <input
        v-model="search"
        type="search"
        class="form-input group-add__search-input"
        placeholder="Search ungrouped students..."
        aria-label="Search ungrouped students"
        :disabled="busy"
      />
    </div>

    <p v-if="loadError" class="group-detail__error" role="alert">{{ loadError }}</p>
    <p v-else-if="loading" class="group-detail__muted">Loading students...</p>
    <p v-else-if="!students.length" class="group-detail__muted">No ungrouped students found.</p>

    <ul v-else class="group-add__list">
      <li v-for="student in students" :key="student.id">
        <label class="group-add__option" :class="{ 'group-add__option--checked': selected.has(student.id) }">
          <input
            type="checkbox"
            :checked="selected.has(student.id)"
            :disabled="busy"
            @change="toggle(student)"
          />
          <span class="group-add__option-info">
            <span class="group-add__option-name">{{ studentName(student) }}</span>
            <span class="group-add__option-email">{{ student.email }}</span>
          </span>
        </label>
      </li>
    </ul>

    <p v-if="overflow > 0" class="group-add__overflow">
      Only {{ remaining }} seat{{ remaining === 1 ? '' : 's' }} left. Deselect {{ overflow }}
      student{{ overflow === 1 ? '' : 's' }}.
    </p>
    <p v-if="submitError" class="group-detail__error" role="alert">{{ submitError }}</p>

    <div class="group-add__actions">
      <button type="button" class="btn btn-outline" :disabled="busy" @click="emit('cancel')">Cancel</button>
      <button
        type="button"
        class="btn btn-primary"
        :disabled="!selected.size || overflow > 0 || remaining === 0 || busy"
        @click="confirm"
      >
        {{ busy ? 'Adding...' : `Add${selected.size ? ` (${selected.size})` : ''}` }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  confirmStudentAssignments,
  fetchAdminUsers,
  type AdminGroupDetail,
  type AdminUser
} from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'

const props = defineProps<{
  group: AdminGroupDetail
  /** Free student seats left in the group, computed by the parent from its live member list. */
  remaining: number
}>()

const emit = defineEmits<{
  (e: 'added', students: AdminUser[]): void
  (e: 'cancel'): void
}>()

const search = ref('')
const students = ref<AdminUser[]>([])
const loading = ref(false)
const loadError = ref('')
const busy = ref(false)
const submitError = ref('')
// Keyed by id so a selection survives the list being re-fetched by a new search.
const selected = ref(new Map<number, AdminUser>())

const overflow = computed(() => Math.max(0, selected.value.size - props.remaining))

const studentName = (student: AdminUser) =>
  [student.firstName, student.lastName].filter(Boolean).join(' ') || student.email || ''

// Guards against an older, slower search response overwriting a newer one.
let requestId = 0

const loadStudents = async () => {
  const current = ++requestId
  loading.value = true
  loadError.value = ''
  try {
    const data = await fetchAdminUsers({
      page: 1,
      limit: 100,
      role: 'student',
      inGroup: 'no',
      search: search.value.trim() || undefined
    })
    if (current !== requestId) return
    students.value = data.items
  } catch (err) {
    if (current !== requestId) return
    logApiError('admin.groups.add-students.load', err)
    loadError.value = err instanceof Error ? err.message : 'Students could not be loaded right now.'
    students.value = []
  } finally {
    if (current === requestId) loading.value = false
  }
}

let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadStudents, 300)
})
onBeforeUnmount(() => clearTimeout(searchTimer))

void loadStudents()

const toggle = (student: AdminUser) => {
  const next = new Map(selected.value)
  if (next.has(student.id)) next.delete(student.id)
  else next.set(student.id, student)
  selected.value = next
}

const confirm = async () => {
  if (!selected.value.size || overflow.value > 0) return
  const picked = Array.from(selected.value.values())
  busy.value = true
  submitError.value = ''
  try {
    await confirmStudentAssignments(
      picked.map((student) => ({ studentId: student.id, groupId: props.group.id }))
    )
    emit('added', picked)
  } catch (err) {
    logApiError('admin.groups.add-students', err)
    submitError.value = err instanceof Error ? err.message : 'Could not add students. Please try again.'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.group-add {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.group-detail__muted {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.875rem;
}

.group-detail__error {
  margin: 0;
  color: var(--danger);
  font-size: 0.875rem;
}

/* .form-input isn't global — each admin component styles it — so match the
   other admin form sheets here. */
.form-input {
  width: 100%;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
  font: inherit;
  font-size: 0.92rem;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.form-input:focus {
  outline: none;
  border-color: var(--dark-green);
  box-shadow: 0 0 0 3px rgba(1, 113, 81, 0.15);
}

.form-input:disabled {
  background-color: var(--bg-light);
  color: var(--text-muted);
}

.group-add__search {
  position: relative;
}

/* Leave room on the left for the icon so typed text doesn't run under it. */
.group-add__search-input {
  padding-left: 2rem;
}

.group-add__search-icon {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 0.85rem;
  pointer-events: none;
}

.group-add__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  max-height: 22rem;
  overflow-y: auto;
}

.group-add__option {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  cursor: pointer;
}

.group-add__option--checked {
  border-color: var(--dark-green);
  background-color: var(--light-green);
}

.group-add__option-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.group-add__option-name {
  font-weight: 600;
  color: var(--charcoal);
}

.group-add__option-email {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.group-add__overflow {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: #b45309;
}

.group-add__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}
</style>
