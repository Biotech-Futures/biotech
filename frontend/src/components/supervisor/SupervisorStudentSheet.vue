<template>
  <!-- A student's details, slid over My Students as admin's user panel is.
       Clicking their guardian opens it at Guardian Details. -->
  <FormSheet
    :model-value="Boolean(student)"
    :title="studentName"
    description="Student details"
    width="min(100vw, 620px)"
    @close="emit('close')"
  >
    <div v-if="student" class="student-sheet">
      <section class="student-sheet__section">
        <div class="student-sheet__heading">
          <h3>Personal information</h3>
          <button v-if="!personalEditing" type="button" class="btn btn-outline btn-sm" @click="startPersonalEdit">
            Edit
          </button>
        </div>
        <p v-if="personalSavedMessage" class="student-sheet__saved">{{ personalSavedMessage }}</p>
        <!-- Email, country and region; role and account status stay as they are. -->
        <form v-if="personalEditing" id="student-sheet-personal" @submit.prevent="savePersonal">
          <label class="student-sheet__item">
            <span class="student-sheet__label">Email</span>
            <input v-model="personalForm.email" class="student-sheet__input" type="email" required />
          </label>
          <label class="student-sheet__item">
            <span class="student-sheet__label">Country</span>
            <select v-model="personalForm.countryId" class="student-sheet__input" @change="personalForm.stateId = null">
              <option :value="null">Not set</option>
              <option v-for="country in editOptions.countries" :key="country.id" :value="country.id">
                {{ country.country_name }}
              </option>
            </select>
          </label>
          <label class="student-sheet__item">
            <span class="student-sheet__label">Region</span>
            <select v-model="personalForm.stateId" class="student-sheet__input">
              <option :value="null">Not set</option>
              <option v-for="region in regionChoices" :key="region.id" :value="region.id">
                {{ region.state_name }}
              </option>
            </select>
          </label>
        </form>
        <dl class="student-sheet__list">
          <template v-if="!personalEditing">
            <div class="student-sheet__item">
              <dt>Email</dt>
              <dd>{{ display(student.email) }}</dd>
            </div>
            <div class="student-sheet__item">
              <dt>Country</dt>
              <dd>{{ display(student.country_name) }}</dd>
            </div>
            <div class="student-sheet__item">
              <dt>Region</dt>
              <dd>{{ display(student.state_name) }}</dd>
            </div>
          </template>
          <div class="student-sheet__item">
            <dt>Role</dt>
            <dd>Student</dd>
          </div>
          <div class="student-sheet__item">
            <dt>Account Status</dt>
            <dd>{{ display(student.account_status) }}</dd>
          </div>
        </dl>
        <template v-if="personalEditing">
          <p v-if="personalError" class="student-sheet__error">{{ personalError }}</p>
          <div class="student-sheet__actions">
            <button type="button" class="btn btn-outline btn-sm" :disabled="personalSaving" @click="personalEditing = false">
              Cancel
            </button>
            <button type="submit" form="student-sheet-personal" class="btn btn-primary btn-sm" :disabled="personalSaving">
              {{ personalSaving ? 'Saving…' : 'Save' }}
            </button>
          </div>
        </template>
      </section>

      <section class="student-sheet__section">
        <div class="student-sheet__heading">
          <h3>Student Details</h3>
          <button
            v-if="!detailsEditing"
            type="button"
            class="btn btn-outline btn-sm"
            @click="startDetailsEdit"
          >
            Edit
          </button>
        </div>
        <p v-if="detailsSavedMessage" class="student-sheet__saved">{{ detailsSavedMessage }}</p>
        <!-- The supervisor edits the student's name, school, year and interests. -->
        <form v-if="detailsEditing" @submit.prevent="saveDetails">
          <label class="student-sheet__item">
            <span class="student-sheet__label">First name</span>
            <input v-model="detailsForm.firstName" class="student-sheet__input" required maxlength="255" />
          </label>
          <label class="student-sheet__item">
            <span class="student-sheet__label">Last name</span>
            <input v-model="detailsForm.lastName" class="student-sheet__input" required maxlength="255" />
          </label>
          <label class="student-sheet__item">
            <span class="student-sheet__label">School</span>
            <input v-model="detailsForm.school" class="student-sheet__input" required maxlength="255" />
          </label>
          <label class="student-sheet__item">
            <span class="student-sheet__label">Year Level</span>
            <select v-model="detailsForm.yearLevel" class="student-sheet__input" required>
              <option v-for="year in YEAR_LEVELS" :key="year" :value="year">{{ year }}</option>
            </select>
          </label>
          <fieldset class="student-sheet__item student-sheet__interest-options">
            <legend class="student-sheet__label">Areas of Interests</legend>
            <label v-for="interest in interestChoices" :key="interest">
              <input v-model="detailsForm.interests" type="checkbox" :value="interest" />
              {{ interest }}
            </label>
          </fieldset>
          <p v-if="detailsError" class="student-sheet__error">{{ detailsError }}</p>
          <div class="student-sheet__actions">
            <button type="button" class="btn btn-outline btn-sm" :disabled="detailsSaving" @click="detailsEditing = false">
              Cancel
            </button>
            <button type="submit" class="btn btn-primary btn-sm" :disabled="detailsSaving">
              {{ detailsSaving ? 'Saving…' : 'Save' }}
            </button>
          </div>
        </form>
        <dl v-else class="student-sheet__list">
          <div class="student-sheet__item">
            <dt>Name</dt>
            <dd>{{ studentName }}</dd>
          </div>
          <div class="student-sheet__item">
            <dt>School</dt>
            <dd>{{ display(student.school_name) }}</dd>
          </div>
          <div class="student-sheet__item">
            <dt>Year Level</dt>
            <dd>{{ display(student.year_lvl) }}</dd>
          </div>
          <div class="student-sheet__item">
            <dt>Areas of Interests</dt>
            <!-- Green bubbles, as the student's page had them. -->
            <dd v-if="student.interests.length" class="student-sheet__interests">
              <span v-for="interest in student.interests" :key="interest" class="student-sheet__interest">
                {{ interest }}
              </span>
            </dd>
            <dd v-else>—</dd>
          </div>
        </dl>
      </section>

      <section ref="guardianSection" class="student-sheet__section">
        <div class="student-sheet__heading">
          <h3>Guardian Details</h3>
          <!-- Not once permission is given: that was for the guardian on file. -->
          <button
            v-if="!editing && !student.has_join_permission"
            type="button"
            class="btn btn-outline btn-sm"
            @click="startEditing"
          >
            Edit
          </button>
        </div>
        <p v-if="savedMessage" class="student-sheet__saved">{{ savedMessage }}</p>
        <!-- Editing turns Name and Email into the form; Permission and Media
             Consent stay below it. -->
        <form v-if="editing" id="student-sheet-guardian" @submit.prevent="saveGuardian">
          <label class="student-sheet__item">
            <span class="student-sheet__label">First name</span>
            <input v-model="guardianForm.firstName" class="student-sheet__input" required />
          </label>
          <label class="student-sheet__item">
            <span class="student-sheet__label">Last name</span>
            <input v-model="guardianForm.lastName" class="student-sheet__input" required />
          </label>
          <label class="student-sheet__item">
            <span class="student-sheet__label">Email</span>
            <input v-model="guardianForm.email" class="student-sheet__input" type="email" />
          </label>
        </form>
        <dl class="student-sheet__list">
          <template v-if="!editing">
            <div class="student-sheet__item">
              <dt>Name</dt>
              <dd>{{ guardianName }}</dd>
            </div>
            <div class="student-sheet__item">
              <dt>Email</dt>
              <dd>{{ display(student.pg_email) }}</dd>
            </div>
          </template>
          <div class="student-sheet__item">
            <dt>Permission</dt>
            <dd>{{ permission }}</dd>
          </div>
          <div class="student-sheet__item">
            <dt>Media Consent</dt>
            <dd>{{ mediaConsent }}</dd>
          </div>
        </dl>
        <template v-if="editing">
          <p v-if="saveError" class="student-sheet__error">{{ saveError }}</p>
          <div class="student-sheet__actions">
            <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="editing = false">
              Cancel
            </button>
            <button type="submit" form="student-sheet-guardian" class="btn btn-primary btn-sm" :disabled="saving">
              {{ saving ? 'Saving…' : 'Save' }}
            </button>
          </div>
        </template>
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
import { computed, nextTick, ref, watch } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import { useFlashMessage } from '@/composables/useFlashMessage'
import { DEFAULT_GROUP_INTERESTS } from '@/utils/supervisedGroups'
import {
  fetchStudentEditOptions,
  fullName,
  saveGuardianDetails,
  updateSupervisedStudentProfile,
  type StudentEditOptions,
  type SupervisedStudent,
} from '@/utils/supervisedStudents'

const props = defineProps<{
  /** The student to show; the panel is open while there is one. */
  student: SupervisedStudent | null
  /** Open at the Guardian Details section. */
  atGuardian?: boolean
  /** Open with the guardian form already open (Enter Guardian Details). */
  editGuardian?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  /** The roster after the guardian was saved. */
  (e: 'saved', students: SupervisedStudent[]): void
  /** The student after their details were saved. */
  (e: 'updated', student: SupervisedStudent): void
}>()

const display = (value?: string | null) => String(value ?? '').trim() || '—'

// Scrolled to the top of the panel when opened at the guardian.
const guardianSection = ref<HTMLElement | null>(null)
watch(
  () => [props.student?.id, props.atGuardian],
  async () => {
    if (!props.student || !props.atGuardian) return
    await nextTick()
    guardianSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  },
  { immediate: true },
)

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

// Only a given permission is recorded; a guardian never answers no.
const permission = computed(() => (props.student?.has_join_permission ? 'Yes' : '—'))

// From the signed form; consent marked received without one has no answer.
const mediaConsent = computed(() => {
  const answer = props.student?.media_consent
  if (answer == null) return '—'
  return answer ? 'Yes' : 'No'
})

// Guardian Details' Edit: the section turns into a form.
const editing = ref(false)
const saving = ref(false)
const saveError = ref('')
const guardianForm = ref({ firstName: '', lastName: '', email: '' })
const { message: savedMessage, show: flashSaved } = useFlashMessage()

const startEditing = () => {
  if (!props.student) return
  const hasGuardian = guardianName.value !== '—'
  guardianForm.value = {
    firstName: hasGuardian ? props.student.pg_first_name : '',
    lastName: hasGuardian ? props.student.pg_last_name : '',
    email: props.student.pg_email || '',
  }
  saveError.value = ''
  editing.value = true
}

// Student Details' Edit: name, school, year and interests.
const YEAR_LEVELS = ['9', '10', '11', '12']
const detailsEditing = ref(false)
const detailsSaving = ref(false)
const detailsError = ref('')
const detailsForm = ref({ firstName: '', lastName: '', school: '', yearLevel: '', interests: [] as string[] })
const { message: detailsSavedMessage, show: flashDetailsSaved } = useFlashMessage()

// The countries, regions and interests the Edit forms offer, read once.
const editOptions = ref<StudentEditOptions>({ countries: [], regions: [], interests: [] })
const loadEditOptions = async () => {
  if (editOptions.value.countries.length || editOptions.value.interests.length) return
  editOptions.value = await fetchStudentEditOptions().catch(() => ({
    countries: [],
    regions: [],
    interests: [...DEFAULT_GROUP_INTERESTS],
  }))
}

// Every area of interest on offer, with any the student already has.
const interestChoices = computed(() => {
  const all = [...editOptions.value.interests]
  for (const interest of props.student?.interests ?? []) {
    if (!all.some((item) => item.toLowerCase() === interest.toLowerCase())) all.push(interest)
  }
  return all
})

const startDetailsEdit = async () => {
  if (!props.student) return
  detailsForm.value = {
    firstName: props.student.first_name,
    lastName: props.student.last_name,
    school: props.student.school_name,
    yearLevel: props.student.year_lvl,
    interests: [...props.student.interests],
  }
  detailsError.value = ''
  detailsEditing.value = true
  await loadEditOptions()
}

const saveDetails = async () => {
  if (!props.student) return
  detailsSaving.value = true
  detailsError.value = ''
  try {
    const updated = await updateSupervisedStudentProfile(props.student.id, {
      first_name: detailsForm.value.firstName.trim(),
      last_name: detailsForm.value.lastName.trim(),
      email: props.student.email,
      school_name: detailsForm.value.school.trim(),
      year_lvl: detailsForm.value.yearLevel,
      interests: detailsForm.value.interests,
    })
    emit('updated', updated)
    detailsEditing.value = false
    flashDetailsSaved('Student details saved.')
  } catch (error) {
    detailsError.value = error instanceof Error ? error.message : 'Student details could not be saved.'
  } finally {
    detailsSaving.value = false
  }
}

// Personal information's Edit: email, country and region.
const personalEditing = ref(false)
const personalSaving = ref(false)
const personalError = ref('')
const personalForm = ref({ email: '', countryId: null as number | null, stateId: null as number | null })
const { message: personalSavedMessage, show: flashPersonalSaved } = useFlashMessage()

const regionChoices = computed(() =>
  editOptions.value.regions.filter((region) => region.country_id === personalForm.value.countryId),
)

const startPersonalEdit = async () => {
  if (!props.student) return
  personalForm.value = {
    email: props.student.email,
    countryId: props.student.country_id ?? null,
    stateId: props.student.state_id ?? null,
  }
  personalError.value = ''
  personalEditing.value = true
  await loadEditOptions()
}

const savePersonal = async () => {
  if (!props.student) return
  personalSaving.value = true
  personalError.value = ''
  try {
    // The endpoint also takes the name, school and year, which stay as they are.
    const updated = await updateSupervisedStudentProfile(props.student.id, {
      first_name: props.student.first_name,
      last_name: props.student.last_name,
      email: personalForm.value.email.trim(),
      school_name: props.student.school_name,
      year_lvl: props.student.year_lvl,
      country_id: personalForm.value.countryId,
      state_id: personalForm.value.stateId,
    })
    emit('updated', updated)
    personalEditing.value = false
    flashPersonalSaved('Personal information saved.')
  } catch (error) {
    personalError.value = error instanceof Error ? error.message : 'Personal information could not be saved.'
  } finally {
    personalSaving.value = false
  }
}

// Another student's panel starts out showing, unless it was opened to edit.
watch(
  () => [props.student?.id, props.editGuardian],
  () => {
    personalEditing.value = false
    detailsEditing.value = false
    editing.value = false
    if (props.editGuardian && props.student && !props.student.has_join_permission) startEditing()
  },
  { immediate: true },
)

const saveGuardian = async () => {
  if (!props.student) return
  saving.value = true
  saveError.value = ''
  try {
    const students = await saveGuardianDetails({
      student_ids: [props.student.id],
      pg_first_name: guardianForm.value.firstName.trim(),
      pg_last_name: guardianForm.value.lastName.trim(),
      pg_email: guardianForm.value.email.trim(),
    })
    emit('saved', students)
    editing.value = false
    flashSaved('Guardian details saved.')
  } catch (error) {
    saveError.value = error instanceof Error ? error.message : 'Guardian details could not be saved.'
  } finally {
    saving.value = false
  }
}
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

/* Guardian Details' heading with its Edit button on the right. */
.student-sheet__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.4rem;
}

.student-sheet__heading h3 {
  margin: 0;
}

.student-sheet__label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-muted);
  flex-shrink: 0;
}

.student-sheet__input {
  flex: 1;
  max-width: 320px;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  font: inherit;
  color: var(--teal);
  background: var(--surface-elevated);
}

.student-sheet__item:has(.student-sheet__input) {
  align-items: center;
}

.student-sheet__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.student-sheet__saved {
  margin: 0 0 0.4rem;
  color: var(--dark-green);
}

/* Student Details' interests to tick, one per line. */
.student-sheet__interest-options {
  flex-direction: column;
  align-items: flex-start;
  margin: 0;
  border: none;
  border-bottom: 1px solid var(--border-light);
  padding: 0.6rem 0;
}

.student-sheet__interest-options legend {
  padding: 0;
  margin-bottom: 0.4rem;
}

.student-sheet__interest-options label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--teal);
}

.student-sheet__error {
  margin: 0.5rem 0 0;
  color: var(--danger);
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

.student-sheet__interests {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.4rem;
}

.student-sheet__interest {
  display: inline-flex;
  align-items: center;
  min-height: 1.75rem;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  background: var(--accent-green-soft);
  color: var(--dark-green);
  font-size: 0.9rem;
}

.student-sheet__item dd {
  margin: 0;
  color: var(--teal);
  text-align: right;
  overflow-wrap: anywhere;
}
</style>
