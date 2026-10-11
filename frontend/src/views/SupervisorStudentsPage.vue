<template>
  <div class="content-area supervisor-students-page">
    <header class="page-header">
      <h1 class="page-title">Registered Students</h1>
      <p class="page-subtitle">This is a list of all students registered under your supervision.</p>
    </header>

    <p v-if="notice" class="supervisor-notice">{{ notice }}</p>
    <p v-if="error" class="supervisor-error">{{ error }}</p>
    <p v-else-if="loading" class="supervisor-muted">Loading students...</p>

    <nav class="tab-bar" role="tablist" aria-label="Student registration">
      <button
        v-for="tab in sectionTabs"
        :key="tab.id"
        type="button"
        role="tab"
        :aria-selected="activeSection === tab.id"
        class="tab-pill"
        :class="{ active: activeSection === tab.id }"
        @click="activeSection = tab.id"
      >
        {{ tab.label }}
      </button>
    </nav>

    <section
      v-for="section in sections.filter((item) => item.id === activeSection)"
      :key="section.id"
      class="supervisor-section"
    >
      <h2 class="subheading">{{ section.title }}</h2>
      <AppDataTable
        :columns="section.columns"
        :rows="section.rows"
        :action-columns="section.rowActions.length"
        :default-sort="section.defaultSort"
        clickable-rows
        @row-click="openSheet"
      >
        <!-- A student, or their guardian, opens the student's panel. -->
        <template #cell-student="{ row, value }">
          <button type="button" class="supervisor-name-btn" @click.stop="openSheet(row)">{{ value }}</button>
        </template>
        <template #cell-parentGuardian="{ row, value }">
          <button type="button" class="supervisor-name-btn" @click.stop="openSheet(row, 'guardian')">{{ value }}</button>
        </template>
        <!-- Options sits beside Search, in the table's search card. -->
        <template #filters="{ rows, pageRows, selectedRows }">
          <SupervisorTableOptions
            :columns="section.columns"
            :rows="rows"
            :page-rows="pageRows"
            :selected-rows="selectedRows"
            :filename="section.filename"
            :email-keys="['email', 'pgEmail']"
          />
        </template>
        <template #search-side>
          <button
            v-if="section.emailAll"
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="emailSending || !section.rows.length"
            @click="onSectionAction(section.id, section.emailAll.value, section.rows)"
          >
            {{ section.emailAll.label }}
          </button>
          <!-- A sheet of guardians, as Grading's Upload marks. -->
          <GuardianUploadDialog v-if="section.id === 'pendingDetails'" @applied="onGuardiansUploaded" />
          <button
            v-if="section.id === 'fullyRegistered' && section.rows.length"
            type="button"
            class="btn btn-primary btn-sm"
            @click="onSectionAction(section.id, 'view-consent-all', section.rows)"
          >
            Download All Consent PDFs
          </button>
        </template>
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
        <!-- Each row button has its own column with no heading. -->
        <template #actions="{ row, column }">
          <button
            type="button"
            class="btn btn-outline btn-sm"
            @click="onSectionAction(section.id, section.rowActions[column].value, [row])"
          >
            {{ section.rowActions[column].label }}
          </button>
        </template>
      </AppDataTable>
    </section>

    <div v-if="guardianModal" class="supervisor-modal-backdrop" @click.self="closeGuardianModal">
      <form class="supervisor-modal" @submit.prevent="submitGuardianDetails">
        <h3>Enter guardian details</h3>
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

    <div v-if="emailConfirm" class="supervisor-modal-backdrop" @click.self="closeEmailConfirm">
      <section class="supervisor-modal" role="dialog" aria-modal="true" aria-labelledby="email-confirm-title">
        <h3 id="email-confirm-title">{{ emailConfirm.title }}</h3>
        <p>{{ emailConfirm.copy }}</p>
        <ul v-if="emailConfirm.names.length" class="email-confirm-list">
          <li v-for="name in emailConfirm.names" :key="name">{{ name }}</li>
        </ul>
        <div class="supervisor-modal-actions">
          <button type="button" class="btn btn-outline" :disabled="emailSending" @click="closeEmailConfirm">
            Cancel
          </button>
          <button type="button" class="btn btn-primary" :disabled="emailSending" @click="confirmSupervisedEmail">
            {{ emailSending ? 'Sending…' : 'Send Emails' }}
          </button>
        </div>
      </section>
    </div>

    <SupervisorStudentSheet
      :student="sheetStudent"
      :at-guardian="route.query.show === 'guardian' || route.query.show === 'edit-guardian'"
      :edit-guardian="route.query.show === 'edit-guardian'"
      @close="closeSheet"
      @saved="students = $event"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter, type LocationQueryRaw } from 'vue-router'
import { useFlashMessage } from '@/composables/useFlashMessage'
import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'
import GuardianUploadDialog from '@/components/supervisor/GuardianUploadDialog.vue'
import SupervisorStudentSheet from '@/components/supervisor/SupervisorStudentSheet.vue'
import SupervisorTableOptions from '@/components/supervisor/SupervisorTableOptions.vue'
import { downloadConsentDocuments, viewConsentDocuments } from '@/utils/consentDocument'
import { buildSessionHeaders } from '@/utils/csrf'
import {
  classifyStudent,
  fetchConsentLinks,
  fetchDetailsLinks,
  fetchSupervisedStudents,
  saveGuardianDetails,
  sendSupervisedEmails,
  toStudentRow,
  type SupervisedEmailKind,
  type SupervisedStudent,
} from '@/utils/supervisedStudents'

type SectionId = 'pendingDetails' | 'pendingPermission' | 'fullyRegistered'
type StudentRow = ReturnType<typeof toStudentRow>

const loading = ref(true)
const error = ref('')
// Clears itself after 3.5s, like the other pages' success messages.
const { message: notice, show: flashNotice } = useFlashMessage()
const students = ref<SupervisedStudent[]>([])
const guardianSaving = ref(false)
const guardianError = ref('')
const guardianModal = ref<{ studentIds: number[] } | null>(null)
const guardianForm = ref({ firstName: '', lastName: '', email: '' })
const emailSending = ref(false)
const emailConfirm = ref<{
  kind: SupervisedEmailKind
  studentIds: number[]
  names: string[]
  title: string
  copy: string
} | null>(null)

// The student whose panel is open, kept in the address (?student=12, plus
// show=guardian to open at their guardian, or show=edit-guardian with its
// form open) so a refresh opens it again.
const route = useRoute()
const router = useRouter()
const sheetStudentId = computed(() => Number(route.query.student) || null)
const sheetStudent = computed(() => students.value.find((student) => student.id === sheetStudentId.value) ?? null)
const openSheet = (row: Record<string, unknown>, show?: 'guardian' | 'edit-guardian') => {
  const query: LocationQueryRaw = { ...route.query, student: String(row.id) }
  if (show) query.show = show
  else delete query.show
  void router.replace({ query })
}
const closeSheet = () => {
  const query = { ...route.query }
  delete query.student
  delete query.show
  void router.replace({ query })
}

const pendingColumns: DataTableColumn[] = [
  { key: 'student', label: 'Student' },
  { key: 'school', label: 'School' },
  { key: 'yearLevel', label: 'Year', type: 'number' },
  { key: 'interests', label: 'Area(s) of Interest', wrap: true },
]

const registeredColumns: DataTableColumn[] = [
  { key: 'student', label: 'Student' },
  { key: 'parentGuardian', label: 'Guardian' },
  { key: 'school', label: 'School' },
  { key: 'yearLevel', label: 'Year', type: 'number' },
  { key: 'interests', label: 'Area(s) of Interest', wrap: true },
]

const fullyRegisteredColumns: DataTableColumn[] = [
  ...registeredColumns,
  // Sorted by when, not by the shown "09/10/26 16:12".
  { key: 'permissionGiven', label: 'Permission', sortValue: (row) => Date.parse(String(row.permissionGivenAt)) || 0 },
]

// A button on the rows or in the selected bar, and whether it needs ticked rows.
type StudentAction = { value: string; label: string; needsSelection?: boolean }

const pendingDetailsActions: StudentAction[] = [
  { value: 'email-students', label: 'Email Student', needsSelection: true },
  { value: 'copy-invite', label: 'Copy Details Link', needsSelection: true },
  { value: 'enter-guardian', label: 'Enter Guardian Details', needsSelection: true },
]

const pendingPermissionActions: StudentAction[] = [
  { value: 'email-guardians', label: 'Email Guardian', needsSelection: true },
  { value: 'copy-invite', label: 'Copy Consent Link', needsSelection: true },
]

// One table at a time, picked from the bar above it as Management's are.
const sectionTabs = [
  { id: 'pendingDetails', label: 'Pending Details' },
  { id: 'pendingPermission', label: 'Pending Permission' },
  { id: 'fullyRegistered', label: 'Fully Registered' },
] as const
const activeSection = ref<SectionId>('pendingDetails')

const sections = computed(() => [
  {
    id: 'pendingDetails' as const,
    title: 'Pending Guardian Details',
    filename: 'pending-guardian-details',
    columns: pendingColumns,
    defaultSort: undefined,
    rowActions: pendingDetailsActions.map((action) => ({ ...action, needsSelection: false })),
    bulkActions: pendingDetailsActions,
    emailAll: { value: 'email-students-all', label: 'Email All Students' },
    rows: students.value.filter((student) => classifyStudent(student) === 'pendingDetails').map(toStudentRow),
  },
  {
    id: 'pendingPermission' as const,
    title: 'Pending Guardian Permission',
    filename: 'pending-guardian-permission',
    columns: registeredColumns,
    defaultSort: undefined,
    rowActions: pendingPermissionActions.map((action) => ({ ...action, needsSelection: false })),
    bulkActions: pendingPermissionActions,
    emailAll: { value: 'email-guardians-all', label: 'Email All Guardians' },
    rows: students.value
      .filter((student) => classifyStudent(student) === 'pendingPermission')
      .map(toStudentRow),
  },
  {
    id: 'fullyRegistered' as const,
    title: 'Fully Registered with Guardian Permission',
    filename: 'fully-registered-students',
    columns: fullyRegisteredColumns,
    // Latest permission first.
    defaultSort: { key: 'permissionGiven', direction: 'desc' } as const,
    rowActions: [
      { value: 'open-consent', label: 'View' },
      { value: 'view-consent', label: 'Download' },
    ],
    bulkActions: [{ value: 'view-consent-selected', label: 'Download Selected PDFs' }],
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

const studentIdsFrom = (rows: StudentRow[]) =>
  [...new Set(rows.map((row) => Number(row.id)).filter((id) => Number.isFinite(id) && id > 0))]

const copyText = async (value: string, success: string) => {
  if (!value.trim()) {
    flashNotice('Nothing to copy for the selected students.')
    return
  }
  await navigator.clipboard.writeText(value)
  flashNotice(success)
}

// One student copies the link alone; several copy a "Name: link" line each.
const linkLines = (made: { name: string; link: string }[]) =>
  made.length === 1 ? made[0]!.link : made.map(({ name, link }) => `${name}: ${link}`).join('\n')

// Pending details: a public form for each guardian's name and email.
// Pending permission: each guardian's consent link.
const copyInviteLinks = async (sectionId: SectionId, rows: StudentRow[]) => {
  error.value = ''
  const details = sectionId === 'pendingDetails'
  const kind = details ? 'details' : 'consent'
  try {
    const links = await (details ? fetchDetailsLinks : fetchConsentLinks)(studentIdsFrom(rows))
    const linkFor = new Map(links.map((item) => [item.studentId, item.link]))
    const made = rows.flatMap((row) => {
      const link = linkFor.get(Number(row.id))
      return link ? [{ name: row.student, link }] : []
    })
    const copied = made.length === 1 ? `${details ? 'Details' : 'Consent'} link copied.` : `${made.length} ${kind} links copied.`
    await copyText(linkLines(made), copied)
    const missed = links.filter((item) => !item.link)
    if (missed.length && made.length) {
      flashNotice(`${notice.value} ${missed.length} could not be made: ${missed[0]!.msg}`)
    }
  } catch (linkError) {
    notice.value = ''
    error.value = linkError instanceof Error ? linkError.message : `The ${kind} links could not be made.`
  }
}

const onGuardiansUploaded = async (saved: number) => {
  await loadStudents()
  flashNotice(`Guardian details saved for ${saved} student${saved === 1 ? '' : 's'}.`)
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

const closeEmailConfirm = () => {
  emailConfirm.value = null
}

const askToSend = (
  kind: SupervisedEmailKind,
  rows: StudentRow[],
  title: string,
  copy: string,
) => {
  const studentIds = studentIdsFrom(rows)
  if (!studentIds.length) {
    flashNotice('Select at least one student first.')
    return
  }
  emailConfirm.value = {
    kind,
    studentIds,
    names: rows.map((row) =>
      kind === 'guardian_consent' ? row.parentGuardian || row.student : row.student,
    ),
    title,
    copy,
  }
}

const sendSelectedEmails = async (kind: SupervisedEmailKind, ids: number[]) => {
  if (!ids.length) {
    flashNotice('Select at least one student first.')
    return
  }
  emailSending.value = true
  error.value = ''
  try {
    const result = await sendSupervisedEmails(ids, kind)
    flashNotice(result.msg)
  } catch (sendError) {
    notice.value = ''
    error.value = sendError instanceof Error ? sendError.message : 'Emails could not be sent.'
  } finally {
    emailSending.value = false
  }
}

const confirmSupervisedEmail = async () => {
  if (!emailConfirm.value) return
  const { kind, studentIds } = emailConfirm.value
  closeEmailConfirm()
  await sendSelectedEmails(kind, studentIds)
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
    flashNotice('Guardian details saved.')
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
    flashNotice('Select at least one student first.')
    return
  }
  if (value === 'email-students' || value === 'email-students-all') {
    askToSend(
      'guardian_details',
      rows,
      value === 'email-students-all' ? 'Email all students?' : 'Email student?',
      value === 'email-students-all'
        ? 'Send the System Email asking these students to add guardian details?'
        : 'Send the System Email asking this student to add guardian details?',
    )
    return
  }
  if (value === 'email-guardians' || value === 'email-guardians-all') {
    askToSend(
      'guardian_consent',
      rows,
      value === 'email-guardians-all' ? 'Email all guardians?' : 'Email guardian?',
      value === 'email-guardians-all'
        ? 'Send the consent form System Email to these guardians?'
        : 'Send the consent form System Email to this guardian?',
    )
    return
  }
  if (value === 'copy-invite') {
    await copyInviteLinks(sectionId, rows)
    return
  }
  if (value === 'enter-guardian') {
    // One student: their panel with the guardian form open. Several share the
    // popup, which saves the same guardian for each.
    if (rows.length === 1) openSheet(rows[0]!, 'edit-guardian')
    else openGuardianModal(rows)
    return
  }
  if (value === 'open-consent') {
    viewConsentDocuments(rows).catch(() => {
      notice.value = ''
      error.value = 'Consent PDF could not be generated.'
    })
    return
  }
  if (value === 'view-consent' || value === 'view-consent-selected' || value === 'view-consent-all') {
    const source = value === 'view-consent-all'
      ? asRows(sections.value.find((section) => section.id === 'fullyRegistered')?.rows || [])
      : rows
    if (!source.length) {
      flashNotice('No consent records are available to download.')
      return
    }
    downloadConsentDocuments(source)
      .then(() => {
        error.value = ''
        flashNotice(
          source.length === 1
            ? 'Downloaded BIOTech Futures consent PDF.'
            : `Downloaded ${source.length} BIOTech Futures consent PDFs.`,
        )
      })
      .catch(() => {
        notice.value = ''
        error.value = 'Consent PDF could not be generated.'
      })
  }
}

onMounted(loadStudents)
</script>

<style scoped>
/* A name that opens the student's panel, looking like the table's links. */
.supervisor-name-btn {
  padding: 0;
  border: none;
  background: none;
  color: var(--dark-green);
  font: inherit;
  font-weight: 600;
  text-align: left;
  text-decoration: underline;
  cursor: pointer;
}

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

.email-confirm-list {
  margin: 0;
  padding-left: 1.1rem;
  color: #3d4a4a;
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
  color: var(--teal);
}

.supervisor-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 0.35rem;
}
</style>
