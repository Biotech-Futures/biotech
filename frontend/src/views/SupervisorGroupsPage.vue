<template>
  <div class="content-area supervisor-groups-page">
    <p v-if="loading" class="supervisor-muted">Loading groups...</p>

    <section v-else class="waiting-area" aria-label="Waiting Area" @dragover.prevent @drop="onDropWaiting">
      <p v-if="flashMessage" class="waiting-flash" role="status">{{ flashMessage }}</p>
      <div class="waiting-area-header">
        <h1>Waiting Area</h1>
        <span class="waiting-count">
          {{ waitingStudents.length }} {{ waitingStudents.length === 1 ? 'Student' : 'Students' }}
        </span>
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
              class="group-check"
              :checked="allGroupsSelected"
              :indeterminate.prop="someGroupsSelected"
              :aria-label="allGroupsSelected ? 'Deselect all groups' : 'Select all groups'"
              @change="toggleSelectAll"
            />
            <h2>My Groups</h2>
          </label>
        </div>
        <div class="groups-board-toolbar-actions">
          <button type="button" class="btn btn-primary" @click="openCreateGroup">Create Group</button>
        </div>
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
              class="group-check"
              :checked="selectedGroupIds.has(group.id)"
              :aria-label="`Select ${group.name}`"
              @change="toggleGroup(group.id)"
            />
            <div>
              <h2>{{ group.name }}</h2>
              <p class="group-id">Group ID {{ group.id }}</p>
            </div>
          </div>
          <div class="group-card-actions">
            <span class="group-count">{{ group.students.length }}/{{ groupLimit }}</span>
          </div>
        </div>

        <div v-if="group.sharedInterests.length" class="interest-tags">
          <span v-for="interest in group.sharedInterests" :key="interest" class="interest-tag">
            {{ interest }}
          </span>
        </div>
        <p v-else class="supervisor-muted">No areas of interest tagged yet.</p>

        <h3>Students</h3>
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
          <li v-if="!group.students.length" class="supervisor-muted">
            No students in this group. Drop a student here.
          </li>
        </ul>
      </article>
    </section>

    <GroupEditorModal
      v-if="editorGroup"
      :group="editorGroup"
      mode="create"
      :students-available="studentChoices"
      :current-user-id="auth.user?.id ?? null"
      @close="closeEditor"
      @updated="onGroupUpdated"
      @deleted="onGroupDeleted"
    />

    <div v-if="pendingSchoolMove" class="bulk-delete-backdrop">
      <section class="bulk-delete-card" role="dialog" aria-modal="true" aria-labelledby="school-match-title">
        <h3 id="school-match-title">
          {{ pendingSchoolMove.kind === 'outside' ? 'Match outside school?' : 'Match inside school?' }}
        </h3>
        <p>{{ pendingSchoolMove.message }}</p>
        <div class="bulk-delete-actions">
          <button type="button" class="btn btn-outline" @click="pendingSchoolMove = null">Cancel</button>
          <button type="button" class="btn btn-primary" @click="confirmSchoolMove">Confirm</button>
        </div>
      </section>
    </div>

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
import { computed, onMounted, onUnmounted, ref } from 'vue'
import GroupEditorModal from '@/components/supervisor/GroupEditorModal.vue'
import { useAuthStore } from '@/stores/auth'
import { useGroupsStore } from '@/stores/groups'
import { buildSessionHeaders } from '@/utils/csrf'
import {
  addSupervisedGroupMembers,
  deleteSupervisedGroup,
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
const flashMessage = ref('')
let flashTimer: ReturnType<typeof setTimeout> | null = null
const students = ref<SupervisedStudent[]>([])
const assignment = ref<Record<number, number | null>>({})
const supervisedGroups = ref<SupervisedGroup[]>([])
const editorGroup = ref<SupervisedGroup | null>(null)
const selectedGroupIds = ref<Set<number>>(new Set())
const pendingBulkDelete = ref(false)
const pendingSchoolMove = ref<{
  studentId: number
  groupId: number
  kind: 'inside' | 'outside'
  message: string
} | null>(null)
const bulkBusy = ref(false)
const moveBusy = ref(false)

const clearFlash = () => {
  if (flashTimer) {
    clearTimeout(flashTimer)
    flashTimer = null
  }
  flashMessage.value = ''
}

const showFlash = (message: string) => {
  if (flashTimer) {
    clearTimeout(flashTimer)
    flashTimer = null
  }
  flashMessage.value = message
  if (!message) return
  flashTimer = setTimeout(() => {
    flashMessage.value = ''
    flashTimer = null
  }, 5000)
}

onUnmounted(clearFlash)

const studentChoices = computed<AvailableMentor[]>(() =>
  students.value.map((student) => ({
    id: student.id,
    first_name: student.first_name,
    last_name: student.last_name,
    email: student.email,
    group_id: student.group_id,
    group_name: student.group_name,
    school_name: student.school_name,
  })),
)

const studentName = (student: SupervisedStudent) =>
  fullName(student.first_name, student.last_name, student.email)

const normalizeSchool = (value?: string | null) => (value || '').trim().toLowerCase()

const listSchools = (schools: string[]) => {
  if (schools.length <= 1) return schools[0] || 'another school'
  if (schools.length === 2) return `${schools[0]} and ${schools[1]}`
  return `${schools.slice(0, -1).join(', ')}, and ${schools[schools.length - 1]}`
}

const schoolsInGroup = (groupId: number, exceptStudentId?: number) => {
  const seen = new Map<string, string>()
  for (const student of students.value) {
    if (assignment.value[student.id] !== groupId || student.id === exceptStudentId) continue
    const label = student.school_name?.trim()
    if (!label) continue
    const key = label.toLowerCase()
    if (!seen.has(key)) seen.set(key, label)
  }
  return [...seen.values()]
}

const schoolMovePrompt = (student: SupervisedStudent, groupId: number) => {
  const studentSchool = student.school_name?.trim()
  if (!studentSchool) return null
  const destSchools = schoolsInGroup(groupId, student.id)
  const groupName = supervisedGroups.value.find((group) => group.id === groupId)?.group_name || 'this group'
  const name = studentName(student)
  const isOutside =
    destSchools.length > 0 &&
    destSchools.some((school) => normalizeSchool(school) !== normalizeSchool(studentSchool))
  if (!isOutside) return null
  return {
    kind: 'outside' as const,
    message: `${name} is from ${studentSchool}. ${groupName} has students from ${listSchools(destSchools)}. Assigning them will match this student outside their school.`,
  }
}

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
        students: members,
        sharedInterests,
      }
    })
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
      showFlash('You can only move students into groups you supervise.')
      return
    }
    const destCount = students.value.filter((student) => assignment.value[student.id] === groupId).length
    if (destCount >= GROUP_LIMIT) {
      showFlash(`This group already has ${GROUP_LIMIT} students.`)
      return
    }
  }

  moveBusy.value = true
  clearFlash()
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
    showFlash(moveError instanceof Error ? moveError.message : 'Student could not be moved.')
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
  if (!Number.isFinite(studentId)) return
  const student = students.value.find((item) => item.id === studentId)
  if (!student) return
  const prompt = schoolMovePrompt(student, groupId)
  if (prompt) {
    pendingSchoolMove.value = { studentId, groupId, ...prompt }
    return
  }
  void moveStudent(studentId, groupId)
}

const confirmSchoolMove = () => {
  const pending = pendingSchoolMove.value
  if (!pending) return
  pendingSchoolMove.value = null
  void moveStudent(pending.studentId, pending.groupId)
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
}

const closeEditor = () => {
  editorGroup.value = null
}

const openCreateGroup = () => {
  clearFlash()
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
  clearFlash()
  try {
    for (const groupId of [...selectedGroupIds.value]) {
      await deleteSupervisedGroup(groupId)
      onGroupDeleted(groupId)
    }
    pendingBulkDelete.value = false
  } catch (deleteError) {
    showFlash(deleteError instanceof Error ? deleteError.message : 'Selected groups could not be deleted.')
  } finally {
    bulkBusy.value = false
  }
}

onMounted(async () => {
  loading.value = true
  clearFlash()
  try {
    const [roster, owned] = await Promise.all([
      fetchSupervisedStudents(buildSessionHeaders({ headers: { Accept: 'application/json' } })),
      fetchSupervisedGroups(),
      groupsStore.load(true),
    ])
    students.value = roster
    supervisedGroups.value = owned
    const next: Record<number, number | null> = {}
    for (const student of roster) {
      next[student.id] = student.group_id
    }
    assignment.value = next
  } catch (loadError) {
    showFlash(loadError instanceof Error ? loadError.message : 'Groups could not be loaded.')
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.waiting-area,
.group-card {
  background: var(--white);
  border: 1px solid #e0e0e0;
  border-radius: 10px;
}

.waiting-area {
  position: relative;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.5rem;
}

.waiting-flash {
  position: absolute;
  left: 1.25rem;
  right: 1.25rem;
  top: 1.15rem;
  z-index: 2;
  margin: 0;
  padding: 0.7rem 0.9rem;
  border: 1px solid #f0b4b0;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.96);
  color: var(--danger, #b42318);
  font-weight: 600;
  text-align: center;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.08);
  pointer-events: none;
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

.group-id {
  margin: 0.2rem 0 0;
  font-size: 0.82rem;
  color: #6c757d;
}

.waiting-count,
.group-count {
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  background: #f0f0f0;
  color: #333;
  font-weight: 700;
  text-align: center;
  white-space: nowrap;
}

.group-count {
  min-width: 2.5rem;
}

.waiting-bubbles {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.student-bubble {
  border: 1px solid #d0d0d0;
  background: #fafafa;
  border-radius: 6px;
  padding: 0.4rem 0.7rem;
  cursor: grab;
  color: #333;
  font-size: 0.9rem;
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
.groups-board-toolbar-actions,
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
.groups-bulk,
.groups-board-toolbar-actions {
  gap: 0.65rem;
}

.groups-board-toolbar h2 {
  margin: 0;
  font-size: 1.2rem;
}

.group-check {
  appearance: none;
  -webkit-appearance: none;
  width: 1.1rem;
  height: 1.1rem;
  border: 2px solid #c0c0c0;
  border-radius: 3px;
  background: #fff;
  cursor: pointer;
  flex-shrink: 0;
  position: relative;
}

.group-check:checked {
  background: var(--dark-green, #017151);
  border-color: var(--dark-green, #017151);
}

.group-check:checked::after {
  content: '✓';
  color: #fff;
  font-size: 0.75rem;
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.group-check:indeterminate {
  background: var(--dark-green, #017151);
  border-color: var(--dark-green, #017151);
}

.group-check:indeterminate::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0.55rem;
  height: 2px;
  background: #fff;
  transform: translate(-50%, -50%);
}

.groups-bulk {
  grid-column: 1 / -1;
  margin: 0;
  color: #6c757d;
}

.group-card.selected {
  outline: 2px solid #333;
}

.group-card-actions {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.bulk-delete-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1100;
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
  color: var(--dark-green);
}

.group-card h3 {
  margin: 0.85rem 0 0.4rem;
  font-size: 0.9rem;
  color: #333;
  font-weight: 600;
}

.interest-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.4rem;
}

.interest-tag {
  padding: 0.18rem 0.5rem;
  border-radius: 999px;
  background: #f0f0f0;
  color: #333;
  font-size: 0.82rem;
}

.student-rows {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-height: 2.5rem;
}

.student-row {
  width: 100%;
  text-align: left;
  border: 1px solid #e0e0e0;
  background: #fafafa;
  border-radius: 6px;
  padding: 0.4rem 0.7rem;
  cursor: grab;
  color: #333;
  font-size: 0.9rem;
}
</style>
