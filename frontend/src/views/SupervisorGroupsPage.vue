<template>
  <div class="content-area supervisor-groups-page">
    <p v-if="error" class="supervisor-error">{{ error }}</p>
    <p v-else-if="loading" class="supervisor-muted">Loading groups...</p>

    <section v-else class="waiting-area" aria-label="Waiting Area" @dragover.prevent @drop="onDropWaiting">
      <div class="waiting-area-header">
        <h1>Waiting Area</h1>
        <span class="waiting-count">{{ waitingStudents.length }}</span>
      </div>
      <p class="waiting-copy">
        Students in this area will be assigned to a group on the challenge start date.
        Students will be matched to groups in the supervisor's school, or in or out of the
        supervisor's school.
      </p>
      <div class="waiting-bubbles">
        <button
          v-for="student in waitingStudents"
          :key="student.id"
          type="button"
          class="student-bubble"
          draggable="true"
          @dragstart="onDragStart($event, student.id)"
        >
          {{ studentName(student) }}
        </button>
        <p v-if="!waitingStudents.length" class="supervisor-muted waiting-empty">
          No unassigned students.
        </p>
      </div>
    </section>

    <section v-if="!loading" class="groups-board">
      <div class="groups-board-toolbar">
        <div class="groups-board-heading">
          <label class="group-select-all">
            <input
              type="checkbox"
              :checked="allGroupsSelected"
              :indeterminate.prop="someGroupsSelected"
              :aria-label="allGroupsSelected ? 'Deselect all groups' : 'Select all groups'"
              @change="toggleSelectAll"
            />
            <h2>My Groups</h2>
          </label>
          <label class="groups-options">
            Options
            <select :value="optionChoice" @change="onGroupOption">
              <option value="">Select</option>
              <option value="select-all">Select all groups</option>
              <option value="clear-selection" :disabled="!selectedGroupIds.size">Clear selection</option>
              <option value="delete-selected" :disabled="!selectedGroupIds.size">Delete selected groups</option>
            </select>
          </label>
        </div>
        <button type="button" class="btn btn-primary" @click="openCreateGroup">Create Group</button>
      </div>
      <p v-if="selectedGroupIds.size" class="groups-bulk">
        {{ selectedGroupIds.size }} selected
        <button type="button" class="btn btn-outline btn-sm" @click="pendingBulkDelete = true">
          Delete selected
        </button>
      </p>
      <article
        v-for="group in groups"
        :key="group.id"
        class="group-card"
        :class="{ selected: selectedGroupIds.has(group.id) }"
        @dragover.prevent
        @drop="onDrop($event, group.id)"
      >
        <div class="group-card-header">
          <div class="group-card-title">
            <input
              type="checkbox"
              :checked="selectedGroupIds.has(group.id)"
              :aria-label="`Select ${group.name}`"
              @change="toggleGroup(group.id)"
            />
            <div>
              <h2>{{ group.name }}</h2>
              <p>{{ group.supervisorName }}</p>
            </div>
          </div>
          <div class="group-card-actions">
            <button type="button" class="btn btn-outline btn-sm" @click="editGroup(group.id)">
              Edit Group
            </button>
            <span class="group-count">{{ group.students.length }}/{{ groupLimit }}</span>
          </div>
        </div>

        <div v-if="group.sharedInterests.length" class="interest-tags">
          <span v-for="interest in group.sharedInterests" :key="interest" class="interest-tag">
            {{ interest }}
          </span>
        </div>
        <p v-else class="supervisor-muted">No areas of interest tagged yet.</p>

        <h3>Existing Students</h3>
        <ul class="student-rows">
          <li v-for="student in group.students" :key="student.id">
            <button
              type="button"
              class="student-row"
              draggable="true"
              @dragstart="onDragStart($event, student.id)"
            >
              {{ studentName(student) }}
            </button>
          </li>
          <li v-if="!group.students.length" class="supervisor-muted">No students in this group.</li>
        </ul>

        <div class="drop-zone">
          <p>Recommended / Moved</p>
          <p class="drop-hint">drop students here</p>
          <label>
            Move a student into this group
            <select :disabled="moveBusy" @change="onSelectMove($event, group.id)">
              <option value="">Select a student</option>
              <option
                v-for="student in movableStudents(group.id)"
                :key="student.id"
                :value="student.id"
              >
                {{ studentName(student) }}
              </option>
            </select>
          </label>
        </div>
      </article>
    </section>

    <GroupEditorModal
      v-if="editorGroup"
      :group="editorGroup"
      :mode="editorMode"
      :existing-names="existingGroupNames"
      :mentors-available="mentors"
      :students-available="studentChoices"
      :current-user-id="auth.user?.id ?? null"
      @close="closeEditor"
      @updated="onGroupUpdated"
      @deleted="onGroupDeleted"
    />

    <div v-if="pendingBulkDelete" class="bulk-delete-backdrop">
      <section class="bulk-delete-card" role="dialog" aria-modal="true">
        <h3>Delete selected groups?</h3>
        <p>
          Delete {{ selectedGroupIds.size }} group{{ selectedGroupIds.size === 1 ? '' : 's' }}?
          Students in them will return to the waiting area.
        </p>
        <div class="bulk-delete-actions">
          <button type="button" class="btn btn-outline" @click="pendingBulkDelete = false">Cancel</button>
          <button type="button" class="btn btn-primary" :disabled="bulkBusy" @click="deleteSelectedGroups">
            Delete groups
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import GroupEditorModal from '@/components/supervisor/GroupEditorModal.vue'
import { useAuthStore } from '@/stores/auth'
import { useGroupsStore } from '@/stores/groups'
import { buildSessionHeaders } from '@/utils/csrf'
import {
  addSupervisedGroupMembers,
  deleteSupervisedGroup,
  fetchAvailableMentors,
  fetchSupervisedGroups,
  removeSupervisedGroupMembers,
  type AvailableMentor,
  type SupervisedGroup,
} from '@/utils/supervisedGroups'
import {
  fetchSupervisedStudents,
  fullName,
  type SupervisedStudent,
} from '@/utils/supervisedStudents'

const GROUP_LIMIT = 5
const groupLimit = GROUP_LIMIT
const auth = useAuthStore()
const groupsStore = useGroupsStore()
const loading = ref(true)
const error = ref('')
const students = ref<SupervisedStudent[]>([])
const assignment = ref<Record<number, number | null>>({})
const supervisedGroups = ref<SupervisedGroup[]>([])
const mentors = ref<AvailableMentor[]>([])
const editorGroup = ref<SupervisedGroup | null>(null)
const editorMode = ref<'create' | 'edit'>('edit')
const selectedGroupIds = ref<Set<number>>(new Set())
const optionChoice = ref('')
const pendingBulkDelete = ref(false)
const bulkBusy = ref(false)
const moveBusy = ref(false)

const studentChoices = computed<AvailableMentor[]>(() =>
  students.value.map((student) => ({
    id: student.id,
    first_name: student.first_name,
    last_name: student.last_name,
    email: student.email,
  })),
)

const studentName = (student: SupervisedStudent) =>
  fullName(student.first_name, student.last_name, student.email)

const waitingStudents = computed(() =>
  students.value.filter((student) => !assignment.value[student.id]),
)

const groups = computed(() => {
  const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })
  return [...supervisedGroups.value]
    .sort((left, right) => collator.compare(left.group_name, right.group_name))
    .map((owned) => {
      const members = students.value.filter(
        (student) => assignment.value[student.id] === owned.id,
      )
      const tagged = owned.interests ?? []
      const sharedInterests = tagged.length
        ? tagged
        : [...new Set(members.flatMap((member) => member.interests))]
      return {
        id: owned.id,
        name: owned.group_name,
        supervisorName: auth.displayName,
        students: members,
        sharedInterests,
      }
    })
})

const existingGroupNames = computed(() => {
  const names = [
    ...groups.value.map((group) => group.name),
    ...supervisedGroups.value.map((group) => group.group_name),
  ]
  if (editorMode.value === 'edit' && editorGroup.value) {
    return names.filter((name) => name !== editorGroup.value?.group_name)
  }
  return [...new Set(names)]
})

const allGroupsSelected = computed(
  () => groups.value.length > 0 && groups.value.every((group) => selectedGroupIds.value.has(group.id)),
)
const someGroupsSelected = computed(
  () => !allGroupsSelected.value && groups.value.some((group) => selectedGroupIds.value.has(group.id)),
)

const toggleGroup = (groupId: number) => {
  const next = new Set(selectedGroupIds.value)
  if (next.has(groupId)) next.delete(groupId)
  else next.add(groupId)
  selectedGroupIds.value = next
}

const toggleSelectAll = () => {
  selectedGroupIds.value = allGroupsSelected.value
    ? new Set()
    : new Set(groups.value.map((group) => group.id))
}

const onGroupOption = (event: Event) => {
  const value = (event.target as HTMLSelectElement).value
  optionChoice.value = ''
  if (value === 'select-all') selectedGroupIds.value = new Set(groups.value.map((group) => group.id))
  if (value === 'clear-selection') selectedGroupIds.value = new Set()
  if (value === 'delete-selected' && selectedGroupIds.value.size) pendingBulkDelete.value = true
}

const movableStudents = (groupId: number) =>
  students.value.filter((student) => assignment.value[student.id] !== groupId)

const applyOwnedGroup = (group: SupervisedGroup) => {
  const index = supervisedGroups.value.findIndex((item) => item.id === group.id)
  if (index >= 0) supervisedGroups.value.splice(index, 1, group)
  else supervisedGroups.value.push(group)
  groupsStore.upsert({ id: group.id, group_name: group.group_name, member_count: group.members.length })
  syncAssignmentsFromGroup(group)
}

const dropStudentFromOtherGroups = (studentId: number, exceptGroupId?: number | null) => {
  supervisedGroups.value = supervisedGroups.value.map((group) => {
    if (exceptGroupId != null && group.id === exceptGroupId) return group
    const members = group.members.filter(
      (member) => !(member.id === studentId && member.role === 'student'),
    )
    if (members.length === group.members.length) return group
    groupsStore.upsert({ id: group.id, group_name: group.group_name, member_count: members.length })
    return { ...group, members }
  })
}

const setStudentGroup = (studentId: number, groupId: number | null) => {
  const groupName = groupId
    ? supervisedGroups.value.find((group) => group.id === groupId)?.group_name ?? null
    : null
  students.value = students.value.map((student) =>
    student.id === studentId ? { ...student, group_id: groupId, group_name: groupName } : student,
  )
}

const moveStudent = async (studentId: number, groupId: number | null) => {
  const fromGroupId = assignment.value[studentId] ?? null
  if (fromGroupId === groupId || moveBusy.value) return
  if (groupId != null) {
    const dest = supervisedGroups.value.find((group) => group.id === groupId)
    if (!dest) {
      error.value = 'You can only move students into groups you supervise.'
      return
    }
    const destCount = students.value.filter((student) => assignment.value[student.id] === groupId).length
    if (destCount >= GROUP_LIMIT) {
      error.value = `This group already has ${GROUP_LIMIT} students.`
      return
    }
  }

  moveBusy.value = true
  error.value = ''
  const previous = fromGroupId
  assignment.value = { ...assignment.value, [studentId]: groupId }
  try {
    if (fromGroupId != null && groupId == null) {
      applyOwnedGroup(await removeSupervisedGroupMembers(fromGroupId, [studentId]))
    } else if (groupId != null) {
      const updated = await addSupervisedGroupMembers(groupId, [studentId], 'student')
      dropStudentFromOtherGroups(studentId, groupId)
      applyOwnedGroup(updated)
    }
    setStudentGroup(studentId, groupId)
  } catch (moveError) {
    assignment.value = { ...assignment.value, [studentId]: previous }
    error.value = moveError instanceof Error ? moveError.message : 'Student could not be moved.'
  } finally {
    moveBusy.value = false
  }
}

const onDragStart = (event: DragEvent, studentId: number) => {
  event.dataTransfer?.setData('text/plain', String(studentId))
}

const onDropWaiting = (event: DragEvent) => {
  const studentId = Number(event.dataTransfer?.getData('text/plain'))
  if (Number.isFinite(studentId)) void moveStudent(studentId, null)
}

const onDrop = (event: DragEvent, groupId: number) => {
  const studentId = Number(event.dataTransfer?.getData('text/plain'))
  if (Number.isFinite(studentId)) void moveStudent(studentId, groupId)
}

const onSelectMove = (event: Event, groupId: number) => {
  const select = event.target as HTMLSelectElement
  const studentId = Number(select.value)
  if (studentId) void moveStudent(studentId, groupId)
  select.value = ''
}

const syncAssignmentsFromGroup = (group: SupervisedGroup) => {
  const studentIds = new Set(
    group.members.filter((member) => member.role === 'student').map((member) => member.id),
  )
  const next = { ...assignment.value }
  for (const student of students.value) {
    if (next[student.id] === group.id && !studentIds.has(student.id)) next[student.id] = null
    if (studentIds.has(student.id)) next[student.id] = group.id
  }
  assignment.value = next
}

const onGroupDeleted = (groupId: number) => {
  supervisedGroups.value = supervisedGroups.value.filter((group) => group.id !== groupId)
  groupsStore.groups = groupsStore.groups.filter((group) => Number(group.id) !== groupId)
  const next = { ...assignment.value }
  for (const studentId of Object.keys(next)) {
    if (next[Number(studentId)] === groupId) next[Number(studentId)] = null
  }
  assignment.value = next
  const selected = new Set(selectedGroupIds.value)
  selected.delete(groupId)
  selectedGroupIds.value = selected
  closeEditor()
}

const onGroupUpdated = (group: SupervisedGroup) => {
  for (const member of group.members) {
    if (member.role === 'student') dropStudentFromOtherGroups(member.id, group.id)
  }
  applyOwnedGroup(group)
  editorMode.value = 'edit'
  editorGroup.value = group
}

const closeEditor = () => {
  editorGroup.value = null
  editorMode.value = 'edit'
}

const editGroup = (groupId: number) => {
  const found = supervisedGroups.value.find((group) => group.id === groupId)
  if (!found) {
    error.value = 'You can only edit groups you supervise.'
    return
  }
  editorMode.value = 'edit'
  editorGroup.value = found
}

const openCreateGroup = () => {
  error.value = ''
  editorMode.value = 'create'
  editorGroup.value = {
    id: 0,
    group_name: 'New Group',
    interests: [],
    members: auth.user
      ? [
          {
            id: auth.user.id,
            first_name: auth.user.first_name,
            last_name: auth.user.last_name,
            email: auth.user.email,
            role: 'supervisor',
          },
        ]
      : [],
  }
}

const deleteSelectedGroups = async () => {
  bulkBusy.value = true
  error.value = ''
  try {
    for (const groupId of [...selectedGroupIds.value]) {
      await deleteSupervisedGroup(groupId)
      onGroupDeleted(groupId)
    }
    pendingBulkDelete.value = false
  } catch (deleteError) {
    error.value = deleteError instanceof Error ? deleteError.message : 'Selected groups could not be deleted.'
  } finally {
    bulkBusy.value = false
  }
}

onMounted(async () => {
  loading.value = true
  error.value = ''
  try {
    const [roster, owned, mentorList] = await Promise.all([
      fetchSupervisedStudents(buildSessionHeaders({ headers: { Accept: 'application/json' } })),
      fetchSupervisedGroups(),
      fetchAvailableMentors(),
      groupsStore.load(true),
    ])
    students.value = roster
    supervisedGroups.value = owned
    mentors.value = mentorList
    const next: Record<number, number | null> = {}
    for (const student of roster) {
      next[student.id] = student.group_id
    }
    assignment.value = next
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : 'Groups could not be loaded.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.waiting-area,
.group-card {
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  box-shadow: 0 2px 4px var(--shadow);
}

.waiting-area {
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.5rem;
}

.waiting-area-header,
.group-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.waiting-area-header h1,
.group-card-header h2 {
  margin: 0;
}

.waiting-area-header h1 {
  font-size: 1.5rem;
}

.waiting-copy,
.supervisor-muted,
.group-card-header p {
  color: #6c757d;
  margin: 0.45rem 0 0.85rem;
}

.waiting-count,
.group-count {
  min-width: 2.5rem;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  background: var(--accent-green-soft, #e7f3ea);
  color: var(--dark-green);
  font-weight: 700;
  text-align: center;
}

.waiting-bubbles {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.student-bubble,
.student-row {
  border: 1px solid var(--border-light);
  background: #f7faf7;
  border-radius: 8px;
  padding: 0.45rem 0.75rem;
  cursor: grab;
}

.waiting-empty {
  margin: 0;
}

.groups-board {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1rem;
}

.groups-board-toolbar,
.groups-board-heading,
.group-select-all,
.group-card-title,
.groups-bulk,
.bulk-delete-actions {
  display: flex;
  align-items: center;
}

.groups-board-toolbar {
  grid-column: 1 / -1;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.groups-board-heading,
.group-select-all,
.group-card-title,
.groups-bulk {
  gap: 0.65rem;
}

.groups-board-toolbar h2,
.groups-options {
  margin: 0;
  font-size: 1.2rem;
}

.groups-options {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: #6c757d;
  font-size: 0.9rem;
}

.groups-options select {
  padding: 0.35rem 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--white);
}

.groups-bulk {
  grid-column: 1 / -1;
  margin: 0;
  color: #6c757d;
}

.group-card.selected {
  outline: 2px solid var(--dark-green);
}

.group-card-actions {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.bulk-delete-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: 1.5rem;
  background: rgba(23, 66, 67, 0.4);
}

.bulk-delete-card {
  width: min(28rem, 100%);
  padding: 1.25rem;
  border-radius: 12px;
  background: var(--white);
}

.bulk-delete-card h3,
.bulk-delete-card p {
  margin: 0 0 0.75rem;
}

.bulk-delete-actions {
  justify-content: flex-end;
  gap: 0.6rem;
}

.group-card {
  padding: 1.15rem;
}

.group-card h2 {
  font-size: 1.2rem;
}

.group-card h3 {
  margin: 1rem 0 0.5rem;
  font-size: 0.95rem;
}

.interest-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.interest-tag {
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background: var(--accent-green-soft, #e7f3ea);
  color: var(--dark-green);
  font-size: 0.85rem;
}

.student-rows {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.student-row {
  width: 100%;
  text-align: left;
}

.drop-zone {
  margin-top: 1rem;
  padding: 0.9rem;
  border: 1px dashed var(--dark-green);
  border-radius: 8px;
  background: #f8fbf8;
}

.drop-zone p {
  margin: 0;
  font-weight: 600;
}

.drop-hint {
  font-weight: 400 !important;
  color: #6c757d;
  margin: 0.25rem 0 0.75rem !important;
}

.drop-zone label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  color: #6c757d;
  font-size: 0.9rem;
}

.drop-zone select {
  padding: 0.45rem 0.55rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
}

.supervisor-error {
  color: var(--danger, #b42318);
}
</style>
