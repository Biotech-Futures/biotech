<template>
  <div class="content-area supervisor-groups-page">
    <p v-if="loading" class="supervisor-muted">Loading groups...</p>

    <section v-else class="waiting-area" aria-label="Waiting Area" @dragover="onDragOverWaiting" @drop="onDropWaiting">
      <p v-if="flashMessage" class="waiting-flash" role="status">{{ flashMessage }}</p>
      <div class="waiting-area-header">
        <h1>Waiting Area</h1>
        <span class="waiting-count">
          {{ waitingCount }} {{ waitingCount === 1 ? 'Student' : 'Students' }}
        </span>
      </div>
      <!-- Each its own paragraph, the same gap between each line of text and
           above the students. -->
      <p class="waiting-copy waiting-copy--tight">
        Students in this area will be assigned to a group on the challenge start date.
        Students will be matched to groups in your school, or in or out of your school.
      </p>
      <p class="waiting-copy waiting-copy--tight">Click a student to see their details.</p>
      <p class="waiting-copy">Drag and drop students around the page from one box to another.</p>
      <!-- Groups formed while registering, a line each: those the supervisor
           registered, then those their students formed. Not named: they
           aren't BIOTech groups until made so (Create all groups). Students go
           from here into a group below, not from one part of the Waiting Area
           to another; back here, onto their own line (waitingLineOf). A line
           with none of its students here isn't shown. -->
      <div
        v-for="section in waitingSections"
        :key="section.title"
        class="waiting-section"
      >
        <div class="waiting-section-header">
          <h2 class="waiting-section-title">{{ section.title }}</h2>
          <!-- Makes them BIOTech groups, onto the Groups board below. -->
          <button
            type="button"
            class="btn btn-primary btn-sm"
            :data-test="`create-all-${section.registeredBy}`"
            @click="pendingCreateAll = section"
          >
            Create all groups
          </button>
        </div>
        <div v-for="group in section.groups" :key="group.id" class="waiting-group">
          <span class="waiting-group-label">Group:</span>
          <div class="waiting-bubbles">
            <button
              v-for="student in group.students"
              :key="student.id"
              type="button"
              class="student-bubble"
              draggable="true"
              @dragstart="onDragStart($event, student.id)"
              @dragend="draggingId = null"
              @click="sheetStudentId = student.id"
            >
              {{ studentName(student) }}
            </button>
          </div>
        </div>
      </div>
      <div class="waiting-section">
        <h2 class="waiting-section-title">Students without a group</h2>
        <div class="waiting-bubbles">
          <button
            v-for="student in waitingStudents"
            :key="student.id"
            type="button"
            class="student-bubble"
            draggable="true"
            @dragstart="onDragStart($event, student.id)"
            @dragend="draggingId = null"
            @click="sheetStudentId = student.id"
          >
            {{ studentName(student) }}
          </button>
          <p v-if="!waitingStudents.length" class="supervisor-muted waiting-empty">
            No unassigned students.
          </p>
        </div>
      </div>
    </section>

    <section v-if="!loading" class="groups-board">
      <div class="groups-board-toolbar">
        <div class="groups-board-heading">
          <h2>Groups</h2>
        </div>
        <div class="groups-board-toolbar-actions">
          <button type="button" class="btn btn-primary" @click="openCreateGroup">Create Group</button>
        </div>
      </div>
      <div v-if="groups.length" class="groups-bulk">
        <label class="groups-select-all">
          <input type="checkbox" class="group-check" :checked="allSelected" @change="toggleSelectAll" />
          Select all
        </label>
        <!-- There, hidden, while nothing's ticked: the row is already as tall
             as with Delete selected, so ticking a card doesn't move the cards. -->
        <span :class="{ 'groups-bulk-hidden': !selectedGroupIds.size }">{{ selectedGroupIds.size }} selected</span>
        <span class="groups-bulk-actions" :class="{ 'groups-bulk-hidden': !selectedGroupIds.size }">
          <button type="button" class="btn btn-outline btn-sm" @click="pendingBulkDelete = true">
            Delete selected
          </button>
        </span>
      </div>
      <article
        v-for="group in groups"
        :key="group.id"
        class="group-card"
        :class="{
          selected: selectedGroupIds.has(group.id),
          'group-card--full': isFullFor(group),
          'group-card--drop-target': dropTargetGroupId === group.id,
          'group-card--moving': draggingGroupId === group.id,
        }"
        @dragover="onDragOver($event, group)"
        @drop="onDrop($event, group.id)"
      >
        <div class="group-card-header">
          <div class="group-card-title">
            <!-- Drag a group by this to move it among the others. -->
            <span
              class="group-drag-handle"
              draggable="true"
              :title="`Drag to move ${group.name}`"
              :aria-label="`Move ${group.name}`"
              @dragstart="onGroupDragStart($event, group.id)"
              @dragend="endGroupDrag"
            >
              <i class="fas fa-grip-vertical" aria-hidden="true"></i>
            </span>
            <input
              type="checkbox"
              class="group-check"
              :checked="selectedGroupIds.has(group.id)"
              :aria-label="`Select ${group.name}`"
              @change="toggleGroup(group.id)"
            />
            <h2>{{ group.name }}</h2>
          </div>
          <div class="group-card-actions">
            <span class="group-count">{{ group.size }}/{{ groupLimit }}</span>
          </div>
        </div>

        <!-- What its students share, each counted, headed like Students. -->
        <h3>Shared Area(s) of Interest</h3>
        <SharedInterestChips
          v-if="group.shared.length"
          :interests="group.shared"
          :total="group.students.length"
          numbered
        />
        <p v-else class="supervisor-muted">None yet.</p>

        <h3>Students</h3>
        <ul class="student-rows">
          <li v-for="(student, index) in group.students" :key="student.id">
            <button
              type="button"
              class="student-row"
              draggable="true"
              @dragstart="onDragStart($event, student.id)"
              @dragend="draggingId = null"
              @click="sheetStudentId = student.id"
            >
              <!-- The number the areas of interest above show them by. -->
              <span class="student-number">{{ index + 1 }}</span>
              {{ studentName(student) }}
            </button>
          </li>
          <!-- Another supervisor's students: greyed, not the supervisor's to move. -->
          <li v-for="member in group.others" :key="`other-${member.id}`">
            <span class="student-row student-row--other" title="Another supervisor's student">
              {{ fullName(member.first_name, member.last_name, member.email) }}
              <small>Another supervisor's student</small>
            </span>
          </li>
          <li v-if="!group.size" class="supervisor-muted">No students in this group.</li>
          <!-- Under the students until the group is full. Only a hint: a drop on
               it lands on the card, as anywhere else on it. -->
          <li v-if="group.size < groupLimit" class="drop-hint">
            Drag and drop students from other boxes
          </li>
        </ul>
      </article>
    </section>

    <!-- A student's details, opened by clicking their box, as on My Students. -->
    <SupervisorStudentSheet
      :student="sheetStudent"
      @close="sheetStudentId = null"
      @saved="students = $event"
      @updated="students = students.map((student) => (student.id === $event.id ? $event : student))"
    />

    <GroupEditorModal
      v-if="editorGroup"
      :group="editorGroup"
      mode="create"
      :students-available="studentChoices"
      :current-user-id="auth.user?.id ?? null"
      @close="closeEditor"
      @updated="onGroupUpdated"
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

    <div v-if="pendingCreateAll" class="bulk-delete-backdrop">
      <section class="bulk-delete-card" role="dialog" aria-modal="true" aria-labelledby="create-all-title">
        <h3 id="create-all-title">
          Create {{ pendingCreateAll.groups.length }} group{{ pendingCreateAll.groups.length === 1 ? '' : 's' }}?
        </h3>
        <p>
          {{ pendingCreateAll.title }} become BIOTech groups and move to Groups below, where their
          students can be moved like any group's.
        </p>
        <div class="bulk-delete-actions">
          <button type="button" class="btn btn-outline" @click="pendingCreateAll = null">Cancel</button>
          <button type="button" class="btn btn-primary" :disabled="bulkBusy" @click="createAllGroups">
            Create groups
          </button>
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
import SharedInterestChips from '@/components/SharedInterestChips.vue'
import GroupEditorModal from '@/components/supervisor/GroupEditorModal.vue'
import SupervisorStudentSheet from '@/components/supervisor/SupervisorStudentSheet.vue'
import { useAuthStore } from '@/stores/auth'
import { useGroupsStore } from '@/stores/groups'
import { buildSessionHeaders } from '@/utils/csrf'
import {
  addSupervisedGroupMembers,
  createAllWaitingGroups,
  deleteSupervisedGroup,
  fetchSupervisedGroups,
  saveSupervisedGroupOrder,
  removeSupervisedGroupMembers,
  type AvailableMentor,
  type SupervisedGroup,
} from '@/utils/supervisedGroups'
import {
  fetchSupervisedStudents,
  fullName,
  type SupervisedStudent,
} from '@/utils/supervisedStudents'
import { DEFAULT_GROUP_MAX_SIZE, GROUP_FULL_MESSAGE } from '@/utils/groupCapacity'
import { sharedInterests } from '@/utils/groupInterests'

const GROUP_LIMIT = DEFAULT_GROUP_MAX_SIZE
const groupLimit = GROUP_LIMIT
const auth = useAuthStore()
const groupsStore = useGroupsStore()
const loading = ref(true)
const flashMessage = ref('')
let flashTimer: ReturnType<typeof setTimeout> | null = null
const students = ref<SupervisedStudent[]>([])
// The student whose details panel is open.
const sheetStudentId = ref<number | null>(null)
const sheetStudent = computed(() => students.value.find((student) => student.id === sheetStudentId.value) ?? null)
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
    interests: student.interests,
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

const rosterIds = computed(() => new Set(students.value.map((student) => student.id)))

// In the supervisor's own order, as the server gives it and moving them sets.
// A group can be shared with another supervisor (their student in it too):
// those students aren't the supervisor's to move, but count towards its 5.
const allGroups = computed(() =>
  supervisedGroups.value.map((owned) => {
    const members = students.value.filter((student) => assignment.value[student.id] === owned.id)
    const others = owned.members.filter(
      (member) => member.role === 'student' && !rosterIds.value.has(member.id),
    )
    return {
      id: owned.id,
      name: owned.group_name,
      registeredBy: owned.registered_by || '',
      placed: Boolean(owned.placed),
      students: members,
      others,
      size: members.length + others.length,
      shared: sharedInterests(members.map((member) => member.interests)),
    }
  }),
)
const groupById = computed(() => new Map(allGroups.value.map((group) => [group.id, group])))

// The Groups board: groups made here (or by an admin), and those formed while
// registering once made BIOTech groups. The rest wait in the Waiting Area.
const groups = computed(() => allGroups.value.filter((group) => !group.registeredBy || group.placed))

// A student's place: undefined when in a group on the board; otherwise in the
// Waiting Area, on the line of the group they registered in (the group
// itself while it waits there, or its line once it's a BIOTech group they've
// come back from), or null with no line, having registered alone.
const waitingLineOf = (student: SupervisedStudent) => {
  const current = assignment.value[student.id]
  if (current != null) {
    const group = groupById.value.get(current)
    return group?.registeredBy && !group.placed ? group : undefined
  }
  const home = student.registration_group_id
  const group = home != null ? groupById.value.get(home) : undefined
  return group?.registeredBy ? group : null
}

// Everyone in the Waiting Area: each line's students, and those with none.
const waitingArea = computed(() => {
  const lines = new Map<number, SupervisedStudent[]>()
  const alone: SupervisedStudent[] = []
  for (const student of students.value) {
    const line = waitingLineOf(student)
    if (line === null) alone.push(student)
    else if (line) lines.set(line.id, [...(lines.get(line.id) ?? []), student])
  }
  return { lines, alone }
})

const waitingStudents = computed(() => waitingArea.value.alone)

// A section's lines, in the groups' order: each with its students here.
const waitingGroups = (registeredBy: string) =>
  allGroups.value
    .filter((group) => group.registeredBy === registeredBy && waitingArea.value.lines.has(group.id))
    .map((group) => ({ id: group.id, students: waitingArea.value.lines.get(group.id)! }))

const waitingSections = computed(() =>
  [
    { title: 'Groups you registered', registeredBy: 'supervisor' as const, groups: waitingGroups('supervisor') },
    { title: 'Groups students formed', registeredBy: 'members' as const, groups: waitingGroups('members') },
  ].filter((section) => section.groups.length),
)

// Create all groups, waiting for its confirm: one section's groups.
const pendingCreateAll = ref<(typeof waitingSections.value)[number] | null>(null)

const createAllGroups = async () => {
  const section = pendingCreateAll.value
  if (!section) return
  bulkBusy.value = true
  clearFlash()
  try {
    for (const group of await createAllWaitingGroups(section.registeredBy)) applyOwnedGroup(group)
    pendingCreateAll.value = null
  } catch (createError) {
    showFlash(createError instanceof Error ? createError.message : 'The groups could not be created.')
  } finally {
    bulkBusy.value = false
  }
}

// Back to the Waiting Area, onto their own line: into the group they
// registered in while it still waits there; otherwise out of their group (on
// that group's line once it's a BIOTech group, or with no group).
const returnTarget = (studentId: number) => {
  const home = students.value.find((student) => student.id === studentId)?.registration_group_id
  const group = home != null ? groupById.value.get(home) : undefined
  return group?.registeredBy && !group.placed ? group.id : null
}

const waitingCount = computed(
  () => waitingArea.value.alone.length + [...waitingArea.value.lines.values()].reduce((sum, line) => sum + line.length, 0),
)


const toggleGroup = (groupId: number) => {
  const next = new Set(selectedGroupIds.value)
  if (next.has(groupId)) next.delete(groupId)
  else next.add(groupId)
  selectedGroupIds.value = next
}

const allSelected = computed(
  () => groups.value.length > 0 && groups.value.every((group) => selectedGroupIds.value.has(group.id)),
)
const toggleSelectAll = () => {
  selectedGroupIds.value = allSelected.value ? new Set() : new Set(groups.value.map((group) => group.id))
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
    if ((groupById.value.get(groupId)?.size ?? 0) >= GROUP_LIMIT) {
      showFlash(GROUP_FULL_MESSAGE)
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

// The student being dragged, so a full group can show it won't take them.
const draggingId = ref<number | null>(null)

const onDragStart = (event: DragEvent, studentId: number) => {
  event.dataTransfer?.setData('text/plain', String(studentId))
  draggingId.value = studentId
}

// A group with no room for the dragged student, who isn't already in it.
const isFullFor = (group: { size: number; students: { id: number }[] }) =>
  draggingId.value !== null &&
  group.size >= groupLimit &&
  !group.students.some((student) => student.id === draggingId.value)

// A group being moved, and the group it would take the place of.
const draggingGroupId = ref<number | null>(null)
const dropTargetGroupId = ref<number | null>(null)

const onGroupDragStart = (event: DragEvent, groupId: number) => {
  draggingGroupId.value = groupId
  if (!event.dataTransfer) return
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('application/x-group', String(groupId))
  // The whole box follows the pointer, not just the handle.
  const card = (event.target as HTMLElement).closest('.group-card')
  if (card) event.dataTransfer.setDragImage(card, 24, 24)
}

const endGroupDrag = () => {
  draggingGroupId.value = null
  dropTargetGroupId.value = null
}

// Moves the dragged group into the target's place: after it when moving
// down the page, before it when moving up. Saved for the supervisor.
const moveGroupTo = async (targetId: number) => {
  const movingId = draggingGroupId.value
  endGroupDrag()
  if (movingId === null || movingId === targetId) return
  const before = [...supervisedGroups.value]
  const from = before.findIndex((group) => group.id === movingId)
  const to = before.findIndex((group) => group.id === targetId)
  if (from < 0 || to < 0) return
  const next = [...before]
  const [moving] = next.splice(from, 1)
  next.splice(to, 0, moving!)
  supervisedGroups.value = next
  try {
    await saveSupervisedGroupOrder(next.map((group) => group.id))
  } catch (saveError) {
    supervisedGroups.value = before
    showFlash(saveError instanceof Error ? saveError.message : 'The new order could not be saved.')
  }
}

// Students drop here; a group being moved doesn't.
const onDragOverWaiting = (event: DragEvent) => {
  if (draggingGroupId.value === null) event.preventDefault()
}

// Only a group with room takes the drop; a full one shows the no-drop cursor.
// A group being moved can go in any other group's place.
const onDragOver = (event: DragEvent, group: { id: number; size: number; students: { id: number }[] }) => {
  if (draggingGroupId.value !== null) {
    event.preventDefault()
    dropTargetGroupId.value = group.id === draggingGroupId.value ? null : group.id
    return
  }
  if (isFullFor(group)) {
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'none'
    return
  }
  event.preventDefault()
}

// Anywhere in the Waiting Area: back onto their own line (returnTarget). One
// already in the Waiting Area stays put, so nothing moves within it.
const onDropWaiting = (event: DragEvent) => {
  if (draggingGroupId.value !== null) return
  const studentId = Number(event.dataTransfer?.getData('text/plain'))
  if (!Number.isFinite(studentId)) return
  const student = students.value.find((item) => item.id === studentId)
  if (student && waitingLineOf(student) !== undefined) return
  void moveStudent(studentId, returnTarget(studentId))
}

// Students sent back to the Waiting Area by deleting their group: into the
// group they registered in while it still waits there; the rest are already
// back on their lines, out of any group.
const returnHome = async (studentIds: number[]) => {
  const byHome = new Map<number, number[]>()
  for (const studentId of studentIds) {
    const home = returnTarget(studentId)
    if (home != null) byHome.set(home, [...(byHome.get(home) ?? []), studentId])
  }
  for (const [home, ids] of byHome) {
    applyOwnedGroup(await addSupervisedGroupMembers(home, ids, 'student'))
    for (const studentId of ids) setStudentGroup(studentId, home)
  }
}

const onDrop = (event: DragEvent, groupId: number) => {
  if (draggingGroupId.value !== null) {
    event.preventDefault()
    void moveGroupTo(groupId)
    return
  }
  draggingId.value = null
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
      const members = students.value
        .filter((student) => assignment.value[student.id] === groupId)
        .map((student) => student.id)
      await deleteSupervisedGroup(groupId)
      onGroupDeleted(groupId)
      await returnHome(members)
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

/* Text over text leaves more room than text over a box, so the hint's
   paragraphs sit closer to look as far apart as the last one is from the
   students below it. */
.waiting-copy--tight {
  margin-bottom: 0.45rem;
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

/* Groups you registered, Groups students formed, Students without a group. */
.waiting-section {
  margin-top: 1.25rem;
}

/* A section's heading, with Create all groups beside it. */
.waiting-section-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 0.6rem;
}

.waiting-section-header .waiting-section-title {
  margin: 0;
}

.waiting-section-title {
  margin: 0 0 0.6rem;
  color: #333;
  font-size: 1rem;
  font-weight: 600;
}

/* A group formed while registering: "Group:", then its students. */
.waiting-group {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.waiting-group + .waiting-group {
  margin-top: 0.6rem;
}

.waiting-group-label {
  flex: 0 0 auto;
  color: #333;
  font-size: 0.9rem;
  font-weight: 600;
}


.groups-board {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1rem;
}

.groups-board-toolbar,
.groups-board-heading,
.groups-board-toolbar-actions,
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

.groups-bulk {
  grid-column: 1 / -1;
  margin: 0;
  color: #6c757d;
}

/* Delete selected, on the right. */
.groups-bulk-actions {
  display: flex;
  gap: 0.5rem;
  margin-left: auto;
}

.groups-bulk-hidden {
  visibility: hidden;
}

/* .btn eases "all" over 0.3s, visibility too, so it would linger after
   the last untick; it goes at once like the count beside it. */
.groups-bulk-hidden .btn {
  transition: none;
}

.groups-select-all {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  cursor: pointer;
}

/* White, rather than the page's tint showing through; hover keeps its green. */
.groups-bulk-actions .btn:not(:hover) {
  background-color: var(--white);
}

.group-card.selected {
  outline: 2px solid #333;
}

/* The grip a group is dragged by, beside its tick box. */
.group-drag-handle {
  color: #9aa3a0;
  cursor: grab;
  padding: 0 0.1rem;
}

.group-drag-handle:active {
  cursor: grabbing;
}

/* Where a group being moved will go, and the group itself while it moves. */
.group-card--drop-target {
  outline: 2px dashed var(--dark-green);
  outline-offset: 2px;
}

.group-card--moving {
  opacity: 0.4;
}

/* A full group while a student is dragged: greyed, as it won't take them. */
.group-card--full {
  opacity: 0.5;
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

/* Where a group's next students go: a dashed white box. */
.drop-hint {
  padding: 0.15rem 1rem;
  line-height: 1.4;
  border: 1px dashed #c0c0c0;
  border-radius: 6px;
  background: var(--white);
  color: #6c757d;
  font-size: 0.85rem;
  text-align: center;
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
  display: flex;
  align-items: center;
  gap: 0.5rem;
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

/* Another supervisor's student: there, but not to be dragged or opened. */
.student-row--other {
  cursor: default;
  background: #f0f0f0;
  color: #6c757d;
}

.student-row--other small {
  margin-left: auto;
  font-size: 0.75rem;
}

/* Just the number, no circle. */
.student-number {
  flex-shrink: 0;
  font-weight: 700;
}
</style>
