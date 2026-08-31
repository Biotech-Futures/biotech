<template>
  <div class="content-area supervisor-students-page">
    <header class="supervisor-page-header">
      <h1>Registered Students</h1>
      <p>This is a list of all students registered under your supervision.</p>
    </header>

    <p v-if="notice" class="supervisor-notice">{{ notice }}</p>
    <p v-if="error" class="supervisor-error">{{ error }}</p>
    <p v-else-if="loading" class="supervisor-muted">Loading students...</p>

    <section v-for="section in sections" :key="section.id" class="supervisor-section">
      <h2>{{ section.title }}</h2>
      <SupervisorDataTable
        :columns="section.columns"
        :rows="section.rows"
        :filename="section.filename"
        :extra-option-groups="section.optionGroups"
        @refresh="loadStudents"
        @action="(value, rows) => onSectionAction(section.id, value, rows)"
      >
        <template #bulk="{ rows }">
          <button
            v-for="action in section.bulkActions"
            :key="action.value"
            type="button"
            class="btn btn-outline btn-sm"
            @click="onSectionAction(section.id, action.value, rows)"
          >
            {{ action.label }}
          </button>
        </template>
        <template #actions="{ row }">
          <div class="supervisor-row-actions">
            <button
              v-for="action in section.rowActions"
              :key="action.value"
              type="button"
              class="btn btn-outline btn-sm"
              @click="onSectionAction(section.id, action.value, [row])"
            >
              {{ action.label }}
            </button>
          </div>
        </template>
      </SupervisorDataTable>
    </section>

    <div v-if="guardianModal" class="supervisor-modal-backdrop" @click.self="closeGuardianModal">
      <form class="supervisor-modal" @submit.prevent="submitGuardianDetails">
        <h3>Enter parent/guardian details</h3>
        <p>
          Applies to {{ guardianModal.studentIds.length }} student{{
            guardianModal.studentIds.length === 1 ? '' : 's'
          }}.
        </p>
        <label>
          First name
          <input v-model="guardianForm.firstName" required />
        </label>
        <label>
          Last name
          <input v-model="guardianForm.lastName" required />
        </label>
        <label>
          Email
          <input v-model="guardianForm.email" type="email" />
        </label>
        <p v-if="guardianError" class="supervisor-error">{{ guardianError }}</p>
        <div class="supervisor-modal-actions">
          <button type="button" class="btn btn-outline" @click="closeGuardianModal">Cancel</button>
          <button type="submit" class="btn btn-primary" :disabled="guardianSaving">Save</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import SupervisorDataTable, {
  type SupervisorColumn,
  type SupervisorTableOption,
  type SupervisorTableOptionGroup,
} from '@/components/supervisor/SupervisorDataTable.vue'
import { downloadConsentDocuments } from '@/utils/consentDocument'
import { buildSessionHeaders } from '@/utils/csrf'
import {
  classifyStudent,
  fetchSupervisedStudents,
  saveGuardianDetails,
  toStudentRow,
  type SupervisedStudent,
} from '@/utils/supervisedStudents'

type SectionId = 'pendingDetails' | 'pendingPermission' | 'fullyRegistered'
type StudentRow = ReturnType<typeof toStudentRow>

const loading = ref(true)
const error = ref('')
const notice = ref('')
const students = ref<SupervisedStudent[]>([])
const guardianSaving = ref(false)
const guardianError = ref('')
const guardianModal = ref<{ studentIds: number[] } | null>(null)
const guardianForm = ref({ firstName: '', lastName: '', email: '' })

const studentLink = (row: Record<string, unknown>) => ({
  name: 'student-summary',
  params: { id: String(row.id) },
})

const guardianLink = (row: Record<string, unknown>) => ({
  name: 'guardian-summary',
  params: { id: String(row.id) },
})

const pendingColumns: SupervisorColumn[] = [
  { key: 'student', label: 'Student', linkTo: studentLink },
  { key: 'school', label: 'School' },
  { key: 'yearLevel', label: 'Year Level', type: 'number' },
  { key: 'interests', label: 'Area(s) of Interest' },
]

const registeredColumns: SupervisorColumn[] = [
  { key: 'student', label: 'Student', linkTo: studentLink },
  { key: 'parentGuardian', label: 'Parent/Guardian', linkTo: guardianLink },
  { key: 'school', label: 'School' },
  { key: 'yearLevel', label: 'Year Level', type: 'number' },
  { key: 'interests', label: 'Area(s) of Interest' },
]

const pendingDetailsActions: SupervisorTableOption[] = [
  { value: 'email-students', label: 'Email student', needsSelection: true },
  { value: 'copy-invite', label: 'Copy invite text', needsSelection: true },
  { value: 'enter-guardian', label: 'Enter guardian details', needsSelection: true },
]

const pendingPermissionActions: SupervisorTableOption[] = [
  { value: 'email-guardians', label: 'Email parent/guardian', needsSelection: true },
  { value: 'copy-invite', label: 'Copy invite text', needsSelection: true },
]

const fullyRegisteredActions: SupervisorTableOption[] = [
  { value: 'view-consent', label: 'Download consent PDFs' },
  { value: 'view-consent-selected', label: 'Download selected consent PDFs', needsSelection: true },
]

const actionGroup = (options: SupervisorTableOption[]): SupervisorTableOptionGroup[] => [
  { label: 'Student actions', options },
]

const sections = computed(() => [
  {
    id: 'pendingDetails' as const,
    title: 'Pending Parent/Guardian Details',
    filename: 'pending-guardian-details',
    columns: pendingColumns,
    optionGroups: actionGroup(pendingDetailsActions),
    rowActions: pendingDetailsActions.map((action) => ({ ...action, needsSelection: false })),
    bulkActions: pendingDetailsActions,
    rows: students.value.filter((student) => classifyStudent(student) === 'pendingDetails').map(toStudentRow),
  },
  {
    id: 'pendingPermission' as const,
    title: 'Pending Parent/Guardian Permission',
    filename: 'pending-guardian-permission',
    columns: registeredColumns,
    optionGroups: actionGroup(pendingPermissionActions),
    rowActions: pendingPermissionActions.map((action) => ({ ...action, needsSelection: false })),
    bulkActions: pendingPermissionActions,
    rows: students.value
      .filter((student) => classifyStudent(student) === 'pendingPermission')
      .map(toStudentRow),
  },
  {
    id: 'fullyRegistered' as const,
    title: 'Fully Registered with Parent/Guardian Permission',
    filename: 'fully-registered-students',
    columns: registeredColumns,
    optionGroups: actionGroup(fullyRegisteredActions),
    rowActions: [{ value: 'view-consent', label: 'Download PDF' }],
    bulkActions: [{ value: 'view-consent-selected', label: 'Download consent PDFs' }],
    rows: students.value
      .filter((student) => classifyStudent(student) === 'fullyRegistered')
      .map(toStudentRow),
  },
])

const loadStudents = async () => {
  loading.value = true
  error.value = ''
  try {
    students.value = await fetchSupervisedStudents(
      buildSessionHeaders({ headers: { Accept: 'application/json' } }),
    )
  } catch (loadError) {
    error.value =
      loadError instanceof Error ? loadError.message : 'Student list could not be loaded.'
  } finally {
    loading.value = false
  }
}

const asRows = (rows: Record<string, unknown>[]) => rows as StudentRow[]

const uniqueEmails = (rows: StudentRow[], key: 'email' | 'pgEmail') =>
  [...new Set(rows.map((row) => String(row[key] || '').trim()).filter(Boolean))]

const copyText = async (value: string, success: string) => {
  if (!value.trim()) {
    notice.value = 'Nothing to copy for the selected students.'
    return
  }
  await navigator.clipboard.writeText(value)
  notice.value = success
}

const openMailto = (addresses: string[], subject: string, body: string) => {
  if (!addresses.length) {
    notice.value = 'No email addresses are available for the selected students.'
    return
  }
  const params = new URLSearchParams({ subject, body })
  const href =
    addresses.length === 1
      ? `mailto:${addresses[0]}?${params.toString()}`
      : `mailto:?bcc=${encodeURIComponent(addresses.join(','))}&${params.toString()}`
  window.location.href = href
}

const inviteText = (sectionId: SectionId, rows: StudentRow[]) => {
  if (sectionId === 'pendingDetails') {
    return rows
      .map(
        (row) =>
          `Please complete parent/guardian details for ${row.student} (${row.email}). A supervisor will follow up with the registration form when it is available.`,
      )
      .join('\n\n')
  }
  return rows
    .map((row) => {
      const recipient = row.pgEmail || row.email
      return `Please complete parent/guardian permission for ${row.student}. Contact: ${recipient}.`
    })
    .join('\n\n')
}

const openGuardianModal = (rows: StudentRow[]) => {
  const firstStudent = students.value.find((student) => student.id === Number(rows[0]?.id))
  guardianModal.value = { studentIds: rows.map((row) => Number(row.id)) }
  guardianForm.value = {
    firstName: rows.length === 1 ? firstStudent?.pg_first_name || '' : '',
    lastName: rows.length === 1 ? firstStudent?.pg_last_name || '' : '',
    email: rows.length === 1 ? firstStudent?.pg_email || '' : '',
  }
  guardianError.value = ''
}

const closeGuardianModal = () => {
  guardianModal.value = null
  guardianError.value = ''
}

const submitGuardianDetails = async () => {
  if (!guardianModal.value) return
  guardianSaving.value = true
  guardianError.value = ''
  try {
    students.value = await saveGuardianDetails({
      student_ids: guardianModal.value.studentIds,
      pg_first_name: guardianForm.value.firstName.trim(),
      pg_last_name: guardianForm.value.lastName.trim(),
      pg_email: guardianForm.value.email.trim(),
    })
    notice.value = 'Parent/guardian details saved.'
    closeGuardianModal()
  } catch (saveError) {
    guardianError.value =
      saveError instanceof Error ? saveError.message : 'Guardian details could not be saved.'
  } finally {
    guardianSaving.value = false
  }
}

const onSectionAction = async (sectionId: SectionId, value: string, rawRows: Record<string, unknown>[]) => {
  const rows = asRows(rawRows)
  if (!rows.length) {
    notice.value = 'Select at least one student first.'
    return
  }
  if (value === 'email-students') {
    openMailto(
      uniqueEmails(rows, 'email'),
      'Parent/guardian details needed',
      inviteText(sectionId, rows),
    )
    return
  }
  if (value === 'email-guardians') {
    const addresses = uniqueEmails(rows, 'pgEmail')
    openMailto(
      addresses.length ? addresses : uniqueEmails(rows, 'email'),
      'Parent/guardian permission needed',
      inviteText(sectionId, rows),
    )
    return
  }
  if (value === 'copy-invite') {
    await copyText(inviteText(sectionId, rows), 'Invite text copied.')
    return
  }
  if (value === 'enter-guardian') {
    openGuardianModal(rows)
    return
  }
  if (value === 'view-consent' || value === 'view-consent-selected') {
    downloadConsentDocuments(rows)
    notice.value = rows.length === 1 ? 'Downloaded guardian consent PDF.' : `Downloaded ${rows.length} consent PDFs.`
  }
}

onMounted(loadStudents)
</script>

<style scoped>
.supervisor-page-header h1 {
  margin: 0 0 0.35rem;
  font-size: 1.85rem;
}

.supervisor-page-header p,
.supervisor-muted,
.supervisor-error,
.supervisor-notice {
  margin: 0 0 1.5rem;
  color: #6c757d;
}

.supervisor-error {
  color: var(--danger, #b42318);
}

.supervisor-notice {
  color: var(--dark-green, #017151);
}

.supervisor-section {
  margin-bottom: 2.25rem;
}

.supervisor-section h2 {
  margin: 0 0 0.85rem;
  font-size: 1.15rem;
  font-weight: 700;
}

.supervisor-row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.supervisor-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 1.5rem;
  background: rgba(23, 66, 67, 0.35);
}

.supervisor-modal {
  width: min(28rem, 100%);
  display: grid;
  gap: 0.75rem;
  padding: 1.25rem;
  border-radius: 10px;
  background: var(--white);
  box-shadow: 0 12px 32px var(--shadow);
}

.supervisor-modal h3,
.supervisor-modal p {
  margin: 0;
}

.supervisor-modal label {
  display: grid;
  gap: 0.3rem;
  color: #6c757d;
  font-size: 0.9rem;
}

.supervisor-modal input {
  padding: 0.5rem 0.65rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  color: var(--charcoal);
}

.supervisor-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 0.35rem;
}
</style>
