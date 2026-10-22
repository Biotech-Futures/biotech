<template>
  <div class="content-area">
    <div v-if="error" class="card" style="margin-bottom:1rem;border-left:4px solid var(--danger);">
      <p style="margin:0;color:#6c757d;">{{ error }}</p>
    </div>
    <Transition name="status-fade">
      <div v-if="statusMessage" class="card status-card">
        <p>{{ statusMessage }}</p>
      </div>
    </Transition>

    <div v-if="loading" class="profile-loading" role="status" aria-live="polite">
      <span class="sr-only">Loading your profile...</span>
      <div class="profile-loading-header">
        <div class="profile-loading-avatar skeleton-block"></div>
        <div class="profile-loading-title skeleton-block"></div>
        <div class="profile-loading-subtitle skeleton-block"></div>
      </div>
      <div class="profile-loading-content">
        <section
          v-for="section in 3"
          :key="`profile-loading-section-${section}`"
          class="profile-loading-section"
        >
          <div class="profile-loading-heading skeleton-block"></div>
          <div
            v-for="row in 4"
            :key="`profile-loading-row-${section}-${row}`"
            class="profile-loading-row"
          >
            <div class="profile-loading-label skeleton-block"></div>
            <div class="profile-loading-value skeleton-block"></div>
          </div>
        </section>
      </div>
    </div>

    <div v-else-if="auth.user" class="card" style="overflow:hidden;padding:0;">
      <div class="profile-header">
        <div class="profile-avatar-wrap">
          <img v-if="avatarUrl" class="profile-avatar-large" :src="avatarUrl" :alt="`${user.name}'s profile picture`" @error="avatarUrl = ''" />
          <div v-else class="profile-avatar-large profile-avatar-initials" :aria-label="user.name">{{ getInitials(user.name) }}</div>
          <label class="avatar-change" for="profile-avatar">Change photo</label>
          <input id="profile-avatar" class="sr-only" type="file" accept="image/png,image/jpeg,image/webp" @change="selectAvatar" />
        </div>
        <h2 class="profile-name">{{ user.name }}</h2>
        <p class="profile-role">{{ capitalise(user.role) }} | {{ user.country }}</p>
      </div>

      <div class="profile-content">
        <div class="profile-section">
          <div class="profile-section-heading">
            <h3 class="profile-section-title">Personal Information</h3>
            <!-- A supervisor can change their own name, and nothing else here. -->
            <button
              v-if="auth.isSupervisor && !nameEditing"
              class="btn btn-outline profile-edit-button"
              type="button"
              @click="startNameEdit"
            >
              Edit
            </button>
            <!-- A mentor or admin changes their country and state here. -->
            <button
              v-if="(auth.isMentor || auth.isAdmin) && !mentorPlaceEditing"
              class="btn btn-outline profile-edit-button"
              type="button"
              data-test="mentor-place-edit"
              @click="startMentorPlaceEdit"
            >
              Edit
            </button>
            <!-- A student changes their country and region here. -->
            <button
              v-if="canEditStudentDetails && !placeEditing"
              class="btn btn-outline profile-edit-button"
              type="button"
              data-test="place-edit"
              @click="startPlaceEdit"
            >
              Edit
            </button>
          </div>
          <form v-if="mentorPlaceEditing" class="student-edit-form" data-test="mentor-place-form" @submit.prevent="saveMentorPlace">
            <label v-if="auth.isAdmin" class="student-edit-form__wide">Email<input v-model.trim="mentorPlace.email" class="app-input" type="email" maxlength="254" data-test="admin-email" /></label>
            <label>Country<AppSelect v-model="mentorPlace.country" class="app-input" :options="mentorCountryOptions" placeholder="Select a country" data-test="mentor-country" @change="mentorPlace.state = ''" /></label>
            <label>State
              <AppSelect v-if="mentorStateOptions.length" v-model="mentorPlace.state" class="app-input" :options="mentorStateOptions" placeholder="Choose a state" data-test="mentor-state" />
              <input v-else v-model.trim="mentorPlace.state" class="app-input" maxlength="255" data-test="mentor-state-name" />
            </label>
            <label v-if="auth.isAdmin">Status<AppSelect v-model="mentorPlace.status" class="app-input" :options="ADMIN_STATUS_OPTIONS" :searchable="false" data-test="admin-status" /></label>
            <p v-if="auth.isAdmin && mentorPlace.status === 'inactive'" class="profile-note student-edit-form__wide">
              Inactive, you won't be able to sign in until another admin makes you Active again.
            </p>
            <div class="student-edit-actions">
              <button class="btn btn-outline" type="button" :disabled="mentorSaving" @click="mentorPlaceEditing = false">Cancel</button>
              <button class="btn btn-primary" type="submit" :disabled="mentorSaving">{{ mentorSaving ? 'Saving…' : 'Save' }}</button>
            </div>
          </form>
          <form v-if="placeEditing" class="student-edit-form" data-test="place-edit-form" @submit.prevent="savePlace">
            <label>Country<AppSelect v-model="placeDraft.country_id" class="app-input" :options="countrySelectOptions" @change="placeDraft.state_id = null" /></label>
            <label>State<AppSelect v-model="placeDraft.state_id" class="app-input" :options="regionSelectOptions" :required="draftInAustralia" placeholder="Choose a state" data-test="student-region" /></label>
            <div class="student-edit-actions">
              <button class="btn btn-outline" type="button" :disabled="placeSaving" @click="placeEditing = false">Cancel</button>
              <button class="btn btn-primary" type="submit" :disabled="placeSaving">{{ placeSaving ? 'Saving…' : 'Save' }}</button>
            </div>
          </form>
          <form v-if="nameEditing" class="student-edit-form" @submit.prevent="saveName">
            <label>First name<input v-model.trim="nameDraft.first_name" class="app-input" required maxlength="255" /></label>
            <label>Last name<input v-model.trim="nameDraft.last_name" class="app-input" required maxlength="255" /></label>
            <label>Pronouns<AppSelect v-model="supervisorPronouns.choice" class="app-input" :options="pronounSelectOptions" data-test="supervisor-pronouns-select" /></label>
            <label v-if="supervisorPronouns.choice === 'Other'">Your pronouns<input v-model="supervisorPronouns.other" class="app-input" maxlength="100" data-test="supervisor-pronouns-other" /></label>
            <div class="student-edit-actions">
              <button class="btn btn-outline" type="button" :disabled="nameSaving" @click="nameEditing = false">Cancel</button>
              <button class="btn btn-primary" type="submit" :disabled="nameSaving">{{ nameSaving ? 'Saving…' : 'Save' }}</button>
            </div>
          </form>
          <div v-if="!(auth.isAdmin && mentorPlaceEditing)" class="profile-field">
            <span class="profile-field-label">Email:</span>
            <span class="profile-field-value">{{ user.email }}</span>
          </div>
          <!-- Not while being edited just above. -->
          <template v-if="!placeEditing && !mentorPlaceEditing">
            <div class="profile-field">
              <span class="profile-field-label">Country:</span>
              <span class="profile-field-value">{{ user.country }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">State:</span>
              <span class="profile-field-value">{{ user.region }}</span>
            </div>
          </template>
          <div class="profile-field">
            <span class="profile-field-label">Role:</span>
            <span class="profile-field-value">{{ capitalise(user.role) }}</span>
          </div>
          <div v-if="!(auth.isAdmin && mentorPlaceEditing)" class="profile-field">
            <span class="profile-field-label">Account Status:</span>
            <span class="profile-field-value">{{ capitalise(user.accountStatus) }}</span>
          </div>
        </div>

        <div class="profile-section">
          <h3 class="profile-section-title">Timezone</h3>
          <div class="profile-field">
            <span class="profile-field-label">Current timezone:</span>
            <span class="profile-field-value">{{ formatTimeZoneLabel(auth.timeZone) }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">This device:</span>
            <span class="profile-field-value">{{ formatTimeZoneLabel(browserTimeZone) }}</span>
          </div>
          <div class="profile-field timezone-field">
            <label class="profile-field-label" for="timezone-input">Set timezone:</label>
            <div class="timezone-control">
              <AppSelect
                id="timezone-input"
                v-model="selectedTimeZone"
                class="timezone-input app-input"
                :options="timeZoneSelectOptions"
              />
              <div class="timezone-actions">
                <button
                  class="btn btn-outline"
                  type="button"
                  @click="useBrowserTimeZone"
                >
                  Use device timezone
                </button>
                <button
                  class="btn btn-primary"
                  type="button"
                  :disabled="timezoneSaving || !timezoneChanged"
                  @click="saveTimeZone"
                >
                  {{ timezoneSaving ? 'Saving...' : 'Save timezone' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="user.student.hasDetails" class="profile-section">
          <div class="profile-section-heading">
            <h3 class="profile-section-title">Student Details <span v-if="detailsLocked" class="registration-lock" role="img" :aria-label="lockReason" :data-tooltip="lockReason" data-test="details-lock"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg></span></h3>
            <button v-if="canEditStudentDetails && !studentEditing" class="btn btn-outline profile-edit-button" type="button" data-test="student-details-edit" @click="startStudentEdit">Edit</button>
          </div>
          <form v-if="studentEditing" class="student-edit-form" @submit.prevent="saveStudentDetails">
            <label>First name<input v-model.trim="studentDraft.first_name" class="app-input" required maxlength="255" /></label>
            <label>Last name<input v-model.trim="studentDraft.last_name" class="app-input" required maxlength="255" /></label>
            <label>School<input v-model.trim="studentDraft.school_name" class="app-input" required maxlength="255" /></label>
            <label>Year level<AppSelect v-model="studentDraft.year_lvl" class="app-input" :options="YEAR_LEVEL_OPTIONS" required /></label>
            <fieldset class="interest-options"><legend>Areas of Interest</legend><label v-for="interest in profileOptions.interests" :key="interest.id"><input v-model="studentDraft.interest_ids" type="checkbox" :value="interest.id" /><span>{{ interest.interest_desc }}</span></label><p v-if="!profileOptions.interests.length">No interests are available yet.</p></fieldset>
            <label>Pronouns<AppSelect v-model="pronounsDraft.choice" class="app-input" :options="pronounSelectOptions" data-test="student-pronouns-select" /></label>
            <label v-if="pronounsDraft.choice === 'Other'">Your pronouns<input v-model="pronounsDraft.other" class="app-input" maxlength="100" data-test="student-pronouns-other" /></label>
            <p class="profile-note">Use the Guardian Details section below to update your guardian.</p>
            <div class="student-edit-actions"><button class="btn btn-outline" type="button" :disabled="studentSaving" @click="cancelStudentEdit">Cancel</button><button class="btn btn-primary" type="submit" :disabled="studentSaving">{{ studentSaving ? 'Saving…' : 'Save Details' }}</button></div>
          </form>
          <template v-else>
          <div class="profile-field"><span class="profile-field-label">Name:</span><span class="profile-field-value">{{ user.name }}</span></div>
          <div class="profile-field">
            <span class="profile-field-label">School:</span>
            <span class="profile-field-value">{{ user.student.schoolName }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Year Level:</span>
            <span class="profile-field-value">{{ user.student.yearLevel }}</span>
          </div>
          <div class="profile-field" data-test="student-interests">
            <span class="profile-field-label">Areas of Interest:</span>
            <span class="profile-field-value">
              {{ user.student.interests.length ? user.student.interests.join(', ') : unsetLabel }}
            </span>
          </div>
          <div class="profile-field" data-test="student-pronouns">
            <span class="profile-field-label">Pronouns:</span>
            <span class="profile-field-value">{{ user.student.pronouns }}</span>
          </div>
          </template>
        </div>

        <!-- Their supervisor, apart from their own details. -->
        <div v-if="user.student.hasDetails" class="profile-section" data-test="student-supervisor">
          <h3 class="profile-section-title">Supervisor Details</h3>
          <div class="profile-field">
            <span class="profile-field-label">Supervisor:</span>
            <span class="profile-field-value">{{ user.student.supervisorName }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Supervisor Email:</span>
            <span class="profile-field-value">
              <a
                v-if="user.student.supervisorEmailAddress"
                class="profile-link"
                :href="`mailto:${user.student.supervisorEmailAddress}`"
              >
                {{ user.student.supervisorEmailAddress }}
              </a>
              <span v-else>{{ user.student.supervisorEmail }}</span>
            </span>
          </div>
        </div>

        <div v-if="user.student.hasDetails && !studentEditing" class="profile-section">
          <h3 class="profile-section-title">Team members</h3>
          <p v-if="teamLoading" class="profile-note">Loading your team…</p>
          <p v-else-if="teamError" class="profile-note">{{ teamError }}</p>
          <template v-else-if="teamMembers.length">
            <p class="profile-note">{{ teamName }}</p>
            <AppSimpleTable class="team-table" :columns="teamColumns" :rows="teamRows" />
          </template>
          <p v-else class="profile-note">You have not been assigned to a team yet.</p>
        </div>

        <div v-if="user.guardian.hasDetails" class="profile-section" data-test="guardian-details">
          <div class="guardian-heading">
            <h3 class="profile-section-title">Guardian Details <span v-if="guardianLocked" class="registration-lock" role="img" :aria-label="GUARDIAN_LOCK_REASON" :data-tooltip="GUARDIAN_LOCK_REASON" data-test="guardian-lock"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg></span></h3>
            <button
              v-if="!guardianEditing && !guardianLocked"
              class="btn btn-outline profile-edit-button"
              type="button"
              data-test="guardian-edit"
              @click="guardianWarningOpen = true"
            >
              Edit
            </button>
          </div>

          <!-- Locked once their guardian has given permission: changes go through support. -->
          <p v-if="guardianLocked" class="profile-note guardian-locked-note" data-test="guardian-locked">
            Your guardian has given permission, so their details can't be changed here. If they need to
            change, contact <a :href="`mailto:${SUPPORT_EMAIL}`">BIOTech Support</a>.
          </p>

          <!-- A warning before editing: a new guardian clears permission given. -->
          <ConfirmDialog
            v-model="guardianWarningOpen"
            title="Change your guardian's details?"
            :message="guardianWarning"
            confirm-label="Continue"
            variant="warning"
            data-test="guardian-warning"
            @confirm="startGuardianEdit"
          />

          <form
            v-if="guardianEditing"
            class="guardian-form"
            data-test="guardian-form"
            novalidate
            @submit.prevent="saveGuardian"
          >
            <p v-if="user.guardian.consentReceived" class="consent-hint guardian-form-hint">
              Saving a new guardian clears the permission {{ user.guardian.consentingName }} gave,
              until your new guardian completes the consent form.
            </p>
            <div class="profile-field guardian-form-field">
              <label class="profile-field-label" for="guardian-first-name">First name:</label>
              <div class="guardian-input-wrap">
                <input
                  id="guardian-first-name"
                  v-model.trim="guardianForm.first_name"
                  class="guardian-input app-input"
                  type="text"
                  autocomplete="off"
                  required
                >
                <span v-if="guardianErrors.first_name" class="guardian-error">{{ guardianErrors.first_name }}</span>
              </div>
            </div>
            <div class="profile-field guardian-form-field">
              <label class="profile-field-label" for="guardian-last-name">Last name:</label>
              <div class="guardian-input-wrap">
                <input
                  id="guardian-last-name"
                  v-model.trim="guardianForm.last_name"
                  class="guardian-input app-input"
                  type="text"
                  autocomplete="off"
                  required
                >
                <span v-if="guardianErrors.last_name" class="guardian-error">{{ guardianErrors.last_name }}</span>
              </div>
            </div>
            <div class="profile-field guardian-form-field">
              <label class="profile-field-label" for="guardian-email">Email:</label>
              <div class="guardian-input-wrap">
                <input
                  id="guardian-email"
                  v-model.trim="guardianForm.email"
                  class="guardian-input app-input"
                  type="email"
                  autocomplete="off"
                  required
                >
                <span v-if="guardianErrors.email" class="guardian-error">{{ guardianErrors.email }}</span>
              </div>
            </div>
            <div class="guardian-actions">
              <button class="btn btn-outline" type="button" :disabled="guardianSaving" @click="cancelGuardianEdit">
                Cancel
              </button>
              <button class="btn btn-primary" type="submit" :disabled="guardianSaving" data-test="guardian-save">
                {{ guardianSaving ? 'Saving...' : 'Save guardian' }}
              </button>
            </div>
          </form>

          <div v-if="user.guardian.pending && !guardianEditing" class="guardian-pending" data-test="guardian-pending">
            <p>
              <strong>Change requested:</strong>
              {{ user.guardian.pending.name }} ({{ user.guardian.pending.email }}).
              Waiting for their consent — until then {{ user.guardian.consentingName }} stays on file.
            </p>
            <p data-test="guardian-pending-permission">
              <strong>Their permission:</strong> not received,
              <button
                v-if="guardianSend.canSend"
                type="button"
                class="consent-send-link"
                data-test="guardian-send"
                :disabled="guardianSending"
                @click="sendGuardianInvitation"
              >
                {{ guardianSending ? 'sending…' : 'click here to send email' }}
              </button>
              <span v-else data-test="guardian-send-blocked">{{ guardianSend.reason }}</span>
              <span v-if="reminderLine" class="consent-hint" data-test="guardian-reminders">{{ reminderLine }}</span>
            </p>
            <button
              class="btn btn-outline"
              type="button"
              :disabled="guardianSaving"
              data-test="guardian-withdraw"
              @click="withdrawGuardianChange"
            >
              {{ guardianSaving ? 'Withdrawing...' : 'Withdraw change' }}
            </button>
          </div>

          <div class="profile-field">
            <span class="profile-field-label">Name:</span>
            <span class="profile-field-value" data-test="guardian-name">{{ user.guardian.name }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Email:</span>
            <span class="profile-field-value" data-test="guardian-email">
              <a
                v-if="user.guardian.emailAddress"
                class="profile-link"
                :href="`mailto:${user.guardian.emailAddress}`"
              >
                {{ user.guardian.emailAddress }}
              </a>
              <span v-else>{{ unsetLabel }}</span>
            </span>
          </div>
          <!-- As slide 14 has it: "Received DD MMM YYYY HH:mm" or "Not received, click here to send email". -->
          <div class="profile-field consent-field">
            <span class="profile-field-label">Permission:</span>
            <span class="profile-field-value">
              <span data-test="guardian-consent">
                <template v-if="user.guardian.consentReceived">
                  <span class="permission-status received">Received</span>
                  {{ user.guardian.consentReceivedAt }}
                </template>
                <template v-else>
                  <span class="permission-status">Not received</span>,
                  <button
                    v-if="guardianSend.canSend"
                    type="button"
                    class="consent-send-link"
                    data-test="guardian-send"
                    :disabled="guardianSending"
                    @click="sendGuardianInvitation"
                  >
                    {{ guardianSending ? 'sending…' : 'click here to send email' }}
                  </button>
                  <span v-else data-test="guardian-send-blocked">{{ guardianSend.reason }}</span>
                </template>
              </span>
              <span v-if="reminderLine && !user.guardian.pending" class="consent-hint" data-test="guardian-reminders">
                {{ reminderLine }}
              </span>
            </span>
          </div>

          <!-- What a guardian action did, at the bottom of the section it's about. -->
          <p
            v-if="guardianNotice"
            class="guardian-notice"
            :class="guardianNotice.ok ? 'guardian-notice--ok' : 'guardian-notice--error'"
            :role="guardianNotice.ok ? 'status' : 'alert'"
            data-test="guardian-notice"
          >
            {{ guardianNotice.text }}
          </p>
        </div>

        <!-- A mentor's own parts, as their admin panel has them (not their
             application's answers): their details, weekly times and groups. -->
        <template v-if="user.mentor.hasDetails">
          <div class="profile-section" data-test="mentor-details">
            <div class="profile-section-heading">
              <h3 class="profile-section-title">Mentor Details</h3>
              <button
                v-if="!mentorDetailsEditing"
                class="btn btn-outline profile-edit-button"
                type="button"
                data-test="mentor-details-edit"
                @click="startMentorDetailsEdit"
              >
                Edit
              </button>
            </div>
            <form v-if="mentorDetailsEditing" class="student-edit-form" data-test="mentor-details-form" @submit.prevent="saveMentorDetails">
              <label>First name<input v-model.trim="mentorDraft.firstName" class="app-input" maxlength="150" data-test="mentor-first-name" /></label>
              <label>Last name<input v-model.trim="mentorDraft.lastName" class="app-input" maxlength="150" data-test="mentor-last-name" /></label>
              <label>Pronouns<AppSelect v-model="mentorPronouns.choice" class="app-input" :options="pronounSelectOptions" data-test="mentor-pronouns" /></label>
              <label v-if="mentorPronouns.choice === 'Other'">Your pronouns<input v-model="mentorPronouns.other" class="app-input" maxlength="100" /></label>
              <label>Background<AppSelect v-model="mentorDraft.background" class="app-input" :options="mentorBackgroundOptions" :searchable="false" placeholder="Choose a background" data-test="mentor-background" /></label>
              <label v-if="mentorDraft.background === 'industry'">Company<input v-model.trim="mentorDraft.company" class="app-input" maxlength="255" data-test="mentor-company" /></label>
              <label v-else>Institution<AppSuggestInput v-model="mentorDraft.institution" class="app-input" :suggestions="universityNames" maxlength="255" data-test="mentor-institution" /></label>
              <label v-if="mentorDraftStudying">Year of study<AppSelect v-model="mentorDraft.universityYear" class="app-input" :options="STUDY_YEAR_OPTIONS" :searchable="false" placeholder="Choose a year" /></label>
              <label v-if="mentorDraft.background !== 'industry'">Field of study<input v-model.trim="mentorDraft.fieldOfStudy" class="app-input" maxlength="255" /></label>
              <fieldset class="interest-options"><legend>Expertise</legend><label v-for="interest in mentorInterestChoices" :key="interest"><input v-model="mentorDraft.interests" type="checkbox" :value="interest" /><span>{{ interest }}</span></label></fieldset>
              <label>Capacity<AppSelect v-model="mentorDraft.capacity" class="app-input" :options="mentorCapacityOptions" :searchable="false" placeholder="Choose a capacity" /></label>
              <label>Hours per week<input class="app-input" :value="mentorDraft.weeklyHours" type="number" inputmode="numeric" min="1" :max="MAX_WEEKLY_HOURS" data-test="mentor-hours" @input="onMentorHoursInput" @keydown="refuseNonDigitKey" @paste="refuseNonDigitPaste" /></label>
              <div class="student-edit-actions">
                <button class="btn btn-outline" type="button" :disabled="mentorSaving" @click="mentorDetailsEditing = false">Cancel</button>
                <button class="btn btn-primary" type="submit" :disabled="mentorSaving">{{ mentorSaving ? 'Saving…' : 'Save' }}</button>
              </div>
            </form>
            <template v-else>
            <div class="profile-field" data-test="mentor-name">
              <span class="profile-field-label">Name:</span>
              <span class="profile-field-value">{{ user.name }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Pronouns:</span>
              <span class="profile-field-value">{{ user.mentor.pronouns }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Background:</span>
              <span class="profile-field-value">{{ user.mentor.background }}</span>
            </div>
            <div v-if="user.mentor.industry" class="profile-field">
              <span class="profile-field-label">Company:</span>
              <span class="profile-field-value">{{ user.mentor.company }}</span>
            </div>
            <div v-else class="profile-field">
              <span class="profile-field-label">Institution:</span>
              <span class="profile-field-value">{{ user.mentor.institution }}</span>
            </div>
            <div v-if="user.mentor.studying" class="profile-field">
              <span class="profile-field-label">Year of study:</span>
              <span class="profile-field-value">{{ user.mentor.studyYear }}</span>
            </div>
            <div v-if="!user.mentor.industry" class="profile-field">
              <span class="profile-field-label">Field of study:</span>
              <span class="profile-field-value">{{ user.mentor.fieldOfStudy }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Expertise:</span>
              <span class="profile-field-value">{{ user.mentor.interests }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Capacity:</span>
              <span class="profile-field-value">{{ user.mentor.capacity }}</span>
            </div>
            <div class="profile-field">
              <span class="profile-field-label">Hours per week:</span>
              <span class="profile-field-value">{{ user.mentor.weeklyHours }}</span>
            </div>
            </template>
          </div>

          <div class="profile-section" data-test="mentor-availability">
            <div class="profile-section-heading">
              <h3 class="profile-section-title">Weekly Availability</h3>
              <button
                v-if="!availabilityEditing"
                class="btn btn-outline profile-edit-button"
                type="button"
                data-test="mentor-availability-edit"
                @click="startAvailabilityEdit"
              >
                Edit
              </button>
            </div>
            <!-- When they're free each week: a day and its times, as many as they like. -->
            <form v-if="availabilityEditing" class="mentor-slots" data-test="mentor-availability-form" @submit.prevent="saveAvailability">
              <div v-for="(slot, index) in availabilityDraft" :key="index" class="mentor-slot" :data-test="`mentor-slot-${index}`">
                <AppSelect v-model="slot.weekday" class="mentor-slot__day" :aria-label="`Day ${index + 1}`" :options="WEEKDAY_OPTIONS" placeholder="Day" />
                <span class="mentor-slot__time">
                  <AppSelect :model-value="slot.startHour" class="mentor-slot__part" :aria-label="`From, hour, time ${index + 1}`" :options="HOUR_OPTIONS" :searchable="false" placeholder="--" @update:model-value="(value) => pickHour(slot, 'start', value)" />
                  <span class="mentor-slot__muted">:</span>
                  <AppSelect v-model="slot.startMinute" class="mentor-slot__part" :aria-label="`From, minutes, time ${index + 1}`" :options="minuteOptions(slot.startMinute)" :searchable="false" placeholder="--" />
                </span>
                <span class="mentor-slot__muted">to</span>
                <span class="mentor-slot__time">
                  <AppSelect :model-value="slot.endHour" class="mentor-slot__part" :aria-label="`To, hour, time ${index + 1}`" :options="HOUR_OPTIONS" :searchable="false" placeholder="--" @update:model-value="(value) => pickHour(slot, 'end', value)" />
                  <span class="mentor-slot__muted">:</span>
                  <AppSelect v-model="slot.endMinute" class="mentor-slot__part" :aria-label="`To, minutes, time ${index + 1}`" :options="minuteOptions(slot.endMinute)" :searchable="false" placeholder="--" />
                </span>
                <button type="button" class="mentor-slot__remove" :aria-label="`Remove time ${index + 1}`" @click="availabilityDraft.splice(index, 1)">
                  <i class="fas fa-xmark" aria-hidden="true"></i>
                </button>
              </div>
              <p v-if="!availabilityDraft.length" class="profile-field-value">No weekly times.</p>
              <button v-if="availabilityDraft.length < MAX_SLOTS" type="button" class="btn btn-outline profile-edit-button" data-test="mentor-add-slot" @click="availabilityDraft.push(blankSlot())">
                Add a time
              </button>
              <div class="student-edit-actions">
                <button class="btn btn-outline" type="button" :disabled="mentorSaving" @click="availabilityEditing = false">Cancel</button>
                <button class="btn btn-primary" type="submit" :disabled="mentorSaving">{{ mentorSaving ? 'Saving…' : 'Save' }}</button>
              </div>
            </form>
            <template v-else>
            <div v-for="slot in user.mentor.availability" :key="`${slot.weekday}-${slot.start}`" class="profile-field">
              <span class="profile-field-label">{{ WEEKDAYS[slot.weekday] }}:</span>
              <span class="profile-field-value">{{ slot.start }} to {{ slot.end }}</span>
            </div>
            <p v-if="!user.mentor.availability.length" class="profile-field-value">{{ unsetLabel }}</p>
            </template>
          </div>

          <div class="profile-section" data-test="mentor-groups">
            <h3 class="profile-section-title">Groups</h3>
            <div class="profile-field">
              <span class="profile-field-label">Groups:</span>
              <span class="profile-field-value">{{ user.mentor.groups }}</span>
            </div>
          </div>
        </template>

        <div v-if="user.supervisor.hasDetails" class="profile-section">
          <h3 class="profile-section-title">Supervisor Details</h3>
          <div class="profile-field">
            <span class="profile-field-label">School:</span>
            <span class="profile-field-value">{{ user.supervisor.schoolName }}</span>
          </div>
          <div class="profile-field" data-test="supervisor-pronouns">
            <span class="profile-field-label">Pronouns:</span>
            <span class="profile-field-value">{{ user.supervisor.pronouns }}</span>
          </div>
        </div>

        <!-- An admin's name and pronouns, as their admin panel's Admin Details. -->
        <div v-if="user.admin.hasDetails" class="profile-section" data-test="admin-details">
          <div class="profile-section-heading">
            <h3 class="profile-section-title">Admin Details</h3>
            <button
              v-if="!adminDetailsEditing"
              class="btn btn-outline profile-edit-button"
              type="button"
              data-test="admin-details-edit"
              @click="startAdminDetailsEdit"
            >
              Edit
            </button>
          </div>
          <form v-if="adminDetailsEditing" class="student-edit-form" data-test="admin-details-form" @submit.prevent="saveAdminDetails">
            <label>First name<input v-model.trim="adminDraft.firstName" class="app-input" required maxlength="150" data-test="admin-first-name" /></label>
            <label>Last name<input v-model.trim="adminDraft.lastName" class="app-input" required maxlength="150" data-test="admin-last-name" /></label>
            <label>Pronouns<AppSelect v-model="adminPronouns.choice" class="app-input" :options="pronounSelectOptions" data-test="admin-pronouns" /></label>
            <label v-if="adminPronouns.choice === 'Other'">Your pronouns<input v-model="adminPronouns.other" class="app-input" maxlength="100" /></label>
            <div class="student-edit-actions">
              <button class="btn btn-outline" type="button" :disabled="mentorSaving" @click="adminDetailsEditing = false">Cancel</button>
              <button class="btn btn-primary" type="submit" :disabled="mentorSaving">{{ mentorSaving ? 'Saving…' : 'Save' }}</button>
            </div>
          </form>
          <template v-else>
            <div class="profile-field" data-test="admin-name">
              <span class="profile-field-label">Name:</span>
              <span class="profile-field-value">{{ user.name }}</span>
            </div>
            <div class="profile-field" data-test="admin-pronouns-view">
              <span class="profile-field-label">Pronouns:</span>
              <span class="profile-field-value">{{ user.admin.pronouns }}</span>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { routeLocationKey } from 'vue-router'

import { buildSessionHeaders, ensureCsrfCookie } from '@/utils/csrf'
import { useAuthStore } from '@/stores/auth'
import { apiErrorFromResponse } from '@/utils/apiError'
import { isPlaceholderGuardian } from '@/utils/guardian'
import AppSimpleTable from '@/components/AppSimpleTable.vue'
import AppSelect from '@/components/AppSelect.vue'
import { PRONOUN_SELECT_OPTIONS as pronounSelectOptions, pronounDraft, pronounsToSave } from '@/utils/pronouns'
import {
  HOUR_OPTIONS,
  MAX_SLOTS,
  MAX_WEEKLY_HOURS,
  MENTOR_BACKGROUNDS,
  STUDY_YEAR_OPTIONS,
  WEEKDAYS,
  WEEKDAY_OPTIONS,
  availabilityTimes,
  blankSlot,
  capacityLabel,
  isStudyingBackground,
  mentorBackgroundCode,
  minuteOptions,
  pickHour,
  splitSlot,
} from '@/utils/mentorForm'
import { useCountryOptions, useStateOptions, useUniversityNames } from '@/registration/useLocationOptions'
import AppSuggestInput from '@/components/AppSuggestInput.vue'
import { INTEREST_CATEGORIES, isAustralia } from '@/registration/registration'
import { keptDigits, refuseNonDigitKey, refuseNonDigitPaste } from '@/utils/digitsOnly'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import { SUPPORT_EMAIL } from '@/constants/brand'
import {
  formatDayMonth,
  formatDayMonthTime,
  formatTimeZoneLabel,
  getBrowserTimeZone,
  getSetTimeZone,
  getTimeZoneDateParts,
  isValidTimeZone,
} from '@/utils/date'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const auth = useAuthStore()

const loading = ref(true)
const error = ref('')
const statusMessage = ref('')
const timezoneSaving = ref(false)
const studentSaving = ref(false)
const studentEditing = ref(false)
const studentDraft = ref({
  first_name: '',
  last_name: '',
  school_name: '',
  year_lvl: '9',
  pg_firstname: '',
  pg_lastname: '',
  pg_email: '',
  interest_ids: [],
})
// Their pronouns as registering asks: a listed choice, or Other with their own.
const pronounsDraft = ref({ choice: '', other: '' })
// A student's country and region, edited under Personal Information.
const placeEditing = ref(false)
const placeSaving = ref(false)
const placeDraft = ref({ country_id: null, state_id: null })
const profileOptions = ref({ countries: [], regions: [], interests: [], selected_interest_ids: [] })
const availableRegions = computed(() => profileOptions.value.regions.filter(region => region.country_id === placeDraft.value.country_id))
// The student details form's dropdown choices.
const YEAR_LEVEL_OPTIONS = ['9', '10', '11', '12'].map(year => ({ value: year, label: year }))
const countrySelectOptions = computed(() => [
  { value: null, label: 'Not set' },
  ...profileOptions.value.countries.map(country => ({ value: country.id, label: country.country_name })),
])
// In Australia a state is needed, as registering asks, so no "Not set".
const draftInAustralia = computed(() =>
  profileOptions.value.countries.find(country => country.id === placeDraft.value.country_id)?.country_name === 'Australia'
)
const regionSelectOptions = computed(() => [
  ...(draftInAustralia.value ? [] : [{ value: null, label: 'Not set' }]),
  ...availableRegions.value.map(region => ({ value: region.id, label: region.state_name })),
])
const guardianSending = ref(false)
// Ticks so "send again in N minutes" counts down.
const now = ref(Date.now())
let clock = null
onMounted(() => {
  clock = window.setInterval(() => { now.value = Date.now() }, 30000)
})
onUnmounted(() => window.clearInterval(clock))

// Messages about the guardian, shown at the bottom of Guardian Details: an
// error stays until the next guardian action, a confirmation fades.
const guardianNotice = ref(null)
let guardianNoticeTimer = null
const noteGuardian = (ok, text) => {
  window.clearTimeout(guardianNoticeTimer)
  guardianNotice.value = text ? { ok, text } : null
  if (ok && text) guardianNoticeTimer = window.setTimeout(() => { guardianNotice.value = null }, 5000)
}
onUnmounted(() => window.clearTimeout(guardianNoticeTimer))
// Matches the server's wait between two consent emails.
const RESEND_WAIT_MS = 10 * 60 * 1000
const browserTimeZone = getBrowserTimeZone()
const selectedTimeZone = ref('UTC')
const teamMembers = ref([])
const teamName = ref('')
const teamColumns = [
  { key: 'first_name', label: 'First name' },
  { key: 'last_name', label: 'Last name' },
  { key: 'year_level', label: 'Year level' },
  { key: 'school', label: 'School' },
  { key: 'supervisor', label: 'Supervisor' },
]
const teamLoading = ref(false)
const teamError = ref('')
const DEFAULT_PROFILE_AVATAR = ''
const avatarUrl = ref(DEFAULT_PROFILE_AVATAR)
const supportEmail = 'support@biotechfutures.org'
const unsetLabel = 'Not set'
const teamRows = computed(() =>
  teamMembers.value.map((member) => ({
    id: member.id,
    first_name: member.first_name || unsetLabel,
    last_name: member.last_name || unsetLabel,
    year_level: member.year_level || unsetLabel,
    school: member.school || unsetLabel,
    supervisor: member.supervisor || 'Not assigned',
  })),
)
let statusMessageTimer = null
const commonTimeZones = [
  'UTC',
  'Australia/Sydney',
  'Australia/Melbourne',
  'Australia/Brisbane',
  'Australia/Adelaide',
  'Australia/Darwin',
  'Australia/Perth',
  'Australia/Hobart',
  'Pacific/Auckland',
  'Pacific/Fiji',
  'Asia/Shanghai',
  'Asia/Hong_Kong',
  'Asia/Taipei',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Asia/Seoul',
  'Asia/Bangkok',
  'Asia/Jakarta',
  'Asia/Kolkata',
  'Asia/Dubai',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Europe/Madrid',
  'Europe/Rome',
  'Europe/Amsterdam',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Toronto',
  'America/Vancouver',
  'America/Sao_Paulo',
  'Africa/Johannesburg'
]

const timeZoneSelectOptions = computed(() =>
  timeZoneOptions.value.map(zone => ({ value: zone, label: formatTimeZoneLabel(zone) })),
)
const timeZoneOptions = computed(() => {
  return Array.from(new Set([
    auth.timeZone,
    browserTimeZone,
    ...commonTimeZones
  ])).filter(Boolean).sort((a, b) => a.localeCompare(b))
})

const timezoneChanged = computed(() => selectedTimeZone.value !== auth.timeZone)
// Registered by their supervisor, or edited by them since: the supervisor
// changes these details. A student who registered themselves (or through a
// peer) changes their own. Guardian details are the student's either way.
const detailsLocked = computed(() => Boolean(auth.user?.details_locked))
// Their guardian too, once permission is given: changes then go through support.
const guardianLocked = computed(() => Boolean(auth.user?.guardian_locked))
const GUARDIAN_LOCK_REASON =
  'Your guardian has given permission. Contact BIOTech Support if their details need to change.'
const canEditStudentDetails = computed(() => user.value?.student?.hasDetails && !detailsLocked.value)
const lockReason = computed(() => {
  const name = String(auth.user?.supervisor_name || '').trim()
  const email = String(auth.user?.supervisor_email || '').trim()
  const who = name && email ? `${name} (${email})` : name || email
  return who
    ? `Your supervisor, ${who}, manages these details. Contact them to make changes.`
    : 'Your supervisor manages these details. Contact them to make changes.'
})

watch(
  () => auth.timeZone,
  (timezone) => {
    selectedTimeZone.value = timezone
  },
  { immediate: true }
)

const useBrowserTimeZone = () => {
  selectedTimeZone.value = browserTimeZone
  statusMessage.value = ''
  clearStatusMessageTimer()
}

const saveTimeZone = async () => {
  statusMessage.value = ''
  clearStatusMessageTimer()

  if (!isValidTimeZone(selectedTimeZone.value)) {
    error.value = 'Please enter a valid IANA timezone, such as Australia/Sydney.'
    return
  }

  timezoneSaving.value = true
  error.value = ''

  try {
    await auth.updateTimeZone(selectedTimeZone.value)
    statusMessage.value = 'Your timezone has been updated.'
    statusMessageTimer = window.setTimeout(() => {
      statusMessage.value = ''
      statusMessageTimer = null
    }, 3200)
  } catch (saveError) {
    error.value = saveError instanceof Error
      ? saveError.message
      : 'Your timezone could not be updated right now.'
  } finally {
    timezoneSaving.value = false
  }
}

const clearStatusMessageTimer = () => {
  if (!statusMessageTimer) return
  window.clearTimeout(statusMessageTimer)
  statusMessageTimer = null
}

// --- A mentor's or admin's own details: their place, and their parts ------
// Saved through users/me/mentor/ (or me/admin/), checked as their admin
// panel's edit is.
const mentorSaving = ref(false)

const saveMentor = async (changes, done) => {
  mentorSaving.value = true
  error.value = ''
  try {
    if (!await ensureCsrfCookie(API_BASE_URL)) {
      throw new Error('Could not initialize a secure session. Please refresh and try again.')
    }
    const response = await fetch(`${API_BASE_URL}/api/v1/users/me/${auth.isAdmin ? 'admin' : 'mentor'}/`, {
      method: 'PATCH',
      credentials: 'include',
      headers: buildSessionHeaders({ includeCSRF: true }),
      body: JSON.stringify(changes),
    })
    if (!response.ok) throw await apiErrorFromResponse(response)
    auth.loginWithUser(await response.json())
    done()
    showTemporaryStatus('Your details have been updated.')
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : 'Your details could not be updated.'
  } finally {
    mentorSaving.value = false
  }
}

// An admin's name and pronouns.
const adminDetailsEditing = ref(false)
const adminDraft = ref({ firstName: '', lastName: '' })
const adminPronouns = ref({ choice: '', other: '' })

const startAdminDetailsEdit = () => {
  adminDraft.value = { firstName: auth.user?.first_name || '', lastName: auth.user?.last_name || '' }
  adminPronouns.value = pronounDraft(auth.user?.pronouns)
  error.value = ''
  adminDetailsEditing.value = true
}

const saveAdminDetails = () => {
  const pronouns = pronounsToSave(adminPronouns.value)
  if (pronouns === null) {
    error.value = 'Enter your pronouns.'
    return
  }
  saveMentor({ ...adminDraft.value, pronouns }, () => (adminDetailsEditing.value = false))
}

// Their country and state, as registering offers them (by name).
const mentorPlaceEditing = ref(false)
const mentorPlace = ref({ country: '', state: '', email: '', status: 'active' })
// An admin's own status, beside their place.
const ADMIN_STATUS_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
]
const mentorCountryOptions = useCountryOptions()
// Offered as they type their institution (Management > Known Universities).
const universityNames = useUniversityNames()
const mentorStateOptions = useStateOptions(() => mentorPlace.value.country)

const startMentorPlaceEdit = () => {
  mentorPlace.value = {
    country: auth.user?.country?.countryName || '',
    state: auth.user?.state?.stateName || '',
    email: auth.user?.email || '',
    status: String(auth.user?.account_status || '').toLowerCase() === 'active' ? 'active' : 'inactive',
  }
  error.value = ''
  mentorPlaceEditing.value = true
}

const saveMentorPlace = () => {
  const { country, state, email, status } = mentorPlace.value
  // An admin's email and status, only when changed.
  const own = {}
  if (auth.isAdmin) {
    const address = email.toLowerCase()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(address)) {
      error.value = 'Enter a valid email address.'
      return
    }
    if (address !== String(auth.user?.email || '').toLowerCase()) own.email = address
    const wasActive = String(auth.user?.account_status || '').toLowerCase() === 'active'
    if ((status === 'active') !== wasActive) own.isActive = status === 'active'
  }
  if (!country) {
    error.value = 'Choose your country.'
    return
  }
  if (isAustralia(country) && !state) {
    error.value = 'Choose your state or territory.'
    return
  }
  saveMentor({ ...own, country, state }, () => (mentorPlaceEditing.value = false))
}

// Mentor Details: as their admin panel has them, nothing required.
const mentorDetailsEditing = ref(false)
const mentorDraft = ref({
  firstName: '', lastName: '', background: null, company: '', institution: '', universityYear: null, fieldOfStudy: '',
  interests: [], capacity: null, weeklyHours: '',
})
const mentorPronouns = ref({ choice: '', other: '' })
const mentorDraftStudying = computed(() => isStudyingBackground(mentorDraft.value.background))
// Registering's backgrounds, and one typed before them, as written.
const mentorBackgroundOptions = computed(() => {
  const current = mentorDraft.value.background
  return current && !MENTOR_BACKGROUNDS.some(option => option.value === current)
    ? [...MENTOR_BACKGROUNDS, { value: current, label: current }]
    : MENTOR_BACKGROUNDS
})
// 1 to 5 groups as registering offers, and whatever they have now.
const mentorCapacityOptions = computed(() => {
  const counts = new Set([1, 2, 3, 4, 5])
  if (mentorDraft.value.capacity != null) counts.add(mentorDraft.value.capacity)
  return [...counts].sort((a, b) => a - b).map(count => ({ value: count, label: capacityLabel(count) }))
})
// The standard interests, and any expertise they have from outside them.
const mentorInterestChoices = computed(() => [
  ...INTEREST_CATEGORIES,
  ...(auth.user?.interests || []).filter(interest => !INTEREST_CATEGORIES.includes(interest)),
])

const startMentorDetailsEdit = () => {
  const details = auth.user?.mentor_details || {}
  mentorDraft.value = {
    firstName: auth.user?.first_name || '',
    lastName: auth.user?.last_name || '',
    background: mentorBackgroundCode(details.mentorBackground),
    company: details.mentorCompany || '',
    institution: details.mentorInstitution || '',
    universityYear: details.mentorUniversityYear || null,
    fieldOfStudy: details.mentorFieldOfStudy || '',
    interests: [...(auth.user?.interests || [])],
    capacity: details.mentorMaxGroupCount ?? null,
    weeklyHours: details.mentorWeeklyHours ? String(details.mentorWeeklyHours) : '',
  }
  mentorPronouns.value = pronounDraft(auth.user?.pronouns)
  error.value = ''
  mentorDetailsEditing.value = true
}

// Hours per week: a number box taking two digits at most.
const onMentorHoursInput = (event) => {
  mentorDraft.value.weeklyHours = String(keptDigits(event.target, 2))
}

const saveMentorDetails = () => {
  const draft = mentorDraft.value
  const pronouns = pronounsToSave(mentorPronouns.value)
  if (pronouns === null) {
    error.value = 'Enter your pronouns.'
    return
  }
  const hours = draft.weeklyHours.trim()
  if (hours && (!/^\d+$/.test(hours) || Number(hours) < 1 || Number(hours) > MAX_WEEKLY_HOURS)) {
    error.value = `Hours per week must be a whole number from 1 to ${MAX_WEEKLY_HOURS}.`
    return
  }
  // What their background doesn't ask for is cleared, as registering does.
  const industry = draft.background === 'industry'
  saveMentor({
    firstName: draft.firstName,
    lastName: draft.lastName,
    pronouns,
    mentorBackground: draft.background,
    mentorCompany: industry ? draft.company : '',
    mentorInstitution: industry ? '' : draft.institution,
    mentorUniversityYear: mentorDraftStudying.value ? draft.universityYear : '',
    mentorFieldOfStudy: industry ? '' : draft.fieldOfStudy,
    interests: draft.interests,
    ...(draft.capacity === null ? {} : { mentorMaxGroupCount: draft.capacity }),
    mentorWeeklyHours: hours ? Number(hours) : null,
  }, () => (mentorDetailsEditing.value = false))
}

// Weekly Availability: a day and its times, as many as they like.
const availabilityEditing = ref(false)
const availabilityDraft = ref([])

const startAvailabilityEdit = () => {
  availabilityDraft.value = (auth.user?.mentor_details?.mentorAvailability || []).map(splitSlot)
  error.value = ''
  availabilityEditing.value = true
}

const saveAvailability = () => {
  const times = availabilityTimes(availabilityDraft.value)
  if (typeof times === 'string') {
    error.value = times
    return
  }
  saveMentor({ mentorAvailability: times }, () => (availabilityEditing.value = false))
}

const showTemporaryStatus = (message) => {
  clearStatusMessageTimer()
  statusMessage.value = message
  statusMessageTimer = window.setTimeout(() => {
    statusMessage.value = ''
    statusMessageTimer = null
  }, 3200)
}

// The countries, regions and interests the edit forms offer.
const loadProfileOptions = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/users/me/profile-options/`, { credentials: 'include', headers: buildSessionHeaders() })
    if (!response.ok) throw await apiErrorFromResponse(response)
    profileOptions.value = await response.json()
    return true
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : 'Profile options could not be loaded.'
    return false
  }
}

const startPlaceEdit = async () => {
  if (!await loadProfileOptions()) return
  placeDraft.value = { country_id: auth.user?.country?.id || null, state_id: auth.user?.state?.id || null }
  error.value = ''
  placeEditing.value = true
}

const savePlace = async () => {
  if (!canEditStudentDetails.value) return
  if (draftInAustralia.value && !placeDraft.value.state_id) {
    error.value = 'Choose your state or territory.'
    return
  }
  placeSaving.value = true
  error.value = ''
  try {
    if (!await ensureCsrfCookie(API_BASE_URL)) {
      throw new Error('Could not initialize a secure session. Please refresh and try again.')
    }
    const response = await fetch(`${API_BASE_URL}/api/v1/users/me/`, {
      method: 'PATCH',
      credentials: 'include',
      headers: buildSessionHeaders({ includeCSRF: true }),
      body: JSON.stringify(placeDraft.value),
    })
    if (!response.ok) throw await apiErrorFromResponse(response)
    auth.loginWithUser(await response.json())
    placeEditing.value = false
    showTemporaryStatus('Your details have been updated.')
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : 'Your details could not be updated.'
  } finally {
    placeSaving.value = false
  }
}

const startStudentEdit = async () => {
  if (!await loadProfileOptions()) return
  const source = auth.user || {}
  studentDraft.value = {
    first_name: source.first_name || '',
    last_name: source.last_name || '',
    school_name: source.school_name || '',
    year_lvl: source.year_lvl || '9',
    interest_ids: [...profileOptions.value.selected_interest_ids],
  }
  pronounsDraft.value = pronounDraft(source.pronouns)
  error.value = ''
  studentEditing.value = true
}

// A supervisor's own name, the one thing of theirs they can change here.
const nameEditing = ref(false)
const nameSaving = ref(false)
const nameDraft = ref({ first_name: '', last_name: '' })
// Their pronouns, edited with their name.
const supervisorPronouns = ref({ choice: '', other: '' })

const startNameEdit = () => {
  nameDraft.value = { first_name: auth.user?.first_name || '', last_name: auth.user?.last_name || '' }
  supervisorPronouns.value = pronounDraft(auth.user?.pronouns)
  error.value = ''
  nameEditing.value = true
}

const saveName = async () => {
  const pronouns = pronounsToSave(supervisorPronouns.value)
  if (pronouns === null) {
    error.value = 'Enter your pronouns.'
    return
  }
  nameSaving.value = true
  error.value = ''
  try {
    if (!await ensureCsrfCookie(API_BASE_URL)) {
      throw new Error('Could not initialize a secure session. Please refresh and try again.')
    }
    const response = await fetch(`${API_BASE_URL}/api/v1/users/me/`, {
      method: 'PATCH',
      credentials: 'include',
      headers: buildSessionHeaders({ includeCSRF: true }),
      body: JSON.stringify({ ...nameDraft.value, pronouns }),
    })
    if (!response.ok) throw await apiErrorFromResponse(response)
    auth.loginWithUser(await response.json())
    nameEditing.value = false
    showTemporaryStatus('Your details have been updated.')
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : 'Your name could not be updated.'
  } finally {
    nameSaving.value = false
  }
}

const cancelStudentEdit = () => {
  if (studentSaving.value) return
  studentEditing.value = false
  error.value = ''
}

const sendGuardianInvitation = async () => {
  guardianSending.value = true
  noteGuardian(false, '')
  try {
    if (!await ensureCsrfCookie(API_BASE_URL)) throw new Error('Please refresh and try again.')
    const response = await fetch(`${API_BASE_URL}/api/v1/users/me/guardian-invitation/`, {
      method: 'POST', credentials: 'include', headers: buildSessionHeaders({ includeCSRF: true }),
      body: JSON.stringify({}),
    })
    if (!response.ok) throw await apiErrorFromResponse(response)
    const refreshed = await fetch(`${API_BASE_URL}/api/v1/users/me/`, { credentials: 'include', headers: buildSessionHeaders() })
    if (!refreshed.ok) throw new Error('Invitation sent, but your profile could not be refreshed. Please reload the page.')
    auth.loginWithUser(await refreshed.json())
    noteGuardian(true, 'The consent form has been emailed to your guardian.')
  } catch (sendError) {
    noteGuardian(false, sendError instanceof Error ? sendError.message : 'The consent form could not be sent.')
  } finally { guardianSending.value = false }
}

const saveStudentDetails = async () => {
  if (!canEditStudentDetails.value) return
  const pronouns = pronounsToSave(pronounsDraft.value)
  if (pronouns === null) {
    error.value = 'Enter your pronouns.'
    return
  }
  studentSaving.value = true
  error.value = ''
  try {
    if (!await ensureCsrfCookie(API_BASE_URL)) {
      throw new Error('Could not initialize a secure session. Please refresh and try again.')
    }
    const response = await fetch(`${API_BASE_URL}/api/v1/users/me/`, {
      method: 'PATCH',
      credentials: 'include',
      headers: buildSessionHeaders({ includeCSRF: true }),
      body: JSON.stringify({
        ...Object.fromEntries(Object.entries(studentDraft.value).filter(([key]) => !key.startsWith('pg_'))),
        pronouns,
      }),
    })
    if (!response.ok) throw await apiErrorFromResponse(response)
    auth.loginWithUser(await response.json())
    studentEditing.value = false
    showTemporaryStatus('Your details have been updated.')
    await loadTeamMembers()
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : 'Your details could not be updated.'
  } finally {
    studentSaving.value = false
  }
}

const selectAvatar = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) {
    error.value = 'Choose a PNG, JPEG, or WebP image smaller than 5 MB.'
    return
  }
  error.value = ''
  statusMessage.value = 'Uploading profile picture…'
  try {
    if (!await ensureCsrfCookie(API_BASE_URL)) {
      throw new Error('Could not initialize a secure upload session. Please refresh and try again.')
    }
    const form = new FormData()
    form.append('image', file)
    const response = await fetch(`${API_BASE_URL}/api/v1/users/me/profile-image/`, {
      method: 'POST',
      credentials: 'include',
      headers: buildSessionHeaders({ includeCSRF: true, isFormData: true }),
      body: form,
    })
    const data = await response.json().catch(() => null)
    if (!response.ok) throw new Error(data?.image?.[0] || data?.detail || 'Your profile picture could not be uploaded.')
    auth.loginWithUser(data)
    avatarUrl.value = data.profile_image_url || DEFAULT_PROFILE_AVATAR
    localStorage.removeItem('btf-local-profile-avatar')
    window.dispatchEvent(new Event('btf-profile-avatar-changed'))
    statusMessage.value = 'Profile picture uploaded successfully.'
  } catch (uploadError) {
    error.value = uploadError instanceof Error ? uploadError.message : 'Your profile picture could not be uploaded.'
    statusMessage.value = ''
  } finally {
    event.target.value = ''
  }
}

const loadTeamMembers = async () => {
  teamLoading.value = true
  teamError.value = ''
  try {
    const groupsResponse = await fetch(`${API_BASE_URL}/groups/groups/?page_size=1&mine=true`, { credentials: 'include', headers: buildSessionHeaders({ headers: { Accept: 'application/json' } }) })
    if (!groupsResponse.ok) throw new Error('Your team could not be loaded.')
    const groups = (await groupsResponse.json())?.results || []
    if (!groups[0]?.id) return
    teamName.value = groups[0].group_name || `Group ${groups[0].id}`
    const response = await fetch(`${API_BASE_URL}/groups/group-members/by-group/${groups[0].id}/`, { credentials: 'include', headers: buildSessionHeaders({ headers: { Accept: 'application/json' } }) })
    if (!response.ok) throw new Error('Your team members could not be loaded.')
    // Student profiles are shown before the challenge begins, when a mentor
    // has not yet been allocated. Keep the table focused on student teammates
    // even if development data already has a mentor attached to the group.
    teamMembers.value = (await response.json())
      .filter((member) => String(member.membership_role || '').trim().toLowerCase() === 'student')
      .map((member) => ({ id: member.id, ...member.student_details }))
  } catch (loadError) {
    teamError.value = loadError instanceof Error ? loadError.message : 'Your team members could not be loaded.'
  } finally { teamLoading.value = false }
}

const valueOrFallback = (value, fallback = 'Not provided') => {
  const text = String(value ?? '').trim()
  return text || fallback
}


const listOrEmpty = (value) => {
  if (!Array.isArray(value)) return []

  return value
    .map((item) => String(item ?? '').trim())
    .filter(Boolean)
}

const normaliseRole = (value) => {
  const role = String(value || '').trim().toLowerCase()
  if (role.includes('admin')) return 'admin'
  if (role.includes('mentor') || role === 'teacher') return 'mentor'
  if (role.includes('supervisor')) return 'supervisor'
  if (role.includes('student')) return 'student'
  return 'member'
}

const user = computed(() => {
  const source = auth.user
  const fullName = `${source?.first_name || ''} ${source?.last_name || ''}`.trim() || source?.email || 'User'
  const roleName = String(source?.current_role_name || auth.roleLabel || 'Member').trim()
  const roleKey = normaliseRole(roleName)
  const interests = listOrEmpty(source?.interests)
  const supervisorEmail = valueOrFallback(source?.supervisor_email, unsetLabel)
  const supervisorEmailAddress = String(source?.supervisor_email || '').trim()
  // Not shown (My Students lists them), but a supervisor with students still
  // gets the Supervisor Details section.
  const supervisedCount = Array.isArray(source?.supervised_students) ? source.supervised_students.length : 0
  const hasStudentDetails = roleKey === 'student'
  const consentReceived = source?.join_perm === true
  const guardianName = `${source?.pg_firstname || ''} ${source?.pg_lastname || ''}`.trim()
  const placeholderGuardian = isPlaceholderGuardian(source?.pg_firstname, source?.pg_lastname, source?.first_name, source?.last_name)
  const hasMentorDetails = roleKey === 'mentor' && Boolean(source?.mentor_details)
  // As their admin panel shows them: an old typed background as the list's choice it means.
  const mentorDetails = source?.mentor_details || {}
  const mentorBackground = mentorBackgroundCode(mentorDetails.mentorBackground)
  const hours = mentorDetails.mentorWeeklyHours
  const hasSupervisorDetails = roleKey === 'supervisor' && ([source?.supervisor_school_name].some(Boolean) || supervisedCount > 0)


  return {
    name: fullName,
    email: source?.email || 'Unavailable',
    role: roleName || 'Member',
    accountStatus: source?.account_status || 'Unavailable',
    country: source?.country?.countryName || 'Unassigned',
    // Sub-national only, and blank for most non-Australian users — not a gap to flag.
    region: source?.state?.stateName || unsetLabel,
    student: {
      hasDetails: hasStudentDetails,
      schoolName: valueOrFallback(source?.school_name, unsetLabel),
      yearLevel: valueOrFallback(source?.year_lvl, unsetLabel),
      interests,
      pronouns: valueOrFallback(source?.pronouns, unsetLabel),
      supervisorName: valueOrFallback(source?.supervisor_name, unsetLabel),
      supervisorEmail,
      supervisorEmailAddress,
      guardianFirstName: valueOrFallback(source?.pg_firstname, unsetLabel),
      guardianLastName: valueOrFallback(source?.pg_lastname, unsetLabel),
      guardianEmail: valueOrFallback(source?.pg_email, unsetLabel),
    },
    guardian: {
      hasDetails: hasStudentDetails,
      name: (!placeholderGuardian && guardianName) || unsetLabel,
      consentingName: (!placeholderGuardian && guardianName) || 'Your current guardian',
      emailAddress: String(source?.pg_email || '').trim(),
      // null when there's no student profile behind the account; treat as not received.
      consentReceived,
      // "14 Sep, 3:30 pm", in the set time.
      consentReceivedAt: consentReceived && source?.join_perm_granted_at
        ? formatDayMonthTime(source.join_perm_granted_at)
        : '',
      pending: source?.pending_guardian
        ? {
          name: `${source.pending_guardian.first_name} ${source.pending_guardian.last_name}`.trim(),
          firstName: source.pending_guardian.first_name,
          lastName: source.pending_guardian.last_name,
          email: source.pending_guardian.email
        }
        : null,
      // Form defaults: blank when the guardian fields only hold the placeholder.
      firstName: placeholderGuardian ? '' : String(source?.pg_firstname || ''),
      lastName: placeholderGuardian ? '' : String(source?.pg_lastname || '')
    },
    mentor: {
      hasDetails: hasMentorDetails,
      pronouns: valueOrFallback(source?.pronouns, unsetLabel),
      background: MENTOR_BACKGROUNDS.find(option => option.value === mentorBackground)?.label
        || valueOrFallback(mentorDetails.mentorBackground),
      industry: mentorBackground === 'industry',
      studying: isStudyingBackground(mentorBackground),
      company: valueOrFallback(mentorDetails.mentorCompany),
      institution: valueOrFallback(mentorDetails.mentorInstitution),
      studyYear: STUDY_YEAR_OPTIONS.find(option => option.value === mentorDetails.mentorUniversityYear)?.label
        || valueOrFallback(mentorDetails.mentorUniversityYear),
      fieldOfStudy: valueOrFallback(mentorDetails.mentorFieldOfStudy),
      interests: interests.length ? interests.join(', ') : unsetLabel,
      capacity: mentorDetails.mentorMaxGroupCount == null ? unsetLabel : capacityLabel(mentorDetails.mentorMaxGroupCount),
      weeklyHours: hours ? `${hours} ${hours === 1 ? 'hour' : 'hours'}` : unsetLabel,
      availability: mentorDetails.mentorAvailability || [],
      groups: (mentorDetails.mentorGroups || []).map(group => group.name).join(', ') || unsetLabel
    },
    admin: {
      hasDetails: roleKey === 'admin',
      pronouns: valueOrFallback(source?.pronouns, unsetLabel)
    },
    supervisor: {
      hasDetails: hasSupervisorDetails,
      schoolName: valueOrFallback(source?.supervisor_school_name),
      pronouns: valueOrFallback(source?.pronouns, unsetLabel)
    }
  }
})

const guardianEditing = ref(false)
const guardianSaving = ref(false)
const guardianForm = ref({ first_name: '', last_name: '', email: '' })
const guardianErrors = ref({})
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

// The guardian waiting on consent: a requested new one, else the one on file.
const guardianToAsk = computed(() => user.value?.guardian?.pending?.email || user.value?.guardian?.emailAddress || '')

/** Whether "click here to send email" can send now, else why not. */
const guardianSend = computed(() => {
  const to = guardianToAsk.value
  if (!to) return { canSend: false, reason: "add your guardian's email to send it" }
  if (to.toLowerCase() === String(auth.user?.email || '').toLowerCase()) {
    return { canSend: false, reason: "use your guardian's email, not your own" }
  }
  const reminder = auth.user?.guardian_reminder
  const lastSent = reminder?.last_sent_at ? new Date(reminder.last_sent_at).getTime() : 0
  const minutesLeft = Math.ceil((lastSent + RESEND_WAIT_MS - now.value) / 60000)
  if (minutesLeft > 0) {
    return {
      canSend: false,
      reason: `emailed ${to}, you can send it again in ${minutesLeft} minute${minutesLeft === 1 ? '' : 's'}`,
    }
  }
  if (reminder && !reminder.can_send) return { canSend: false, reason: reminder.unavailable_reason }
  return { canSend: true, reason: '' }
})

/** When the guardian was last emailed the consent form, and when they will be next. */
const reminderLine = computed(() => {
  const reminder = auth.user?.guardian_reminder
  if (!reminder || !guardianToAsk.value) return ''
  const guardian = user.value?.guardian
  if (guardian?.consentReceived && !guardian?.pending) return ''
  const last = reminder.last_sent_at
    ? `Last emailed ${formatDayMonthTime(reminder.last_sent_at)}.`
    : 'Not emailed yet.'
  if (!reminder.next_due_at) return last
  const zone = getSetTimeZone()
  const today = getTimeZoneDateParts(new Date(now.value), zone)
  const due = getTimeZoneDateParts(reminder.next_due_at, zone)
  const days = today && due
    ? Math.round((Date.UTC(due.year, due.month - 1, due.day) - Date.UTC(today.year, today.month - 1, today.day)) / 86400000)
    : null
  const when = days !== null && days <= 0
    ? 'today'
    : days === 1
      ? 'tomorrow'
      : `on ${formatDayMonth(reminder.next_due_at)}`
  return `${last} They'll be emailed again ${when}.`
})

// The warning before editing the guardian: what changing them does.
const guardianWarningOpen = ref(false)
const guardianWarning = computed(() =>
  user.value.guardian.consentReceived
    ? `Changing your guardian's details clears the permission ${user.value.guardian.consentingName} gave. ` +
      "Your new guardian will be emailed the consent form, and until they complete it you won't be able to " +
      'take part in most of the program.'
    : 'Your new guardian will be emailed the consent form to complete.',
)

const startGuardianEdit = () => {
  const { guardian } = user.value
  // Editing a pending change picks up where the student left off.
  guardianForm.value = guardian.pending
    ? { first_name: guardian.pending.firstName, last_name: guardian.pending.lastName, email: guardian.pending.email }
    : { first_name: guardian.firstName, last_name: guardian.lastName, email: guardian.emailAddress }
  guardianErrors.value = {}
  error.value = ''
  guardianEditing.value = true
}

const cancelGuardianEdit = () => {
  guardianEditing.value = false
  guardianErrors.value = {}
}

const validateGuardianForm = () => {
  const errors = {}
  const form = guardianForm.value
  if (!form.first_name) errors.first_name = 'Enter their first name.'
  if (!form.last_name) errors.last_name = 'Enter their last name.'
  if (!form.email) {
    errors.email = 'Enter their email.'
  } else if (!EMAIL_PATTERN.test(form.email)) {
    errors.email = 'Enter a valid email address.'
  } else if (form.email.toLowerCase() === String(auth.user?.email || '').toLowerCase()) {
    errors.email = "Enter your parent or guardian's email, not your own."
  }
  guardianErrors.value = errors
  return Object.keys(errors).length === 0
}

const saveGuardian = async () => {
  if (!validateGuardianForm()) return

  guardianSaving.value = true
  noteGuardian(false, '')
  const hadConsent = user.value.guardian.consentReceived

  try {
    await auth.updateGuardian({ ...guardianForm.value })
    guardianEditing.value = false
    noteGuardian(true, hadConsent && !user.value.guardian.consentReceived
      ? 'Saved. Your guardian permission is cleared until your new guardian completes the consent form.'
      : 'Your guardian details have been updated.')
  } catch (saveError) {
    const fields = saveError?.fields || {}
    guardianErrors.value = Object.fromEntries(
      Object.entries(fields).map(([key, messages]) => [key, [].concat(messages)[0]])
    )
    if (!Object.keys(guardianErrors.value).length) {
      noteGuardian(false, saveError instanceof Error
        ? saveError.message
        : 'Your guardian details could not be updated right now.')
    }
  } finally {
    guardianSaving.value = false
  }
}

const withdrawGuardianChange = async () => {
  guardianSaving.value = true
  noteGuardian(false, '')

  try {
    await auth.withdrawGuardianChange()
    noteGuardian(true, 'The guardian change has been withdrawn.')
  } catch (withdrawError) {
    noteGuardian(false, withdrawError instanceof Error
      ? withdrawError.message
      : 'The guardian change could not be withdrawn right now.')
  } finally {
    guardianSaving.value = false
  }
}

const getInitials = (name) => String(name || 'U')
  .split(' ')
  .filter(Boolean)
  .map((part) => part[0])
  .join('')
  .toUpperCase()
  .slice(0, 2) || 'U'

const capitalise = (value) => {
  const text = String(value || '').trim()
  if (!text) return 'Member'
  return text
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ')
}

async function loadProfile() {
  loading.value = true
  error.value = ''

  try {
    await auth.fetchUserData()

    if (!auth.user) {
      throw new Error('Your current user profile could not be loaded.')
    }
    avatarUrl.value = auth.user.profile_image_url || DEFAULT_PROFILE_AVATAR
  } catch (loadError) {
    error.value = loadError instanceof Error
      ? loadError.message
      : 'Your profile could not be loaded right now.'
  } finally {
    loading.value = false
  }
}

// The route, when the page runs under the router (tests may mount it bare).
const route = inject(routeLocationKey, null)

// The guardian details email links here with ?guardian=edit: open the form.
const openGuardianFromLink = async () => {
  if (route?.query?.guardian !== 'edit' || !user.value?.guardian?.hasDetails) return
  startGuardianEdit()
  await nextTick()
  document.querySelector('[data-test="guardian-details"]')?.scrollIntoView?.({ block: 'start' })
}

onMounted(async () => {
  // The profile and team members load together; the guardian form opens once the profile is in.
  const profile = loadProfile()
  loadTeamMembers()
  await profile
  await openGuardianFromLink()
})
</script>

<style scoped>
.profile-loading {
  overflow: hidden;
  border-radius: 8px;
  background: var(--white);
  box-shadow: 0 2px 4px var(--shadow);
}

.profile-loading-header {
  display: flex;
  min-height: 180px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.85rem;
  padding: 2rem;
  background: linear-gradient(135deg, var(--dark-green), var(--mint-green));
}

.profile-loading-content {
  padding: 2rem;
}

.profile-loading-section {
  padding: 1.5rem 0;
  border-bottom: 1px solid var(--border-light);
}

.profile-loading-section:first-child {
  padding-top: 0;
}

.profile-loading-section:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.profile-loading-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.5rem 0;
}

.skeleton-block {
  position: relative;
  overflow: hidden;
  border-radius: 6px;
  background: #e9ecef;
}

.profile-loading-avatar {
  width: 82px;
  height: 82px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.35);
}

.profile-loading-title {
  width: min(280px, 68%);
  height: 26px;
  background: rgba(255, 255, 255, 0.55);
}

.profile-loading-subtitle {
  width: min(220px, 58%);
  height: 16px;
  background: rgba(255, 255, 255, 0.42);
}

.profile-loading-heading {
  width: 180px;
  height: 20px;
  margin-bottom: 1rem;
}

.profile-loading-label {
  width: 140px;
  height: 16px;
}

.profile-loading-value {
  width: min(320px, 55%);
  height: 16px;
}

.status-card {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 1000;
  width: min(360px, calc(100vw - 2rem));
  margin-bottom: 0;
  border-left: 4px solid var(--dark-green);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.14);
}

.status-card p {
  margin: 0;
  color: #6c757d;
}

.status-fade-enter-active,
.status-fade-leave-active {
  transition:
    opacity 0.25s ease,
    transform 0.25s ease;
}

.status-fade-enter-from,
.status-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.timezone-field {
  align-items: flex-start;
}

.timezone-control {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 0.75rem;
}

/* The shared box (app-input) with the page's colour. */
.timezone-input {
  color: var(--teal);
}

/* Dark theme: the timezone box and its list on black, rather than white. */
:root[data-theme='dark'] .timezone-input {
  background: #000;
  color-scheme: dark;
}

.timezone-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.timezone-actions .btn {
  margin: 0;
}

.consent-field {
  align-items: flex-start;
}

.guardian-notice {
  margin: 1rem 0 0;
  padding: 0.6rem 0.8rem;
  border-left: 4px solid var(--dark-green);
  border-radius: 6px;
  background: var(--bg-light);
  color: var(--teal);
}

.guardian-notice--error {
  border-left-color: var(--danger);
}

/* "click here to send email": a button that reads as a link. */
.consent-send-link {
  padding: 0;
  border: 0;
  background: none;
  color: var(--dark-green);
  font: inherit;
  text-decoration: underline;
  cursor: pointer;
}

.consent-send-link:disabled {
  opacity: 0.6;
  cursor: wait;
}

.consent-hint {
  display: block;
  margin-top: 0.4rem;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.guardian-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.guardian-heading .btn {
  margin: 0;
}

.guardian-form {
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-light);
}

.guardian-form-hint {
  margin: 0 0 0.75rem;
}

.guardian-form-field {
  align-items: flex-start;
}

.guardian-input-wrap {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 0.3rem;
}

/* The shared box (app-input) with the page's colour. */
.guardian-input {
  color: var(--teal);
}

.guardian-error {
  color: var(--danger);
  font-size: 0.9rem;
}

.guardian-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.guardian-actions .btn,
.guardian-pending .btn {
  margin: 0;
}

.guardian-pending {
  margin-bottom: 1rem;
  padding: 0.85rem 1rem;
  border-left: 4px solid var(--warning);
  border-radius: 6px;
  background: var(--accent-green-soft);
}

.guardian-pending p {
  margin: 0 0 0.75rem;
  color: var(--teal);
}

.profile-link {
  color: var(--dark-green);
  overflow-wrap: anywhere;
}

.profile-avatar-wrap { position: relative; display:flex; flex-direction:column; align-items:center; }
.profile-avatar-initials { display:flex; align-items:center; justify-content:center; border-radius:50%; background:var(--white); color:var(--dark-green); font-size:2rem; font-weight:700; }
.profile-section-heading { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:1rem; margin-bottom:1.25rem; }
.profile-section-heading .profile-section-title { margin:0; }
.profile-avatar-large { width: 104px; height: 104px; flex-shrink:0; border: 4px solid rgba(255,255,255,.82); object-fit: cover; object-position:center; }
.avatar-change { display: block; margin-top: .45rem; cursor: pointer; color: white; font-size: .85rem; text-decoration: underline; }
.permission-status { font-weight: 600; color: #9c401a; }
.permission-status.received { color: var(--dark-green); }
.profile-note { margin: 1rem 0 0; color: #5c6670; font-size: .92rem; }
.profile-note a { color: var(--dark-green); }
.registration-lock { position:relative; display:inline-flex; width:.9rem; height:.9rem; margin-left:.3rem; color:#657069; vertical-align:-.08rem; cursor:help; }
.registration-lock svg { width:100%; height:100%; fill:none; stroke:currentColor; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; }
.registration-lock::after { content:attr(data-tooltip); position:absolute; z-index:10; bottom:calc(100% + .5rem); left:50%; width:max-content; max-width:min(18rem, 70vw); padding:.45rem .6rem; border-radius:4px; background:#26332d; color:#fff; font-size:.75rem; font-weight:400; line-height:1.35; text-align:left; white-space:normal; opacity:0; pointer-events:none; transform:translate(-50%, .2rem); transition:opacity .15s ease, transform .15s ease; }
.registration-lock:hover::after { opacity:1; transform:translate(-50%, 0); }
.profile-edit-button { margin:0; font-size:.85rem; }
/* A weekly time: day, from, to, and its ×. */
.student-edit-form__wide { grid-column:1 / -1; }
.mentor-slots { display:grid; gap:.6rem; margin-top:1rem; }
.mentor-slot { display:flex; flex-wrap:wrap; align-items:center; gap:.5rem; }
.mentor-slots .app-select { padding:.65rem .75rem; border:1px solid var(--border-light); border-radius:6px; color:var(--teal); background:var(--white); }
.mentor-slots .mentor-slot__day { flex:1 1 7rem; min-width:7rem; }
.mentor-slot__time { display:inline-flex; align-items:center; gap:.2rem; }
/* Just wide enough for two digits and the arrow. */
.mentor-slots .mentor-slot__part { width:3.5rem; padding-left:.5rem; padding-right:.5rem; }
.mentor-slot__muted { color:var(--text-muted); font-size:.85rem; }
.mentor-slot__remove { padding:.25rem .4rem; border:none; background:transparent; color:var(--text-muted); cursor:pointer; }
.mentor-slots > .profile-edit-button { justify-self:start; }
.guardian-locked-note { margin:.25rem 0 1rem; }
.student-edit-form { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:1rem; margin-top:1rem; }
.student-edit-form label { display:grid; gap:.35rem; color:#4c5750; font-size:.85rem; font-weight:600; }
/* The interests in two columns, as registering shows them, in their box. */
.student-edit-form fieldset { grid-column:1 / -1; display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:30px 16px; margin:0; padding:1.25rem 1rem; border:1px solid var(--border-light); border-radius:6px; }
.student-edit-form legend { padding:0 .35rem; color:#4c5750; font-size:.85rem; font-weight:700; }
.student-edit-form .interest-options label { display:flex; align-items:flex-start; gap:10px; padding:0 12px 0 2px; color:var(--charcoal); font-weight:400; line-height:1.35; cursor:pointer; }
/* Centred on the first line of its text, at any text size. */
.student-edit-form .interest-options input { flex:0 0 auto; width:1.0625rem; height:1.0625rem; margin:calc((.85rem * 1.35 - 1.0625rem) / 2) 0 0; padding:0; accent-color:var(--dark-green); cursor:pointer; }
.student-edit-form .profile-note, .student-edit-actions { grid-column:1 / -1; }
.student-edit-actions { display:flex; justify-content:flex-end; gap:.75rem; }
.student-edit-actions .btn { margin:0; }
.team-table { margin-top:1rem; }
.member-initial { display:inline-grid; place-items:center; width:2rem; height:2rem; border-radius:50%; background:var(--accent-green-soft); color:var(--dark-green); font-weight:700; }
.member-role { color:#657069; font-size:.88rem; }

@media (max-width: 640px) {
  .status-card {
    top: 0.75rem;
    right: 0.75rem;
    width: calc(100vw - 1.5rem);
  }

  .profile-loading-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .profile-loading-value {
    width: 100%;
  }

  :deep(.profile-field) {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.35rem;
  }

  :deep(.profile-field-label) {
    width: auto;
  }

  .timezone-actions,
  .guardian-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .student-edit-form, .student-edit-form fieldset {
    grid-template-columns:1fr;
  }
}

/* Timezone dropdown - dark mode */
:global(html[data-theme='dark']) .timezone-input {
  background-color: #1d2826 !important;
  color: #e6efed !important;
  border: 1px solid #3c4b47 !important;
  color-scheme: dark;
}

:global(html[data-theme='dark']) .timezone-input option {
  background-color: #1d2826;
  color: #e6efed;
}

/* Save timezone button - dark mode */
:global(html[data-theme='dark']) .timezone-actions .btn-primary {
  background: #017151 !important;
  color: #ffffff !important;
  border: 1px solid #017151 !important;
}

/* Save timezone button hover */
:global(html[data-theme='dark']) .timezone-actions .btn-primary:hover:not(:disabled) {
  background: #015940 !important;
  border-color: #015940 !important;
}

/* Use device timezone button - dark mode */
:global(html[data-theme='dark']) .timezone-actions .btn-outline {
  background: transparent !important;
  color: #e6efed !important;
  border: 1px solid #3c4b47 !important;
}

/* Disabled Save timezone button */
:global(html[data-theme='dark']) .timezone-actions .btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
