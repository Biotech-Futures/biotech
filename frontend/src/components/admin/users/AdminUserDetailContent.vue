<template>
  <div class="admin-users-detail">
    <section v-if="user" class="admin-users-detail__section" data-test="admin-account">
      <div class="admin-users-detail__heading">
        <h3>Account</h3>
        <button
          v-if="EDITED_IN_PARTS.includes(user.role ?? '') && editable && editing !== 'account'"
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-edit-account"
          @click="startEdit('account')"
        >
          Edit
        </button>
      </div>
      <!-- A student's, mentor's or supervisor's email, country, state and status. -->
      <form v-if="editing === 'account'" data-test="admin-account-form" @submit.prevent="save">
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">Email</span>
          <input v-model.trim="form.email" class="admin-users-detail__input" type="email" required maxlength="254" />
        </label>
        <div class="admin-users-detail__item">
          <label class="admin-users-detail__label" for="admin-detail-country">Country</label>
          <AppSelect
            size="large"
            id="admin-detail-country"
            :model-value="form.countryId"
            class="admin-users-detail__input"
            data-test="admin-country-select"
            :options="countryOptions"
            :loading="placesLoading"
            placeholder="Search countries"
            empty-text="No country matches"
            @update:model-value="pickCountry"
          />
        </div>
        <!-- Australia's states to pick; elsewhere, typed. -->
        <label v-if="!inAustralia" class="admin-users-detail__item">
          <span class="admin-users-detail__label">State</span>
          <input
            v-model.trim="form.stateName"
            class="admin-users-detail__input"
            data-test="admin-state-text"
            maxlength="255"
            placeholder="State, province or region"
          />
        </label>
        <div v-else class="admin-users-detail__item">
          <label class="admin-users-detail__label" for="admin-detail-state">State</label>
          <AppSelect
            size="large"
            id="admin-detail-state"
            v-model="form.stateId"
            class="admin-users-detail__input"
            data-test="admin-state-select"
            :options="stateOptions"
            :loading="placesLoading"
            :searchable="false"
            placeholder="Choose a state"
            required
          />
        </div>
        <div class="admin-users-detail__item">
          <label class="admin-users-detail__label" for="admin-detail-status">Status</label>
          <AppSelect
            size="large"
            id="admin-detail-status"
            v-model="form.status"
            class="admin-users-detail__input"
            data-test="admin-status-select"
            :options="STATUS_OPTIONS"
            :searchable="false"
          />
        </div>
        <p v-if="placesError" class="admin-users-detail__save-error" role="alert">{{ placesError }}</p>
        <p v-if="saveError" class="admin-users-detail__save-error" role="alert">{{ saveError }}</p>
        <div class="admin-users-detail__actions">
          <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="cancelEdit">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </form>
      <dl v-else class="admin-users-detail__list">
        <div class="admin-users-detail__item">
          <dt>Email</dt>
          <dd>{{ user.email || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Role</dt>
          <dd><span class="admin-users__role-badge">{{ roleLabel(user.role) }}</span></dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Country</dt>
          <dd>{{ labelizeCountry(user.country) }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>State</dt>
          <dd>{{ labelizeState(user.state) }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Status</dt>
          <dd>
            <span class="admin-users__status-badge" :class="{ 'admin-users__status-badge--inactive': !user.isActive }">
              {{ user.isActive ? 'Active' : 'Inactive' }}
            </span>
          </dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Has logged in</dt>
          <dd>
            <span class="admin-users__logged-in-badge" :class="{ 'admin-users__logged-in-badge--yes': user.hasLoggedIn }">
              {{ user.hasLoggedIn ? 'Yes' : 'No' }}
            </span>
          </dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Last login</dt>
          <dd>{{ user.lastLogin ? formatFullDate(user.lastLogin) : 'Never' }}</dd>
        </div>
        <div class="admin-users-detail__item" data-test="admin-last-edited">
          <dt>Last edited</dt>
          <dd>
            {{
              user.lastEditedBy && user.lastEditedAt
                ? `${user.lastEditedBy} · ${formatFullDate(user.lastEditedAt)}`
                : 'No edits on record'
            }}
          </dd>
        </div>
      </dl>
    </section>

    <section v-if="user?.role === 'student'" class="admin-users-detail__section" data-test="admin-supervisor-group">
      <div class="admin-users-detail__heading">
        <h3>Supervisor and Group</h3>
        <button
          v-if="editable && editing !== 'supervisor'"
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-edit-supervisor"
          @click="startEdit('supervisor')"
        >
          Edit
        </button>
      </div>
      <!-- Each picked from a list; replacing one they have asks first. -->
      <form v-if="editing === 'supervisor'" data-test="admin-supervisor-form" @submit.prevent="save">
        <div class="admin-users-detail__item">
          <label class="admin-users-detail__label" for="admin-detail-supervisor">Supervisor</label>
          <AppSelect
            size="large"
            id="admin-detail-supervisor"
            v-model="form.supervisorEmail"
            class="admin-users-detail__input"
            data-test="admin-supervisor-select"
            searchable
            :options="supervisorOptions"
            :loading="picksLoading"
            placeholder="Search by name or email"
            empty-text="No supervisor matches"
          />
        </div>
        <div class="admin-users-detail__item">
          <label class="admin-users-detail__label" for="admin-detail-group">Group</label>
          <AppSelect
            size="large"
            id="admin-detail-group"
            v-model="form.groupId"
            class="admin-users-detail__input"
            data-test="admin-group-select"
            searchable
            :options="groupOptions"
            :loading="picksLoading"
            placeholder="Search by group name"
            empty-text="No group matches"
          />
        </div>
        <p v-if="picksError" class="admin-users-detail__save-error" role="alert">{{ picksError }}</p>
        <p v-if="saveError" class="admin-users-detail__save-error" role="alert">{{ saveError }}</p>
        <div class="admin-users-detail__actions">
          <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="cancelEdit">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </form>
      <dl v-else class="admin-users-detail__list">
        <div class="admin-users-detail__item">
          <dt>Supervisor</dt>
          <dd>{{ supervisorLabel(user) }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Group</dt>
          <dd>{{ user.groupName || '—' }}</dd>
        </div>
      </dl>
    </section>

    <!-- A student's parts as their supervisor's panel shows them, each with
         its own Edit beside its heading; the admin's consent parts under
         Guardian Details. -->
    <section v-if="user?.role === 'student'" class="admin-users-detail__section" data-test="admin-student-details">
      <div class="admin-users-detail__heading">
        <h3>Student Details</h3>
        <button
          v-if="editable && editing !== 'details'"
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-edit-details"
          @click="startEdit('details')"
        >
          Edit
        </button>
      </div>
      <form v-if="editing === 'details'" data-test="admin-details-form" @submit.prevent="save">
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">First name</span>
          <input v-model.trim="form.firstName" class="admin-users-detail__input" required maxlength="255" />
        </label>
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">Last name</span>
          <input v-model.trim="form.lastName" class="admin-users-detail__input" required maxlength="255" />
        </label>
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">School</span>
          <input v-model.trim="form.schoolName" class="admin-users-detail__input" required maxlength="255" />
        </label>
        <div class="admin-users-detail__item">
          <label class="admin-users-detail__label" for="admin-detail-year">Year Level</label>
          <AppSelect
            size="large"
            id="admin-detail-year"
            v-model="form.yearLevel"
            class="admin-users-detail__input"
            data-test="admin-year-select"
            :options="YEAR_OPTIONS"
            :searchable="false"
            placeholder="Choose a year"
          />
        </div>
        <fieldset class="admin-users-detail__item admin-users-detail__options">
          <legend class="admin-users-detail__label">Interests</legend>
          <label v-for="interest in INTEREST_OPTIONS" :key="interest">
            <input v-model="form.interests" type="checkbox" :value="interest" />
            {{ interest }}
          </label>
        </fieldset>
        <p v-if="saveError" class="admin-users-detail__save-error" role="alert">{{ saveError }}</p>
        <div class="admin-users-detail__actions">
          <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="cancelEdit">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </form>
      <dl v-else class="admin-users-detail__list">
        <div class="admin-users-detail__item">
          <dt>Name</dt>
          <dd>{{ [user.firstName, user.lastName].filter(Boolean).join(' ') || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>School</dt>
          <dd>{{ user.schoolName || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Year Level</dt>
          <dd>{{ user.yearLevel ?? '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Interests</dt>
          <dd>{{ joinInterests(user.interests) }}</dd>
        </div>
      </dl>
    </section>

    <section v-if="user?.role === 'student'" class="admin-users-detail__section" data-test="admin-guardian">
      <div class="admin-users-detail__heading">
        <h3>Guardian Details</h3>
        <button
          v-if="editable && editing !== 'guardian'"
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-edit-guardian"
          @click="startEdit('guardian')"
        >
          Edit
        </button>
      </div>
      <form v-if="editing === 'guardian'" data-test="admin-guardian-form" @submit.prevent="save">
        <p v-if="user.pendingGuardian" class="admin-users-detail__note">
          The student asked to change their guardian to
          <strong>{{ user.pendingGuardian.firstName }} {{ user.pendingGuardian.lastName }}</strong>
          ({{ user.pendingGuardian.email || 'no email' }}). They become the guardian once they sign the consent
          form; changing the guardian here discards the request.
        </p>
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">First name</span>
          <input v-model.trim="form.guardianFirstName" class="admin-users-detail__input" />
        </label>
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">Last name</span>
          <input v-model.trim="form.guardianLastName" class="admin-users-detail__input" />
        </label>
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">Email</span>
          <input v-model.trim="form.guardianEmail" class="admin-users-detail__input" type="email" />
        </label>
        <!-- Ticked when given: ticking records it, unticking records a withdrawal.
             Each on its own line, as the fields above: words left, box right. -->
        <label class="admin-users-detail__item admin-users-detail__check">
          <span class="admin-users-detail__label">Consent to take part</span>
          <input v-model="form.consentGiven" type="checkbox" data-test="admin-consent-given" />
        </label>
        <label class="admin-users-detail__item admin-users-detail__check" :class="{ 'is-disabled': !form.consentGiven }">
          <span class="admin-users-detail__label">Media consent</span>
          <input v-model="form.mediaGiven" type="checkbox" :disabled="!form.consentGiven" />
        </label>
        <label v-if="user.pendingGuardian" class="admin-users-detail__item admin-users-detail__check">
          <span class="admin-users-detail__label">
            {{ user.pendingGuardian.firstName }} {{ user.pendingGuardian.lastName }} (new guardian) has given consent
          </span>
          <input v-model="form.pendingConsentGiven" type="checkbox" />
        </label>
        <p v-if="saveError" class="admin-users-detail__save-error" role="alert">{{ saveError }}</p>
        <div class="admin-users-detail__actions">
          <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="cancelEdit">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </form>
      <dl v-else class="admin-users-detail__list">
        <div class="admin-users-detail__item">
          <dt>Name</dt>
          <dd data-test="admin-guardian-name">{{ guardian.name || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Email</dt>
          <dd>{{ user.guardianEmail || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Permission</dt>
          <dd data-test="admin-consent">
            {{ permissionLabel
            }}<span v-if="guardian.consent === 'unverified'" class="admin-users-detail__flag"> (no signed form on record)</span>
          </dd>
        </div>
        <div class="admin-users-detail__item" data-test="admin-media-consent">
          <dt>Media Consent</dt>
          <dd>{{ mediaConsentLabel }}</dd>
        </div>
        <div v-if="user.pendingGuardian" class="admin-users-detail__item" data-test="admin-pending-guardian">
          <dt>Requested change</dt>
          <dd>
            {{ user.pendingGuardian.firstName }} {{ user.pendingGuardian.lastName }}
            ({{ user.pendingGuardian.email || 'no email' }}), waiting for their consent
          </dd>
        </div>
        <div v-if="user.consentRequestSentAt" class="admin-users-detail__item" data-test="admin-consent-request-sent">
          <dt>Consent requested</dt>
          <dd>{{ formatFullDate(user.consentRequestSentAt) }}</dd>
        </div>
      </dl>
      <div v-if="consentRequestTo" class="admin-users-detail__consent-request">
        <button
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-send-consent-request"
          :disabled="sendingRequest"
          @click="sendConsentRequest"
        >
          {{ sendingRequest ? 'Sending…' : user.consentRequestSentAt ? 'Resend consent request' : 'Send consent request' }}
        </button>
        <p
          v-if="requestMessage"
          class="admin-users-detail__consent-message"
          :class="{ 'admin-users-detail__consent-message--error': requestFailed }"
          role="status"
          data-test="admin-consent-request-message"
        >
          {{ requestMessage }}
        </p>
        <p v-else class="admin-users-detail__consent-hint">Emails the consent form to {{ consentRequestTo }}.</p>
      </div>

      <div v-if="user.joinPermissionReceived && signedOnPlatform" class="admin-users-detail__consent-actions">
        <button
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-view-consent"
          :disabled="consentsLoading"
          @click="toggleConsents"
        >
          {{ consentsOpen ? 'Hide signed form' : 'View signed form' }}
        </button>
      </div>
      <p
        v-if="consentsMessage"
        class="admin-users-detail__consent-message"
        :class="{ 'admin-users-detail__consent-message--error': consentsFailed }"
        role="status"
        data-test="admin-consent-message"
      >
        {{ consentsMessage }}
      </p>

      <ul v-if="consentsOpen && consents.length" class="admin-users-detail__consents" data-test="admin-signed-consents">
        <li v-for="consent in consents" :key="consent.id" class="admin-users-detail__consent">
          <p class="admin-users-detail__consent-head">
            <strong>{{ consent.reference }}</strong>
            <span v-if="consent.withdrawnAt" class="admin-users-detail__flag">Withdrawn {{ formatFullDate(consent.withdrawnAt) }}</span>
          </p>
          <p>
            Signed by {{ consent.guardianFullName }} ({{ consent.guardianEmail }}) on
            {{ formatFullDate(consent.signedAt) }}, form version {{ consent.consentVersion }}.
          </p>
          <p>
            Media consent: {{ consent.mediaConsent ? 'Yes' : 'No' }}<template v-if="consent.mediaWithdrawnAt">, withdrawn {{ formatFullDate(consent.mediaWithdrawnAt) }}</template>
          </p>
          <img :src="consent.signature" :alt="`Signature of ${consent.guardianFullName}`" class="admin-users-detail__signature" />
          <button
            type="button"
            class="btn btn-outline btn-sm admin-users-detail__record"
            data-test="admin-download-record"
            :disabled="downloadingId === consent.id"
            @click="downloadRecord(consent)"
          >
            {{ downloadingId === consent.id ? 'Downloading…' : 'Download PDF' }}
          </button>
        </li>
      </ul>
    </section>

    <!-- A mentor's parts, each edited in place as a student's are: their
         groups, what they registered with, and their application's answers. -->
    <section v-if="user?.role === 'mentor'" class="admin-users-detail__section" data-test="admin-mentor-groups">
      <div class="admin-users-detail__heading">
        <h3>Groups</h3>
        <button
          v-if="editable && editing !== 'mentorGroups'"
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-edit-mentor-groups"
          @click="startEdit('mentorGroups')"
        >
          Edit
        </button>
      </div>
      <!-- Group 1, 2, …: the next one once the last is picked, up to their
           capacity. Taking one off, or one with another mentor, asks first. -->
      <form v-if="editing === 'mentorGroups'" data-test="admin-mentor-groups-form" @submit.prevent="save">
        <div v-for="(groupId, index) in mentorGroupSlots" :key="index" class="admin-users-detail__item">
          <label class="admin-users-detail__label" :for="`admin-mentor-group-${index}`">Group {{ index + 1 }}</label>
          <AppSelect
            :id="`admin-mentor-group-${index}`"
            size="large"
            :model-value="groupId"
            class="admin-users-detail__input"
            :data-test="`admin-mentor-group-${index}`"
            :options="mentorGroupOptions(index)"
            :loading="picksLoading"
            searchable
            placeholder="Choose a group"
            empty-text="No group matches"
            @update:model-value="(value) => pickMentorGroup(index, value)"
          />
        </div>
        <p v-if="!mentorGroupSlots.length || form.mentorGroupIds.length >= mentorCapacity" class="admin-users-detail__note admin-users-detail__note--after">
          {{ mentorCapacityNote }}
        </p>
        <p v-if="picksError" class="admin-users-detail__save-error" role="alert">{{ picksError }}</p>
        <p v-if="saveError" class="admin-users-detail__save-error" role="alert">{{ saveError }}</p>
        <div class="admin-users-detail__actions">
          <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="cancelEdit">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </form>
      <dl v-else class="admin-users-detail__list">
        <div class="admin-users-detail__item">
          <dt>Groups</dt>
          <dd data-test="admin-mentor-group-names">{{ mentorGroupNames || '—' }}</dd>
        </div>
      </dl>
    </section>

    <section v-if="user?.role === 'mentor'" class="admin-users-detail__section" data-test="admin-mentor-details">
      <div class="admin-users-detail__heading">
        <h3>Mentor Details</h3>
        <button
          v-if="editable && editing !== 'mentorDetails'"
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-edit-mentor-details"
          @click="startEdit('mentorDetails')"
        >
          Edit
        </button>
      </div>
      <!-- As the registration form asks: where they work or study depends on
           their background. -->
      <form v-if="editing === 'mentorDetails'" data-test="admin-mentor-details-form" @submit.prevent="save">
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">First name</span>
          <input v-model.trim="form.firstName" class="admin-users-detail__input" required maxlength="150" />
        </label>
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">Last name</span>
          <input v-model.trim="form.lastName" class="admin-users-detail__input" required maxlength="150" />
        </label>
        <div class="admin-users-detail__item">
          <label class="admin-users-detail__label" for="admin-mentor-background">Background</label>
          <AppSelect
            id="admin-mentor-background"
            v-model="form.mentorBackground"
            size="large"
            class="admin-users-detail__input"
            data-test="admin-mentor-background"
            :options="mentorBackgroundOptions"
            placeholder="Choose a background"
          />
        </div>
        <label v-if="form.mentorBackground === 'industry'" class="admin-users-detail__item">
          <span class="admin-users-detail__label">Company</span>
          <input v-model.trim="form.mentorCompany" class="admin-users-detail__input" data-test="admin-mentor-company" maxlength="255" />
        </label>
        <label v-else class="admin-users-detail__item">
          <span class="admin-users-detail__label">Institution</span>
          <input v-model.trim="form.mentorInstitution" class="admin-users-detail__input" data-test="admin-mentor-institution" maxlength="255" />
        </label>
        <div v-if="mentorStudying" class="admin-users-detail__item">
          <label class="admin-users-detail__label" for="admin-mentor-year">Year of study</label>
          <AppSelect
            id="admin-mentor-year"
            v-model="form.mentorUniversityYear"
            size="large"
            class="admin-users-detail__input"
            data-test="admin-mentor-year"
            :options="STUDY_YEAR_OPTIONS"
            placeholder="Choose a year"
          />
        </div>
        <label v-if="form.mentorBackground !== 'industry'" class="admin-users-detail__item">
          <span class="admin-users-detail__label">Field of study</span>
          <input v-model.trim="form.mentorFieldOfStudy" class="admin-users-detail__input" data-test="admin-mentor-field" maxlength="255" />
        </label>
        <fieldset class="admin-users-detail__item admin-users-detail__options">
          <legend class="admin-users-detail__label">Interests</legend>
          <label v-for="interest in mentorInterestOptions" :key="interest">
            <input v-model="form.interests" type="checkbox" :value="interest" />
            {{ interest }}
          </label>
        </fieldset>
        <div class="admin-users-detail__item">
          <label class="admin-users-detail__label" for="admin-mentor-capacity">Capacity</label>
          <AppSelect
            id="admin-mentor-capacity"
            v-model="form.mentorCapacity"
            size="large"
            class="admin-users-detail__input"
            data-test="admin-mentor-capacity"
            :options="mentorCapacityOptions"
          />
        </div>
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">Hours per week</span>
          <input
            :value="form.mentorWeeklyHours"
            type="number"
            inputmode="numeric"
            min="1"
            :max="MAX_WEEKLY_HOURS"
            step="1"
            class="admin-users-detail__input"
            data-test="admin-mentor-hours-input"
            @input="onHoursInput"
            @keydown="refuseNonDigitKey"
            @paste="refuseNonDigitPaste"
          />
        </label>
        <p v-if="saveError" class="admin-users-detail__save-error" role="alert">{{ saveError }}</p>
        <div class="admin-users-detail__actions">
          <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="cancelEdit">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </form>
      <dl v-else class="admin-users-detail__list">
        <div class="admin-users-detail__item">
          <dt>Name</dt>
          <dd>{{ [user.firstName, user.lastName].filter(Boolean).join(' ') || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Background</dt>
          <dd data-test="admin-mentor-background-label">{{ mentorBackgroundLabel(user.mentorBackground) }}</dd>
        </div>
        <div v-if="user.mentorBackground === 'industry'" class="admin-users-detail__item">
          <dt>Company</dt>
          <dd>{{ user.mentorCompany || '—' }}</dd>
        </div>
        <div v-else class="admin-users-detail__item">
          <dt>Institution</dt>
          <dd>{{ user.mentorInstitution || '—' }}</dd>
        </div>
        <div v-if="isStudyingBackground(user.mentorBackground)" class="admin-users-detail__item">
          <dt>Year of study</dt>
          <dd>{{ studyYearLabel(user.mentorUniversityYear) }}</dd>
        </div>
        <div v-if="user.mentorBackground !== 'industry'" class="admin-users-detail__item">
          <dt>Field of study</dt>
          <dd>{{ user.mentorFieldOfStudy || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Interests</dt>
          <dd>{{ joinInterests(user.interests) }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Capacity</dt>
          <dd>{{ capacityLabel(user.mentorMaxGroupCount) }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Hours per week</dt>
          <dd data-test="admin-mentor-hours">{{ hoursLabel(user.mentorWeeklyHours) }}</dd>
        </div>
      </dl>
    </section>

    <section v-if="user?.role === 'mentor'" class="admin-users-detail__section" data-test="admin-mentor-availability">
      <div class="admin-users-detail__heading">
        <h3>Weekly Availability</h3>
        <button
          v-if="editable && editing !== 'availability'"
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-edit-availability"
          @click="startEdit('availability')"
        >
          Edit
        </button>
      </div>
      <!-- When they're free each week: a day and its times, as many as they like. -->
      <form v-if="editing === 'availability'" data-test="admin-availability-form" @submit.prevent="save">
        <div
          v-for="(slot, index) in form.mentorAvailability"
          :key="index"
          class="admin-users-detail__item admin-users-detail__slot"
          :data-test="`admin-mentor-slot-${index}`"
        >
          <AppSelect
            v-model="slot.weekday"
            size="large"
            class="admin-users-detail__input"
            :aria-label="`Day ${index + 1}`"
            :options="WEEKDAY_OPTIONS"
            placeholder="Day"
          />
          <!-- Each time as its hour and its minutes, in 5-minute steps (a time
               box's own picker lists every minute). -->
          <span class="admin-users-detail__time" :data-test="`admin-mentor-slot-${index}-start`">
            <AppSelect
              :model-value="slot.startHour"
              size="large"
              class="admin-users-detail__input admin-users-detail__time-part"
              :data-test="`admin-mentor-slot-${index}-start-hour`"
              :aria-label="`From, hour, time ${index + 1}`"
              :options="HOUR_OPTIONS"
              :searchable="false"
              placeholder="--"
              @update:model-value="(value) => pickHour(slot, 'start', value)"
            />
            <span class="admin-users-detail__time-colon">:</span>
            <AppSelect
              v-model="slot.startMinute"
              size="large"
              class="admin-users-detail__input admin-users-detail__time-part"
              :data-test="`admin-mentor-slot-${index}-start-minute`"
              :aria-label="`From, minutes, time ${index + 1}`"
              :options="minuteOptions(slot.startMinute)"
              :searchable="false"
              placeholder="--"
            />
          </span>
          <span class="admin-users-detail__slot-to">to</span>
          <span class="admin-users-detail__time" :data-test="`admin-mentor-slot-${index}-end`">
            <AppSelect
              :model-value="slot.endHour"
              size="large"
              class="admin-users-detail__input admin-users-detail__time-part"
              :data-test="`admin-mentor-slot-${index}-end-hour`"
              :aria-label="`To, hour, time ${index + 1}`"
              :options="HOUR_OPTIONS"
              :searchable="false"
              placeholder="--"
              @update:model-value="(value) => pickHour(slot, 'end', value)"
            />
            <span class="admin-users-detail__time-colon">:</span>
            <AppSelect
              v-model="slot.endMinute"
              size="large"
              class="admin-users-detail__input admin-users-detail__time-part"
              :data-test="`admin-mentor-slot-${index}-end-minute`"
              :aria-label="`To, minutes, time ${index + 1}`"
              :options="minuteOptions(slot.endMinute)"
              :searchable="false"
              placeholder="--"
            />
          </span>
          <button
            type="button"
            class="admin-users-detail__slot-remove"
            :aria-label="`Remove time ${index + 1}`"
            @click="form.mentorAvailability.splice(index, 1)"
          >
            <i class="fas fa-xmark" aria-hidden="true"></i>
          </button>
        </div>
        <p v-if="!form.mentorAvailability.length" class="admin-users-detail__note admin-users-detail__note--after">
          No weekly times.
        </p>
        <button
          v-if="form.mentorAvailability.length < 21"
          type="button"
          class="btn btn-outline btn-sm admin-users-detail__slot-add"
          data-test="admin-mentor-add-slot"
          @click="form.mentorAvailability.push(blankSlot())"
        >
          Add a time
        </button>
        <p v-if="saveError" class="admin-users-detail__save-error" role="alert">{{ saveError }}</p>
        <div class="admin-users-detail__actions">
          <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="cancelEdit">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </form>
      <dl v-else class="admin-users-detail__list" data-test="admin-mentor-times">
        <div v-for="(slot, index) in user.mentorAvailability || []" :key="index" class="admin-users-detail__item">
          <dt>{{ WEEKDAYS[slot.weekday] }}</dt>
          <dd>{{ slot.start }} – {{ slot.end }}</dd>
        </div>
        <div v-if="!user.mentorAvailability?.length" class="admin-users-detail__item">
          <dt>Times</dt>
          <dd>—</dd>
        </div>
      </dl>
    </section>

    <section v-if="user?.role === 'mentor'" class="admin-users-detail__section" data-test="admin-mentor-application">
      <div class="admin-users-detail__heading">
        <h3>Application Form</h3>
        <button
          v-if="editable && editing !== 'application'"
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-edit-application"
          @click="startEdit('application')"
        >
          Edit
        </button>
      </div>
      <!-- The three questions registering asks, 150 words each at most. -->
      <form v-if="editing === 'application'" data-test="admin-application-form" @submit.prevent="save">
        <label
          v-for="question in APPLICATION_QUESTIONS"
          :key="question.key"
          class="admin-users-detail__item admin-users-detail__item--stacked admin-users-detail__item--boxed"
        >
          <span class="admin-users-detail__label">{{ question.label }}</span>
          <textarea
            v-model="form[question.key]"
            v-auto-grow
            class="admin-users-detail__input admin-users-detail__textarea"
            :data-test="`admin-answer-${question.key}`"
            rows="9"
          ></textarea>
          <span
            class="admin-users-detail__words"
            :class="{ 'is-over': wordCount(form[question.key]) > MAX_ANSWER_WORDS }"
          >
            {{ wordCount(form[question.key]) }}/{{ MAX_ANSWER_WORDS }} words
          </span>
        </label>
        <p v-if="saveError" class="admin-users-detail__save-error" role="alert">{{ saveError }}</p>
        <div class="admin-users-detail__actions">
          <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="cancelEdit">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </form>
      <dl v-else class="admin-users-detail__list">
        <div
          v-for="question in APPLICATION_QUESTIONS"
          :key="question.key"
          class="admin-users-detail__item admin-users-detail__item--stacked admin-users-detail__item--boxed"
        >
          <dt>{{ question.label }}</dt>
          <dd class="admin-users-detail__answer" :data-test="`admin-answer-view-${question.key}`">{{ user[question.field] || '—' }}</dd>
        </div>
      </dl>
    </section>

    <!-- A supervisor's parts: their groups and students come from each
         student's own Supervisor and Group; their details are edited here. -->
    <section v-if="user?.role === 'supervisor'" class="admin-users-detail__section" data-test="admin-supervisor-groups">
      <div class="admin-users-detail__heading">
        <h3>Groups</h3>
        <button
          v-if="editable && editing !== 'supervisorGroups'"
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-edit-supervisor-groups"
          @click="startEdit('supervisorGroups')"
        >
          Edit
        </button>
      </div>
      <!-- Group 1, 2, …: a group added makes them every student's supervisor in
           it; one taken off leaves its students of theirs with none. -->
      <form v-if="editing === 'supervisorGroups'" data-test="admin-supervisor-groups-form" @submit.prevent="save">
        <div v-for="(groupId, index) in supervisorGroupSlots" :key="index" class="admin-users-detail__item">
          <label class="admin-users-detail__label" :for="`admin-supervisor-group-${index}`">Group {{ index + 1 }}</label>
          <AppSelect
            :id="`admin-supervisor-group-${index}`"
            size="large"
            :model-value="groupId"
            class="admin-users-detail__input"
            :data-test="`admin-supervisor-group-${index}`"
            :options="supervisorGroupOptions(index)"
            :loading="picksLoading"
            searchable
            placeholder="Choose a group"
            empty-text="No group matches"
            @update:model-value="(value) => pickSupervisorGroup(index, value)"
          />
        </div>
        <p v-if="picksError" class="admin-users-detail__save-error" role="alert">{{ picksError }}</p>
        <p v-if="saveError" class="admin-users-detail__save-error" role="alert">{{ saveError }}</p>
        <div class="admin-users-detail__actions">
          <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="cancelEdit">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </form>
      <dl v-else class="admin-users-detail__list">
        <div class="admin-users-detail__item">
          <dt>Groups</dt>
          <dd data-test="admin-supervisor-group-names">
            {{ (user.supervisorGroups || []).map((group) => group.name).join(', ') || '—' }}
          </dd>
        </div>
      </dl>
    </section>

    <section v-if="user?.role === 'supervisor'" class="admin-users-detail__section" data-test="admin-supervisor-details">
      <div class="admin-users-detail__heading">
        <h3>Supervisor Details</h3>
        <button
          v-if="editable && editing !== 'supervisorDetails'"
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-edit-supervisor-details"
          @click="startEdit('supervisorDetails')"
        >
          Edit
        </button>
      </div>
      <form v-if="editing === 'supervisorDetails'" data-test="admin-supervisor-details-form" @submit.prevent="save">
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">First name</span>
          <input v-model.trim="form.firstName" class="admin-users-detail__input" required maxlength="150" />
        </label>
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">Last name</span>
          <input v-model.trim="form.lastName" class="admin-users-detail__input" required maxlength="150" />
        </label>
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">School</span>
          <input
            v-model.trim="form.supervisorSchoolName"
            class="admin-users-detail__input"
            data-test="admin-supervisor-school"
            maxlength="255"
          />
        </label>
        <p v-if="saveError" class="admin-users-detail__save-error" role="alert">{{ saveError }}</p>
        <div class="admin-users-detail__actions">
          <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="cancelEdit">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </form>
      <dl v-else class="admin-users-detail__list">
        <div class="admin-users-detail__item">
          <dt>Name</dt>
          <dd>{{ [user.firstName, user.lastName].filter(Boolean).join(' ') || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>School</dt>
          <dd>{{ user.schoolName || '—' }}</dd>
        </div>
      </dl>
    </section>

    <section v-if="user?.role === 'supervisor'" class="admin-users-detail__section" data-test="admin-supervisees">
      <div class="admin-users-detail__heading">
        <h3>Supervisees</h3>
        <button
          v-if="editable && editing !== 'supervisees'"
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-edit-supervisees"
          @click="startEdit('supervisees')"
        >
          Edit
        </button>
      </div>
      <!-- Their students, each with its ×, and any student to add. -->
      <form v-if="editing === 'supervisees'" data-test="admin-supervisees-form" @submit.prevent="save">
        <div
          v-for="(student, index) in form.superviseeRows"
          :key="student.id"
          class="admin-users-detail__item"
          :data-test="`admin-supervisee-${index}`"
        >
          <span class="admin-users-detail__label">{{ student.name || student.email }}</span>
          <span class="admin-users-detail__supervisee">
            <span class="admin-users-detail__value">{{ student.email }}</span>
            <button
              type="button"
              class="admin-users-detail__slot-remove"
              :aria-label="`Take ${student.name || student.email} off`"
              @click="form.superviseeRows.splice(index, 1)"
            >
              <i class="fas fa-xmark" aria-hidden="true"></i>
            </button>
          </span>
        </div>
        <div class="admin-users-detail__item">
          <label class="admin-users-detail__label" for="admin-supervisee-add">Add a student</label>
          <AppSelect
            id="admin-supervisee-add"
            size="large"
            :model-value="null"
            class="admin-users-detail__input"
            data-test="admin-supervisee-add"
            :options="studentOptions"
            :loading="picksLoading"
            searchable
            placeholder="Search by name or email"
            empty-text="No student matches"
            @update:model-value="addSupervisee"
          />
        </div>
        <p v-if="picksError" class="admin-users-detail__save-error" role="alert">{{ picksError }}</p>
        <p v-if="saveError" class="admin-users-detail__save-error" role="alert">{{ saveError }}</p>
        <div class="admin-users-detail__actions">
          <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="cancelEdit">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </form>
      <dl v-else class="admin-users-detail__list">
        <div v-for="supervisee in user.supervisees || []" :key="supervisee.email" class="admin-users-detail__item">
          <dt>{{ supervisee.name || '—' }}</dt>
          <dd>{{ supervisee.email }}</dd>
        </div>
        <div v-if="!user.supervisees?.length" class="admin-users-detail__item">
          <dt>Students</dt>
          <dd>—</dd>
        </div>
      </dl>
    </section>

    <section v-if="user?.role === 'admin'" class="admin-users-detail__section">
      <h3>Admin Details</h3>
      <dl class="admin-users-detail__list">
        <div class="admin-users-detail__item" data-test="admin-admin-name">
          <dt>Name</dt>
          <dd>{{ [user.firstName, user.lastName].filter(Boolean).join(' ') || '—' }}</dd>
        </div>
      </dl>
    </section>

    <ConfirmDialog
      v-model="confirmOpen"
      :title="confirmSetup.title"
      :message="confirmSetup.message"
      confirm-label="Save"
      busy-label="Saving…"
      variant="warning"
      :busy="saving"
      @confirm="confirmSetup.confirm()"
    >
      <ul class="admin-users-detail__replacing" data-test="admin-replacing">
        <li v-for="line in confirmSetup.lines" :key="line">{{ line }}.</li>
      </ul>
    </ConfirmDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import AppSelect, { type AppSelectOption } from '@/components/AppSelect.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import {
  changeSupervisees,
  confirmMentorAssignments,
  confirmStudentAssignments,
  downloadGuardianConsentRecord,
  fetchAdminCountries,
  fetchAdminGroupList,
  fetchAdminStates,
  fetchAdminUser,
  fetchAdminUsers,
  fetchGuardianConsents,
  removeGroupMember,
  sendGuardianConsentRequest,
  setAdminUserActive,
  unassignMentors,
  updateAdminUser
} from '@/utils/adminAPI'
import type {
  AdminGroupDetail,
  AdminGuardianConsent,
  AdminUser,
  AdminUserCountry,
  AdminUserState,
  SuperviseeChange,
  SuperviseesChangeInput
} from '@/utils/adminAPI'
import { DEFAULT_GROUP_MAX_SIZE, studentCount } from '@/utils/groupCapacity'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatShortDateTime } from '@/utils/date'
import { keptDigits, refuseNonDigitKey, refuseNonDigitPaste } from '@/utils/digitsOnly'
import { isPlaceholderGuardian } from '@/utils/guardian'
import {
  formatFullDate,
  joinInterests,
  labelizeCountry,
  labelizeState,
  roleLabel,
  supervisorLabel,
  userName
} from '@/utils/userFormat'
import { INTEREST_OPTIONS } from '@/utils/userOptions'

const props = withDefaults(
  defineProps<{
    user: AdminUser | null
    /** Whether a student's parts each offer Edit (not on Matched Groups). */
    editable?: boolean
  }>(),
  { editable: true }
)

const emit = defineEmits<{
  (e: 'updated', user: AdminUser): void
}>()

const guardian = computed(() => {
  const user = props.user
  const placeholder = isPlaceholderGuardian(user?.guardianFirstName, user?.guardianLastName, user?.firstName, user?.lastName)
  return {
    name: placeholder ? '' : `${user?.guardianFirstName || ''} ${user?.guardianLastName || ''}`.trim(),
    // Consent with no form response on record is what the old admin path
    // granted as a side effect — flag it rather than show it as received.
    consent: !user?.joinPermissionReceived ? 'missing' : user.joinpermResponseId ? 'received' : 'unverified'
  }
})

// An answer and when it was given, as the supervisor's panel shows them:
// "Yes, 14/10/26 21:30".
const answeredAt = (answer: string, at: string | null | undefined) =>
  [answer, formatShortDateTime(at)].filter(Boolean).join(', ')

// Only a given permission is recorded; a guardian never answers no.
const permissionLabel = computed(() =>
  props.user?.joinPermissionReceived ? answeredAt('Yes', props.user.joinPermissionGrantedAt) : '—'
)

// Who a consent request would go to: a requested guardian change first, else
// the guardian on file while consent is still missing. Mirrors the backend.
const consentRequestTo = computed(() => {
  const user = props.user
  if (!user) return null
  if (user.pendingGuardian) return user.pendingGuardian.email
  if (user.joinPermissionReceived) return null
  return user.guardianEmail
})

const sendingRequest = ref(false)
const requestMessage = ref('')
const requestFailed = ref(false)

watch(() => props.user?.id, () => {
  editing.value = null
  requestMessage.value = ''
  requestFailed.value = false
  consents.value = []
  consentsOpen.value = false
  consentsMessage.value = ''
  consentsFailed.value = false
})

// --- a student's parts, each edited in place ----------------------------------

// Roles whose parts each have their own Edit; an admin keeps the sheet's own.
const EDITED_IN_PARTS = ['student', 'mentor', 'supervisor']

type Part =
  | 'account'
  | 'supervisorDetails'
  | 'supervisorGroups'
  | 'supervisees'
  | 'details'
  | 'guardian'
  | 'supervisor'
  | 'mentorGroups'
  | 'mentorDetails'
  | 'availability'
  | 'application'

const YEAR_OPTIONS: AppSelectOption[] = [9, 10, 11, 12].map((year) => ({ value: year, label: String(year) }))

const editing = ref<Part | null>(null)
const saving = ref(false)
const saveError = ref('')

const STATUS_OPTIONS: AppSelectOption[] = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' }
]

const blankForm = () => ({
  email: '',
  status: 'active' as AppSelectOption['value'],
  countryId: null as number | null,
  stateId: null as number | null,
  stateName: '',
  firstName: '',
  lastName: '',
  schoolName: '',
  yearLevel: null as AppSelectOption['value'],
  interests: [] as string[],
  guardianFirstName: '',
  guardianLastName: '',
  guardianEmail: '',
  consentGiven: false,
  mediaGiven: false,
  pendingConsentGiven: false,
  supervisorEmail: '',
  groupId: null as number | null,
  mentorGroupIds: [] as number[],
  mentorBackground: null as AppSelectOption['value'],
  mentorCompany: '',
  mentorInstitution: '',
  mentorUniversityYear: null as AppSelectOption['value'],
  mentorFieldOfStudy: '',
  mentorCapacity: null as AppSelectOption['value'],
  mentorWeeklyHours: '' as string | number,
  mentorAvailability: [] as MentorSlot[],
  mentorRelevantBackground: '',
  supervisorSchoolName: '',
  supervisorGroupIds: [] as number[],
  superviseeRows: [] as { id: number; name: string; email: string }[],
  mentorReason: '',
  mentorMentoringApproach: ''
})
const form = reactive(blankForm())

const startEdit = (part: Part) => {
  const user = props.user
  if (!user) return
  Object.assign(form, blankForm(), {
    email: user.email || '',
    status: user.isActive ? 'active' : 'inactive',
    countryId: user.country?.id ?? null,
    stateId: user.state?.id ?? null,
    stateName: user.state?.stateName || '',
    firstName: user.firstName || '',
    lastName: user.lastName || '',
    schoolName: user.schoolName || '',
    yearLevel: user.yearLevel ?? null,
    // A mentor keeps expertise from outside the list; a student picks from it.
    interests:
      user.role === 'mentor'
        ? [...(user.interests || [])]
        : (user.interests || []).filter((interest) => INTEREST_OPTIONS.includes(interest)),
    // A placeholder guardian (the student's own name) is no guardian at all.
    guardianFirstName: guardian.value.name ? user.guardianFirstName || '' : '',
    guardianLastName: guardian.value.name ? user.guardianLastName || '' : '',
    guardianEmail: user.guardianEmail || '',
    consentGiven: Boolean(user.joinPermissionReceived),
    mediaGiven: Boolean(user.joinPermissionReceived) && user.mediaConsent === true,
    supervisorEmail: (user.supervisorEmail || '').toLowerCase(),
    groupId: user.groupId ?? null,
    mentorGroupIds: (user.mentorGroups || []).map((group) => group.id),
    mentorBackground: user.mentorBackground || null,
    mentorCompany: user.mentorCompany || '',
    mentorInstitution: user.mentorInstitution || '',
    mentorUniversityYear: user.mentorUniversityYear || null,
    mentorFieldOfStudy: user.mentorFieldOfStudy || '',
    mentorCapacity: user.mentorMaxGroupCount ?? null,
    mentorWeeklyHours: user.mentorWeeklyHours ?? '',
    mentorAvailability: (user.mentorAvailability || []).map(splitSlot),
    mentorRelevantBackground: user.mentorRelevantBackground || '',
    supervisorSchoolName: user.role === 'supervisor' ? user.schoolName || '' : '',
    supervisorGroupIds: (user.supervisorGroups || []).map((group) => group.id),
    superviseeRows: (user.supervisees || []).flatMap((student) =>
      student.id ? [{ id: student.id, name: student.name, email: student.email }] : []
    ),
    mentorReason: user.mentorReason || '',
    mentorMentoringApproach: user.mentorMentoringApproach || ''
  })
  saveError.value = ''
  editing.value = part
  if (part === 'supervisor') loadPicks()
  if (part === 'account') loadPlaces()
  if (part === 'mentorGroups' || part === 'supervisorGroups') loadGroups()
  if (part === 'supervisees') loadStudents()
}

const cancelEdit = () => {
  editing.value = null
  saveError.value = ''
}

// What a part's Save sends: only what it changes, so the rest stays as it is.
const payloadFor = (part: Part): Record<string, unknown> | string => {
  const user = props.user!
  if (part === 'account') {
    const email = form.email.toLowerCase()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'Enter a valid email address.'
    const account: Record<string, unknown> = {}
    if (email !== (user.email || '').toLowerCase()) account.email = email
    // The pair goes together, so a new country never keeps the old state:
    // Australia's picked, elsewhere's typed.
    const countryChanged = form.countryId !== (user.country?.id ?? null)
    if (inAustralia.value) {
      if (form.stateId === null) return 'Choose a state or territory.'
      if (countryChanged || form.stateId !== (user.state?.id ?? null)) {
        account.countryId = form.countryId
        account.stateId = form.stateId
      }
    } else if (countryChanged || form.stateName !== (user.state?.stateName || '')) {
      account.countryId = form.countryId
      account.stateName = form.stateName
    }
    if ('countryId' in account && form.countryId === null) return 'Choose a country.'
    return account
  }
  if (part === 'mentorDetails') return mentorDetailsPayload()
  if (part === 'application') return applicationPayload()
  if (part === 'availability') return availabilityPayload()
  if (part === 'supervisorDetails') {
    if (!form.firstName || !form.lastName) return 'Enter their first and last name.'
    return { firstName: form.firstName, lastName: form.lastName, supervisorSchoolName: form.supervisorSchoolName }
  }
  if (part === 'details') {
    if (form.yearLevel === null) return 'Choose a year level.'
    if (!form.interests.length) return 'Choose at least one interest.'
    return {
      firstName: form.firstName,
      lastName: form.lastName,
      schoolName: form.schoolName,
      yearLevel: form.yearLevel,
      interests: form.interests
    }
  }
  const payload: Record<string, unknown> = {}
  const wasFirst = guardian.value.name ? user.guardianFirstName || '' : ''
  const wasLast = guardian.value.name ? user.guardianLastName || '' : ''
  if (form.guardianFirstName !== wasFirst || form.guardianLastName !== wasLast) {
    if (!form.guardianFirstName || !form.guardianLastName) return "Enter the guardian's first and last name."
    payload.guardianFirstName = form.guardianFirstName
    payload.guardianLastName = form.guardianLastName
  }
  if (form.guardianEmail !== (user.guardianEmail || '')) payload.guardianEmail = form.guardianEmail
  // As the full form records them: the new guardian's consent, a change to
  // consent, or media consent alone.
  const consentWas = Boolean(user.joinPermissionReceived)
  const mediaWas = consentWas && user.mediaConsent === true
  if (user.pendingGuardian && form.pendingConsentGiven) {
    payload.consentGiven = true
    payload.mediaConsent = form.mediaGiven
  } else if (form.consentGiven !== consentWas) {
    payload.consentGiven = form.consentGiven
    if (form.consentGiven) payload.mediaConsent = form.mediaGiven
  } else if (form.consentGiven && form.mediaGiven !== mediaWas) {
    payload.mediaConsent = form.mediaGiven
  }
  return payload
}

const save = async () => {
  const user = props.user
  const part = editing.value
  if (!user || !part || saving.value) return
  if (part === 'supervisor') {
    saveSupervisorAndGroup()
    return
  }
  if (part === 'mentorGroups') {
    saveMentorGroups()
    return
  }
  if (part === 'supervisorGroups' || part === 'supervisees') {
    saveSupervisees(superviseeLists(part))
    return
  }
  const payload = payloadFor(part)
  if (typeof payload === 'string') {
    saveError.value = payload
    return
  }
  // Account's Status is set on its own.
  const active = form.status === 'active'
  const statusChanged = part === 'account' && active !== Boolean(user.isActive)
  if (!Object.keys(payload).length && !statusChanged) {
    cancelEdit()
    return
  }
  saving.value = true
  saveError.value = ''
  let updated: AdminUser | null = null
  try {
    if (Object.keys(payload).length) {
      const result = await updateAdminUser(user.id, payload)
      if (!result.data) {
        saveError.value = result.msg || 'The change could not be saved.'
        return
      }
      updated = result.data
    }
    if (statusChanged) updated = (await setAdminUserActive(user.id, active)).data
    editing.value = null
  } catch (error) {
    saveError.value = apiErrorFromUnknown(error, 'The change could not be saved.').message
  } finally {
    // What did save shows, even when the status after it didn't.
    if (updated) emit('updated', updated)
    saving.value = false
  }
}

// --- Account: the country and state picked from lists ------------------------

const countryList = ref<AdminUserCountry[]>([])
const stateList = ref<AdminUserState[]>([])
const placesLoading = ref(false)
const placesError = ref('')

// Loaded once: the countries and states hardly change.
const loadPlaces = async () => {
  if (countryList.value.length) return
  placesLoading.value = true
  placesError.value = ''
  try {
    const [countries, states] = await Promise.all([fetchAdminCountries(), fetchAdminStates()])
    countryList.value = countries
    stateList.value = states
  } catch (error) {
    placesError.value = apiErrorFromUnknown(error, 'Could not load the countries and states.').message
  } finally {
    placesLoading.value = false
  }
}

const byLabel = (a: AppSelectOption, b: AppSelectOption) => a.label.localeCompare(b.label)

const countryOptions = computed<AppSelectOption[]>(() =>
  countryList.value.map((country) => ({ value: country.id, label: country.countryName })).sort(byLabel)
)

// The chosen country's name, known before the list loads for their own.
const countryName = computed(
  () =>
    countryList.value.find((country) => country.id === form.countryId)?.countryName ??
    (form.countryId === props.user?.country?.id ? props.user?.country?.countryName : undefined)
)
const inAustralia = computed(() => countryName.value === 'Australia')

// Australia's states: one is needed, as registering asks.
const stateOptions = computed<AppSelectOption[]>(() =>
  stateList.value
    .filter((state) => state.countryName === countryName.value)
    .map((state) => ({ value: state.id, label: state.stateName }))
    .sort(byLabel)
)

// A new country clears the state, which belonged to the old one.
const pickCountry = (value: AppSelectOption['value']) => {
  if (value === form.countryId) return
  form.countryId = value as number | null
  form.stateId = null
  form.stateName = ''
}

// --- Supervisor and Group: picked from lists ---------------------------------

const supervisorList = ref<AdminUser[]>([])
const groupList = ref<AdminGroupDetail[]>([])
const picksLoading = ref(false)
const picksError = ref('')

const fetchAllGroups = async () => {
  const groups: AdminGroupDetail[] = []
  for (let page = 1; page <= 20; page += 1) {
    const data = await fetchAdminGroupList({ page, limit: 200 })
    // The list gives each id as text; a user's own groups give numbers.
    groups.push(...data.items.map((group) => ({ ...group, id: Number(group.id) })))
    if (!data.has_more) break
  }
  return groups
}

// Every group, fresh each time a mentor's Groups Edit is pressed.
const loadGroups = async () => {
  picksLoading.value = true
  picksError.value = ''
  try {
    groupList.value = await fetchAllGroups()
  } catch (error) {
    picksError.value = apiErrorFromUnknown(error, 'Could not load the groups.').message
  } finally {
    picksLoading.value = false
  }
}

// Every supervisor and group, fresh each time Edit is pressed so the seats
// left are current.
const loadPicks = async () => {
  picksLoading.value = true
  picksError.value = ''
  try {
    const [supervisors, groups] = await Promise.all([
      fetchAdminUsers({ page: 1, limit: 200, role: 'supervisor' }),
      fetchAllGroups()
    ])
    supervisorList.value = supervisors.items
    groupList.value = groups
  } catch (error) {
    picksError.value = apiErrorFromUnknown(error, 'Could not load the supervisors and groups.').message
  } finally {
    picksLoading.value = false
  }
}

// By name, with the email underneath; the one they have stays a choice even
// when it isn't in the list.
const supervisorOptions = computed<AppSelectOption[]>(() => {
  const options = supervisorList.value
    .flatMap((supervisor) => {
      const email = supervisor.email
      return email ? [{ value: email.toLowerCase(), label: userName(supervisor) || email, detail: email }] : []
    })
    .sort((a, b) => a.label.localeCompare(b.label))
  const current = (props.user?.supervisorEmail || '').toLowerCase()
  if (current && !options.some((option) => option.value === current)) {
    options.unshift({ value: current, label: props.user?.supervisorName || current, detail: current })
  }
  return options
})

// "No group" first, then each group with its seats taken; a full one can't
// be picked, unless it's theirs.
const groupOptions = computed<AppSelectOption[]>(() => {
  const currentId = props.user?.groupId ?? null
  const groups: AppSelectOption[] = [...groupList.value]
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))
    .map((group) => {
      const taken = studentCount(group)
      const full = taken >= DEFAULT_GROUP_MAX_SIZE && group.id !== currentId
      return {
        value: group.id,
        label: group.name,
        detail: `${taken}/${DEFAULT_GROUP_MAX_SIZE} students${full ? ' · Full' : ''}`,
        disabled: full
      }
    })
  if (currentId !== null && !groups.some((option) => option.value === currentId)) {
    groups.unshift({ value: currentId, label: props.user?.groupName || 'Their group' })
  }
  return [{ value: null, label: 'No group', detail: 'Not in a group' }, ...groups]
})

const optionLabel = (options: AppSelectOption[], value: AppSelectOption['value']) =>
  options.find((option) => option.value === value)?.label ?? String(value)

const supervisorChanged = computed(
  () => Boolean(form.supervisorEmail) && form.supervisorEmail !== (props.user?.supervisorEmail || '').toLowerCase()
)
const groupChanged = computed(() => form.groupId !== (props.user?.groupId ?? null))

// What Save would replace, for the popup: nothing when they had none.
const replacing = computed(() => {
  const user = props.user
  if (!user) return []
  const lines: string[] = []
  if (supervisorChanged.value && user.supervisorEmail) {
    lines.push(
      `Change supervisor from ${user.supervisorName || user.supervisorEmail} to ` +
        optionLabel(supervisorOptions.value, form.supervisorEmail)
    )
  }
  if (groupChanged.value && user.groupId != null) {
    lines.push(
      form.groupId === null
        ? `Take them out of ${user.groupName || 'their group'}`
        : `Move them from ${user.groupName || 'their group'} to ${optionLabel(groupOptions.value, form.groupId)}`
    )
  }
  return lines
})

const confirmOpen = ref(false)

const saveSupervisorAndGroup = () => {
  if (!supervisorChanged.value && !groupChanged.value) {
    cancelEdit()
    return
  }
  if (replacing.value.length) {
    confirmOpen.value = true
    return
  }
  commitSupervisorAndGroup()
}

// The supervisor first, so the group move brings the right one into it.
const commitSupervisorAndGroup = async () => {
  const user = props.user
  if (!user || saving.value) return
  saving.value = true
  saveError.value = ''
  let updated: AdminUser | null = null
  try {
    if (supervisorChanged.value) {
      const result = await updateAdminUser(user.id, { supervisorEmail: form.supervisorEmail })
      if (!result.data) {
        saveError.value = result.msg || 'The change could not be saved.'
        return
      }
      updated = result.data
    }
    if (groupChanged.value) {
      if (form.groupId === null) await removeGroupMember(user.groupId!, user.id)
      else await confirmStudentAssignments([{ studentId: user.id, groupId: form.groupId }])
      updated = await fetchAdminUser(user.id)
    }
    editing.value = null
  } catch (error) {
    saveError.value = apiErrorFromUnknown(error, 'The change could not be saved.').message
  } finally {
    // What did save shows, even when the group move after it didn't.
    if (updated) emit('updated', updated)
    saving.value = false
    confirmOpen.value = false
  }
}

// --- a mentor's parts ----------------------------------------------------------

// As the registration form offers them (apps.users.mentor_registration).
const MENTOR_BACKGROUNDS: AppSelectOption[] = [
  { value: 'undergraduate', label: 'University Student - Undergraduate' },
  { value: 'postgraduate', label: 'University Student - Postgraduate' },
  { value: 'hdr', label: 'University Student - HDR' },
  { value: 'academic', label: 'Academic / research staff' },
  { value: 'industry', label: 'Industry' }
]
const STUDY_YEAR_OPTIONS: AppSelectOption[] = [
  { value: '1', label: 'Year 1' },
  { value: '2', label: 'Year 2' },
  { value: '3', label: 'Year 3' },
  { value: '4', label: 'Year 4' },
  { value: '5+', label: 'Year 5 or later' }
]
// Hours a week they can give, as registering asks: 1 to 40.
const MAX_WEEKLY_HOURS = 40

// A weekly time they're free (Monday is 0), each end as its hour and its
// minutes, put back together as "HH:MM" to save.
interface MentorSlot {
  weekday: AppSelectOption['value']
  startHour: AppSelectOption['value']
  startMinute: AppSelectOption['value']
  endHour: AppSelectOption['value']
  endMinute: AppSelectOption['value']
}
const blankSlot = (): MentorSlot => ({
  weekday: null,
  startHour: null,
  startMinute: null,
  endHour: null,
  endMinute: null
})
const splitSlot = (slot: { weekday: number; start: string; end: string }): MentorSlot => ({
  weekday: slot.weekday,
  startHour: slot.start.slice(0, 2),
  startMinute: slot.start.slice(3, 5),
  endHour: slot.end.slice(0, 2),
  endMinute: slot.end.slice(3, 5)
})

const twoDigits = (count: number) => String(count).padStart(2, '0')
const HOUR_OPTIONS: AppSelectOption[] = Array.from({ length: 24 }, (_, hour) => ({
  value: twoDigits(hour),
  label: twoDigits(hour)
}))
// 00 to 55 in 5-minute steps; minutes saved between them stay a choice.
const FIVE_MINUTES: AppSelectOption[] = Array.from({ length: 12 }, (_, step) => ({
  value: twoDigits(step * 5),
  label: twoDigits(step * 5)
}))
const minuteOptions = (current: AppSelectOption['value']): AppSelectOption[] =>
  typeof current === 'string' && current && !FIVE_MINUTES.some((option) => option.value === current)
    ? [...FIVE_MINUTES, { value: current, label: current }].sort((a, b) => a.label.localeCompare(b.label))
    : FIVE_MINUTES

// An hour picked first takes :00 until its minutes are picked.
const pickHour = (slot: MentorSlot, end: 'start' | 'end', hour: AppSelectOption['value']) => {
  if (end === 'start') {
    slot.startHour = hour
    slot.startMinute ??= '00'
  } else {
    slot.endHour = hour
    slot.endMinute ??= '00'
  }
}
const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const WEEKDAY_OPTIONS: AppSelectOption[] = WEEKDAYS.map((day, index) => ({ value: index, label: day }))

// Each time given in full and ending after it starts; a row left empty is dropped.
const availabilityPayload = (): Record<string, unknown> | string => {
  const availability = []
  for (const slot of form.mentorAvailability) {
    const parts = [slot.weekday, slot.startHour, slot.startMinute, slot.endHour, slot.endMinute]
    if (parts.every((part) => part === null)) continue
    if (parts.some((part) => part === null)) return 'Give each weekly time a day and both times.'
    const start = `${slot.startHour}:${slot.startMinute}`
    const end = `${slot.endHour}:${slot.endMinute}`
    if (end <= start) return 'Each weekly time must end after it starts.'
    availability.push({ weekday: slot.weekday, start, end })
  }
  return { mentorAvailability: availability }
}
const MAX_ANSWER_WORDS = 150
const APPLICATION_QUESTIONS = [
  { key: 'mentorRelevantBackground', field: 'mentorRelevantBackground', label: 'Relevant background' },
  { key: 'mentorReason', field: 'mentorReason', label: 'Why would you like to mentor?' },
  { key: 'mentorMentoringApproach', field: 'mentorMentoringApproach', label: 'How would you mentor BIOTech groups?' }
] as const

const isStudyingBackground = (background: AppSelectOption['value'] | undefined) =>
  background === 'undergraduate' || background === 'postgraduate'
const mentorStudying = computed(() => isStudyingBackground(form.mentorBackground))

// Older mentors' backgrounds were typed; they show, and stay a choice, as written.
const mentorBackgroundLabel = (background: string | null | undefined) =>
  MENTOR_BACKGROUNDS.find((option) => option.value === background)?.label ?? (background || '—')
const mentorBackgroundOptions = computed<AppSelectOption[]>(() => {
  const current = props.user?.mentorBackground
  return current && !MENTOR_BACKGROUNDS.some((option) => option.value === current)
    ? [...MENTOR_BACKGROUNDS, { value: current, label: current }]
    : MENTOR_BACKGROUNDS
})
const studyYearLabel = (year: string | null | undefined) =>
  STUDY_YEAR_OPTIONS.find((option) => option.value === year)?.label ?? (year || '—')

const mentorCapacity = computed(() => props.user?.mentorMaxGroupCount ?? 0)
const capacityLabel = (count: number | null | undefined) =>
  count == null ? '—' : `${count} ${count === 1 ? 'group' : 'groups'}`
// 1 to 5 as registering offers, and whatever they have now.
const mentorCapacityOptions = computed<AppSelectOption[]>(() => {
  const counts = new Set([1, 2, 3, 4, 5])
  if (props.user?.mentorMaxGroupCount != null) counts.add(props.user.mentorMaxGroupCount)
  return [...counts].sort((a, b) => a - b).map((count) => ({ value: count, label: capacityLabel(count) }))
})

// The standard interests, and any expertise they have from outside them.
const mentorInterestOptions = computed(() => [
  ...INTEREST_OPTIONS,
  ...(props.user?.interests || []).filter((interest) => !INTEREST_OPTIONS.includes(interest))
])

// Hours per week: a number box taking two digits at most.
const onHoursInput = (event: Event) => {
  form.mentorWeeklyHours = keptDigits(event.target as HTMLInputElement, 2)
}

const hoursLabel = (hours: number | null | undefined) =>
  hours ? `${hours} ${hours === 1 ? 'hour' : 'hours'}` : '—'

// An answer's box grows with what's written, from its 9 rows, rather than
// scrolling.
const growToFit = (box: HTMLTextAreaElement) => {
  box.style.height = ''
  if (box.scrollHeight > box.clientHeight) {
    box.style.height = `${box.scrollHeight + box.offsetHeight - box.clientHeight}px`
  }
}
const vAutoGrow = { mounted: growToFit, updated: growToFit }

const wordCount = (text: string) => (text.trim() ? text.trim().split(/\s+/).length : 0)

const mentorDetailsPayload = (): Record<string, unknown> | string => {
  const background = form.mentorBackground as string | null
  if (!background) return 'Choose a background.'
  const industry = background === 'industry'
  const listed = MENTOR_BACKGROUNDS.some((option) => option.value === background)
  if (industry && !form.mentorCompany) return 'Enter their company or organisation.'
  if (!industry && !form.mentorInstitution) return 'Enter their university or institution.'
  if (!industry && listed && !form.mentorFieldOfStudy) return 'Enter their field of study or research.'
  if (mentorStudying.value && !form.mentorUniversityYear) return 'Choose their year of study.'
  if (!form.interests.length) return 'Choose at least one interest.'
  if (form.mentorCapacity === null) return 'Choose their capacity.'
  // Hours a week: a whole number from 1 to 40, or left empty.
  const hours = String(form.mentorWeeklyHours ?? '').trim()
  if (hours && (!/^\d+$/.test(hours) || Number(hours) < 1 || Number(hours) > MAX_WEEKLY_HOURS)) {
    return `Hours per week must be a whole number from 1 to ${MAX_WEEKLY_HOURS}.`
  }
  // What the background doesn't ask for is cleared, as registering does.
  return {
    firstName: form.firstName,
    lastName: form.lastName,
    mentorBackground: background,
    mentorCompany: industry ? form.mentorCompany : '',
    mentorInstitution: industry ? '' : form.mentorInstitution,
    mentorUniversityYear: mentorStudying.value ? form.mentorUniversityYear : '',
    mentorFieldOfStudy: industry ? '' : form.mentorFieldOfStudy,
    interests: form.interests,
    mentorMaxGroupCount: form.mentorCapacity,
    mentorWeeklyHours: hours ? Number(hours) : null
  }
}

const applicationPayload = (): Record<string, unknown> | string => {
  if (!form.mentorReason.trim()) return 'Say why they would like to mentor.'
  for (const question of APPLICATION_QUESTIONS) {
    if (wordCount(form[question.key]) > MAX_ANSWER_WORDS) {
      return `Keep each answer to ${MAX_ANSWER_WORDS} words or fewer.`
    }
  }
  return {
    mentorRelevantBackground: form.mentorRelevantBackground.trim(),
    mentorReason: form.mentorReason.trim(),
    mentorMentoringApproach: form.mentorMentoringApproach.trim()
  }
}

// Groups: what they mentor now, and each Group N's choice.
const mentorGroupNames = computed(() => (props.user?.mentorGroups || []).map((group) => group.name).join(', '))
const mentorGroupSlots = computed<(number | null)[]>(() =>
  form.mentorGroupIds.length < mentorCapacity.value ? [...form.mentorGroupIds, null] : [...form.mentorGroupIds]
)
const mentorCapacityNote = computed(() =>
  mentorCapacity.value
    ? `That's their capacity of ${capacityLabel(mentorCapacity.value)}; raise it in Mentor Details for more.`
    : 'Their capacity is 0 groups; raise it in Mentor Details to give them one.'
)

const mentorOf = (group: AdminGroupDetail) => group.mentor && Number(group.mentor.id) !== props.user?.id ? group.mentor : null

// Every group not picked in another slot: its students and its mentor under it.
// A filled slot can be emptied ("No group").
const mentorGroupOptions = (index: number): AppSelectOption[] => {
  const pickedElsewhere = new Set(form.mentorGroupIds.filter((_, at) => at !== index))
  const groups = [...groupList.value]
    .filter((group) => !pickedElsewhere.has(group.id))
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))
    .map((group) => {
      const other = mentorOf(group)
      const taken = studentCount(group)
      return {
        value: group.id,
        label: group.name,
        detail: `${taken} ${taken === 1 ? 'student' : 'students'} · ${other ? `mentor: ${other.name}` : group.mentor ? 'theirs' : 'no mentor'}`
      }
    })
  // Theirs stays a choice even before the list loads.
  for (const group of props.user?.mentorGroups || []) {
    if (!pickedElsewhere.has(group.id) && !groups.some((option) => option.value === group.id)) {
      groups.unshift({ value: group.id, label: group.name, detail: 'theirs' })
    }
  }
  const filled = form.mentorGroupIds[index] !== undefined
  return filled ? [{ value: null, label: 'No group', detail: 'Take them off this group' }, ...groups] : groups
}

const pickMentorGroup = (index: number, value: AppSelectOption['value']) => {
  if (value === null) form.mentorGroupIds.splice(index, 1)
  else form.mentorGroupIds[index] = value as number
}

const mentorGroupChanges = computed(() => {
  const had = (props.user?.mentorGroups || []).map((group) => group.id)
  return {
    removed: had.filter((id) => !form.mentorGroupIds.includes(id)),
    added: form.mentorGroupIds.filter((id) => !had.includes(id))
  }
})

const groupNameOf = (id: number) =>
  groupList.value.find((group) => group.id === id)?.name ??
  props.user?.mentorGroups?.find((group) => group.id === id)?.name ??
  `group ${id}`

// What Save would take away, for the popup: a group they had, or one's other mentor.
const mentorGroupReplacing = computed(() => {
  const { removed, added } = mentorGroupChanges.value
  const lines = removed.map((id) => `Take them off ${groupNameOf(id)}`)
  for (const id of added) {
    const group = groupList.value.find((candidate) => candidate.id === id)
    const other = group ? mentorOf(group) : null
    if (other) lines.push(`Replace ${other.name} as ${groupNameOf(id)}'s mentor`)
  }
  return lines
})

const saveMentorGroups = () => {
  const { removed, added } = mentorGroupChanges.value
  if (!removed.length && !added.length) {
    cancelEdit()
    return
  }
  if (mentorGroupReplacing.value.length) {
    confirmOpen.value = true
    return
  }
  commitMentorGroups()
}

// Off the old ones first, so their capacity has room for the new.
const commitMentorGroups = async () => {
  const user = props.user
  if (!user || saving.value) return
  const { removed, added } = mentorGroupChanges.value
  saving.value = true
  saveError.value = ''
  let changed = false
  try {
    if (removed.length) {
      await unassignMentors(removed)
      changed = true
    }
    if (added.length) {
      await confirmMentorAssignments(added.map((groupId) => ({ groupId, mentorUserId: user.id })))
      changed = true
    }
    editing.value = null
  } catch (error) {
    saveError.value = apiErrorFromUnknown(error, 'The change could not be saved.').message
  } finally {
    // What did save shows, even when a later step didn't.
    if (changed) {
      try {
        emit('updated', await fetchAdminUser(user.id))
      } catch {
        // The page shows what it had; a reload brings the rest.
      }
    }
    saving.value = false
    confirmOpen.value = false
  }
}

// --- a supervisor's groups and students ------------------------------------------

// Groups: Group 1, 2, …, with a new one after the last picked.
const supervisorGroupSlots = computed<(number | null)[]>(() => [...form.supervisorGroupIds, null])

const supervisorGroupOptions = (index: number): AppSelectOption[] => {
  const pickedElsewhere = new Set(form.supervisorGroupIds.filter((_, at) => at !== index))
  const groups: AppSelectOption[] = [...groupList.value]
    .filter((group) => !pickedElsewhere.has(group.id))
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))
    .map((group) => {
      const taken = studentCount(group)
      return { value: group.id, label: group.name, detail: `${taken} ${taken === 1 ? 'student' : 'students'}` }
    })
  for (const group of props.user?.supervisorGroups || []) {
    if (!pickedElsewhere.has(group.id) && !groups.some((option) => option.value === group.id)) {
      groups.unshift({ value: group.id, label: group.name, detail: 'theirs' })
    }
  }
  return form.supervisorGroupIds[index] !== undefined
    ? [{ value: null, label: 'No group', detail: 'Take them off this group' }, ...groups]
    : groups
}

const pickSupervisorGroup = (index: number, value: AppSelectOption['value']) => {
  if (value === null) form.supervisorGroupIds.splice(index, 1)
  else form.supervisorGroupIds[index] = value as number
}

// Supervisees: every student, to add one; who supervises them now under each.
const studentList = ref<AdminUser[]>([])

const loadStudents = async () => {
  picksLoading.value = true
  picksError.value = ''
  try {
    const students: AdminUser[] = []
    for (let page = 1; page <= 25; page += 1) {
      const data = await fetchAdminUsers({ page, limit: 200, role: 'student' })
      students.push(...data.items)
      if (!data.hasMore) break
    }
    studentList.value = students
  } catch (error) {
    picksError.value = apiErrorFromUnknown(error, 'Could not load the students.').message
  } finally {
    picksLoading.value = false
  }
}

const studentOptions = computed<AppSelectOption[]>(() => {
  const listed = new Set(form.superviseeRows.map((student) => student.id))
  return studentList.value
    .filter((student) => !listed.has(student.id))
    .map((student) => ({
      value: student.id,
      label: userName(student) || student.email || `Student ${student.id}`,
      detail: [
        student.email,
        student.groupName || 'no group',
        student.supervisorName ? `supervisor: ${student.supervisorName}` : 'no supervisor'
      ]
        .filter(Boolean)
        .join(' · ')
    }))
    .sort((a, b) => a.label.localeCompare(b.label))
})

const addSupervisee = (value: AppSelectOption['value']) => {
  const student = studentList.value.find((candidate) => candidate.id === value)
  if (!student) return
  form.superviseeRows.push({ id: student.id, name: userName(student), email: student.email || '' })
}

// What a part's Save asks for: the groups or students added and taken off.
const superviseeLists = (part: Part): SuperviseesChangeInput => {
  if (part === 'supervisorGroups') {
    const had = (props.user?.supervisorGroups || []).map((group) => group.id)
    return {
      addGroupIds: form.supervisorGroupIds.filter((id) => !had.includes(id)),
      removeGroupIds: had.filter((id) => !form.supervisorGroupIds.includes(id))
    }
  }
  const had = (props.user?.supervisees || []).flatMap((student) => (student.id ? [student.id] : []))
  const now = form.superviseeRows.map((student) => student.id)
  return {
    addStudentIds: now.filter((id) => !had.includes(id)),
    removeStudentIds: had.filter((id) => !now.includes(id))
  }
}

const pendingSupervisees = ref<SuperviseesChangeInput | null>(null)
const superviseeChanges = ref<SuperviseeChange[]>([])

const joinNames = (names: string[]) =>
  names.length > 1 ? `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}` : (names[0] ?? '')

// The warning: who moves from another supervisor, and who's left with none,
// a group's together.
const superviseeLines = computed(() => {
  const lines = new Map<string, { prefix: string; names: string[]; end: (many: boolean) => string }>()
  for (const change of superviseeChanges.value) {
    if (change.from && change.to) {
      const key = `move|${change.group}|${change.from}`
      if (!lines.has(key)) {
        lines.set(key, {
          prefix: change.group ? `${change.group}: ` : '',
          names: [],
          end: (many) => `${many ? 'move' : 'moves'} from ${change.from} to ${change.to}`
        })
      }
      lines.get(key)!.names.push(change.name)
    } else if (!change.to) {
      const key = `none|${change.group}`
      if (!lines.has(key)) {
        lines.set(key, {
          prefix: change.group ? `${change.group}: ` : '',
          names: [],
          end: () => 'will have no supervisor'
        })
      }
      lines.get(key)!.names.push(change.name)
    }
  }
  return [...lines.values()].map(({ prefix, names, end }) => `${prefix}${joinNames(names)} ${end(names.length > 1)}`)
})

// First asked as a preview: anyone moving from another supervisor, or left
// with none, is warned of before anything changes.
const saveSupervisees = async (lists: SuperviseesChangeInput) => {
  const user = props.user
  if (!user || saving.value) return
  if (!Object.values(lists).some((ids) => ids?.length)) {
    cancelEdit()
    return
  }
  saving.value = true
  saveError.value = ''
  let changes: SuperviseeChange[]
  try {
    changes = (await changeSupervisees(user.id, { ...lists, preview: true })).changes
  } catch (error) {
    saveError.value = apiErrorFromUnknown(error, 'The change could not be saved.').message
    return
  } finally {
    saving.value = false
  }
  if (!changes.length) {
    cancelEdit()
    return
  }
  pendingSupervisees.value = lists
  superviseeChanges.value = changes
  if (superviseeLines.value.length) confirmOpen.value = true
  else commitSupervisees()
}

const commitSupervisees = async () => {
  const user = props.user
  const lists = pendingSupervisees.value
  if (!user || !lists || saving.value) return
  saving.value = true
  saveError.value = ''
  try {
    const result = await changeSupervisees(user.id, lists)
    if (result.user) emit('updated', result.user)
    editing.value = null
  } catch (error) {
    saveError.value = apiErrorFromUnknown(error, 'The change could not be saved.').message
  } finally {
    saving.value = false
    confirmOpen.value = false
  }
}

// The popup, for whichever part is saving.
const confirmSetup = computed(() => {
  const name = userName(props.user)
  if (editing.value === 'mentorGroups') {
    return {
      title: 'Change their groups?',
      message: `This changes the groups ${name} mentors. Saving will:`,
      lines: mentorGroupReplacing.value,
      confirm: commitMentorGroups
    }
  }
  if (editing.value === 'supervisorGroups' || editing.value === 'supervisees') {
    return {
      title: 'Change their students?',
      message: `This changes who ${name} supervises. Saving will:`,
      lines: superviseeLines.value,
      confirm: commitSupervisees
    }
  }
  return {
    title: 'Replace supervisor or group?',
    message: `${name} already has one. Saving will:`,
    lines: replacing.value,
    confirm: commitSupervisorAndGroup
  }
})

const mediaConsentLabel = computed(() => {
  const media = props.user?.mediaConsent
  if (media == null) return '—'
  return answeredAt(media ? 'Yes' : 'No', props.user?.mediaConsentAt)
})

// Consents signed on the platform carry a BTF- reference; old Qualtrics ones don't.
const signedOnPlatform = computed(() => (props.user?.joinpermResponseId || '').startsWith('BTF-'))

const consents = ref<AdminGuardianConsent[]>([])
const consentsOpen = ref(false)
const consentsLoading = ref(false)
// The outcome of loading the signed form or recording a withdrawal.
const consentsMessage = ref('')
const consentsFailed = ref(false)

const showConsentsMessage = (message: string, failed: boolean) => {
  consentsMessage.value = message
  consentsFailed.value = failed
}

const toggleConsents = async () => {
  const user = props.user
  if (!user) return
  if (consentsOpen.value) {
    consentsOpen.value = false
    return
  }
  consentsLoading.value = true
  consentsMessage.value = ''
  try {
    consents.value = await fetchGuardianConsents(user.id)
    consentsOpen.value = true
  } catch (error) {
    showConsentsMessage(apiErrorFromUnknown(error, 'Could not load the signed form.').message, true)
  } finally {
    consentsLoading.value = false
  }
}

const downloadingId = ref<number | null>(null)

const downloadRecord = async (consent: AdminGuardianConsent) => {
  const user = props.user
  if (!user || downloadingId.value !== null) return
  downloadingId.value = consent.id
  try {
    await downloadGuardianConsentRecord(user.id, consent)
  } catch (error) {
    showConsentsMessage(apiErrorFromUnknown(error, 'Could not download the consent record.').message, true)
  } finally {
    downloadingId.value = null
  }
}

const sendConsentRequest = async () => {
  const user = props.user
  if (!user || sendingRequest.value) return
  sendingRequest.value = true
  try {
    const result = await sendGuardianConsentRequest(user.id)
    requestFailed.value = false
    requestMessage.value = result.msg
    if (result.data) emit('updated', result.data)
  } catch (error) {
    requestFailed.value = true
    requestMessage.value = apiErrorFromUnknown(error, 'Could not send the consent request.').message
  } finally {
    sendingRequest.value = false
  }
}
</script>

<style scoped>
/* Role, status and logged in as plain text, as in the People tables;
   inactive and never logged in are greyed. */
.admin-users__role-badge,
.admin-users__status-badge,
.admin-users__logged-in-badge {
  text-transform: capitalize;
}

.admin-users__status-badge--inactive,
.admin-users__logged-in-badge:not(.admin-users__logged-in-badge--yes) {
  color: var(--text-muted);
}

.admin-users-detail__section h3 {
  margin: 0 0 0.4rem;
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--dark-green);
}

/* A part's heading with its Edit beside it, as on the supervisor's panel. */
.admin-users-detail__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.4rem;
}

.admin-users-detail__heading h3 {
  margin: 0;
}

.admin-users-detail__label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-muted);
  flex-shrink: 0;
}

.admin-users-detail__value {
  color: var(--teal);
}

.admin-users-detail__input {
  flex: 1;
  max-width: 320px;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  font: inherit;
  color: var(--teal);
  background: var(--surface-elevated);
}

/* A label over its field, for long answers and the weekly times. */
.admin-users-detail__item--stacked {
  flex-direction: column;
  align-items: stretch;
  gap: 0.4rem;
}

.admin-users-detail__item.admin-users-detail__item--stacked dd {
  text-align: left;
}

/* The application's answers, shown and edited: 15px. */
.admin-users-detail__answer {
  white-space: pre-wrap;
  font-size: 0.75rem;
  /* In a box, as its edit box is drawn. */
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--surface-elevated);
}

.admin-users-detail__item--stacked .admin-users-detail__input {
  max-width: none;
}

.admin-users-detail__textarea {
  /* Its own height, not the row's flex: it grows with what's written. */
  flex: none;
  resize: vertical;
  min-height: 6rem;
  font-size: 0.75rem;
}

.admin-users-detail__words {
  align-self: flex-end;
  color: var(--text-muted);
  font-size: 0.8rem;
}

.admin-users-detail__words.is-over {
  color: var(--danger);
}

/* A supervisee's email and their ×, together at the right. */
.admin-users-detail__supervisee {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  min-width: 0;
  overflow-wrap: anywhere;
}

/* A weekly time: day, from, to, and its ×. */
.admin-users-detail__item.admin-users-detail__slot {
  flex-wrap: wrap;
  justify-content: flex-start;
  align-items: center;
  gap: 0.5rem;
}

.admin-users-detail__slot > .admin-users-detail__input {
  flex: 1 1 7rem;
  min-width: 7rem;
  max-width: none;
}

/* A time: its hour and its minutes, together. */
.admin-users-detail__time {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
}

/* Just wide enough for two digits and the arrow. */
.admin-users-detail__input.admin-users-detail__time-part {
  flex: none;
  width: 3.5rem;
  min-width: 0;
  padding-left: 0.5rem;
  padding-right: 0.5rem;
}

.admin-users-detail__time-colon {
  color: var(--text-muted);
}

.admin-users-detail__slot-to {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.admin-users-detail__slot-remove {
  padding: 0.25rem 0.4rem;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
}

.admin-users-detail__slot-remove:hover {
  color: var(--danger);
}

.admin-users-detail__slot-add {
  margin-top: 0.6rem;
}

.admin-users-detail__note--after {
  margin: 0.5rem 0 0;
}

.admin-users-detail__replacing {
  margin: 0.5rem 0 0;
  padding-left: 1.2rem;
}

.admin-users-detail__item:has(.admin-users-detail__input) {
  align-items: center;
}

/* An answer in its box needs no line under it as well. */
.admin-users-detail__item.admin-users-detail__item--boxed {
  border-bottom: none;
}

/* Except a label over its field, which runs the row's full width. */
.admin-users-detail__item.admin-users-detail__item--stacked {
  align-items: stretch;
}

/* Interests, or consents, to tick: one per line. */
.admin-users-detail__options {
  flex-direction: column;
  align-items: flex-start;
  margin: 0;
  border: none;
  border-bottom: 1px solid var(--border-light);
  padding: 0.6rem 0;
}

.admin-users-detail__options legend {
  padding: 0;
  margin-bottom: 0.4rem;
}

.admin-users-detail__options label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--teal);
}

.admin-users-detail__options label.is-disabled {
  color: var(--text-muted);
}

/* A consent to tick, a row of its own. */
.admin-users-detail__check {
  align-items: center;
  cursor: pointer;
}

.admin-users-detail__check.is-disabled .admin-users-detail__label {
  opacity: 0.6;
}

.admin-users-detail__check.is-disabled {
  cursor: not-allowed;
}

/* Bigger tick boxes, for consents and interests alike. */
.admin-users-detail__check input,
.admin-users-detail__options input[type='checkbox'] {
  width: 1.1rem;
  height: 1.1rem;
  margin: 0;
  flex-shrink: 0;
  accent-color: var(--dark-green);
  cursor: inherit;
}

.admin-users-detail__note {
  margin: 0 0 0.4rem;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.admin-users-detail__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.75rem;
}


.admin-users-detail__save-error {
  margin: 0.5rem 0 0;
  color: var(--danger);
}

.admin-users-detail__section + .admin-users-detail__section {
  margin-top: 1.4rem;
}

.admin-users-detail__list {
  margin: 0;
}

.admin-users-detail__item {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--border-light);
}

.admin-users-detail__item dt {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-muted);
  flex-shrink: 0;
}

.admin-users-detail__item dd {
  margin: 0;
  color: var(--teal);
  text-align: right;
  overflow-wrap: anywhere;
}

.admin-users-detail__consent-request {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.4rem;
  margin-top: 0.75rem;
}

.admin-users-detail__consent-hint,
.admin-users-detail__consent-message {
  margin: 0;
  font-size: 0.8rem;
  color: var(--text-muted);
  text-align: right;
  overflow-wrap: anywhere;
}

.admin-users-detail__consent-message--error {
  color: var(--danger);
}

.admin-users-detail__flag {
  color: var(--danger);
}

.admin-users-detail__consent-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.admin-users-detail__consents {
  margin: 0.75rem 0 0;
  padding: 0;
  list-style: none;
}

.admin-users-detail__consent {
  padding: 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  font-size: 0.85rem;
  color: var(--teal);
}

.admin-users-detail__consent + .admin-users-detail__consent {
  margin-top: 0.5rem;
}

.admin-users-detail__consent p {
  margin: 0 0 0.35rem;
  overflow-wrap: anywhere;
}

.admin-users-detail__consent-head {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
}

.admin-users-detail__signature {
  display: block;
  max-width: 100%;
  max-height: 120px;
  margin-top: 0.5rem;
  background: var(--white, #ffffff);
  border: 1px solid var(--border-light);
  border-radius: 6px;
}

.admin-users-detail__record {
  margin-top: 0.5rem;
}

.admin-users-detail__supervisees {
  text-align: right;
}
</style>
