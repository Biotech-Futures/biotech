<template>
  <!-- A student's details, slid over My Students as admin's user panel is. -->
  <FormSheet
    :model-value="Boolean(student)"
    :title="studentName"
    description="Student details"
    width="min(100vw, 620px)"
    @close="emit('close')"
  >
    <div v-if="student" class="student-sheet">
      <section class="student-sheet__section">
        <h3>Personal information</h3>
        <dl class="student-sheet__list">
          <div class="student-sheet__item">
            <dt>Email</dt>
            <dd>{{ display(student.email) }}</dd>
          </div>
          <div class="student-sheet__item">
            <dt>Country</dt>
            <dd>{{ display(student.country_name) }}</dd>
          </div>
          <div class="student-sheet__item">
            <dt>State</dt>
            <dd>{{ display(student.state_name) }}</dd>
          </div>
          <div class="student-sheet__item">
            <dt>Role</dt>
            <dd>Student</dd>
          </div>
          <div class="student-sheet__item">
            <dt>Account Status</dt>
            <dd>{{ display(student.account_status) }}</dd>
          </div>
        </dl>
      </section>

      <section class="student-sheet__section">
        <h3>Student Details</h3>
        <dl class="student-sheet__list">
          <div class="student-sheet__item">
            <dt>Name</dt>
            <dd>{{ studentName }}</dd>
          </div>
          <div class="student-sheet__item">
            <dt>School</dt>
            <dd>{{ display(student.school_name) }}</dd>
          </div>
          <div class="student-sheet__item">
            <dt>Year level</dt>
            <dd>{{ display(student.year_lvl) }}</dd>
          </div>
          <div class="student-sheet__item">
            <dt>Areas of interest</dt>
            <dd>{{ student.interests.length ? student.interests.join(', ') : '—' }}</dd>
          </div>
        </dl>
      </section>

      <section class="student-sheet__section">
        <h3>Guardian Details</h3>
        <dl class="student-sheet__list">
          <div class="student-sheet__item">
            <dt>Name</dt>
            <dd>{{ guardianName }}</dd>
          </div>
          <div class="student-sheet__item">
            <dt>Email</dt>
            <dd>{{ display(student.pg_email) }}</dd>
          </div>
          <div class="student-sheet__item">
            <dt>Permission</dt>
            <dd>{{ permission }}</dd>
          </div>
          <div class="student-sheet__item">
            <dt>Media consent</dt>
            <dd>{{ mediaConsent }}</dd>
          </div>
        </dl>
      </section>

      <section class="student-sheet__section">
        <h3>Group</h3>
        <dl class="student-sheet__list">
          <div class="student-sheet__item">
            <dt>Group</dt>
            <dd>{{ display(student.group_name) }}</dd>
          </div>
        </dl>
      </section>
    </div>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import { fullName, type SupervisedStudent } from '@/utils/supervisedStudents'

const props = defineProps<{
  /** The student to show; the panel is open while there is one. */
  student: SupervisedStudent | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const display = (value?: string | null) => String(value ?? '').trim() || '—'

const studentName = computed(() =>
  props.student ? fullName(props.student.first_name, props.student.last_name, props.student.email) : '',
)

// A student made without a guardian has their own name in the guardian
// fields; that isn't a guardian.
const guardianName = computed(() => {
  if (!props.student) return '—'
  const name = fullName(props.student.pg_first_name, props.student.pg_last_name)
  return name === studentName.value ? '—' : name
})

const permission = computed(() => (props.student?.has_join_permission ? 'Yes' : 'No'))

// From the signed form; consent marked received without one has no answer.
const mediaConsent = computed(() => {
  const answer = props.student?.media_consent
  if (answer == null) return '—'
  return answer ? 'Yes' : 'No'
})
</script>

<style scoped>
/* Laid out as admin's user panel: green capital headings over label and
   value rows. */
.student-sheet__section h3 {
  margin: 0 0 0.4rem;
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--dark-green);
}

.student-sheet__section + .student-sheet__section {
  margin-top: 1.4rem;
}

.student-sheet__list {
  margin: 0;
}

.student-sheet__item {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--border-light);
}

.student-sheet__item dt {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-muted);
  flex-shrink: 0;
}

.student-sheet__item dd {
  margin: 0;
  color: var(--teal);
  text-align: right;
  overflow-wrap: anywhere;
}
</style>
