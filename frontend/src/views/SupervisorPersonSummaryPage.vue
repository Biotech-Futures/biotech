<template>
  <div class="content-area supervisor-summary-page">
    <RouterLink class="supervisor-summary-back" to="/my-students">← Back to My Students</RouterLink>

    <p v-if="error" class="supervisor-error">{{ error }}</p>
    <p v-else-if="loading" class="supervisor-muted">Loading profile...</p>

    <div v-else-if="student" class="card" style="overflow: hidden; padding: 0">
      <div class="profile-header">
        <div class="profile-avatar-large">{{ avatar }}</div>
        <h2 class="profile-name">{{ title }}</h2>
        <p class="profile-role">{{ subtitle }}</p>
      </div>

      <div class="profile-content">
        <div v-if="canEdit" class="profile-edit-bar">
          <p v-if="notice" class="supervisor-notice">{{ notice }}</p>
          <template v-if="!editing">
            <button type="button" class="btn btn-primary btn-sm" @click="startEdit">Edit profile</button>
          </template>
          <template v-else>
            <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="cancelEdit">Cancel</button>
            <button type="button" class="btn btn-primary btn-sm" :disabled="saving" @click="saveEdit">Save</button>
          </template>
        </div>
        <p v-else-if="!isGuardian && student && !student.has_join_permission" class="supervisor-muted">
          Student details can be edited after parent/guardian permission is recorded.
        </p>
        <template v-if="isGuardian">
          <section class="profile-section">
            <h3 class="profile-section-title">Parent/Guardian information</h3>
            <div class="profile-field">
              <span class="profile-field-label">Name:</span>
              <span class="profile-field-value">{{ guardianName }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Email:</span>
              <span class="profile-field-value">{{ display(student.pg_email) }}</span>
            </div>
          </section>
          <section class="profile-section">
            <h3 class="profile-section-title">Linked student</h3>
            <div class="profile-field">
              <span class="profile-field-label">Student:</span>
              <span class="profile-field-value">
                <RouterLink class="supervisor-table-link" :to="studentRoute">{{ studentName }}</RouterLink>
              </span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">School:</span>
              <span class="profile-field-value">{{ display(student.school_name) }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Year level:</span>
              <span class="profile-field-value">{{ display(student.year_lvl) }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Permission:</span>
              <span class="profile-field-value">{{ student.has_join_permission ? 'Yes' : 'No' }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Permission given:</span>
              <span class="profile-field-value">{{ permissionGiven }}</span>
            </div>
          </section>
        </template>

        <template v-else>
          <section class="profile-section">
            <h3 class="profile-section-title">Personal information</h3>
            <div v-if="editing" class="profile-field">
              <span class="profile-field-label">First name:</span>
              <input v-model="form.firstName" class="profile-field-input" />
            </div>
            <div v-if="editing" class="profile-field">
              <span class="profile-field-label">Last name:</span>
              <input v-model="form.lastName" class="profile-field-input" />
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Email:</span>
              <span class="profile-field-value">{{ display(student.email) }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Role:</span>
              <span class="profile-field-value">Student</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">School:</span>
              <input v-if="editing" v-model="form.schoolName" class="profile-field-input" />
              <span v-else class="profile-field-value">{{ display(student.school_name) }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Year level:</span>
              <select v-if="editing" v-model="form.yearLevel" class="profile-field-input">
                <option v-for="year in yearLevels" :key="year" :value="year">{{ year }}</option>
              </select>
              <span v-else class="profile-field-value">{{ display(student.year_lvl) }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Group:</span>
              <span class="profile-field-value">{{ display(student.group_name) }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Registration:</span>
              <span class="profile-field-value">{{ registrationLabel(student) }}</span>
            </div>
          </section>
          <section class="profile-section">
            <h3 class="profile-section-title">Areas of interest</h3>
            <div v-if="editing" class="interest-options">
              <label v-for="option in interestOptions" :key="option" class="interest-option">
                <input
                  type="checkbox"
                  :checked="form.interests.some((item) => item.toLowerCase() === option.toLowerCase())"
                  @change="toggleInterest(option)"
                />
                <span>{{ option }}</span>
              </label>
            </div>
            <div v-else-if="student.interests.length" class="profile-interest-list">
              <span v-for="interest in student.interests" :key="interest" class="profile-interest">
                {{ interest }}
              </span>
            </div>
            <p v-else class="supervisor-muted">No interests recorded.</p>
          </section>
          <section class="profile-section">
            <h3 class="profile-section-title">Parent/Guardian</h3>
            <div class="profile-field">
              <span class="profile-field-label">Name:</span>
              <span class="profile-field-value">
                <RouterLink v-if="guardianName !== '—'" class="supervisor-table-link" :to="guardianRoute">
                  {{ guardianName }}
                </RouterLink>
                <template v-else>—</template>
              </span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Email:</span>
              <span class="profile-field-value">{{ display(student.pg_email) }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Permission:</span>
              <span class="profile-field-value">{{ student.has_join_permission ? 'Yes' : 'No' }}</span>
            </div>
          </section>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { buildSessionHeaders } from '@/utils/csrf'
import { formatDateTimeAU } from '@/utils/date'
import { DEFAULT_GROUP_INTERESTS } from '@/utils/supervisedGroups'
import {
  fetchSupervisedStudent,
  fullName,
  initials,
  registrationLabel,
  updateSupervisedStudentProfile,
  type SupervisedStudent,
} from '@/utils/supervisedStudents'

const yearLevels = ['9', '10', '11', '12']
const route = useRoute()
const loading = ref(true)
const error = ref('')
const notice = ref('')
const student = ref<SupervisedStudent | null>(null)
const editing = ref(false)
const saving = ref(false)
const form = ref({
  firstName: '',
  lastName: '',
  schoolName: '',
  yearLevel: '11',
  interests: [] as string[],
})

const isGuardian = computed(() => route.name === 'guardian-summary')
const studentId = computed(() => Number(route.params.id))
const studentName = computed(() =>
  student.value ? fullName(student.value.first_name, student.value.last_name, student.value.email) : '—',
)
const guardianName = computed(() =>
  student.value ? fullName(student.value.pg_first_name, student.value.pg_last_name) : '—',
)
const title = computed(() => (isGuardian.value ? guardianName.value : studentName.value))
const subtitle = computed(() =>
  isGuardian.value ? 'Parent/Guardian summary' : 'Student summary',
)
const avatar = computed(() =>
  isGuardian.value
    ? initials(student.value?.pg_first_name, student.value?.pg_last_name, guardianName.value)
    : initials(student.value?.first_name, student.value?.last_name, studentName.value),
)
const studentRoute = computed(() => ({ name: 'student-summary', params: { id: String(studentId.value) } }))
const guardianRoute = computed(() => ({ name: 'guardian-summary', params: { id: String(studentId.value) } }))
const permissionGiven = computed(() =>
  student.value?.has_join_permission
    ? formatDateTimeAU(student.value.joinperm_granted_at) || 'Recorded'
    : '—',
)
const canEdit = computed(() => !isGuardian.value && Boolean(student.value?.has_join_permission))
const interestOptions = computed(() => {
  const extras = form.value.interests.filter(
    (item) => !DEFAULT_GROUP_INTERESTS.some((official) => official.toLowerCase() === item.toLowerCase()),
  )
  return [...DEFAULT_GROUP_INTERESTS, ...extras]
})

const display = (value?: string | null) => {
  const text = String(value ?? '').trim()
  return text || '—'
}

const startEdit = () => {
  if (!student.value) return
  form.value = {
    firstName: student.value.first_name,
    lastName: student.value.last_name,
    schoolName: student.value.school_name,
    yearLevel: yearLevels.includes(student.value.year_lvl) ? student.value.year_lvl : '11',
    interests: [...student.value.interests],
  }
  notice.value = ''
  error.value = ''
  editing.value = true
}

const cancelEdit = () => {
  editing.value = false
  saving.value = false
}

const toggleInterest = (interest: string) => {
  const selected = form.value.interests.some((item) => item.toLowerCase() === interest.toLowerCase())
  form.value.interests = selected
    ? form.value.interests.filter((item) => item.toLowerCase() !== interest.toLowerCase())
    : [...form.value.interests, interest]
}

const saveEdit = async () => {
  if (!student.value) return
  const firstName = form.value.firstName.trim()
  const lastName = form.value.lastName.trim()
  const schoolName = form.value.schoolName.trim()
  if (!firstName || !lastName || !schoolName) {
    error.value = 'First name, last name, and school are required.'
    return
  }
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    student.value = await updateSupervisedStudentProfile(student.value.id, {
      first_name: firstName,
      last_name: lastName,
      school_name: schoolName,
      year_lvl: form.value.yearLevel,
      interests: form.value.interests,
    })
    editing.value = false
    notice.value = 'Student profile saved.'
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : 'Student profile could not be saved.'
  } finally {
    saving.value = false
  }
}

const load = async () => {
  loading.value = true
  error.value = ''
  notice.value = ''
  editing.value = false
  student.value = null
  try {
    const found = await fetchSupervisedStudent(
      studentId.value,
      buildSessionHeaders({ headers: { Accept: 'application/json' } }),
    )
    if (!found) {
      error.value = 'This person is not on your student roster.'
      return
    }
    student.value = found
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : 'Profile could not be loaded.'
  } finally {
    loading.value = false
  }
}

watch(() => [route.name, route.params.id], load, { immediate: true })
</script>

<style scoped>
.supervisor-summary-back {
  display: inline-block;
  margin-bottom: 1rem;
  color: var(--dark-green);
  font-weight: 600;
  text-decoration: underline;
}

.supervisor-muted,
.supervisor-error {
  margin: 0 0 1.5rem;
  color: #6c757d;
}

.supervisor-error {
  color: var(--danger, #b42318);
}

.supervisor-notice {
  margin: 0 0.75rem 0 0;
  color: var(--dark-green, #017151);
}

.profile-edit-bar {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1.25rem;
}

.profile-field-input {
  flex: 1;
  min-width: 0;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  color: var(--charcoal);
  background: var(--white);
}

.interest-options {
  display: grid;
  gap: 0.4rem;
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

.supervisor-table-link {
  color: var(--dark-green);
  font-weight: 600;
  text-decoration: underline;
}

.profile-interest-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.profile-interest {
  display: inline-flex;
  align-items: center;
  min-height: 1.75rem;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  background: var(--accent-green-soft);
  color: var(--dark-green);
  font-size: 0.9rem;
}
</style>
