<template>
  <Teleport to="body">
  <div class="group-editor-backdrop" @click.self="emit('close')">
    <section class="group-editor" role="dialog" aria-modal="true" :aria-label="group.group_name">
      <header class="group-editor-header">
        <div class="group-editor-title-row">
          <i class="fas fa-user-group group-editor-lead-icon" aria-hidden="true"></i>
          <div>
            <h2>{{ displayName }}</h2>
            <p>{{ isCreate ? 'Areas of interest and students are optional. The system will assign a BTF group number.' : 'View and edit group details' }}</p>
          </div>
        </div>
        <button type="button" class="group-editor-close" aria-label="Close" @click="emit('close')">
          ×
        </button>
      </header>

      <div class="group-editor-body">
      <p v-if="error" class="group-editor-error">{{ error }}</p>

      <section class="group-editor-section">
        <p class="group-editor-label">Group Name</p>
        <p class="group-name-value">{{ displayName }}</p>
        <p v-if="!isCreate" class="group-editor-hint">Group ID {{ group.id }}</p>
        <p class="group-editor-hint">
          {{
            isCreate
              ? 'A group number will be assigned automatically when the group is created (e.g. BTF01, BTF02).'
              : 'Group names are assigned by the system and may repeat across challenges. The group ID uniquely identifies this group.'
          }}
        </p>
      </section>

      <hr class="group-editor-rule" />

      <section class="group-editor-section">
        <p class="group-editor-label">
          <i class="fas fa-tags" aria-hidden="true"></i>
          Area(s) of Interest
          <span class="member-count">({{ selectedInterests.length }})</span>
        </p>
        <p class="group-editor-hint">Select one or more areas of interest, these will be used to assign an appropriate mentor</p>
        <div class="interest-options">
          <label v-for="option in interestOptions" :key="option" class="interest-option">
            <input
              type="checkbox"
              :checked="isSelectedInterest(option)"
              @change="toggleInterest(option)"
            />
            <span>{{ option }}</span>
          </label>
        </div>
      </section>

      <hr class="group-editor-rule" />

      <section class="group-editor-section">
        <div class="group-editor-section-head">
          <p class="group-editor-label">
            <i class="fas fa-user-group" aria-hidden="true"></i>
            Group Members
            <span class="member-count">({{ students.length }})</span>
          </p>
          <button type="button" class="btn btn-outline btn-sm" @click="picker = 'student'">
            <i class="fas fa-user-plus" aria-hidden="true"></i>
            Add Students
          </button>
        </div>
        <div class="person-bubbles">
          <article v-for="person in students" :key="`student-${person.id}`" class="person-bubble">
            <div>
              <p class="person-name">{{ personName(person) }}</p>
              <p class="person-email">{{ person.email }}</p>
            </div>
            <div class="person-meta">
              <span class="person-tag">student</span>
              <button
                type="button"
                class="icon-button danger"
                :aria-label="`Remove ${personName(person)}`"
                @click="askRemove(person)"
              >
                <i class="fas fa-user-minus" aria-hidden="true"></i>
              </button>
            </div>
          </article>
          <p v-if="!students.length" class="group-editor-empty">No students in this group.</p>
        </div>
      </section>

      </div>

      <div class="group-editor-footer">
        <template v-if="isCreate">
          <button type="button" class="btn btn-outline" @click="emit('close')">Cancel</button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="busy"
            @click="createGroup"
          >
            Create Group
          </button>
        </template>
        <template v-else>
          <button
            type="button"
            class="btn btn-outline group-delete-button"
            @click="pendingDelete = true"
          >
            Delete Group
          </button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="busy || selectedInterests.length < 1"
            :title="selectedInterests.length < 1 ? 'Select at least one area of interest' : ''"
            @click="saveGroup"
          >
            Save
          </button>
        </template>
      </div>
    </section>

    <div v-if="picker" class="picker-overlay">
    <section class="picker-card" role="dialog" aria-modal="true">
      <h3>Add Students</h3>
      <label v-for="option in pickerOptions" :key="option.id" class="picker-option">
        <input v-model="pickedIds" type="checkbox" :value="option.id" />
        <span>
          <strong>{{ personName(option) }}</strong>
          <small>{{ option.email }}</small>
          <small v-if="assignedGroupName(option)" class="picker-group-note">
            Student is already in {{ assignedGroupName(option) }}, assigning them to another group will remove them from {{ assignedGroupName(option) }}
          </small>
        </span>
      </label>
      <p v-if="!pickerOptions.length" class="group-editor-empty">No people available to add.</p>
      <div class="picker-actions">
        <button type="button" class="btn btn-outline" @click="closePicker">Cancel</button>
        <button type="button" class="btn btn-primary" :disabled="!pickedIds.length || busy" @click="applyPicker()">
          Add
        </button>
      </div>
    </section>
    </div>

    <div v-if="pendingSchoolMix" class="picker-overlay">
    <section class="picker-card" role="dialog" aria-modal="true">
      <h3>{{ pendingSchoolMix.kind === 'outside' ? 'Match outside school?' : 'Match inside school?' }}</h3>
      <p>{{ pendingSchoolMix.message }}</p>
      <div class="picker-actions">
        <button type="button" class="btn btn-outline" @click="pendingSchoolMix = null">Cancel</button>
        <button type="button" class="btn btn-primary" :disabled="busy" @click="applyPicker(true)">Confirm</button>
      </div>
    </section>
    </div>

    <div v-if="pendingDelete" class="picker-overlay">
    <section class="picker-card" role="dialog" aria-modal="true">
      <h3>Delete this group?</h3>
      <p>
        Delete {{ displayName }}? Students in it will return to the waiting area.
      </p>
      <div class="picker-actions">
        <button type="button" class="btn btn-outline" @click="pendingDelete = false">Cancel</button>
        <button type="button" class="btn btn-primary" :disabled="busy" @click="confirmDelete">Delete Group</button>
      </div>
    </section>
    </div>

    <div v-if="pendingRemove" class="picker-overlay">
    <section class="picker-card" role="dialog" aria-modal="true">
      <h3>Remove from group?</h3>
      <p>
        Remove {{ personName(pendingRemove) }} ({{ pendingRemove.email }}) from
        {{ displayName }}?
      </p>
      <div class="picker-actions">
        <button type="button" class="btn btn-outline" @click="pendingRemove = null">Cancel</button>
        <button type="button" class="btn btn-primary" :disabled="busy" @click="confirmRemove">Remove</button>
      </div>
    </section>
    </div>
  </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  addSupervisedGroupMembers,
  createSupervisedGroup,
  DEFAULT_GROUP_INTERESTS,
  deleteSupervisedGroup,
  personName,
  removeSupervisedGroupMembers,
  updateSupervisedGroup,
  type AvailableMentor,
  type GroupPerson,
  type SupervisedGroup,
} from '@/utils/supervisedGroups'

const props = withDefaults(
  defineProps<{
    group: SupervisedGroup
    studentsAvailable: AvailableMentor[]
    currentUserId: number | null
    mode?: 'create' | 'edit'
  }>(),
  { mode: 'edit' },
)

const emit = defineEmits<{
  close: []
  updated: [group: SupervisedGroup]
  deleted: [groupId: number]
}>()

const error = ref('')
const busy = ref(false)
const picker = ref<'student' | null>(null)
const pickedIds = ref<number[]>([])
const pendingRemove = ref<GroupPerson | null>(null)
const pendingDelete = ref(false)
const pendingSchoolMix = ref<{ kind: 'inside' | 'outside'; message: string } | null>(null)
const localMembers = ref<GroupPerson[]>([...props.group.members])
const selectedInterests = ref<string[]>([...(props.group.interests || [])])

const isCreate = computed(() => props.mode === 'create')
const displayName = computed(() => (isCreate.value ? 'New Group' : props.group.group_name))
const displayMembers = computed(() => (isCreate.value ? localMembers.value : props.group.members))
const students = computed(() => displayMembers.value.filter((member) => member.role === 'student'))
const memberIds = computed(() => new Set(displayMembers.value.map((member) => member.id)))
const sameInterest = (left: string, right: string) => left.trim().toLowerCase() === right.trim().toLowerCase()
const interestOptions = computed(() => {
  const extras = selectedInterests.value.filter(
    (item) => !DEFAULT_GROUP_INTERESTS.some((official) => sameInterest(official, item)),
  )
  return [...DEFAULT_GROUP_INTERESTS, ...extras]
})
const isSelectedInterest = (interest: string) =>
  selectedInterests.value.some((item) => sameInterest(item, interest))
const pickerOptions = computed(() =>
  props.studentsAvailable.filter((person) => !memberIds.value.has(person.id)),
)
const assignedGroupName = (person: AvailableMentor) => {
  const name = person.group_name?.trim()
  if (!name) return ''
  if (!isCreate.value && person.group_id === props.group.id) return ''
  return name
}

watch(
  () => props.group.interests,
  (next) => {
    selectedInterests.value = [...(next || [])]
  },
)

const persistInterests = async (next: string[]) => {
  selectedInterests.value = next
}

const toggleInterest = (interest: string) => {
  const next = isSelectedInterest(interest)
    ? selectedInterests.value.filter((item) => !sameInterest(item, interest))
    : [...selectedInterests.value, interest]
  void persistInterests(next)
}

const closePicker = () => {
  picker.value = null
  pickedIds.value = []
  pendingSchoolMix.value = null
}

const schoolLabel = (person?: AvailableMentor | null) => person?.school_name?.trim() || ''

const listSchools = (schools: string[]) => {
  if (schools.length <= 1) return schools[0] || 'another school'
  if (schools.length === 2) return `${schools[0]} and ${schools[1]}`
  return `${schools.slice(0, -1).join(', ')}, and ${schools[schools.length - 1]}`
}

const schoolMixPrompt = () => {
  const incoming = props.studentsAvailable.filter((person) => pickedIds.value.includes(person.id))
  const existingSchools = [...new Map(
    students.value
      .map((member) => schoolLabel(props.studentsAvailable.find((person) => person.id === member.id)))
      .filter(Boolean)
      .map((name) => [name.toLowerCase(), name]),
  ).values()]
  const incomingSchools = [...new Map(
    incoming
      .map((person) => schoolLabel(person))
      .filter(Boolean)
      .map((name) => [name.toLowerCase(), name]),
  ).values()]
  const combined = [...new Map(
    [...existingSchools, ...incomingSchools].map((name) => [name.toLowerCase(), name]),
  ).values()]
  if (combined.length <= 1) return null
  const names = incoming.map((person) => personName(person)).join(', ')
  return {
    kind: 'outside' as const,
    message: `${names || 'These students'} would be grouped with students from ${listSchools(combined)}. This will match one or more students outside their school.`,
  }
}

const applyPicker = async (skipSchoolConfirm = false) => {
  if (!picker.value || !pickedIds.value.length) return
  if (!skipSchoolConfirm) {
    const prompt = schoolMixPrompt()
    if (prompt) {
      pendingSchoolMix.value = prompt
      return
    }
  }
  pendingSchoolMix.value = null
  if (isCreate.value) {
    const chosen = props.studentsAvailable.filter((person) => pickedIds.value.includes(person.id))
    const existing = new Set(localMembers.value.map((member) => member.id))
    localMembers.value = [
      ...localMembers.value,
      ...chosen
        .filter((person) => !existing.has(person.id))
        .map((person) => ({ ...person, role: 'student' })),
    ]
    closePicker()
    return
  }
  busy.value = true
  error.value = ''
  try {
    emit(
      'updated',
      await addSupervisedGroupMembers(props.group.id, pickedIds.value, 'student'),
    )
    closePicker()
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : 'Could not update group members.'
  } finally {
    busy.value = false
  }
}

const askRemove = (person: GroupPerson) => {
  pendingRemove.value = person
}

const confirmDelete = async () => {
  busy.value = true
  error.value = ''
  try {
    await deleteSupervisedGroup(props.group.id)
    emit('deleted', props.group.id)
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : 'Group could not be deleted.'
    pendingDelete.value = false
  } finally {
    busy.value = false
  }
}

const confirmRemove = async () => {
  if (!pendingRemove.value) return
  if (isCreate.value) {
    localMembers.value = localMembers.value.filter(
      (member) => !(member.id === pendingRemove.value?.id && member.role === pendingRemove.value.role),
    )
    pendingRemove.value = null
    return
  }
  busy.value = true
  error.value = ''
  try {
    emit('updated', await removeSupervisedGroupMembers(props.group.id, [pendingRemove.value.id]))
    pendingRemove.value = null
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : 'Could not remove this person.'
  } finally {
    busy.value = false
  }
}

const createGroup = async () => {
  busy.value = true
  error.value = ''
  try {
    let created = await createSupervisedGroup(selectedInterests.value)
    const studentIds = localMembers.value.filter((member) => member.role === 'student').map((member) => member.id)
    if (studentIds.length) created = await addSupervisedGroupMembers(created.id, studentIds, 'student')
    emit('updated', created)
    emit('close')
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : 'Group could not be created.'
  } finally {
    busy.value = false
  }
}

const saveGroup = async () => {
  if (selectedInterests.value.length < 1) {
    error.value = 'Please select at least one area of interest.'
    return
  }
  busy.value = true
  error.value = ''
  try {
    emit('updated', await updateSupervisedGroup(props.group.id, { interests: selectedInterests.value }))
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : 'Group could not be saved.'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.group-editor-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1100;
  display: grid;
  place-items: start center;
  padding: 5.5rem 1rem 1.25rem;
  background: rgba(23, 66, 67, 0.4);
}

.group-editor,
.picker-card {
  width: min(32rem, 100%);
  background: var(--white);
  border-radius: 12px;
  box-shadow: 0 16px 40px var(--shadow);
}

.group-editor {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 6.75rem);
  overflow: hidden;
  padding: 1rem 1.15rem 1.1rem;
}

.group-editor-body {
  min-height: 0;
  overflow: auto;
  padding-right: 0.25rem;
}

.picker-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: grid;
  place-items: start center;
  padding: 5.5rem 1rem 1.25rem;
  background: rgba(23, 66, 67, 0.35);
}

.picker-card {
  max-height: calc(100vh - 6.75rem);
  overflow: auto;
  padding: 1.25rem;
}

.group-editor-header,
.group-editor-title-row,
.group-editor-section-head,
.group-name-row,
.person-bubble,
.person-meta,
.picker-option,
.picker-actions {
  display: flex;
  align-items: center;
}

.group-editor-header,
.group-editor-section-head,
.group-name-row,
.person-bubble {
  justify-content: space-between;
  gap: 0.75rem;
}

.group-editor-title-row {
  gap: 0.85rem;
}

.group-editor-lead-icon {
  color: var(--dark-green);
  font-size: 1.35rem;
}

.group-editor-header h2 {
  margin: 0;
  font-size: 1.45rem;
}

.group-editor-header p,
.group-editor-label,
.group-editor-empty,
.group-editor-hint,
.person-email,
.member-count {
  color: #6c757d;
}

.group-editor-header p,
.group-editor-empty,
.person-name,
.person-email,
.group-name-value,
.group-editor-label {
  margin: 0;
}

.group-editor-close {
  border: 0;
  background: transparent;
  color: #6c757d;
  font-size: 1.6rem;
  line-height: 1;
  cursor: pointer;
}

.group-editor-section {
  display: grid;
  gap: 0.7rem;
}

.group-editor-label {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.92rem;
}

.group-name-value {
  font-size: 1.05rem;
}

.group-name-input {
  flex: 1;
  padding: 0.4rem 0.55rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
}

.group-editor-hint {
  margin: 0;
  font-size: 0.85rem;
}

.interest-chips,
.interest-options,
.interest-custom-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.interest-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.2rem 0.45rem 0.2rem 0.65rem;
  border-radius: 999px;
  background: var(--accent-green-soft, #e7f3ea);
  color: var(--dark-green);
  font-size: 0.85rem;
}

.interest-chip button {
  border: 0;
  background: transparent;
  color: inherit;
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
}

.interest-options {
  display: grid;
  gap: 0.35rem;
}

.interest-option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  color: #3d4a4a;
  font-size: 0.9rem;
}

.interest-option input[type="checkbox"] {
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

.interest-option input[type="checkbox"]:checked {
  background: var(--dark-green, #017151);
  border-color: var(--dark-green, #017151);
}

.interest-option input[type="checkbox"]:checked::after {
  content: '✓';
  color: #fff;
  font-size: 0.75rem;
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.interest-custom-row {
  align-items: center;
}

.group-editor-rule {
  border: 0;
  border-top: 1px solid var(--border-light);
  margin: 1.1rem 0;
}

.person-bubbles {
  display: grid;
  gap: 0.55rem;
}

.person-bubble {
  padding: 0.7rem 0.85rem;
  border-radius: 10px;
  background: #f1f3f4;
}

.person-name {
  font-weight: 600;
}

.person-email {
  font-size: 0.88rem;
}

.person-meta {
  gap: 0.5rem;
}

.person-tag {
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  background: #e4e7e8;
  color: #5f6368;
  font-size: 0.78rem;
  text-transform: lowercase;
}

.icon-button {
  width: 2rem;
  height: 2rem;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--dark-green);
  cursor: pointer;
}

.icon-button.danger {
  color: #5f6368;
}

.icon-button:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.group-editor-error {
  color: var(--danger, #b42318);
  margin: 0 0 0.75rem;
}

.picker-card h3,
.picker-card p {
  margin: 0 0 0.85rem;
}

.picker-option {
  align-items: flex-start;
  gap: 0.65rem;
  margin-bottom: 0.75rem;
}

.picker-option input[type="checkbox"] {
  margin-top: 0.15rem;
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

.picker-option input[type="checkbox"]:checked {
  background: var(--dark-green, #017151);
  border-color: var(--dark-green, #017151);
}

.picker-option input[type="checkbox"]:checked::after {
  content: '✓';
  color: #fff;
  font-size: 0.75rem;
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.picker-option span {
  display: grid;
}

.picker-option small {
  color: #6c757d;
}

.picker-group-note {
  margin-top: 0.15rem;
  color: #8a6d3b;
  font-size: 0.78rem;
  line-height: 1.35;
}

.picker-actions {
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 1rem;
}

.group-editor-header,
.group-editor-footer {
  flex-shrink: 0;
}

.group-editor-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 0.85rem;
  padding-top: 0.85rem;
  border-top: 1px solid var(--border-light);
}

.group-delete-button {
  color: var(--danger, #b42318);
  border-color: #f0b4b0;
}
</style>
