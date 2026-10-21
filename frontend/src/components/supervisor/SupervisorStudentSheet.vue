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
      <!-- Their photo, as the admin's user panel has it: changed with Save. -->
      <section class="student-sheet__section" data-test="student-sheet-photo">
        <div class="student-sheet__heading">
          <h3>Profile Photo</h3>
          <button v-if="!photoEditing" type="button" class="btn btn-outline btn-sm" @click="startPhotoEdit">
            Edit
          </button>
        </div>
        <form v-if="photoEditing" data-test="student-sheet-photo-form" @submit.prevent="savePhoto">
          <div class="student-sheet__item student-sheet__photo-row">
            <span class="student-sheet__label">Photo</span>
            <div class="student-sheet__photo-edit">
              <img v-if="photoShown" class="student-sheet__photo" :src="photoShown" alt="Profile photo" />
              <span v-else>—</span>
              <label class="btn btn-outline btn-sm">
                Choose photo
                <input
                  type="file"
                  class="sr-only"
                  :accept="PROFILE_PHOTO_ACCEPT"
                  data-test="student-sheet-photo-input"
                  @change="choosePhoto"
                />
              </label>
              <button
                v-if="photoShown"
                type="button"
                class="btn btn-outline btn-sm"
                data-test="student-sheet-photo-remove"
                @click="removePhotoDraft"
              >
                Remove
              </button>
            </div>
          </div>
          <p class="student-sheet__photo-note">PNG, JPEG or WebP, smaller than 5 MB.</p>
          <p v-if="photoError" class="student-sheet__error">{{ photoError }}</p>
          <div class="student-sheet__actions">
            <button type="button" class="btn btn-outline btn-sm" :disabled="photoSaving" @click="cancelPhotoEdit">
              Cancel
            </button>
            <button type="submit" class="btn btn-primary btn-sm" :disabled="photoSaving">
              {{ photoSaving ? 'Saving…' : 'Save' }}
            </button>
          </div>
        </form>
        <dl v-else class="student-sheet__list">
          <div class="student-sheet__item student-sheet__photo-row">
            <dt>Photo</dt>
            <dd>
              <img v-if="student.profile_image_url" class="student-sheet__photo" :src="student.profile_image_url" alt="Profile photo" />
              <template v-else>—</template>
            </dd>
          </div>
        </dl>
      </section>

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
            <input v-model="personalForm.email" class="student-sheet__input app-input" type="email" required />
          </label>
          <label class="student-sheet__item">
            <span class="student-sheet__label">Country</span>
            <AppSelect
              v-model="personalForm.countryId"
              class="student-sheet__input app-input"
              :options="countryOptions"
              @change="personalForm.stateId = null"
            />
          </label>
          <label class="student-sheet__item">
            <span class="student-sheet__label">State</span>
            <AppSelect
              v-model="personalForm.stateId"
              class="student-sheet__input app-input"
              :options="regionOptions"
              :required="inAustralia"
              placeholder="Choose a state"
              data-test="student-sheet-region"
            />
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
              <dt>State</dt>
              <dd>{{ display(student.state_name) }}</dd>
            </div>
          </template>
          <div class="student-sheet__item">
            <dt>Role</dt>
            <dd>Student</dd>
          </div>
          <!-- When they agreed to the policies, registering themselves. -->
          <div class="student-sheet__item" data-test="student-sheet-policies">
            <dt>Policies</dt>
            <dd>{{ student.policies_agreed_at ? answeredAt('Agreed', student.policies_agreed_at) : '—' }}</dd>
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
            <input v-model="detailsForm.firstName" class="student-sheet__input app-input" required maxlength="255" />
          </label>
          <label class="student-sheet__item">
            <span class="student-sheet__label">Last name</span>
            <input v-model="detailsForm.lastName" class="student-sheet__input app-input" required maxlength="255" />
          </label>
          <label class="student-sheet__item">
            <span class="student-sheet__label">School</span>
            <input v-model="detailsForm.school" class="student-sheet__input app-input" required maxlength="255" />
          </label>
          <label class="student-sheet__item">
            <span class="student-sheet__label">Year Level</span>
            <AppSelect v-model="detailsForm.yearLevel" class="student-sheet__input app-input" :options="YEAR_OPTIONS" required />
          </label>
          <fieldset class="student-sheet__item student-sheet__interest-options">
            <legend class="student-sheet__label">Interests</legend>
            <label v-for="interest in interestChoices" :key="interest">
              <input v-model="detailsForm.interests" type="checkbox" :value="interest" />
              {{ interest }}
            </label>
          </fieldset>
          <label class="student-sheet__item">
            <span class="student-sheet__label">Pronouns</span>
            <AppSelect
              v-model="detailsForm.pronounsChoice"
              class="student-sheet__input app-input"
              data-test="student-sheet-pronouns"
              :options="PRONOUN_SELECT_OPTIONS"
              :searchable="false"
            />
          </label>
          <label v-if="detailsForm.pronounsChoice === 'Other'" class="student-sheet__item">
            <span class="student-sheet__label">Their pronouns</span>
            <input
              v-model="detailsForm.pronounsOther"
              class="student-sheet__input app-input"
              data-test="student-sheet-pronouns-other"
              maxlength="100"
            />
          </label>
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
            <dt>Interests</dt>
            <dd>{{ student.interests.length ? student.interests.join(', ') : '—' }}</dd>
          </div>
          <div class="student-sheet__item" data-test="student-sheet-pronouns-view">
            <dt>Pronouns</dt>
            <dd>{{ display(student.pronouns) }}</dd>
          </div>
        </dl>
      </section>

      <section ref="guardianSection" class="student-sheet__section">
        <div class="student-sheet__heading">
          <h3>Guardian Details</h3>
          <!-- Once permission is given, a warning first: a new guardian clears it. -->
          <button
            v-if="!editing"
            type="button"
            class="btn btn-outline btn-sm"
            @click="editGuardianDetails"
          >
            Edit
          </button>
        </div>
        <ConfirmDialog
          v-model="guardianWarningOpen"
          title="Change the guardian's details?"
          :message="guardianWarning"
          confirm-label="Continue"
          variant="warning"
          data-test="student-sheet-guardian-warning"
          @confirm="startEditing"
        />
        <p v-if="savedMessage" class="student-sheet__saved">{{ savedMessage }}</p>
        <!-- Editing turns Name and Email into the form; Permission and Media
             Consent stay below it. -->
        <form v-if="editing" id="student-sheet-guardian" @submit.prevent="saveGuardian">
          <label class="student-sheet__item">
            <span class="student-sheet__label">First name</span>
            <input v-model="guardianForm.firstName" class="student-sheet__input app-input" required />
          </label>
          <label class="student-sheet__item">
            <span class="student-sheet__label">Last name</span>
            <input v-model="guardianForm.lastName" class="student-sheet__input app-input" required />
          </label>
          <label class="student-sheet__item">
            <span class="student-sheet__label">Email</span>
            <input v-model="guardianForm.email" class="student-sheet__input app-input" type="email" />
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
import AppSelect, { type AppSelectOption } from '@/components/AppSelect.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import { useFlashMessage } from '@/composables/useFlashMessage'
import { formatShortDateTime } from '@/utils/date'
import { DEFAULT_GROUP_INTERESTS } from '@/utils/supervisedGroups'
import { PRONOUN_SELECT_OPTIONS, pronounDraft, pronounsToSave } from '@/utils/pronouns'
import { PROFILE_PHOTO_ACCEPT, PROFILE_PHOTO_PROBLEM, isProfilePhoto } from '@/utils/profilePhoto'
import {
  fetchStudentEditOptions,
  fullName,
  removeSupervisedStudentPhoto,
  saveGuardianDetails,
  updateSupervisedStudentProfile,
  uploadSupervisedStudentPhoto,
  type StudentEditOptions,
  type SupervisedStudent,
} from '@/utils/supervisedStudents'

const props = defineProps<{
  /** The student to show; the panel is open while there is one. */
  student: SupervisedStudent | null
  /** Open at the guardian form, already open (Enter Guardian Details). */
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

// --- Profile Photo: a new one, or none, saved with Save ----------------------
const photoEditing = ref(false)
const photoSaving = ref(false)
const photoError = ref('')
const photoFile = ref<File | null>(null)
const photoPreview = ref('')
const photoRemoved = ref(false)
// What Save would leave: the chosen photo, none, or the one they have.
const photoShown = computed(() =>
  photoRemoved.value ? '' : photoPreview.value || props.student?.profile_image_url || '',
)

function clearPhotoDraft() {
  if (photoPreview.value) URL.revokeObjectURL(photoPreview.value)
  photoFile.value = null
  photoPreview.value = ''
  photoRemoved.value = false
}

const startPhotoEdit = () => {
  clearPhotoDraft()
  photoError.value = ''
  photoEditing.value = true
}

const cancelPhotoEdit = () => {
  clearPhotoDraft()
  photoError.value = ''
  photoEditing.value = false
}

const choosePhoto = (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  // So choosing the same file again still counts.
  input.value = ''
  if (!file) return
  if (!isProfilePhoto(file)) {
    photoError.value = PROFILE_PHOTO_PROBLEM
    return
  }
  clearPhotoDraft()
  photoError.value = ''
  photoFile.value = file
  photoPreview.value = URL.createObjectURL(file)
}

const removePhotoDraft = () => {
  clearPhotoDraft()
  photoRemoved.value = true
}

const savePhoto = async () => {
  if (!props.student || photoSaving.value) return
  if (!photoFile.value && !photoRemoved.value) {
    cancelPhotoEdit()
    return
  }
  photoSaving.value = true
  photoError.value = ''
  try {
    const updated = photoFile.value
      ? await uploadSupervisedStudentPhoto(props.student.id, photoFile.value)
      : await removeSupervisedStudentPhoto(props.student.id)
    cancelPhotoEdit()
    emit('updated', updated)
  } catch (error) {
    photoError.value = error instanceof Error ? error.message : 'The photo could not be saved.'
  } finally {
    photoSaving.value = false
  }
}

// Scrolled to the top of the panel when opened to edit the guardian.
const guardianSection = ref<HTMLElement | null>(null)
watch(
  () => [props.student?.id, props.editGuardian],
  async () => {
    if (!props.student || !props.editGuardian) return
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

// An answer and when it was given: "Yes, 14/10/26 21:30".
const answeredAt = (answer: string, at: string | null | undefined) =>
  [answer, formatShortDateTime(at)].filter(Boolean).join(', ')

// Only a given permission is recorded; a guardian never answers no.
const permission = computed(() =>
  props.student?.has_join_permission ? answeredAt('Yes', props.student.joinperm_granted_at) : '—',
)

// From the signed form; consent marked received without one has no answer.
const mediaConsent = computed(() => {
  const answer = props.student?.media_consent
  if (answer == null) return '—'
  return answeredAt(answer ? 'Yes' : 'No', props.student?.media_consent_at)
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

// Once their guardian has given permission, a warning before the form: a new
// guardian clears it, as on the student's own profile.
const guardianWarningOpen = ref(false)
const guardianWarning = computed(() => {
  const name = props.student?.first_name || 'this student'
  return (
    `${guardianName.value} has given permission for ${name}. Changing the guardian's details clears it, ` +
    `and the new guardian will be sent the consent form. Until they complete it, ${name} won't be fully registered.`
  )
})
const editGuardianDetails = () => {
  if (props.student?.has_join_permission) guardianWarningOpen.value = true
  else startEditing()
}

// Student Details' Edit: name, school, year and interests.
const YEAR_OPTIONS: AppSelectOption[] = ['9', '10', '11', '12'].map((year) => ({ value: year, label: year }))
const detailsEditing = ref(false)
const detailsSaving = ref(false)
const detailsError = ref('')
const detailsForm = ref({
  firstName: '',
  lastName: '',
  school: '',
  yearLevel: '',
  interests: [] as string[],
  pronounsChoice: '' as AppSelectOption['value'],
  pronounsOther: '',
})
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
    // Their own words, not a listed choice, come back under Other.
    pronounsChoice: pronounDraft(props.student.pronouns).choice,
    pronounsOther: pronounDraft(props.student.pronouns).other,
  }
  detailsError.value = ''
  detailsEditing.value = true
  await loadEditOptions()
}

const saveDetails = async () => {
  if (!props.student) return
  const pronouns = pronounsToSave({
    choice: String(detailsForm.value.pronounsChoice ?? ''),
    other: detailsForm.value.pronounsOther,
  })
  if (pronouns === null) {
    detailsError.value = 'Enter their pronouns.'
    return
  }
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
      pronouns,
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

// Country and Region's choices, after "Not set".
const countryOptions = computed<AppSelectOption[]>(() => [
  { value: null, label: 'Not set' },
  ...editOptions.value.countries.map((country) => ({ value: country.id, label: country.country_name })),
])
// In Australia a state is needed, as registering asks, so no "Not set".
const inAustralia = computed(
  () =>
    editOptions.value.countries.find((country) => country.id === personalForm.value.countryId)?.country_name ===
    'Australia',
)
const regionOptions = computed<AppSelectOption[]>(() => [
  ...(inAustralia.value ? [] : [{ value: null, label: 'Not set' }]),
  ...regionChoices.value.map((region) => ({ value: region.id, label: region.state_name })),
])

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
  if (inAustralia.value && !personalForm.value.stateId) {
    personalError.value = 'Choose their state or territory.'
    return
  }
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
      // Warned first (editGuardianDetails): their permission is cleared.
      clear_permission: Boolean(props.student.has_join_permission),
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
/* The photo as the student's dashboard shows it: round, filling its circle. */
.student-sheet__photo {
  display: block;
  width: 104px;
  height: 104px;
  border-radius: 50%;
  object-fit: cover;
  object-position: center;
  border: 1px solid var(--border-light);
}

.student-sheet__item.student-sheet__photo-row {
  align-items: center;
}

.student-sheet__photo-edit {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

/* Choose photo is a label (for its file box), which would take the page's
   taller line; both buttons take the button's, so they match. */
.student-sheet__photo-edit .btn {
  margin: 0;
  font-family: inherit;
  line-height: normal;
  cursor: pointer;
}

.student-sheet__photo-note {
  margin: 0.4rem 0 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

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

/* The shared box (app-input), growing beside its label. */
.student-sheet__input {
  flex: 1;
}

/* A box beside its label is as wide as every other, whatever its label:
   --app-input-panel-width, or less when the row leaves its label under 6rem
   (a longer label wraps). A searchable dropdown doesn't widen it for its
   search text. */
.student-sheet__item > .student-sheet__input.app-input:not(.app-input--wide) {
  flex: 0 0 min(var(--app-input-panel-width), 100% - 6rem);
  min-width: 0;
}

.student-sheet__item:has(> .app-input:not(.app-input--wide)) > .student-sheet__label {
  flex-shrink: 1;
  min-width: 0;
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

.student-sheet__item dd {
  margin: 0;
  color: var(--teal);
  text-align: right;
  overflow-wrap: anywhere;
}
</style>
