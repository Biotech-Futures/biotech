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
            <div class="profile-field">
              <span class="profile-field-label">Details received:</span>
              <span class="profile-field-value">{{ student.parent_guardian_flag ? 'Yes' : 'No' }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Permission:</span>
              <span class="profile-field-value">{{ student.has_join_permission ? 'Received' : 'Pending' }}</span>
            </div>
            <div v-if="student.joinperm_response_id" class="profile-field">
              <span class="profile-field-label">Reference:</span>
              <span class="profile-field-value">{{ student.joinperm_response_id }}</span>
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
          </section>
        </template>

        <template v-else>
          <section class="profile-section">
            <h3 class="profile-section-title">Personal information</h3>
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
              <span class="profile-field-value">{{ display(student.school_name) }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Year level:</span>
              <span class="profile-field-value">{{ display(student.year_lvl) }}</span>
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
            <div v-if="student.interests.length" class="profile-interest-list">
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
import {
  fetchSupervisedStudent,
  fullName,
  initials,
  registrationLabel,
  type SupervisedStudent,
} from '@/utils/supervisedStudents'

const route = useRoute()
const loading = ref(true)
const error = ref('')
const student = ref<SupervisedStudent | null>(null)

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

const display = (value?: string | null) => {
  const text = String(value ?? '').trim()
  return text || '—'
}

const load = async () => {
  loading.value = true
  error.value = ''
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
