<template>
  <div class="group-editor-backdrop" @click.self="emit('close')">
    <section class="group-editor" role="dialog" aria-modal="true" :aria-label="group.group_name">
      <header class="group-editor-header">
        <div class="group-editor-title-row">
          <i class="fas fa-user-group group-editor-lead-icon" aria-hidden="true"></i>
          <div>
            <h2>{{ displayName }}</h2>
            <p>{{ isCreate ? 'Configure this group, then create it.' : 'View group details and composition' }}</p>
          </div>
        </div>
        <button type="button" class="group-editor-close" aria-label="Close" @click="emit('close')">
          ×
        </button>
      </header>

      <p v-if="error" class="group-editor-error">{{ error }}</p>

      <section class="group-editor-section">
        <p class="group-editor-label">Group Name</p>
        <div class="group-name-row">
          <input
            v-if="isCreate || editingName"
            ref="nameInput"
            v-model="nameDraft"
            class="group-name-input"
            @keydown.enter.prevent="saveName"
            @keydown.escape.prevent="cancelName"
          />
          <p v-else class="group-name-value">{{ group.group_name }}</p>
          <button
            v-if="!isCreate"
            type="button"
            class="icon-button"
            :aria-label="editingName ? 'Save group name' : 'Edit group name'"
            @click="editingName ? saveName() : startNameEdit()"
          >
            <i :class="editingName ? 'fas fa-check' : 'fas fa-pencil'" aria-hidden="true"></i>
          </button>
        </div>
      </section>

      <hr class="group-editor-rule" />

      <section class="group-editor-section">
        <p class="group-editor-label">
          <i class="fas fa-tags" aria-hidden="true"></i>
          Area(s) of Interest
          <span class="member-count">({{ selectedInterests.length }})</span>
        </p>
        <p class="group-editor-hint">A group can have more than one area of interest.</p>
        <div v-if="selectedInterests.length" class="interest-chips">
          <span v-for="interest in selectedInterests" :key="interest" class="interest-chip">
            {{ interest }}
            <button type="button" :aria-label="`Remove ${interest}`" @click="removeInterest(interest)">
              ×
            </button>
          </span>
        </div>
        <p v-else class="group-editor-empty">No areas tagged yet.</p>
        <div class="interest-options">
          <label v-for="option in interestOptions" :key="option" class="interest-option">
            <input
              type="checkbox"
              :checked="isSelectedInterest(option)"
              :disabled="busy && !isCreate"
              @change="toggleInterest(option)"
            />
            <span>{{ option }}</span>
          </label>
        </div>
        <div class="interest-custom-row">
          <input
            v-model="customInterest"
            class="group-name-input"
            placeholder="Add another area"
            @keydown.enter.prevent="addCustomInterest"
          />
          <button type="button" class="btn btn-outline btn-sm" @click="addCustomInterest">Add</button>
        </div>
      </section>

      <hr class="group-editor-rule" />

      <section class="group-editor-section">
        <p class="group-editor-label">
          <i class="fas fa-user-tie" aria-hidden="true"></i>
          Supervisor/s
          <span class="member-count">({{ supervisors.length }})</span>
        </p>
        <div class="person-bubbles">
          <article v-for="person in supervisors" :key="`supervisor-${person.id}`" class="person-bubble">
            <div>
              <p class="person-name">{{ personName(person) }}</p>
              <p class="person-email">{{ person.email }}</p>
            </div>
            <span class="person-tag">supervisor</span>
          </article>
          <p v-if="!supervisors.length" class="group-editor-empty">No supervisor assigned.</p>
        </div>
      </section>

      <hr class="group-editor-rule" />

      <section class="group-editor-section">
        <div class="group-editor-section-head">
          <p class="group-editor-label">
            <i class="fas fa-user" aria-hidden="true"></i>
            Mentor/s
            <span class="member-count">({{ mentors.length }})</span>
          </p>
          <button type="button" class="btn btn-outline btn-sm" @click="picker = 'mentor'">
            Assign Mentor
          </button>
        </div>
        <div class="person-bubbles">
          <article v-for="person in mentors" :key="`mentor-${person.id}`" class="person-bubble">
            <div>
              <p class="person-name">{{ personName(person) }}</p>
              <p class="person-email">{{ person.email }}</p>
            </div>
            <div class="person-meta">
              <span class="person-tag">mentor</span>
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
          <p v-if="!mentors.length" class="group-editor-empty">No mentor assigned.</p>
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

      <hr class="group-editor-rule" />

      <section class="group-editor-section">
        <p class="group-editor-label">
          <i class="fas fa-wand-magic-sparkles" aria-hidden="true"></i>
          Suggested Students
        </p>
        <p class="group-editor-empty">No recommendations found.</p>
      </section>

      <hr class="group-editor-rule" />

      <div class="group-editor-footer">
        <template v-if="isCreate">
          <button type="button" class="btn btn-outline" @click="emit('close')">Cancel</button>
          <button type="button" class="btn btn-primary" :disabled="busy" @click="createGroup">
            Create Group
          </button>
        </template>
        <button
          v-else
          type="button"
          class="btn btn-outline group-delete-button"
          @click="pendingDelete = true"
        >
          Delete Group
        </button>
      </div>
    </section>

    <div v-if="picker" class="picker-overlay">
    <section class="picker-card" role="dialog" aria-modal="true">
      <h3>{{ picker === 'mentor' ? 'Assign Mentor' : 'Add Students' }}</h3>
      <label v-for="option in pickerOptions" :key="option.id" class="picker-option">
        <input v-model="pickedIds" type="checkbox" :value="option.id" />
        <span>
          <strong>{{ personName(option) }}</strong>
          <small>{{ option.email }}</small>
        </span>
      </label>
      <p v-if="!pickerOptions.length" class="group-editor-empty">No people available to add.</p>
      <div class="picker-actions">
        <button type="button" class="btn btn-outline" @click="closePicker">Cancel</button>
        <button type="button" class="btn btn-primary" :disabled="!pickedIds.length || busy" @click="applyPicker">
          {{ picker === 'mentor' ? 'Assign' : 'Add' }}
        </button>
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
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import {
  addSupervisedGroupMembers,
  createSupervisedGroup,
  DEFAULT_GROUP_INTERESTS,
  deleteSupervisedGroup,
  fetchInterestCatalog,
  personName,
  removeSupervisedGroupMembers,
  renameSupervisedGroup,
  updateSupervisedGroup,
  type AvailableMentor,
  type GroupPerson,
  type SupervisedGroup,
} from '@/utils/supervisedGroups'

const props = withDefaults(
  defineProps<{
    group: SupervisedGroup
    mentorsAvailable: AvailableMentor[]
    studentsAvailable: AvailableMentor[]
    currentUserId: number | null
    mode?: 'create' | 'edit'
    existingNames?: string[]
  }>(),
  { mode: 'edit', existingNames: () => [] },
)

const emit = defineEmits<{
  close: []
  updated: [group: SupervisedGroup]
  deleted: [groupId: number]
}>()

const error = ref('')
const busy = ref(false)
const editingName = ref(false)
const nameDraft = ref(props.group.group_name)
const nameInput = ref<HTMLInputElement | null>(null)
const picker = ref<'mentor' | 'student' | null>(null)
const pickedIds = ref<number[]>([])
const pendingRemove = ref<GroupPerson | null>(null)
const pendingDelete = ref(false)
const localMembers = ref<GroupPerson[]>([...props.group.members])
const selectedInterests = ref<string[]>([...(props.group.interests || [])])
const catalogInterests = ref<string[]>([...DEFAULT_GROUP_INTERESTS])
const customInterest = ref('')

const isCreate = computed(() => props.mode === 'create')
const displayName = computed(() => (isCreate.value ? nameDraft.value.trim() || 'New Group' : props.group.group_name))
const displayMembers = computed(() => (isCreate.value ? localMembers.value : props.group.members))
const supervisors = computed(() => displayMembers.value.filter((member) => member.role === 'supervisor'))
const mentors = computed(() => displayMembers.value.filter((member) => member.role === 'mentor'))
const students = computed(() => displayMembers.value.filter((member) => member.role === 'student'))
const memberIds = computed(() => new Set(displayMembers.value.map((member) => member.id)))
const interestOptions = computed(() => {
  const merged = [...catalogInterests.value, ...selectedInterests.value]
  return [...new Set(merged)].sort((left, right) => left.localeCompare(right, undefined, { sensitivity: 'base' }))
})
const sameInterest = (left: string, right: string) => left.trim().toLowerCase() === right.trim().toLowerCase()
const isSelectedInterest = (interest: string) =>
  selectedInterests.value.some((item) => sameInterest(item, interest))
const canonicalInterest = (interest: string) => {
  const match = interestOptions.value.find((option) => sameInterest(option, interest))
  return (match || interest).trim()
}

const nameIsTaken = (name: string) => {
  const needle = name.trim().toLowerCase()
  return props.existingNames.some((existing) => existing.trim().toLowerCase() === needle)
}
const pickerOptions = computed(() => {
  const source = picker.value === 'mentor' ? props.mentorsAvailable : props.studentsAvailable
  return source.filter((person) => !memberIds.value.has(person.id))
})

watch(
  () => props.group.interests,
  (next) => {
    selectedInterests.value = [...(next || [])]
  },
)

onMounted(async () => {
  try {
    const extras = await fetchInterestCatalog()
    catalogInterests.value = [
      ...new Set([...DEFAULT_GROUP_INTERESTS, ...extras, ...selectedInterests.value]),
    ]
  } catch {
    catalogInterests.value = [...new Set([...DEFAULT_GROUP_INTERESTS, ...selectedInterests.value])]
  }
})

const persistInterests = async (next: string[]) => {
  if (isCreate.value) {
    selectedInterests.value = next
    return
  }
  if (busy.value) return
  selectedInterests.value = next
  busy.value = true
  error.value = ''
  try {
    emit('updated', await updateSupervisedGroup(props.group.id, { interests: next }))
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : 'Areas of interest could not be saved.'
    selectedInterests.value = [...props.group.interests]
  } finally {
    busy.value = false
  }
}

const toggleInterest = (interest: string) => {
  const next = isSelectedInterest(interest)
    ? selectedInterests.value.filter((item) => !sameInterest(item, interest))
    : [...selectedInterests.value, canonicalInterest(interest)]
  void persistInterests(next)
}

const removeInterest = (interest: string) => {
  void persistInterests(selectedInterests.value.filter((item) => !sameInterest(item, interest)))
}

const addCustomInterest = () => {
  const next = canonicalInterest(customInterest.value)
  if (!next) return
  customInterest.value = ''
  if (isSelectedInterest(next)) return
  void persistInterests([...selectedInterests.value, next])
}

const startNameEdit = async () => {
  nameDraft.value = props.group.group_name
  editingName.value = true
  await nextTick()
  nameInput.value?.focus()
}

const cancelName = () => {
  editingName.value = false
  nameDraft.value = props.group.group_name
}

const saveName = async () => {
  const next = nameDraft.value.trim()
  if (!next) {
    error.value = 'Enter a group name.'
    return
  }
  if (isCreate.value) {
    if (nameIsTaken(next)) {
      error.value = `A group named "${next}" already exists. Choose a different name.`
      return
    }
    error.value = ''
    return
  }
  if (next === props.group.group_name) {
    editingName.value = false
    return
  }
  if (nameIsTaken(next)) {
    error.value = `A group named "${next}" already exists. Choose a different name.`
    return
  }
  busy.value = true
  error.value = ''
  try {
    emit('updated', await renameSupervisedGroup(props.group.id, next))
    editingName.value = false
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : 'Group name could not be saved.'
  } finally {
    busy.value = false
  }
}

const closePicker = () => {
  picker.value = null
  pickedIds.value = []
}

const applyPicker = async () => {
  if (!picker.value || !pickedIds.value.length) return
  if (isCreate.value) {
    const source = picker.value === 'mentor' ? props.mentorsAvailable : props.studentsAvailable
    const chosen = source.filter((person) => pickedIds.value.includes(person.id))
    const role = picker.value === 'mentor' ? 'mentor' : 'student'
    const next = localMembers.value.filter((member) => member.role !== role || role === 'student')
    if (role === 'mentor') {
      localMembers.value = [
        ...next.filter((member) => member.role !== 'mentor'),
        ...chosen.slice(0, 1).map((person) => ({ ...person, role })),
      ]
    } else {
      const existing = new Set(next.map((member) => member.id))
      localMembers.value = [
        ...next,
        ...chosen
          .filter((person) => !existing.has(person.id))
          .map((person) => ({ ...person, role })),
      ]
    }
    closePicker()
    return
  }
  busy.value = true
  error.value = ''
  try {
    emit(
      'updated',
      await addSupervisedGroupMembers(
        props.group.id,
        picker.value === 'mentor' ? pickedIds.value.slice(0, 1) : pickedIds.value,
        picker.value === 'mentor' ? 'mentor' : 'student',
      ),
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
  const next = nameDraft.value.trim() || 'New Group'
  if (nameIsTaken(next)) {
    error.value = `A group named "${next}" already exists. Choose a different name.`
    return
  }
  busy.value = true
  error.value = ''
  try {
    let created = await createSupervisedGroup(next, selectedInterests.value)
    const mentorIds = localMembers.value.filter((member) => member.role === 'mentor').map((member) => member.id)
    const studentIds = localMembers.value.filter((member) => member.role === 'student').map((member) => member.id)
    if (mentorIds.length) created = await addSupervisedGroupMembers(created.id, mentorIds.slice(0, 1), 'mentor')
    if (studentIds.length) created = await addSupervisedGroupMembers(created.id, studentIds, 'student')
    emit('updated', created)
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : 'Group could not be created.'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.group-editor-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: 1.5rem;
  background: rgba(23, 66, 67, 0.4);
}

.group-editor,
.picker-card {
  width: min(40rem, 100%);
  background: var(--white);
  border-radius: 12px;
  box-shadow: 0 16px 40px var(--shadow);
}

.group-editor {
  max-height: calc(100vh - 3rem);
  overflow: auto;
  padding: 1.35rem 1.5rem 1.5rem;
}

.picker-overlay {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  padding: 1.5rem;
  background: rgba(23, 66, 67, 0.35);
}

.picker-card {
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
  gap: 0.65rem;
  margin-bottom: 0.55rem;
}

.picker-option span {
  display: grid;
}

.picker-option small {
  color: #6c757d;
}

.picker-actions {
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 1rem;
}

.group-editor-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
}

.group-delete-button {
  color: var(--danger, #b42318);
  border-color: #f0b4b0;
}
</style>
