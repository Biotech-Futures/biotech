<template>
  <!-- A supervisor's, in the portal: laid out as its other pages are. -->
  <main
    class="registration-page"
    :class="{ 'registration-page--supervisor content-area': isSupervisorMode }"
  >
    <header v-if="!isSupervisorMode" class="registration-header">
      <RouterLink to="/login" class="brand-link" aria-label="BIOTech Connect home">
        <img :src="logo" :alt="BRAND_NAME" />
        <span>{{ BRAND_CONNECT }}</span>
      </RouterLink>
      <RouterLink to="/login" class="sign-in-link">Already registered? Sign in</RouterLink>
    </header>

    <section v-if="success" class="success-panel" aria-live="polite">
      <div class="success-mark" aria-hidden="true">
        <svg viewBox="0 0 24 24">
          <path d="m5 12 4.2 4.2L19 6.5" />
        </svg>
      </div>
      <h1>{{ successHeading }}</h1>
      <p>
        {{ successMessage }} <strong>{{ success.referenceCode }}</strong
        >.
      </p>
      <dl class="success-details">
        <div>
          <dt>Journey</dt>
          <dd>{{ selectedJourney?.title }}</dd>
        </div>
        <div>
          <dt>Students represented</dt>
          <dd>{{ success.studentCount }}</dd>
        </div>
        <div>
          <dt>Saved</dt>
          <dd>{{ formatSavedDate(success.submittedAt) }}</dd>
        </div>
      </dl>
      <div class="success-actions">
        <button type="button" class="primary-action" @click="startAnotherRegistration">
          {{
            isSupervisorMode && journey === 'supervisor_individual'
              ? 'Register another student'
              : 'Start another journey'
          }}
        </button>
        <RouterLink :to="isSupervisorMode ? '/dashboard' : '/login'" class="secondary-action">
          {{ isSupervisorMode ? 'Return to dashboard' : 'Return to sign in' }}
        </RouterLink>
      </div>
    </section>

    <section
      v-else-if="!journey && selectionStage === 'welcome'"
      class="welcome-layout"
      aria-labelledby="welcome-title"
    >
      <div class="welcome-copy">
        <h1 id="welcome-title">Join BIOTech Connect</h1>
        <div class="welcome-actions">
          <button type="button" class="primary-action welcome-primary" @click="beginRegistration">
            Register now
          </button>
          <RouterLink to="/login" class="secondary-action">Sign in</RouterLink>
        </div>
      </div>

      <aside class="welcome-aside" aria-label="Registration overview">
        <div class="welcome-aside__mark" aria-hidden="true">
          <svg viewBox="0 0 48 48">
            <path d="M16 25.5 22 31l11-14" />
            <circle cx="24" cy="24" r="18" />
          </svg>
        </div>
        <h2>One clear registration</h2>
        <ul>
          <li>Choose how you would like to register.</li>
          <li>Complete a guided form with clear progress.</li>
          <li>Review everything before you submit.</li>
        </ul>
      </aside>
    </section>

    <section
      v-else-if="!journey && selectionStage === 'role'"
      class="setup-layout"
      aria-labelledby="role-title"
    >
      <button type="button" class="btn btn-outline btn-sm setup-back" @click="selectionStage = 'welcome'">
        <i class="fas fa-chevron-left" aria-hidden="true"></i> Back
      </button>
      <header class="setup-heading">
        <h1 id="role-title">Who are you registering as?</h1>
      </header>
      <div class="role-options">
        <button
          v-for="role in visibleRoleOptions"
          :key="role.value"
          type="button"
          class="role-option"
          @click="selectRole(role.value)"
        >
          <span class="role-option__icon" aria-hidden="true">
            <svg v-if="role.value === 'student'" viewBox="0 0 32 32">
              <circle cx="16" cy="10" r="5" />
              <path d="M7 27c.7-6 3.8-9 9-9s8.3 3 9 9" />
            </svg>
            <svg v-else-if="role.value === 'supervisor'" viewBox="0 0 32 32">
              <path d="m5 12 11-6 11 6-11 6Z" />
              <path d="M9 16v6c4.5 3.5 9.5 3.5 14 0v-6M27 12v8" />
            </svg>
            <svg v-else viewBox="0 0 32 32">
              <path d="M16 27V14" />
              <path d="M16 18c-5.5 0-9-3.5-9-9 5.5 0 9 3.5 9 9Z" />
              <path d="M16 14c5.5 0 9-3.5 9-9-5.5 0-9 3.5-9 9Z" />
            </svg>
          </span>
          <span class="role-option__copy">
            <strong>{{ role.title }}</strong>
            <small>{{ role.description }}</small>
          </span>
          <span class="role-option__arrow" aria-hidden="true">→</span>
        </button>
      </div>
      <p class="setup-signin">
        Already have an account? <RouterLink to="/login">Sign in</RouterLink>
      </p>
      <p v-if="!invitationToken" class="supervisor-guidance">
        Supervisors:
        <RouterLink to="/supervisor/registration">Sign in to register students</RouterLink>. First
        time supervising? <a :href="`mailto:${SUPPORT_EMAIL}`">Contact BIOTech for an invitation</a>
        before registering students.
      </p>
    </section>

    <section
      v-else-if="!journey && selectionStage === 'pathway'"
      class="setup-layout"
      aria-labelledby="pathway-title"
    >
      <button
        v-if="!isSupervisorMode"
        type="button"
        class="btn btn-outline btn-sm setup-back"
        @click="backToRoleSelection"
      >
        <i class="fas fa-chevron-left" aria-hidden="true"></i> Back to roles
      </button>
      <!-- A supervisor's, in the portal: the platform's own page heading. -->
      <header v-if="isSupervisorMode" class="page-header">
        <h1 id="pathway-title" class="page-title">{{ pathwayHeading }}</h1>
        <p class="page-subtitle">Register students individually, as a group, or from a CSV.</p>
      </header>
      <header v-else class="setup-heading">
        <h1 id="pathway-title">{{ pathwayHeading }}</h1>
      </header>
      <div class="pathway-choices">
        <button
          v-for="option in roleJourneyOptions"
          :key="option.value"
          type="button"
          class="pathway-choice"
          @click="selectJourney(option.value)"
        >
          <span class="pathway-choice__copy">
            <strong>{{ option.title }}</strong>
            <small>{{ option.description }}</small>
          </span>
          <span class="btn btn-outline btn-sm pathway-choice__arrow" aria-hidden="true">
            Continue <i class="fas fa-chevron-right"></i>
          </span>
        </button>
      </div>
    </section>

    <div v-else class="work-layout">
      <aside class="journey-context">
        <button
          type="button"
          class="btn btn-outline btn-sm change-journey"
          :disabled="isCsvEditing"
          @click="changeJourney"
        >
          <i class="fas fa-chevron-left" aria-hidden="true"></i> Change registration type
        </button>
        <!-- A supervisor's, in the portal: the platform's own page heading. -->
        <header v-if="isSupervisorMode" class="page-header">
          <h1 class="page-title">{{ selectedJourney?.title }}</h1>
          <p class="page-subtitle">{{ selectedJourney?.description }}</p>
        </header>
        <h1 v-else>{{ selectedJourney?.title }}</h1>
      </aside>

      <section class="form-surface">
        <!-- The steps, with what * means at the right. -->
        <div class="step-bar">
          <nav class="step-navigation" aria-label="Registration progress">
            <ol>
              <li v-for="(step, index) in steps" :key="step.label">
                <button
                  type="button"
                  class="tab-pill"
                  :class="{
                    active: currentStep === index,
                    current: currentStep === index,
                    complete: index < currentStep,
                  }"
                  :disabled="index > maxReachedStep || isCsvEditing"
                  :aria-current="currentStep === index ? 'step' : undefined"
                  @click="goToStep(index)"
                >
                  <span>{{ index + 1 }}</span>
                  <span class="step-navigation__label">{{ step.label }}</span>
                </button>
              </li>
            </ol>
          </nav>
          <p class="form-required-note">Fields marked <span class="required-mark">*</span> are required.</p>
        </div>

        <form novalidate :aria-busy="isSubmitting" @submit.prevent="handlePrimaryAction">
          <section
            v-if="registrationWarnings.length"
            ref="warningSummaryRef"
            class="registration-warnings"
            role="alert"
            tabindex="-1"
            aria-labelledby="registration-warnings-title"
          >
            <h2 id="registration-warnings-title">Check before submitting</h2>
            <p>
              No registration has been saved. Correct the details, or confirm each item to continue.
            </p>
            <label v-for="warning in registrationWarnings" :key="warning.overrideField">
              <input
                v-model="warningAcknowledgements[warning.overrideField]"
                type="checkbox"
                :disabled="isSubmitting"
              />
              <span
                ><strong>{{ warningSubject(warning) }}:</strong> {{ warning.message }}</span
              >
            </label>
          </section>
          <div v-if="serverError" class="server-error" role="alert" tabindex="-1">
            <strong>We couldn’t submit this registration.</strong>
            <span>{{ serverError }}</span>
          </div>

          <div
            v-if="errorMessages.length"
            ref="errorSummaryRef"
            class="error-summary"
            role="alert"
            tabindex="-1"
          >
            <strong>Initial checks found information to review.</strong>
            <ul>
              <li v-for="message in errorMessages" :key="message">{{ message }}</li>
            </ul>
          </div>

          <section class="step-content" :aria-labelledby="stepHeadingId">
            <h2 :id="stepHeadingId" ref="stepHeadingRef" class="sr-only" tabindex="-1">
              {{ currentStepDefinition.title }}
            </h2>

            <template v-if="journey === 'student_individual'">
              <RegistrationStudentEditor
                v-if="currentStep === 0"
                v-model:student="forms.studentIndividual.student"
                prefix="studentIndividual.student"
                section="identity"
                :errors="errors"
                require-email-confirm
              />

              <RegistrationStudentEditor
                v-else-if="currentStep === 1"
                v-model:student="forms.studentIndividual.student"
                prefix="studentIndividual.student"
                section="profile"
                :errors="errors"
                show-optional-profile
                :preview-url="photoPreviews['studentIndividual.student']"
                @photo-selected="
                  handlePhoto(forms.studentIndividual.student, 'studentIndividual.student', $event)
                "
                @remove-photo="
                  removePhoto(forms.studentIndividual.student, 'studentIndividual.student')
                "
              />

              <div v-else-if="currentStep === 2" class="step-stack">
                <fieldset class="choice-fieldset">
                  <legend>Who will supervise this student?</legend>
                  <div class="choice-row">
                    <label>
                      <input
                        v-model="forms.studentIndividual.supervisorMode"
                        type="radio"
                        name="student-individual-supervisor-mode"
                        value="school"
                      />
                      <span>
                        <strong>Teacher / school supervisor</strong>
                        <small>A teacher or school staff member supporting this student.</small>
                      </span>
                    </label>
                    <label>
                      <input
                        v-model="forms.studentIndividual.supervisorMode"
                        type="radio"
                        name="student-individual-supervisor-mode"
                        value="parent"
                      />
                      <span>
                        <strong>Nominated parent-supervisor</strong>
                        <small>A parent supporting only this student in a limited role.</small>
                      </span>
                    </label>
                  </div>
                </fieldset>

                <div
                  v-if="forms.studentIndividual.supervisorMode === 'parent'"
                  class="scope-explanation"
                >
                  A nominated parent is linked only to this student, not other group members.
                  Guardian details remain private, and registration does not record guardian
                  permission or provide teacher or administrator access.
                </div>

                <div class="field-grid">
                  <RegistrationTextField
                    id="student-individual-supervisor-first"
                    v-model="forms.studentIndividual.supervisor.firstName"
                    label="Supervisor first name"
                    :error="errors['studentIndividual.supervisor.firstName']"
                    required
                  />
                  <RegistrationTextField
                    id="student-individual-supervisor-last"
                    v-model="forms.studentIndividual.supervisor.lastName"
                    label="Supervisor last name"
                    :error="errors['studentIndividual.supervisor.lastName']"
                    required
                  />
                  <RegistrationTextField
                    id="student-individual-supervisor-email"
                    v-model="forms.studentIndividual.supervisor.email"
                    label="Supervisor email"
                    type="email"
                    :error="errors['studentIndividual.supervisor.email']"
                    required
                  />
                  <RegistrationTextField
                    id="student-individual-supervisor-school"
                    v-model="forms.studentIndividual.supervisor.school"
                    label="Supervisor school"
                    :optional="forms.studentIndividual.supervisorMode === 'parent'"
                    :required="forms.studentIndividual.supervisorMode === 'school'"
                    :error="errors['studentIndividual.supervisor.school']"
                  />
                </div>

                <div class="section-divider">
                  <h3>Guardian contact</h3>
                  <p>
                    {{ guardianContactExplanation }}
                  </p>
                </div>
                <RegistrationStudentEditor
                  v-model:student="forms.studentIndividual.student"
                  prefix="studentIndividual.student"
                  section="guardian"
                  :errors="errors"
                />
              </div>
            </template>

            <template v-else-if="journey === 'student_team'">
              <RegistrationStudentEditor
                v-if="currentStep === 0"
                v-model:student="forms.studentTeam.creator"
                prefix="studentTeam.creator"
                section="identity"
                :errors="errors"
                require-email-confirm
              />

              <div v-else-if="currentStep === 2" class="step-stack">
                <RegistrationInterestSelector
                  id="student-team-interests"
                  v-model="forms.studentTeam.interests"
                  label="Mutual Areas of Interest"
                  description="Choose the areas your group wants to explore together."
                  :error="errors['studentTeam.interests']"
                />
                <div class="section-divider section-divider--with-action">
                  <div>
                    <h3>Group members</h3>
                    <p>There may be between 2 and 5 students per group.</p>
                  </div>
                  <button
                    type="button"
                    class="small-action"
                    :disabled="forms.studentTeam.teammates.length >= 4"
                    @click="addStudentTeammate"
                  >
                    Add member
                  </button>
                </div>
                <div class="student-entry creator-summary">
                  <div class="student-entry__heading">
                    <h3>Member 1 (you)</h3>
                    <button type="button" @click="goToStep(0)">Edit your details</button>
                  </div>
                  <dl>
                    <div>
                      <dt>Name</dt>
                      <dd>{{ studentName(forms.studentTeam.creator) }}</dd>
                    </div>
                    <div>
                      <dt>Email</dt>
                      <dd>{{ forms.studentTeam.creator.email }}</dd>
                    </div>
                  </dl>
                </div>

                <div
                  v-for="(_, index) in forms.studentTeam.teammates"
                  :key="`teammate-${index}`"
                  class="student-entry"
                >
                  <div class="student-entry__heading">
                    <h3>Member {{ index + 2 }}</h3>
                    <button
                      v-if="forms.studentTeam.teammates.length > 1"
                      type="button"
                      @click="removeStudentTeammate(index)"
                    >
                      Remove
                    </button>
                  </div>
                  <RegistrationStudentEditor
                    v-model:student="forms.studentTeam.teammates[index]"
                    :prefix="`studentTeam.teammates.${index}`"
                    section="teammate"
                    :errors="errors"
                    require-email-confirm
                    allow-guardian-defer
                  />
                </div>
              </div>

              <div v-else-if="currentStep === 1" class="step-stack">
                <RegistrationStudentEditor
                  v-model:student="forms.studentTeam.creator"
                  prefix="studentTeam.creator"
                  section="profile"
                  :errors="errors"
                  :show-interests="false"
                  show-optional-profile
                  :preview-url="photoPreviews['studentTeam.creator']"
                  @photo-selected="
                    handlePhoto(forms.studentTeam.creator, 'studentTeam.creator', $event)
                  "
                  @remove-photo="removePhoto(forms.studentTeam.creator, 'studentTeam.creator')"
                />
                <div class="section-divider">
                  <h3>Creator’s supervisor</h3>
                  <p>Nominate a teacher or school supervisor, or a parent supporting only you.</p>
                </div>
                <fieldset class="choice-fieldset">
                  <legend>Supervisor type</legend>
                  <div class="choice-row">
                    <label>
                      <input
                        v-model="forms.studentTeam.supervisorMode"
                        type="radio"
                        name="student-team-supervisor-mode"
                        value="school"
                      />
                      <span>
                        <strong>Teacher / school supervisor</strong>
                        <small>A teacher or school staff member supporting this student.</small>
                      </span>
                    </label>
                    <label>
                      <input
                        v-model="forms.studentTeam.supervisorMode"
                        type="radio"
                        name="student-team-supervisor-mode"
                        value="parent"
                      />
                      <span>
                        <strong>Nominated parent-supervisor</strong>
                        <small>A parent supporting only this student in a limited role.</small>
                      </span>
                    </label>
                  </div>
                </fieldset>
                <div v-if="forms.studentTeam.supervisorMode === 'parent'" class="scope-explanation">
                  A parent-supervisor confirms their email and may view only this student’s
                  high-level status and update school, year, interests, and profile photo. This does
                  not create teacher/admin authority, show guardian records or consent PDFs, or
                  authorize consent. Consent still requires the guardian’s recipient-bound link.
                </div>
                <div class="field-grid">
                  <RegistrationTextField
                    id="student-team-supervisor-first"
                    v-model="forms.studentTeam.supervisor.firstName"
                    label="Supervisor first name"
                    :error="errors['studentTeam.supervisor.firstName']"
                    required
                  />
                  <RegistrationTextField
                    id="student-team-supervisor-last"
                    v-model="forms.studentTeam.supervisor.lastName"
                    label="Supervisor last name"
                    :error="errors['studentTeam.supervisor.lastName']"
                    required
                  />
                  <RegistrationTextField
                    id="student-team-supervisor-email"
                    v-model="forms.studentTeam.supervisor.email"
                    label="Supervisor email"
                    type="email"
                    :error="errors['studentTeam.supervisor.email']"
                    required
                  />
                  <RegistrationTextField
                    id="student-team-supervisor-school"
                    v-model="forms.studentTeam.supervisor.school"
                    label="Supervisor school"
                    :optional="forms.studentTeam.supervisorMode === 'parent'"
                    :required="forms.studentTeam.supervisorMode === 'school'"
                    :error="errors['studentTeam.supervisor.school']"
                  />
                </div>
                <div class="section-divider">
                  <h3>Guardian contact</h3>
                  <p>{{ guardianContactExplanation }}</p>
                </div>
                <RegistrationStudentEditor
                  v-model:student="forms.studentTeam.creator"
                  prefix="studentTeam.creator"
                  section="guardian"
                  :errors="errors"
                />
              </div>
            </template>

            <template v-else-if="journey === 'supervisor_individual'">
              <RegistrationStudentEditor
                v-if="currentStep === 0"
                v-model:student="forms.supervisorIndividual.student"
                prefix="supervisorIndividual.student"
                section="full"
                :errors="errors"
                allow-guardian-defer
              />
            </template>

            <template v-else-if="journey === 'supervisor_group'">
              <div v-if="currentStep === 0" class="step-stack">
                <RegistrationInterestSelector
                  id="supervisor-group-interests"
                  v-model="forms.supervisorGroup.interests"
                  label="Mutual Areas of Interest"
                  description="Choose the areas of interest for this group."
                  :error="errors['supervisorGroup.interests']"
                />
              </div>

              <div v-else-if="currentStep === 1" class="step-stack">
                <div class="section-divider section-divider--with-action section-divider--first">
                  <div>
                    <h3>Students</h3>
                    <p>
                      Enter 2–5 complete student records. Guardian details can be deferred for the
                      student’s private follow-up journey.
                    </p>
                  </div>
                  <button
                    type="button"
                    class="small-action"
                    :disabled="forms.supervisorGroup.students.length >= 5"
                    @click="addSupervisorGroupStudent"
                  >
                    Add student
                  </button>
                </div>
                <div
                  v-for="(student, index) in forms.supervisorGroup.students"
                  :key="`group-student-${index}`"
                  class="student-entry"
                >
                  <div class="student-entry__heading">
                    <h3>Student {{ index + 1 }}</h3>
                    <button
                      v-if="forms.supervisorGroup.students.length > 2"
                      type="button"
                      @click="removeSupervisorGroupStudent(index)"
                    >
                      Remove
                    </button>
                  </div>
                  <RegistrationStudentEditor
                    v-model:student="forms.supervisorGroup.students[index]"
                    :prefix="`supervisorGroup.students.${index}`"
                    section="full"
                    :errors="errors"
                    allow-guardian-defer
                  />
                </div>
              </div>
            </template>

            <template v-else-if="journey === 'supervisor_csv'">
              <div v-if="currentStep === 0" class="upload-step">
                <div class="template-download">
                  <div>
                    <h3>Use the prescribed CSV template</h3>
                    <p>
                      Keep the column names unchanged. Separate multiple interests with commas in
                      one quoted CSV cell. Guardian fields may be left blank.
                    </p>
                  </div>
                  <button type="button" class="secondary-action" @click="downloadCsvTemplate">
                    Download example template
                  </button>
                </div>
                <label class="csv-upload">
                  <span>Choose completed CSV <span class="required-mark" aria-hidden="true">*</span></span>
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    :aria-invalid="Boolean(errors['supervisorCsv.file'])"
                    @change="handleCsvUpload"
                  />
                  <small v-if="forms.supervisorCsv.fileName">
                    Loaded {{ forms.supervisorCsv.fileName }} ·
                    {{ forms.supervisorCsv.rows.length }} student rows
                  </small>
                  <small v-else>CSV only, up to 2 MB.</small>
                  <strong v-if="errors['supervisorCsv.file']" class="inline-error">
                    {{ errors['supervisorCsv.file'] }}
                  </strong>
                </label>
                <div v-if="csvFileErrors.length" class="server-error" role="alert">
                  <strong>The CSV could not be previewed.</strong>
                  <span v-for="message in csvFileErrors" :key="message">{{ message }}</span>
                </div>
              </div>

              <div v-else-if="currentStep === 1" class="csv-preview">
                <div class="csv-totals" aria-label="CSV row totals">
                  <div>
                    <strong>{{ csvCounts.valid }}</strong>
                    <span>Valid</span>
                  </div>
                  <div>
                    <strong>{{ csvCounts.review }}</strong>
                    <span>Review required</span>
                  </div>
                  <div>
                    <strong>{{ csvCounts.invalid }}</strong>
                    <span>Invalid</span>
                  </div>
                  <div>
                    <strong>{{ csvCounts.excluded }}</strong>
                    <span>Excluded</span>
                  </div>
                </div>
                <p class="preview-guidance">
                  Choose Edit row to correct any student details here. Validation updates as you
                  type, without re-uploading. Review-required rows can be included for authoritative
                  review; invalid rows must be fixed or explicitly excluded.
                </p>
                <section
                  v-if="editingCsvRow"
                  id="csv-row-editor"
                  class="csv-row-editor"
                  aria-labelledby="csv-row-editor-title"
                >
                  <h3 id="csv-row-editor-title" ref="csvEditorHeadingRef" tabindex="-1">
                    Edit row {{ editingCsvRow.rowNumber }}
                  </h3>
                  <p class="preview-guidance">
                    Changes are kept in this upload and included when you submit the registration.
                  </p>
                  <p v-if="isCsvRowExcluded(editingCsvRow.rowNumber)" class="preview-guidance">
                    This row is still excluded. Clear its exclusion checkbox to include it after
                    correcting the details.
                  </p>
                  <RegistrationCsvRowEditor
                    :key="editingCsvRow.rowNumber"
                    :row="editingCsvRow"
                    :excluded="isCsvRowExcluded(editingCsvRow.rowNumber)"
                    :errors="{
                      ...editingCsvRow.fieldErrors,
                      ...csvServerFieldsByRow[editingCsvRow.rowNumber],
                    }"
                    @update:values="updateCsvRow(editingCsvRow, $event)"
                  />
                  <footer class="csv-editor-footer">
                    <p id="csv-editor-confirmation-hint" class="preview-guidance">
                      Choose Done editing below to confirm your row changes before continuing.
                    </p>
                    <button type="button" class="primary-action" @click="closeCsvEditor">
                      Done editing
                    </button>
                  </footer>
                </section>
                <div class="table-scroll">
                  <table>
                    <caption>
                      Parsed student rows
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">Row</th>
                        <th scope="col">Student</th>
                        <th scope="col">Email</th>
                        <th scope="col">Status and action</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="row in forms.supervisorCsv.rows"
                        :key="row.rowNumber"
                        :class="{ 'is-excluded': isCsvRowExcluded(row.rowNumber) }"
                      >
                        <td>{{ row.rowNumber }}</td>
                        <td>{{ row.values.first_name }} {{ row.values.last_name }}</td>
                        <td>{{ row.values.email || 'Missing' }}</td>
                        <td>
                          <strong :class="`csv-status csv-status--${row.category}`">
                            {{ csvCategoryLabel(row.category) }}
                          </strong>
                          <ul v-if="csvRowIssues(row).length">
                            <li v-for="issue in csvRowIssues(row)" :key="issue">{{ issue }}</li>
                          </ul>
                          <button
                            type="button"
                            :id="`csv-edit-${row.rowNumber}`"
                            class="csv-edit-action"
                            :aria-label="`Edit row ${row.rowNumber}`"
                            :aria-expanded="editingCsvRowNumber === row.rowNumber"
                            aria-controls="csv-row-editor"
                            @click="editCsvRow(row.rowNumber)"
                          >
                            Edit row
                          </button>
                          <label class="exclude-row">
                            <input
                              type="checkbox"
                              :aria-label="`Exclude row ${row.rowNumber}`"
                              :checked="isCsvRowExcluded(row.rowNumber)"
                              @change="toggleCsvRow(row.rowNumber)"
                            />
                            Exclude this row
                          </label>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </template>

            <template v-else-if="journey === 'mentor'">
              <div v-if="currentStep === 0" class="field-grid">
                <RegistrationTextField
                  id="mentor-first"
                  v-model="forms.mentor.firstName"
                  label="First name"
                  autocomplete="given-name"
                  :error="errors['mentor.firstName']"
                  required
                />
                <RegistrationTextField
                  id="mentor-last"
                  v-model="forms.mentor.lastName"
                  label="Last name"
                  autocomplete="family-name"
                  :error="errors['mentor.lastName']"
                  required
                />
                <RegistrationTextField
                  id="mentor-email"
                  v-model="forms.mentor.email"
                  label="Email"
                  type="email"
                  autocomplete="email"
                  :error="errors['mentor.email']"
                  required
                />
                <RegistrationTextField
                  id="mentor-phone"
                  v-model="forms.mentor.phone"
                  :error="errors['mentor.phone']"
                  label="Phone"
                  type="tel"
                  autocomplete="tel"
                  optional
                />
                <RegistrationTextField
                  id="mentor-country"
                  v-model="forms.mentor.country"
                  label="Country"
                  :options="mentorCountryOptions.length ? mentorCountryOptions : undefined"
                  :placeholder="mentorCountryOptions.length ? 'Select a country' : undefined"
                  :error="errors['mentor.country']"
                  required
                />
                <!-- In Australia, a dropdown of its states and territories. -->
                <RegistrationTextField
                  id="mentor-state"
                  v-model="forms.mentor.state"
                  label="State or region"
                  :options="mentorStateOptions.length ? mentorStateOptions : undefined"
                  :placeholder="mentorStateOptions.length ? 'Select a state' : undefined"
                  :error="errors['mentor.state']"
                  required
                />
              </div>

              <div v-else-if="currentStep === 1" class="step-stack">
                <fieldset
                  class="choice-fieldset"
                  :aria-invalid="Boolean(errors['mentor.affiliation'])"
                  :aria-describedby="
                    errors['mentor.affiliation'] ? 'mentor-affiliation-error' : undefined
                  "
                >
                  <legend>Current affiliation</legend>
                  <div class="affiliation-options">
                    <label v-for="option in mentorAffiliations" :key="option.value">
                      <input
                        v-model="forms.mentor.affiliation"
                        type="radio"
                        name="mentor-affiliation"
                        :value="option.value"
                        :aria-invalid="Boolean(errors['mentor.affiliation'])"
                        required
                      />
                      <span>{{ option.label }}</span>
                    </label>
                  </div>
                  <span
                    v-if="errors['mentor.affiliation']"
                    id="mentor-affiliation-error"
                    class="inline-error"
                  >
                    {{ errors['mentor.affiliation'] }}
                  </span>
                </fieldset>

                <div v-if="forms.mentor.affiliation" class="field-grid">
                  <RegistrationTextField
                    v-if="forms.mentor.affiliation !== 'industry'"
                    id="mentor-institution"
                    v-model="forms.mentor.institution"
                    label="University or institution"
                    :error="errors['mentor.institution']"
                    required
                    wide
                  />
                  <RegistrationTextField
                    v-else
                    id="mentor-company"
                    v-model="forms.mentor.company"
                    label="Company or organisation"
                    :error="errors['mentor.company']"
                    required
                    wide
                  />
                  <RegistrationTextField
                    v-if="['undergraduate', 'postgraduate'].includes(forms.mentor.affiliation)"
                    id="mentor-year"
                    v-model="forms.mentor.universityYear"
                    label="Current year of study"
                    :error="errors['mentor.universityYear']"
                    required
                  />
                  <RegistrationTextField
                    v-if="forms.mentor.affiliation !== 'industry'"
                    id="mentor-field-study"
                    v-model="forms.mentor.fieldOfStudy"
                    label="Field of study or research"
                    :error="errors['mentor.fieldOfStudy']"
                    required
                  />
                </div>
              </div>

              <div v-else-if="currentStep === 2" class="step-stack">
                <RegistrationInterestSelector
                  id="mentor-interests"
                  v-model="forms.mentor.interests"
                  label="Relevant interests"
                  description="Choose the areas where you could support a student group."
                  :error="errors['mentor.interests']"
                />
                <label class="select-field">
                  <span>Capacity <span class="required-mark" aria-hidden="true">*</span></span>
                  <select
                    id="mentor-capacity"
                    v-model="forms.mentor.capacity"
                    :aria-invalid="Boolean(errors['mentor.capacity'])"
                    :aria-describedby="
                      errors['mentor.capacity'] ? 'mentor-capacity-error' : undefined
                    "
                    required
                  >
                    <option value="" disabled>Select group capacity</option>
                    <option v-for="count in ['1', '2', '3', '4', '5']" :key="count" :value="count">
                      {{ count }} {{ count === '1' ? 'group' : 'groups' }}
                    </option>
                  </select>
                  <span
                    v-if="errors['mentor.capacity']"
                    id="mentor-capacity-error"
                    class="inline-error"
                  >
                    {{ errors['mentor.capacity'] }}
                  </span>
                </label>
                <RegistrationTextField
                  id="mentor-background"
                  v-model="forms.mentor.background"
                  label="Relevant background"
                  hint="Describe experience that would help you support a student group."
                  :error="errors['mentor.background']"
                  multiline
                  required
                  wide
                />
                <RegistrationTextField
                  id="mentor-motivation"
                  v-model="forms.mentor.motivation"
                  label="Why would you like to mentor?"
                  :error="errors['mentor.motivation']"
                  multiline
                  required
                  wide
                />
              </div>

              <div v-else-if="currentStep === 3" class="step-stack">
                <div class="scope-explanation">
                  <strong>Safeguarding review status: Pending review</strong><br />
                  Exact jurisdictional evidence, retention, and legal wording remain approval
                  controlled. Any required clearance or declaration must be verified by an
                  administrator. Self-attestation never activates matching or group access.
                </div>
                <div class="field-grid">
                  <RegistrationTextField
                    id="mentor-safeguarding-region"
                    v-model="forms.mentor.safeguardingJurisdiction"
                    label="Safeguarding jurisdiction"
                    hint="Country and state/region whose requirements apply."
                    :error="errors['mentor.safeguardingJurisdiction']"
                    required
                    wide
                  />
                  <label class="select-field">
                    <span>Indigenous identification <small>Optional</small></span>
                    <select v-model="forms.mentor.indigenousStatus">
                      <option value="">Select an option</option>
                      <option>Yes</option>
                      <option>No</option>
                      <option>Prefer not to say</option>
                    </select>
                  </label>
                  <RegistrationTextField
                    id="mentor-languages"
                    v-model="forms.mentor.languages"
                    :error="errors['mentor.languages']"
                    label="Languages spoken"
                    :disabled="forms.mentor.languagesPreferNot"
                    optional
                  />
                  <label class="prefer-control">
                    <input v-model="forms.mentor.languagesPreferNot" type="checkbox" />
                    Prefer not to say for languages
                  </label>
                  <RegistrationTextField
                    id="mentor-dob"
                    v-model="forms.mentor.dateOfBirth"
                    :error="errors['mentor.dateOfBirth']"
                    label="Date of birth"
                    type="date"
                    :disabled="forms.mentor.dateOfBirthPreferNot"
                    optional
                  />
                  <label class="prefer-control">
                    <input v-model="forms.mentor.dateOfBirthPreferNot" type="checkbox" />
                    Prefer not to say for date of birth
                  </label>
                </div>
                <label class="attestation-control">
                  <input
                    v-model="forms.mentor.complianceDeclaration"
                    type="checkbox"
                    :aria-invalid="Boolean(errors['mentor.attestation'])"
                    :aria-describedby="
                      errors['mentor.attestation'] ? 'mentor-attestation-error' : undefined
                    "
                    required
                  />
                  <span>
                    I understand that safeguarding and compliance information may require restricted
                    administrator review before any mentor access or matching eligibility.
                  </span>
                </label>
                <label class="attestation-control">
                  <input
                    v-model="forms.mentor.attestation"
                    type="checkbox"
                    :aria-invalid="Boolean(errors['mentor.attestation'])"
                    :aria-describedby="
                      errors['mentor.attestation'] ? 'mentor-attestation-error' : undefined
                    "
                    required
                  />
                  <span>
                    I attest that the information in this registration is accurate to the best of my
                    knowledge.
                  </span>
                </label>
                <span
                  v-if="errors['mentor.attestation']"
                  id="mentor-attestation-error"
                  class="inline-error"
                >
                  {{ errors['mentor.attestation'] }}
                </span>
              </div>
            </template>

            <div v-if="currentStep === steps.length - 1" class="review-step">
              <div v-for="section in reviewSections" :key="section.title" class="review-section">
                <h3>{{ section.title }}</h3>
                <dl>
                  <div v-for="item in section.items" :key="item.label">
                    <dt>{{ item.label }}</dt>
                    <dd>{{ item.value || 'Not provided' }}</dd>
                  </div>
                </dl>
              </div>
            </div>
          </section>

          <!-- Back from the second step on; Change registration type, above,
               goes back from the first. -->
          <footer class="form-footer">
            <button
              v-if="currentStep > 0"
              type="button"
              class="secondary-action"
              :disabled="isSubmitting || isCsvEditing"
              @click="goBack"
            >
              Back
            </button>
            <button
              type="submit"
              class="primary-action"
              :disabled="isSubmitting || isCsvEditing"
              :aria-describedby="isCsvEditing ? 'csv-editor-confirmation-hint' : undefined"
            >
              <span v-if="isSubmitting" class="spinner" aria-hidden="true"></span>
              {{
                isSubmitting
                  ? 'Submitting…'
                  : currentStep === steps.length - 1
                    ? 'Submit registration'
                    : 'Continue'
              }}
            </button>
          </footer>
        </form>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import logo from '@/assets/btf-logo.png'
import RegistrationInterestSelector from '@/components/registration/RegistrationInterestSelector.vue'
import RegistrationCsvRowEditor from '@/components/registration/RegistrationCsvRowEditor.vue'
import RegistrationStudentEditor from '@/components/registration/RegistrationStudentEditor.vue'
import RegistrationTextField from '@/components/registration/RegistrationTextField.vue'
import { BRAND_CONNECT, BRAND_NAME, SUPPORT_EMAIL } from '@/constants/brand'
import { earliestRegistrationErrorStep } from '@/registration/registrationErrorNavigation'
import { useCountryOptions, useStateOptions } from '@/registration/useLocationOptions'
import {
  buildRegistrationRequest,
  REGISTRATION_GATEWAY_KEY,
  type RegistrationGateway,
  type RegistrationReceipt,
  type RegistrationWarning,
} from '@/registration/registrationGateway'
import {
  createRegistrationForms,
  CSV_HEADERS,
  createStudent,
  createPendingPeer,
  findCrossRoleEmailConflicts,
  isValidRegistrationEmail,
  parseRegistrationCsv,
  registrationCsvTemplate,
  revalidateRegistrationCsvRows,
  type CsvCategory,
  type CsvHeader,
  type CsvRow,
  type GuardianDetails,
  type MentorForm,
  type RegistrationJourney,
  type StudentDetails,
  type SupervisorDetails,
} from '@/registration/registration'

interface StepDefinition {
  label: string
  title: string
  description: string
}

interface JourneyOption {
  value: RegistrationJourney
  role: string
  title: string
  description: string
  steps: StepDefinition[]
}

type RegistrationRole = 'student' | 'supervisor' | 'mentor'
type SelectionStage = 'welcome' | 'role' | 'pathway'

interface RoleOption {
  value: RegistrationRole
  title: string
  description: string
}

interface ReviewSection {
  title: string
  items: Array<{ label: string; value: string }>
}

const MAX_PHOTO_BYTES = 5 * 1024 * 1024
const MAX_CSV_BYTES = 2 * 1024 * 1024
const initialInvitationToken =
  new URLSearchParams(window.location.hash.split('?')[1] || window.location.search).get('invite') ||
  undefined
const allowedPhotoTypes = new Set(['image/jpeg', 'image/png', 'image/webp'])
const emailLikePattern = /\b[^\s@]+@[^\s@]+\.[^\s@]+\b/i
const guardianContactExplanation =
  'Your nominated guardian must provide permission through the existing guardian consent process before you can access most features of the program. Registration saves their contact details; it does not send a permission email or record consent.'

const roleOptions: RoleOption[] = [
  {
    value: 'student',
    title: 'Student',
    description: 'Register yourself or create a group with classmates.',
  },
  {
    value: 'supervisor',
    title: 'Supervisor or teacher',
    description: 'Register students individually, as a group, or from a CSV.',
  },
  {
    value: 'mentor',
    title: 'Mentor',
    description: 'Apply to support student groups with your expertise.',
  },
]

const journeyOptions: JourneyOption[] = [
  {
    value: 'student_individual',
    role: 'Student',
    title: 'Register as an individual student',
    description: 'Enter your own details, supervisor, and required guardian contact.',
    steps: [
      {
        label: 'About you',
        title: 'Tell us who you are',
        description: 'Use the email address you can access for this registration.',
      },
      {
        label: 'School & profile',
        title: 'Add your school and interests',
        description: 'Choose the areas you want to explore and optionally add profile details.',
      },
      {
        label: 'Support',
        title: 'Add your supervisor and guardian',
        description: 'These contacts have distinct roles and permissions.',
      },
      {
        label: 'Review',
        title: 'Review your registration',
        description: 'Check the details before submitting.',
      },
    ],
  },
  {
    value: 'student_team',
    role: 'Student',
    title: 'Create a student group',
    description: 'Register a group of 2–5 students, including yourself.',
    steps: [
      {
        label: 'Creator',
        title: 'Start with your details',
        description: 'You will be Member 1 of this group.',
      },
      {
        label: 'Your profile',
        title: 'Complete your own details first',
        description: 'Add your school, profile, supervisor, and required guardian contact.',
      },
      {
        label: 'Group',
        title: 'Build your group',
        description: 'Add 1–4 other members and choose your group interests.',
      },
      {
        label: 'Review',
        title: 'Review the group registration',
        description: 'Check the group before saving.',
      },
    ],
  },
  {
    value: 'supervisor_individual',
    role: 'Supervisor / teacher',
    title: 'Register one student',
    description: 'Add one student and review their registration details.',
    steps: [
      {
        label: 'Student',
        title: 'Add the student',
        description: 'Guardian contact may be supplied now or deferred.',
      },
      {
        label: 'Review',
        title: 'Review the student registration',
        description: 'Check the record before saving.',
      },
    ],
  },
  {
    value: 'supervisor_group',
    role: 'Supervisor / teacher',
    title: 'Register a student group',
    description: 'Create a pre-formed group with 2–5 complete student entries.',
    steps: [
      {
        label: 'Group',
        title: 'Describe the group',
        description: 'Choose the areas of interest for the group.',
      },
      {
        label: 'Students',
        title: 'Add 2–5 students',
        description: 'Each student later completes their own action and guardian journey.',
      },
      {
        label: 'Review',
        title: 'Review the group registration',
        description: 'Check membership and shared details before saving.',
      },
    ],
  },
  {
    value: 'supervisor_csv',
    role: 'Supervisor / teacher',
    title: 'Upload students by CSV',
    description:
      'Use the prescribed template, parse it locally, and resolve row issues before save.',
    steps: [
      {
        label: 'Upload',
        title: 'Upload the prescribed CSV',
        description: 'The file is parsed in your browser for preview.',
      },
      {
        label: 'Preview',
        title: 'Resolve the row preview',
        description: 'Invalid rows must be corrected or explicitly excluded.',
      },
      {
        label: 'Review',
        title: 'Review the import',
        description: 'Confirm included and excluded rows before saving.',
      },
    ],
  },
  {
    value: 'mentor',
    role: 'Mentor',
    title: 'Register as a mentor',
    description: 'Share your affiliation, interests, capacity, background, and review information.',
    steps: [
      {
        label: 'Contact',
        title: 'Your contact details',
        description: 'Tell BIOTech how to identify and contact you.',
      },
      {
        label: 'Affiliation',
        title: 'Your current affiliation',
        description: 'The questions adapt to university, academic, or industry backgrounds.',
      },
      {
        label: 'Contribution',
        title: 'How you could contribute',
        description: 'Choose interests, capacity, background, and motivation.',
      },
      {
        label: 'Compliance',
        title: 'Safeguarding and attestation',
        description:
          'Sensitive information is optional and review remains administrator controlled.',
      },
      {
        label: 'Review',
        title: 'Review the mentor registration',
        description: 'Submission does not activate matching access.',
      },
    ],
  },
]

const mentorAffiliations: Array<{ value: MentorForm['affiliation']; label: string }> = [
  { value: 'undergraduate', label: 'Undergraduate student' },
  { value: 'postgraduate', label: 'Postgraduate coursework student' },
  { value: 'hdr', label: 'HDR / research student' },
  { value: 'academic', label: 'Academic / research staff' },
  { value: 'industry', label: 'Industry professional' },
]

const props = withDefaults(
  defineProps<{
    mode?: 'canonical' | 'supervisor'
    invitationToken?: string | null
  }>(),
  { mode: 'canonical' },
)
const isSupervisorMode = computed(() => props.mode === 'supervisor')
const invitationToken = computed(() =>
  props.invitationToken === undefined ? initialInvitationToken : props.invitationToken || undefined,
)
const injectedGateway = inject(REGISTRATION_GATEWAY_KEY, null)
const unavailableGateway: RegistrationGateway = {
  async submit() {
    return {
      ok: false,
      message: 'Registration submission is not configured in this environment.',
    }
  },
}
const registrationGateway = injectedGateway || unavailableGateway
const forms = reactive(createRegistrationForms())
// The countries, and in Australia its states, from the database, for the
// mentor's dropdowns.
const mentorCountryOptions = useCountryOptions()
const mentorStateOptions = useStateOptions(() => forms.mentor.country)
const journey = ref<RegistrationJourney | null>(null)
const selectionStage = ref<SelectionStage>(isSupervisorMode.value ? 'pathway' : 'role')
const selectedRole = ref<RegistrationRole | null>(isSupervisorMode.value ? 'supervisor' : null)
const currentStep = ref(0)
const maxReachedStep = ref(0)
const clientErrors = reactive<Record<string, string>>({})
const serverFieldErrors = reactive<Record<string, string>>({})
const errors = computed<Record<string, string>>(() => ({
  ...serverFieldErrors,
  ...clientErrors,
}))
const csvFileErrors = ref<string[]>([])
const editingCsvRowNumber = ref<number | null>(null)
const csvEditorHeadingRef = ref<HTMLElement | null>(null)
const photoPreviews = reactive<Record<string, string>>({})
const photoFiles = new WeakMap<StudentDetails, File>()
let submissionKey = ''
let submissionSignature = ''
const serverError = ref('')
const registrationWarnings = ref<RegistrationWarning[]>([])
const warningAcknowledgements = reactive<Record<string, boolean>>({})
const warningOverrides = ref<Record<string, boolean>>({})
const warningSummaryRef = ref<HTMLElement | null>(null)
const isSubmitting = ref(false)
const success = ref<RegistrationReceipt | null>(null)
const stepHeadingRef = ref<HTMLElement | null>(null)
const errorSummaryRef = ref<HTMLElement | null>(null)

const selectedJourney = computed(() =>
  journey.value ? journeyOptions.find((option) => option.value === journey.value) : undefined,
)
const visibleRoleOptions = computed(() =>
  roleOptions.filter(
    (role) =>
      role.value !== 'supervisor' &&
      (!invitationToken.value || role.value === 'student') &&
      (role.value !== 'mentor' ||
        !registrationGateway.supportedJourneys ||
        registrationGateway.supportedJourneys.includes('mentor')),
  ),
)
const successHeading = computed(() =>
  journey.value === 'mentor' ? 'Application received' : 'Registration details received',
)
const successMessage = computed(() => {
  if (journey.value === 'mentor') {
    return 'Your application is pending safeguarding and administrator review. Reference'
  }
  return 'Guardian consent is still required before full registration. Reference'
})
const steps = computed(() => selectedJourney.value?.steps || [])
const roleJourneyOptions = computed(() => {
  if (selectedRole.value === 'student') {
    return journeyOptions.filter((option) =>
      (invitationToken.value
        ? ['student_individual']
        : ['student_individual', 'student_team']
      ).includes(option.value),
    )
  }
  if (selectedRole.value === 'supervisor') {
    return journeyOptions.filter((option) =>
      ['supervisor_individual', 'supervisor_group', 'supervisor_csv'].includes(option.value),
    )
  }
  return journeyOptions.filter((option) => option.value === 'mentor')
})
const pathwayHeading = computed(() =>
  isSupervisorMode.value
    ? 'Register students'
    : selectedRole.value === 'student'
      ? 'How would you like to register?'
      : 'How are you registering students?',
)
const currentStepDefinition = computed(
  () =>
    steps.value[currentStep.value] || {
      label: '',
      title: '',
      description: '',
    },
)
const stepHeadingId = computed(() => `registration-step-${currentStep.value + 1}`)
const errorMessages = computed(() => [...new Set(Object.values(errors.value))])
const includedCsvRows = computed(() =>
  forms.supervisorCsv.rows.filter(
    (row) => !forms.supervisorCsv.excludedRowNumbers.includes(row.rowNumber),
  ),
)
const warningSubject = (warning: RegistrationWarning) => {
  const field = warning.field.endsWith('.school') ? 'School' : 'Student email'
  const csvRow = /^supervisorCsv\.rows\.(\d+)\./.exec(warning.field)
  if (csvRow) return `CSV row ${includedCsvRows.value[Number(csvRow[1])]?.rowNumber} - ${field}`
  const student = /^supervisorGroup\.students\.(\d+)\./.exec(warning.field)
  if (student) return `Student ${Number(student[1]) + 1} - ${field}`
  const teammate = /^studentTeam\.teammates\.(\d+)\./.exec(warning.field)
  if (teammate) return `Member ${Number(teammate[1]) + 2} - ${field}`
  return warning.field.startsWith('studentTeam.creator.') ? `Member 1 (you) - ${field}` : field
}
const editingCsvRow = computed(() =>
  forms.supervisorCsv.rows.find((row) => row.rowNumber === editingCsvRowNumber.value),
)
const isCsvEditing = computed(
  () => journey.value === 'supervisor_csv' && Boolean(editingCsvRow.value),
)
const csvRequestPaths: Record<CsvHeader, string> = {
  first_name: 'firstName',
  last_name: 'lastName',
  email: 'email',
  school: 'school',
  year_level: 'yearLevel',
  country: 'country',
  state: 'state',
  interests: 'interests',
  guardian_first_name: 'guardian.firstName',
  guardian_last_name: 'guardian.lastName',
  guardian_email: 'guardian.email',
  guardian_relationship: 'guardian.relationship',
  guardian_relationship_other: 'guardian.relationshipOther',
  grouping_preference: 'groupingPreference',
}
const csvServerFieldsByRow = computed(() => {
  const result: Record<number, Partial<Record<CsvHeader, string>>> = {}
  includedCsvRows.value.forEach((row, index) => {
    const fields: Partial<Record<CsvHeader, string>> = {}
    for (const header of CSV_HEADERS) {
      const error = serverFieldErrors[`supervisorCsv.rows.${index}.${csvRequestPaths[header]}`]
      if (error) fields[header] = error
    }
    result[row.rowNumber] = fields
  })
  return result
})
const csvRowIssues = (row: CsvRow) => [
  ...new Set([...row.issues, ...Object.values(csvServerFieldsByRow.value[row.rowNumber] || {})]),
]
const csvCounts = computed(() => ({
  valid: includedCsvRows.value.filter((row) => row.category === 'valid').length,
  review: includedCsvRows.value.filter((row) => row.category === 'review-required').length,
  invalid: includedCsvRows.value.filter((row) => row.category === 'invalid').length,
  excluded: forms.supervisorCsv.excludedRowNumbers.length,
}))

const studentName = (student: StudentDetails) =>
  `${student.firstName} ${student.lastName}`.trim() || 'Not provided'
const guardianName = (guardian: GuardianDetails) =>
  guardian.firstName && guardian.lastName
    ? `${guardian.firstName} ${guardian.lastName}`
    : 'Deferred or not provided'
const interestSummary = (interests: string[]) => interests.join(', ') || 'Not provided'
const reviewSections = computed<ReviewSection[]>(() => {
  switch (journey.value) {
    case 'student_individual': {
      const form = forms.studentIndividual
      return [
        {
          title: 'Student',
          items: [
            { label: 'Name', value: studentName(form.student) },
            { label: 'Email', value: form.student.email },
            {
              label: 'School and year',
              value: `${form.student.school} · Year ${form.student.yearLevel}`,
            },
            {
              label: 'Location',
              value: [form.student.state, form.student.country].filter(Boolean).join(', '),
            },
            { label: 'Interests', value: interestSummary(form.student.interests) },
            { label: 'Profile photo', value: form.student.profilePhoto?.name || 'Not added' },
          ],
        },
        {
          title: 'Support',
          items: [
            {
              label: 'Supervisor type',
              value:
                form.supervisorMode === 'parent'
                  ? 'Nominated parent-supervisor'
                  : 'Teacher / school supervisor',
            },
            {
              label: 'Supervisor',
              value: `${form.supervisor.firstName} ${form.supervisor.lastName} · ${form.supervisor.email}`,
            },
            {
              label: 'Guardian',
              value: `${guardianName(form.student.guardian)} · ${form.student.guardian.email}`,
            },
          ],
        },
      ]
    }
    case 'student_team':
      return [
        {
          title: 'Group',
          items: [
            { label: 'Total students', value: String(forms.studentTeam.teammates.length + 1) },
            { label: 'Interests', value: interestSummary(forms.studentTeam.interests) },
          ],
        },
        {
          title: 'People',
          items: [
            {
              label: 'Member 1 (you)',
              value: `${studentName(forms.studentTeam.creator)} · ${forms.studentTeam.creator.email}`,
            },
            ...forms.studentTeam.teammates.map((student, index) => ({
              label: `Member ${index + 2}`,
              value: `${studentName(student)} · ${student.email} · Guardian ${student.guardianDeferred ? 'deferred' : 'provided'}`,
            })),
            {
              label: 'Creator guardian',
              value: forms.studentTeam.creator.guardianDeferred
                ? 'Deferred'
                : guardianName(forms.studentTeam.creator.guardian),
            },
            {
              label: 'Creator supervisor',
              value: `${forms.studentTeam.supervisor.firstName} ${forms.studentTeam.supervisor.lastName} · ${forms.studentTeam.supervisor.email}`,
            },
          ],
        },
      ]
    case 'supervisor_individual':
      return [
        {
          title: 'Student',
          items: [
            { label: 'Name', value: studentName(forms.supervisorIndividual.student) },
            { label: 'Email', value: forms.supervisorIndividual.student.email },
            {
              label: 'Guardian',
              value: forms.supervisorIndividual.student.guardianDeferred
                ? 'Deferred'
                : guardianName(forms.supervisorIndividual.student.guardian),
            },
          ],
        },
      ]
    case 'supervisor_group':
      return [
        {
          title: 'Group',
          items: [
            { label: 'Students', value: String(forms.supervisorGroup.students.length) },
            { label: 'Interests', value: interestSummary(forms.supervisorGroup.interests) },
          ],
        },
        {
          title: 'Members',
          items: forms.supervisorGroup.students.map((student, index) => ({
            label: `Student ${index + 1}`,
            value: `${studentName(student)} · ${student.email} · Guardian ${student.guardianDeferred ? 'deferred' : 'provided'}`,
          })),
        },
      ]
    case 'supervisor_csv':
      return [
        {
          title: 'Import owner',
          items: [{ label: 'File', value: forms.supervisorCsv.fileName }],
        },
        {
          title: 'Rows',
          items: [
            { label: 'Included', value: String(includedCsvRows.value.length) },
            { label: 'Valid', value: String(csvCounts.value.valid) },
            { label: 'Pending review', value: String(csvCounts.value.review) },
            { label: 'Explicitly excluded', value: String(csvCounts.value.excluded) },
          ],
        },
      ]
    case 'mentor':
      return [
        {
          title: 'Mentor',
          items: [
            { label: 'Name', value: `${forms.mentor.firstName} ${forms.mentor.lastName}` },
            { label: 'Email', value: forms.mentor.email },
            { label: 'Location', value: `${forms.mentor.state}, ${forms.mentor.country}` },
            {
              label: 'Affiliation',
              value:
                mentorAffiliations.find((option) => option.value === forms.mentor.affiliation)
                  ?.label || '',
            },
            {
              label: 'Organisation',
              value:
                forms.mentor.affiliation === 'industry'
                  ? forms.mentor.company
                  : forms.mentor.institution,
            },
          ],
        },
        {
          title: 'Contribution and review',
          items: [
            { label: 'Interests', value: interestSummary(forms.mentor.interests) },
            {
              label: 'Capacity',
              value: `${forms.mentor.capacity} group${forms.mentor.capacity === '1' ? '' : 's'}`,
            },
            { label: 'Safeguarding status', value: 'Pending administrator review' },
            { label: 'Matching access', value: 'Not activated by this submission' },
          ],
        },
      ]
    default:
      return []
  }
})

const clearErrors = () => {
  Object.keys(clientErrors).forEach((key) => delete clientErrors[key])
}

const clearServerErrors = () => {
  Object.keys(serverFieldErrors).forEach((key) => delete serverFieldErrors[key])
}

const requireValue = (key: string, value: string, message: string) => {
  const trimmed = value.trim()
  if (!trimmed) {
    clientErrors[key] = message
    return
  }
  if (!key.toLowerCase().includes('email') && emailLikePattern.test(trimmed)) {
    clientErrors[key] = 'Enter a name or description here, not an email address.'
  }
}

const validateEmail = (key: string, value: string, label: string) => {
  requireValue(key, value, `Enter the ${label.toLowerCase()}.`)
  if (value.trim() && !isValidRegistrationEmail(value))
    clientErrors[key] = `Enter a valid ${label.toLowerCase()}.`
}

const validateSupervisor = (
  supervisor: SupervisorDetails,
  prefix: string,
  requireSchool = true,
) => {
  requireValue(`${prefix}.firstName`, supervisor.firstName, 'Enter the supervisor first name.')
  requireValue(`${prefix}.lastName`, supervisor.lastName, 'Enter the supervisor last name.')
  validateEmail(`${prefix}.email`, supervisor.email, 'Supervisor email')
  if (requireSchool)
    requireValue(`${prefix}.school`, supervisor.school, 'Enter the supervisor school.')
}

const validateStudentIdentity = (student: StudentDetails, prefix: string, confirmEmail = false) => {
  requireValue(`${prefix}.firstName`, student.firstName, 'Enter the student first name.')
  requireValue(`${prefix}.lastName`, student.lastName, 'Enter the student last name.')
  validateEmail(`${prefix}.email`, student.email, 'Student email')
  if (confirmEmail) {
    validateEmail(`${prefix}.emailConfirm`, student.emailConfirm, 'Confirmation email')
    if (
      student.emailConfirm.trim() &&
      student.email.trim().toLowerCase() !== student.emailConfirm.trim().toLowerCase()
    ) {
      clientErrors[`${prefix}.emailConfirm`] = 'The student email addresses do not match.'
    }
  }
}

// A student's Areas of Interest are optional.
const validateStudentProfile = (student: StudentDetails, prefix: string) => {
  requireValue(`${prefix}.school`, student.school, 'Enter the student school.')
  requireValue(`${prefix}.yearLevel`, student.yearLevel, 'Select the student year level.')
  requireValue(`${prefix}.country`, student.country, 'Enter the student country.')
  if (student.country.trim().toLowerCase() === 'australia')
    requireValue(`${prefix}.state`, student.state, 'Enter the Australian state or territory.')
  if (student.pronouns === 'Other') {
    requireValue(`${prefix}.pronounsOther`, student.pronounsOther, 'Enter the student pronouns.')
  }
}

// A guardian is their name and email, as on the Guardian Details form.
const validateGuardian = (student: StudentDetails, prefix: string, canDefer = true) => {
  if (canDefer && student.guardianDeferred) return
  const guardian = student.guardian
  requireValue(`${prefix}.guardian.firstName`, guardian.firstName, 'Enter the guardian first name.')
  requireValue(`${prefix}.guardian.lastName`, guardian.lastName, 'Enter the guardian last name.')
  validateEmail(`${prefix}.guardian.email`, guardian.email, 'Guardian email')
}

// A supervisor's students: each email given once, with no confirming it.
const validateStudentFull = (student: StudentDetails, prefix: string) => {
  validateStudentIdentity(student, prefix)
  validateStudentProfile(student, prefix)
  validateGuardian(student, prefix)
}

const validateCrossRoleEmails = () => {
  if (!journey.value) return
  const conflicts = findCrossRoleEmailConflicts(journey.value, forms)
  conflicts.forEach((message, index) => {
    clientErrors[`emailConflict.${index}`] = message
  })
}

const validateCurrentStep = () => {
  clearErrors()
  if (!journey.value) return false
  const step = currentStep.value

  if (journey.value === 'student_individual') {
    if (step === 0)
      validateStudentIdentity(forms.studentIndividual.student, 'studentIndividual.student', true)
    if (step === 1)
      validateStudentProfile(forms.studentIndividual.student, 'studentIndividual.student')
    if (step === 2) {
      validateSupervisor(
        forms.studentIndividual.supervisor,
        'studentIndividual.supervisor',
        forms.studentIndividual.supervisorMode === 'school',
      )
      validateGuardian(forms.studentIndividual.student, 'studentIndividual.student', false)
    }
  } else if (journey.value === 'student_team') {
    if (step === 0) validateStudentIdentity(forms.studentTeam.creator, 'studentTeam.creator', true)
    if (step === 1) {
      validateStudentProfile(forms.studentTeam.creator, 'studentTeam.creator')
      validateSupervisor(
        forms.studentTeam.supervisor,
        'studentTeam.supervisor',
        forms.studentTeam.supervisorMode === 'school',
      )
      validateGuardian(forms.studentTeam.creator, 'studentTeam.creator', false)
    }
    if (step === 2) {
      if (!forms.studentTeam.interests.length)
        clientErrors['studentTeam.interests'] = 'Choose at least one group interest.'
      if (forms.studentTeam.teammates.length < 1 || forms.studentTeam.teammates.length > 4) {
        clientErrors['studentTeam.size'] = 'A group must include 2–5 students, including you.'
      }
      forms.studentTeam.teammates.forEach((student, index) => {
        validateStudentIdentity(student, `studentTeam.teammates.${index}`, true)
        validateGuardian(student, `studentTeam.teammates.${index}`)
      })
    }
  } else if (journey.value === 'supervisor_individual') {
    if (step === 0)
      validateStudentFull(forms.supervisorIndividual.student, 'supervisorIndividual.student')
  } else if (journey.value === 'supervisor_group') {
    if (step === 0) {
      if (!forms.supervisorGroup.interests.length)
        clientErrors['supervisorGroup.interests'] = 'Choose at least one group interest.'
    }
    if (step === 1) {
      if (forms.supervisorGroup.students.length < 2 || forms.supervisorGroup.students.length > 5) {
        clientErrors['supervisorGroup.size'] = 'A supervisor group must include 2–5 students.'
      }
      forms.supervisorGroup.students.forEach((student, index) =>
        validateStudentFull(student, `supervisorGroup.students.${index}`),
      )
    }
  } else if (journey.value === 'supervisor_csv') {
    if (step === 0 && !forms.supervisorCsv.rows.length) {
      clientErrors['supervisorCsv.file'] = 'Upload a CSV that contains at least one student row.'
    }
    if (step === 1) {
      refreshCsvRows()
      if (!includedCsvRows.value.length) {
        clientErrors['supervisorCsv.rows'] = 'Keep at least one student row in the import.'
      }
      if (csvCounts.value.invalid) {
        clientErrors['supervisorCsv.invalid'] =
          'Edit and correct, or explicitly exclude, every invalid row before continuing.'
      }
    }
  } else if (journey.value === 'mentor') {
    if (step === 0) {
      requireValue('mentor.firstName', forms.mentor.firstName, 'Enter your first name.')
      requireValue('mentor.lastName', forms.mentor.lastName, 'Enter your last name.')
      validateEmail('mentor.email', forms.mentor.email, 'Email')
      requireValue('mentor.country', forms.mentor.country, 'Enter your country.')
      requireValue('mentor.state', forms.mentor.state, 'Enter your state or region.')
    }
    if (step === 1) {
      requireValue('mentor.affiliation', forms.mentor.affiliation, 'Select your affiliation.')
      if (forms.mentor.affiliation === 'industry') {
        requireValue('mentor.company', forms.mentor.company, 'Enter your company or organisation.')
      } else if (forms.mentor.affiliation) {
        requireValue(
          'mentor.institution',
          forms.mentor.institution,
          'Enter your university or institution.',
        )
        requireValue(
          'mentor.fieldOfStudy',
          forms.mentor.fieldOfStudy,
          'Enter your field of study or research.',
        )
      }
      if (['undergraduate', 'postgraduate'].includes(forms.mentor.affiliation)) {
        requireValue(
          'mentor.universityYear',
          forms.mentor.universityYear,
          'Enter your current year of study.',
        )
      }
    }
    if (step === 2) {
      if (!forms.mentor.interests.length)
        clientErrors['mentor.interests'] = 'Choose at least one relevant interest.'
      requireValue(
        'mentor.capacity',
        forms.mentor.capacity,
        'Select how many groups you can support.',
      )
      requireValue(
        'mentor.background',
        forms.mentor.background,
        'Describe your relevant background.',
      )
      requireValue(
        'mentor.motivation',
        forms.mentor.motivation,
        'Tell us why you would like to mentor.',
      )
    }
    if (step === 3) {
      requireValue(
        'mentor.safeguardingJurisdiction',
        forms.mentor.safeguardingJurisdiction,
        'Enter the safeguarding jurisdiction.',
      )
      if (!forms.mentor.complianceDeclaration) {
        clientErrors['mentor.attestation'] =
          'Acknowledge the compliance review and complete the attestation.'
      }
      if (!forms.mentor.attestation) {
        clientErrors['mentor.attestation'] =
          'Acknowledge the compliance review and complete the attestation.'
      }
    }
  }

  if (journey.value !== 'supervisor_csv') validateCrossRoleEmails()
  return !Object.keys(clientErrors).length
}

const focusErrors = async () => {
  await nextTick()
  const invalid = document.querySelector<HTMLElement>(
    '.form-surface [aria-invalid="true"], .form-surface input:invalid',
  )
  if (invalid) invalid.focus()
  else errorSummaryRef.value?.focus()
}

const focusStep = async () => {
  await nextTick()
  stepHeadingRef.value?.focus({ preventScroll: true })
}

const selectJourney = (value: RegistrationJourney) => {
  journey.value = value
  currentStep.value = 0
  maxReachedStep.value = 0
  clearErrors()
  clearServerErrors()
  serverError.value = ''
  focusStep()
}

const beginRegistration = () => {
  selectionStage.value = 'role'
  selectedRole.value = null
  scrollToTop()
}

const selectRole = (role: RegistrationRole) => {
  selectedRole.value = role
  if (role === 'mentor') {
    selectJourney('mentor')
    return
  }
  selectionStage.value = 'pathway'
  scrollToTop()
}

const backToRoleSelection = () => {
  selectionStage.value = 'role'
  selectedRole.value = null
  scrollToTop()
}

const changeJourney = () => {
  if (blockCsvEditorAction()) return
  journey.value = null
  currentStep.value = 0
  maxReachedStep.value = 0
  clearErrors()
  clearServerErrors()
  serverError.value = ''
  selectionStage.value =
    isSupervisorMode.value ||
    selectedRole.value === 'student' ||
    selectedRole.value === 'supervisor'
      ? 'pathway'
      : selectedRole.value === 'mentor'
        ? 'role'
        : 'welcome'
  scrollToTop()
}

const goToStep = (index: number) => {
  if (blockCsvEditorAction()) return
  if (index > maxReachedStep.value || index === currentStep.value) return
  currentStep.value = index
  clearErrors()
  serverError.value = ''
  focusStep()
}

const goBack = () => {
  if (blockCsvEditorAction()) return
  if (currentStep.value === 0) {
    changeJourney()
    return
  }
  currentStep.value -= 1
  clearErrors()
  serverError.value = ''
  focusStep()
}

const continueJourney = async () => {
  if (blockCsvEditorAction()) return
  if (!validateCurrentStep()) {
    await focusErrors()
    return
  }
  const currentJourney = journey.value
  if (currentJourney) {
    const currentServerKeys = Object.keys(serverFieldErrors).filter(
      (key) => earliestRegistrationErrorStep(currentJourney, [key]) === currentStep.value,
    )
    currentServerKeys.forEach((key) => delete serverFieldErrors[key])
  }
  currentStep.value += 1
  maxReachedStep.value = Math.max(maxReachedStep.value, currentStep.value)
  await focusStep()
}

const validateJourneyBeforeSubmit = async () => {
  const reviewStep = steps.value.length - 1
  for (let index = 0; index < reviewStep; index += 1) {
    currentStep.value = index
    if (!validateCurrentStep()) {
      await nextTick()
      await focusErrors()
      return false
    }
  }
  currentStep.value = reviewStep
  clearErrors()
  return true
}

const handlePrimaryAction = () => {
  if (currentStep.value === steps.value.length - 1) {
    submitRegistration()
    return
  }
  continueJourney()
}

const addStudentTeammate = () => {
  if (forms.studentTeam.teammates.length < 4) {
    forms.studentTeam.teammates.push(createPendingPeer())
  }
}

const removeStudentTeammate = (index: number) => {
  if (forms.studentTeam.teammates.length > 1) {
    forms.studentTeam.teammates.splice(index, 1)
    reindexStudentErrors('studentTeam.teammates', index)
  }
}

const addSupervisorGroupStudent = () => {
  if (forms.supervisorGroup.students.length < 5) {
    forms.supervisorGroup.students.push(createStudent({ deferGuardian: true }))
  }
}

const removeSupervisorGroupStudent = (index: number) => {
  if (forms.supervisorGroup.students.length > 2) {
    forms.supervisorGroup.students.splice(index, 1)
    reindexStudentErrors('supervisorGroup.students', index)
  }
}

const reindexErrorMap = (
  errorMap: Record<string, string>,
  prefix: string,
  removedIndex: number,
) => {
  const indexedPrefix = `${prefix}.`
  Object.entries(errorMap).forEach(([key, message]) => {
    if (!key.startsWith(indexedPrefix)) return
    const suffix = key.slice(indexedPrefix.length)
    const separator = suffix.indexOf('.')
    const indexText = separator === -1 ? suffix : suffix.slice(0, separator)
    const fieldIndex = Number(indexText)
    if (!Number.isInteger(fieldIndex) || fieldIndex < removedIndex) return
    delete errorMap[key]
    if (fieldIndex > removedIndex) {
      errorMap[
        `${indexedPrefix}${fieldIndex - 1}${separator === -1 ? '' : suffix.slice(separator)}`
      ] = message
    }
  })
}

const reindexStudentErrors = (prefix: string, removedIndex: number) => {
  reindexErrorMap(clientErrors, prefix, removedIndex)
  reindexErrorMap(serverFieldErrors, prefix, removedIndex)
}

const handlePhoto = (student: StudentDetails, prefix: string, file: File) => {
  delete clientErrors[`${prefix}.profilePhoto`]
  if (!allowedPhotoTypes.has(file.type)) {
    removePhoto(student, prefix)
    clientErrors[`${prefix}.profilePhoto`] = 'Choose a JPG, PNG, or WebP image.'
    return
  }
  if (file.size > MAX_PHOTO_BYTES) {
    removePhoto(student, prefix)
    clientErrors[`${prefix}.profilePhoto`] = 'Choose an image no larger than 5 MB.'
    return
  }
  if (photoPreviews[prefix]) URL.revokeObjectURL(photoPreviews[prefix])
  photoPreviews[prefix] = URL.createObjectURL(file)
  student.profilePhoto = { name: file.name, type: file.type, size: file.size }
  photoFiles.set(student, file)
  submissionKey = ''
}

const removePhoto = (student: StudentDetails, prefix: string) => {
  if (photoPreviews[prefix]) URL.revokeObjectURL(photoPreviews[prefix])
  delete photoPreviews[prefix]
  student.profilePhoto = null
  photoFiles.delete(student)
  submissionKey = ''
  delete clientErrors[`${prefix}.profilePhoto`]
}

const handleCsvUpload = async (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  clearCsvServerErrors()
  csvFileErrors.value = []
  forms.supervisorCsv.rows = []
  forms.supervisorCsv.excludedRowNumbers = []
  forms.supervisorCsv.fileName = ''
  editingCsvRowNumber.value = null
  delete clientErrors['supervisorCsv.file']
  if (!file) return
  if (file.size > MAX_CSV_BYTES) {
    clientErrors['supervisorCsv.file'] = 'Choose a CSV no larger than 2 MB.'
    return
  }
  try {
    const result = parseRegistrationCsv(await file.text())
    if (result.errors.length) {
      csvFileErrors.value = result.errors
      return
    }
    forms.supervisorCsv.fileName = file.name
    forms.supervisorCsv.rows = result.rows
  } catch {
    csvFileErrors.value = [
      'The browser could not read this CSV. Try saving and uploading it again.',
    ]
  }
}

const downloadCsvTemplate = () => {
  const blob = new Blob([registrationCsvTemplate()], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'biotech-registration-template.csv'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

const isCsvRowExcluded = (rowNumber: number) =>
  forms.supervisorCsv.excludedRowNumbers.includes(rowNumber)

const toggleCsvRow = (rowNumber: number) => {
  const previousRows = includedCsvRows.value
  const rowErrors = Object.entries(serverFieldErrors).filter(([key]) =>
    key.startsWith('supervisorCsv.rows.'),
  )
  const existing = forms.supervisorCsv.excludedRowNumbers.indexOf(rowNumber)
  if (existing >= 0) forms.supervisorCsv.excludedRowNumbers.splice(existing, 1)
  else forms.supervisorCsv.excludedRowNumbers.push(rowNumber)
  const nextIndices = new Map(includedCsvRows.value.map((row, index) => [row.rowNumber, index]))
  for (const [key] of rowErrors) delete serverFieldErrors[key]
  for (const [key, error] of rowErrors) {
    const match = /^supervisorCsv\.rows\.(\d+)(\..+)$/.exec(key)
    const previousRow = match ? previousRows[Number(match[1])] : undefined
    if (!match || !previousRow) {
      serverFieldErrors[key] = error
      continue
    }
    const nextIndex = nextIndices.get(previousRow.rowNumber)
    if (nextIndex !== undefined)
      serverFieldErrors[`supervisorCsv.rows.${nextIndex}${match[2]}`] = error
  }
  if (!Object.keys(serverFieldErrors).length) serverError.value = ''
  refreshCsvRows()
}

const clearCsvServerErrors = (row?: CsvRow) => {
  const index = row
    ? includedCsvRows.value.findIndex((candidate) => candidate.rowNumber === row.rowNumber)
    : -1
  const prefix = row ? `supervisorCsv.rows.${index}.` : 'supervisorCsv.'
  for (const key of Object.keys(serverFieldErrors)) {
    if (key.startsWith(prefix)) delete serverFieldErrors[key]
  }
  if (!Object.keys(serverFieldErrors).length) serverError.value = ''
}

const refreshCsvRows = () => {
  forms.supervisorCsv.rows = revalidateRegistrationCsvRows(
    forms.supervisorCsv.rows,
    forms.supervisorCsv.excludedRowNumbers,
  )
  if (!csvCounts.value.invalid) delete clientErrors['supervisorCsv.invalid']
  if (includedCsvRows.value.length) delete clientErrors['supervisorCsv.rows']
}

const editCsvRow = async (rowNumber: number) => {
  editingCsvRowNumber.value = rowNumber
  await nextTick()
  csvEditorHeadingRef.value?.scrollIntoView?.({ block: 'center' })
  csvEditorHeadingRef.value?.focus({ preventScroll: true })
}

const closeCsvEditor = async () => {
  const rowNumber = editingCsvRowNumber.value
  editingCsvRowNumber.value = null
  delete clientErrors['supervisorCsv.editor']
  await nextTick()
  document.getElementById(`csv-edit-${rowNumber}`)?.focus()
}

const blockCsvEditorAction = () => {
  const row = editingCsvRow.value
  if (!isCsvEditing.value || !row) return false
  clientErrors['supervisorCsv.editor'] =
    'Choose Done editing below the row fields before continuing.'
  currentStep.value = 1
  void editCsvRow(row.rowNumber)
  return true
}

const updateCsvRow = (row: CsvRow, values: CsvRow['values']) => {
  clearCsvServerErrors(row)
  row.values = values
  refreshCsvRows()
}

const csvCategoryLabel = (category: CsvCategory) =>
  category === 'review-required' ? 'Review required' : category === 'invalid' ? 'Invalid' : 'Valid'

const submitRegistration = async () => {
  if (!journey.value || isSubmitting.value) return
  if (blockCsvEditorAction()) return
  if (!(await validateJourneyBeforeSubmit())) return
  if (
    registrationWarnings.value.some((warning) => !warningAcknowledgements[warning.overrideField])
  ) {
    warningSummaryRef.value?.focus()
    return
  }
  for (const warning of registrationWarnings.value)
    warningOverrides.value[warning.overrideField] = true
  serverError.value = ''
  isSubmitting.value = true
  try {
    const request = buildRegistrationRequest(journey.value, forms)
    const signature = JSON.stringify({ request, overrides: warningOverrides.value })
    if (!submissionKey || submissionSignature !== signature) submissionKey = crypto.randomUUID()
    submissionSignature = signature
    const attachments: Record<string, File> = {}
    const attach = (student: StudentDetails, prefix: string) => {
      const file = photoFiles.get(student)
      if (file) attachments[prefix] = file
    }
    if (journey.value === 'student_individual')
      attach(forms.studentIndividual.student, 'studentIndividual.student')
    if (journey.value === 'student_team') {
      attach(forms.studentTeam.creator, 'studentTeam.creator')
      forms.studentTeam.teammates.forEach((student, index) =>
        attach(student, `studentTeam.teammates.${index}`),
      )
    }
    if (journey.value === 'supervisor_individual')
      attach(forms.supervisorIndividual.student, 'supervisorIndividual.student')
    if (journey.value === 'supervisor_group')
      forms.supervisorGroup.students.forEach((student, index) =>
        attach(student, `supervisorGroup.students.${index}`),
      )
    const result = await registrationGateway.submit(request, {
      attachments,
      invitationToken: invitationToken.value,
      idempotencyKey: submissionKey,
      overrides: { ...warningOverrides.value },
    })
    clearServerErrors()
    if (!result.ok) {
      if (result.warnings?.length) {
        registrationWarnings.value = result.warnings
        Object.keys(warningAcknowledgements).forEach((key) => delete warningAcknowledgements[key])
        await nextTick()
        warningSummaryRef.value?.scrollIntoView?.({ block: 'center' })
        warningSummaryRef.value?.focus()
        return
      }
      const fieldErrors = result.fieldErrors || {}
      Object.assign(serverFieldErrors, fieldErrors)
      serverError.value = result.message
      const errorStep = earliestRegistrationErrorStep(journey.value, Object.keys(fieldErrors))
      if (errorStep !== null) currentStep.value = errorStep
      if (journey.value === 'supervisor_csv') {
        const rowKey = Object.keys(fieldErrors).find((key) =>
          /^supervisorCsv\.rows\.\d+\./.test(key),
        )
        if (rowKey)
          editingCsvRowNumber.value =
            includedCsvRows.value[Number(rowKey.split('.')[2])]?.rowNumber ?? null
      }
      await focusErrors()
      return
    }
    success.value = result.receipt
    scrollToTop()
  } catch (error) {
    serverError.value =
      error instanceof Error ? error.message : 'The registration service could not be reached.'
    await nextTick()
    document.querySelector<HTMLElement>('.server-error')?.focus()
  } finally {
    isSubmitting.value = false
  }
}

const scrollToTop = () => {
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  window.scrollTo({ top: 0, behavior: reducedMotion ? 'auto' : 'smooth' })
}

const resetRegistration = () => {
  submissionKey = ''
  submissionSignature = ''
  Object.values(photoPreviews).forEach((url) => URL.revokeObjectURL(url))
  Object.keys(photoPreviews).forEach((key) => delete photoPreviews[key])
  Object.assign(forms, createRegistrationForms())
  journey.value = null
  selectedRole.value = isSupervisorMode.value ? 'supervisor' : null
  selectionStage.value = isSupervisorMode.value ? 'pathway' : 'role'
  currentStep.value = 0
  maxReachedStep.value = 0
  success.value = null
  serverError.value = ''
  csvFileErrors.value = []
  editingCsvRowNumber.value = null
  clearErrors()
  clearServerErrors()
  scrollToTop()
}

const startAnotherRegistration = () => {
  const registerStudent = isSupervisorMode.value && journey.value === 'supervisor_individual'
  resetRegistration()
  if (registerStudent) selectJourney('supervisor_individual')
}

const formatSavedDate = (value: string) => {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(date)
}

watch(invitationToken, resetRegistration)
watch(
  forms,
  () => {
    registrationWarnings.value = []
    warningOverrides.value = {}
    Object.keys(warningAcknowledgements).forEach((key) => delete warningAcknowledgements[key])
  },
  { deep: true },
)

onBeforeUnmount(() => {
  Object.values(photoPreviews).forEach((url) => URL.revokeObjectURL(url))
})
</script>

<style scoped>
.registration-warnings {
  margin-block: 1rem;
  padding: 1rem;
  border: 1px solid #9c7940;
  background: #fff8e8;
  color: #543f1e;
  overflow-wrap: anywhere;
}

.registration-warnings h2 {
  margin: 0 0 0.5rem;
  font-size: 1.125rem;
}

.registration-warnings label {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  margin-block-start: 1rem;
  cursor: pointer;
}

.registration-warnings input {
  flex: none;
  margin-block-start: 0.2rem;
}

.registration-page {
  --registration-ink: var(--charcoal);
  --registration-muted: var(--text-muted);
  --registration-green: var(--dark-green);
  --registration-green-dark: #015940;
  --registration-line: var(--border-light);
  --registration-field-line: var(--border-light);
  position: relative;
  min-height: 100vh;
  min-height: 100dvh;
  overflow: hidden;
  background: var(--bg-light);
  color: var(--registration-ink);
  font-family: inherit;
}

.registration-page,
.registration-page * {
  box-sizing: border-box;
}

/* .content-area gives its padding and background; its height is put back
   here over .registration-page's whole screen. */
.registration-page--supervisor {
  min-height: calc(100vh - 60px);
  overflow: visible;
  font-family: inherit;
}

/* From the page's top left corner and its full width, as the portal's
   other pages are. */
.registration-page--supervisor .setup-layout,
.registration-page--supervisor .work-layout {
  width: auto;
  max-width: none;
  margin: 0;
}

/* The page heading's own space below it, as on the first page. */
.registration-page--supervisor .work-layout {
  gap: 0;
}

.registration-page--supervisor .pathway-choices,
.registration-page--supervisor .form-surface {
  border-color: var(--border-light);
  border-radius: 8px;
  background: var(--white, #fff);
  box-shadow: none;
}

.registration-page--supervisor .pathway-choice {
  min-height: 88px;
  padding: 18px 22px;
}

.registration-page--supervisor .pathway-choice:hover,
.registration-page--supervisor .pathway-choice:focus-visible {
  background: var(--light-green, #e9f5ef);
}

.registration-header {
  position: relative;
  z-index: 2;
  width: 100%;
  padding: 14px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  background: var(--dark-green);
}

.brand-link,
.sign-in-link {
  color: #fff;
  text-decoration: none;
}

.brand-link {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  font-size: 1.25rem;
  font-weight: 600;
}

.brand-link img {
  width: 42px;
  height: 42px;
  object-fit: contain;
  padding: 4px;
  border-radius: 50%;
  background: #fff;
}

.sign-in-link {
  font-size: 0.9rem;
  font-weight: 600;
}

.sign-in-link:hover,
.sign-in-link:focus-visible {
  color: #fff;
  text-decoration: underline;
  text-underline-offset: 4px;
}

.work-layout {
  position: relative;
  z-index: 1;
  width: min(1220px, calc(100% - 40px));
  margin: 32px auto 72px;
  display: grid;
  grid-template-columns: minmax(250px, 0.68fr) minmax(0, 1.55fr);
  align-items: start;
  gap: clamp(42px, 6vw, 86px);
}

.welcome-layout {
  position: relative;
  z-index: 1;
  width: min(1120px, calc(100% - 40px));
  min-height: calc(100vh - 116px);
  margin: 12px auto 52px;
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(340px, 0.72fr);
  align-items: center;
  gap: clamp(54px, 8vw, 110px);
}

.welcome-copy h1 {
  margin: 0 0 16px;
  color: var(--registration-ink);
  font-size: 1.75rem;
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.025em;
}

.welcome-actions {
  margin-top: 34px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.welcome-primary {
  min-width: 170px;
}

.welcome-aside {
  padding: clamp(30px, 5vw, 48px);
  border: 1px solid rgba(20, 63, 57, 0.13);
  border-radius: 8px;
  background: var(--white);
}

.welcome-aside__mark {
  width: 58px;
  height: 58px;
  margin-bottom: 28px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #deefe7;
  color: var(--registration-green);
}

.welcome-aside__mark svg {
  width: 36px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
}

.welcome-aside h2 {
  margin: 0;
  font-size: 1.65rem;
  letter-spacing: -0.025em;
}

.welcome-aside ul {
  margin: 22px 0 0;
  padding: 0;
  display: grid;
  gap: 15px;
  list-style: none;
}

.welcome-aside li {
  position: relative;
  padding-left: 25px;
  color: var(--registration-muted);
  line-height: 1.5;
}

.welcome-aside li::before {
  content: '✓';
  position: absolute;
  left: 0;
  color: var(--registration-green);
  font-weight: 900;
}

.setup-layout {
  position: relative;
  z-index: 1;
  width: min(880px, calc(100% - 40px));
  margin: 42px auto 72px;
}

.setup-heading {
  margin: 20px 0 24px;
}

.setup-heading h1 {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.025em;
}

.role-options {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.role-option {
  min-height: 260px;
  padding: 28px;
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: 25px;
  border: 1px solid rgba(20, 63, 57, 0.16);
  border-radius: 8px;
  background: var(--white);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 160ms ease;
}

.role-option:hover,
.role-option:focus-visible {
  border-color: var(--registration-green);
  outline: none;
}

.role-option:focus-visible {
  outline: 2px solid var(--registration-green);
  outline-offset: 3px;
}

.role-option__icon {
  width: 54px;
  height: 54px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #e4f1ea;
  color: var(--registration-green-dark);
}

.role-option__icon svg {
  width: 31px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.7;
}

.role-option__copy {
  display: grid;
  align-content: start;
  gap: 8px;
}

.role-option__copy strong {
  font-size: 1.12rem;
}

.role-option__copy small {
  color: var(--registration-muted);
  font-size: 0.86rem;
  line-height: 1.5;
}

.role-option__arrow {
  color: var(--registration-green);
  font-size: 1.25rem;
  font-weight: 700;
}

.setup-signin {
  margin: 30px 0 0;
  color: var(--registration-muted);
  text-align: center;
}

.setup-signin a {
  color: var(--registration-green-dark);
  font-weight: 700;
}

.supervisor-guidance {
  max-width: 68ch;
  margin: 16px auto 0;
  color: var(--registration-muted);
  text-align: center;
  font-size: 0.9rem;
}

.supervisor-guidance a {
  color: var(--registration-green);
  text-decoration: underline;
}

.pathway-choices {
  overflow: hidden;
  border: 1px solid rgba(20, 63, 57, 0.14);
  border-radius: 8px;
  background: var(--white);
}

.pathway-choice {
  width: 100%;
  min-height: 118px;
  padding: 26px 30px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  border: 0;
  border-bottom: 1px solid var(--registration-line);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.pathway-choice:last-child {
  border-bottom: 0;
}

.pathway-choice:hover,
.pathway-choice:focus-visible {
  outline: none;
  background: #edf5f0;
}

.pathway-choice:focus-visible {
  box-shadow: inset 0 0 0 3px rgba(8, 116, 90, 0.2);
}

.pathway-choice__copy {
  display: grid;
  gap: 7px;
}

.pathway-choice__copy strong {
  font-size: 1.08rem;
}

.pathway-choice__copy small {
  max-width: 62ch;
  color: var(--registration-muted);
  font-size: 0.88rem;
  line-height: 1.5;
}

/* The platform's small outline button (as Group Marking's Next); the whole
   card is the button, so pointing at the card is pointing at it. */
.pathway-choice__arrow {
  flex: 0 0 auto;
}

.pathway-choice:hover .pathway-choice__arrow,
.pathway-choice:focus-visible .pathway-choice__arrow {
  background-color: var(--light-green);
  border-color: var(--dark-green);
}

.work-layout {
  width: min(980px, calc(100% - 40px));
  margin-top: 16px;
  margin-bottom: 40px;
  grid-template-columns: 1fr;
  gap: 16px;
}

.work-layout .journey-context {
  position: static;
  padding: 0;
}

/* Room under it, as under the platform's other back buttons. */
.change-journey {
  margin-bottom: 1rem;
}

.work-layout .journey-context h1:not(.page-title) {
  max-width: none;
  margin: 8px 0 0;
  font-size: clamp(1.5rem, 2vw, 1.75rem);
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.025em;
}

.registration-intro,
.journey-context {
  position: sticky;
  top: 30px;
  padding-top: 26px;
}

.registration-intro h1,
.journey-context h1:not(.page-title),
.success-panel h1 {
  max-width: none;
  margin: 0 0 16px;
  color: var(--registration-ink);
  font-size: 1.75rem;
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.025em;
}

.success-panel > p {
  max-width: 54ch;
  margin: 0;
  color: var(--registration-muted);
  font-size: 1rem;
  line-height: 1.7;
}

.context-note {
  margin-top: 30px;
  padding: 20px 0;
  border-block: 1px solid rgba(8, 116, 90, 0.22);
}

.context-note strong {
  color: var(--registration-green-dark);
  font-size: 0.9rem;
}

.context-note p {
  margin: 7px 0 0;
  color: var(--registration-muted);
  font-size: 0.86rem;
  line-height: 1.55;
}

.pathway-surface,
.form-surface,
.success-panel {
  overflow: hidden;
  border: 1px solid rgba(20, 63, 57, 0.13);
  border-radius: 8px;
  background: var(--white);
}

.pathway-heading {
  padding: clamp(28px, 4vw, 44px);
  border-bottom: 1px solid var(--registration-line);
}

.pathway-heading h2 {
  margin: 0;
  color: var(--registration-ink);
  font-size: clamp(1.5rem, 3vw, 1.75rem);
  letter-spacing: -0.025em;
}

.pathway-heading p {
  margin: 8px 0 0;
  color: var(--registration-muted);
}

.pathway-list {
  display: grid;
}

.pathway-option {
  min-width: 0;
  min-height: 100px;
  padding: 20px clamp(22px, 4vw, 42px);
  display: grid;
  grid-template-columns: 128px minmax(0, 1fr) auto;
  align-items: center;
  gap: 20px;
  border: 0;
  border-bottom: 1px solid var(--registration-line);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    background 160ms ease,
    color 160ms ease;
}

.pathway-option:last-child {
  border-bottom: 0;
}

.pathway-option:hover,
.pathway-option:focus-visible {
  outline: none;
  background: #edf5f0;
}

.pathway-option:focus-visible {
  box-shadow: inset 0 0 0 3px rgba(8, 116, 90, 0.22);
}

.pathway-option__role {
  color: var(--registration-green-dark);
  font-size: 0.78rem;
  font-weight: 700;
  line-height: 1.35;
}

.pathway-option__copy {
  min-width: 0;
  display: grid;
  gap: 5px;
}

.pathway-option__copy strong {
  color: var(--registration-ink);
  font-size: 1rem;
}

.pathway-option__copy small {
  color: var(--registration-muted);
  font-size: 0.84rem;
  line-height: 1.45;
}

.pathway-option__action {
  color: var(--registration-green-dark);
  font-size: 0.84rem;
  font-weight: 700;
  white-space: nowrap;
}

/* On a narrow screen the note drops below the steps, still on the right. */
.step-bar {
  padding: 8px clamp(16px, 3vw, 32px);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  border-bottom: 1px solid var(--registration-line);
  background: var(--white);
}

.step-navigation {
  min-width: 0;
  overflow-x: auto;
}

.step-navigation ol {
  min-width: max-content;
  margin: 0;
  padding: 0;
  display: flex;
  gap: 6px;
  list-style: none;
}

.step-navigation li {
  display: flex;
}

/* The steps are the platform's pill tabs (.tab-pill), each with its number
   in a circle as tall as the pill's line, so it stays a 34px pill. */
.step-navigation button > span {
  width: 1.1rem;
  height: 1.1rem;
  display: grid;
  place-items: center;
  border: 1px solid #aebdb7;
  border-radius: 50%;
  font-size: 0.7rem;
}

.step-navigation__label {
  width: auto !important;
  height: auto !important;
  display: inline !important;
  border: 0 !important;
  border-radius: 0 !important;
  background: transparent !important;
  color: inherit !important;
  font-size: inherit !important;
}

.step-navigation button.complete > span {
  border-color: var(--registration-green);
  background: var(--registration-green);
  color: #fff;
}

/* On the open step's green, the number in white. */
.step-navigation button.current > span {
  border-color: #fff;
  background: #fff;
  color: var(--dark-green);
}

.step-navigation button:disabled {
  background: transparent;
  cursor: not-allowed;
  opacity: 0.52;
}

form {
  padding: clamp(24px, 3vw, 32px);
}

.step-content {
  position: relative;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.step-stack {
  display: grid;
  gap: 30px;
}

.choice-fieldset {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

.choice-fieldset legend {
  padding: 0;
  color: var(--registration-ink);
  font-size: 1rem;
  font-weight: 700;
}

.fieldset-help {
  margin: 6px 0 0;
  color: var(--registration-muted);
  font-size: 0.84rem;
}

.choice-row {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.choice-row > label {
  min-height: 88px;
  padding: 16px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  border: 1px solid var(--registration-field-line);
  border-radius: 4px;
  background: var(--white);
  cursor: pointer;
}

.choice-row > label:has(input:checked) {
  border-color: var(--registration-green);
  background: #edf6f1;
}

.choice-row input,
.attestation-control input,
.prefer-control input,
.exclude-row input {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  margin-top: 2px;
  accent-color: var(--registration-green);
}

.choice-row label > span {
  display: grid;
  gap: 4px;
}

.choice-row strong {
  color: var(--registration-ink);
  font-size: 0.9rem;
}

.choice-row small {
  color: var(--registration-muted);
  font-size: 0.8rem;
  line-height: 1.42;
}

.choice-row input:focus-visible,
.attestation-control input:focus-visible,
.prefer-control input:focus-visible,
.exclude-row input:focus-visible {
  outline: 3px solid rgba(8, 116, 90, 0.22);
  outline-offset: 3px;
}

.scope-explanation {
  padding: 17px 18px;
  border: 1px solid #bdd8cc;
  border-radius: 4px;
  background: #edf6f1;
  color: #315f54;
  font-size: 0.86rem;
  line-height: 1.55;
}

.section-divider {
  padding-top: 28px;
  border-top: 1px solid var(--registration-line);
}

.section-divider--first {
  padding-top: 0;
  border-top: 0;
}

.section-divider h3,
.student-entry__heading h3,
.template-download h3,
.review-section h3 {
  margin: 0;
  color: var(--registration-ink);
  font-size: 1.25rem;
  font-weight: 600;
}

.section-divider p,
.template-download p {
  max-width: 68ch;
  margin: 7px 0 0;
  color: var(--registration-muted);
  font-size: 0.84rem;
  line-height: 1.52;
}

.section-divider--with-action,
.template-download {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.small-action {
  flex: 0 0 auto;
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid var(--registration-green);
  border-radius: 4px;
  background: transparent;
  color: var(--registration-green-dark);
  font: inherit;
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
}

.small-action:hover:not(:disabled),
.small-action:focus-visible {
  background: #e8f3ed;
}

.small-action:focus-visible {
  outline: 3px solid rgba(8, 116, 90, 0.2);
  outline-offset: 2px;
}

.small-action:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

.student-entry {
  padding-top: 28px;
  display: grid;
  gap: 22px;
  border-top: 1px solid var(--registration-line);
}

.student-entry__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.student-entry__heading button {
  min-height: 44px;
  padding: 6px;
  border: 0;
  background: transparent;
  color: #8b302b;
  font: inherit;
  font-size: 0.8rem;
  font-weight: 500;
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
}

.creator-summary dl {
  margin: 0;
  display: grid;
  gap: 8px;
}

.creator-summary dl > div {
  display: grid;
  grid-template-columns: 100px minmax(0, 1fr);
  gap: 16px;
}

.creator-summary .student-entry__heading button {
  color: var(--registration-green);
}

.upload-step {
  display: grid;
  gap: 30px;
}

.template-download {
  padding-bottom: 28px;
  border-bottom: 1px solid var(--registration-line);
}

.csv-upload {
  min-height: 180px;
  padding: 30px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 12px;
  border: 1px dashed #8eaa9f;
  border-radius: 4px;
  background: var(--white);
  text-align: center;
}

.csv-upload > span {
  color: var(--registration-ink);
  font-size: 0.94rem;
  font-weight: 700;
}

.csv-upload small {
  color: var(--registration-muted);
  font-size: 0.82rem;
}

.csv-upload input {
  max-width: 100%;
  color: var(--registration-muted);
  font: inherit;
  font-size: 0.82rem;
}

.csv-upload input::file-selector-button {
  min-height: 40px;
  margin-right: 10px;
  padding: 0 14px;
  border: 1px solid var(--registration-field-line);
  border-radius: 4px;
  background: var(--white);
  color: var(--registration-green-dark);
  font: inherit;
  font-weight: 750;
  cursor: pointer;
}

.csv-preview {
  display: grid;
  gap: 22px;
}

.csv-totals {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-block: 1px solid var(--registration-line);
}

.csv-totals div {
  min-width: 0;
  padding: 18px 12px;
  display: grid;
  justify-items: center;
  gap: 3px;
  border-right: 1px solid var(--registration-line);
}

.csv-totals div:last-child {
  border-right: 0;
}

.csv-totals strong {
  color: var(--registration-ink);
  font-size: 1.5rem;
}

.csv-totals span {
  color: var(--registration-muted);
  font-size: 0.75rem;
  text-align: center;
}

.preview-guidance {
  margin: 0;
  color: var(--registration-muted);
  font-size: 0.86rem;
  line-height: 1.55;
}

.csv-row-editor {
  display: grid;
  gap: 20px;
  padding-block: 22px;
  border-block: 1px solid var(--registration-line);
}

.csv-row-editor h3 {
  margin: 0;
  font-size: 1.1rem;
}

.csv-editor-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}

.csv-edit-action {
  display: block;
  margin-top: 10px;
  padding: 5px 0;
  min-height: 44px;
  border: 0;
  background: transparent;
  color: var(--registration-green-dark);
  font: inherit;
  font-weight: 750;
  text-decoration: underline;
  cursor: pointer;
}

.table-scroll {
  overflow-x: auto;
}

table {
  width: 100%;
  min-width: 780px;
  border-collapse: collapse;
  color: var(--registration-ink);
  font-size: 0.8rem;
}

caption {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

th,
td {
  padding: 13px 12px;
  border-bottom: 1px solid var(--registration-line);
  text-align: left;
  vertical-align: top;
}

th {
  background: #f2f6f2;
  color: #3c5c54;
  font-size: 0.75rem;
}

td ul {
  margin: 6px 0 0;
  padding-left: 16px;
  color: var(--registration-muted);
  line-height: 1.4;
}

tr.is-excluded {
  opacity: 0.52;
  text-decoration: line-through;
}

.csv-status {
  font-size: 0.76rem;
}

.csv-status--valid {
  color: #087057;
}

.csv-status--review-required {
  color: #765a10;
}

.csv-status--invalid {
  color: #9b2f2a;
}

.exclude-row {
  margin-top: 9px;
  display: flex;
  align-items: flex-start;
  gap: 7px;
  color: #803530;
  font-weight: 750;
  cursor: pointer;
}

.affiliation-options {
  margin-top: 14px;
  display: grid;
  border-top: 1px solid var(--registration-line);
}

.affiliation-options label {
  min-height: 48px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid var(--registration-line);
  color: var(--registration-ink);
  font-size: 0.88rem;
  cursor: pointer;
}

.affiliation-options input {
  width: 18px;
  height: 18px;
  accent-color: var(--registration-green);
}

.select-field {
  display: grid;
  align-content: start;
  gap: 7px;
}

.select-field > span {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  color: var(--registration-ink);
  font-size: 0.9rem;
  font-weight: 600;
}

.select-field small {
  color: var(--registration-muted);
  font-size: 0.78rem;
  font-weight: 500;
}

/* As tall as the text boxes beside it (RegistrationTextField). */
.select-field select {
  width: 100%;
  min-height: 2.5rem;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--registration-field-line);
  border-radius: 4px;
  outline: none;
  background: var(--white);
  color: var(--registration-ink);
  font: inherit;
}

.select-field select:focus-visible {
  border-color: var(--registration-green);
  box-shadow: 0 0 0 3px rgba(8, 116, 90, 0.14);
}

.prefer-control {
  min-height: 50px;
  display: flex;
  align-items: center;
  gap: 9px;
  color: var(--registration-muted);
  font-size: 0.82rem;
  cursor: pointer;
}

.attestation-control {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  color: var(--registration-ink);
  font-size: 0.86rem;
  line-height: 1.5;
  cursor: pointer;
}

.review-section dl,
.success-details {
  margin: 0;
}

.review-section dl > div,
.success-details > div {
  padding: 13px 0;
  display: grid;
  grid-template-columns: minmax(130px, 0.48fr) minmax(0, 1fr);
  gap: 20px;
  border-bottom: 1px solid var(--registration-line);
}

.review-section dl > div:last-child,
.success-details > div:last-child {
  border-bottom: 0;
}

dt {
  color: var(--registration-muted);
  font-size: 0.8rem;
}

dd {
  min-width: 0;
  margin: 0;
  color: var(--registration-ink);
  font-size: 0.86rem;
  font-weight: 700;
  overflow-wrap: anywhere;
}

.review-step {
  display: grid;
  gap: 32px;
}

.review-section {
  padding-bottom: 24px;
  border-bottom: 1px solid var(--registration-line);
}

.review-section h3 {
  margin-bottom: 10px;
}

.error-summary,
.server-error {
  margin-bottom: 28px;
  padding: 16px 18px;
  display: grid;
  gap: 5px;
  border: 1px solid #dfb4af;
  border-radius: 4px;
  background: #fff3f1;
  color: #7d2d28;
  font-size: 0.86rem;
  line-height: 1.45;
}

.error-summary:focus {
  outline: 3px solid rgba(153, 44, 39, 0.18);
}

.error-summary ul {
  margin: 4px 0 0;
  padding-left: 18px;
}

.inline-error {
  color: #982c27;
  font-size: 0.82rem;
  line-height: 1.35;
}

.form-required-note {
  margin: 0 0 0 auto;
  color: var(--registration-muted);
  font-size: 0.78rem;
  white-space: nowrap;
}

/* Back on the left (once there's a step to go back to), Continue or Submit
   on the right. */
.form-footer {
  margin-top: 46px;
  display: flex;
  align-items: center;
  gap: 18px;
}

.form-footer .primary-action {
  margin-left: auto;
}

.primary-action,
.secondary-action {
  min-height: 44px;
  padding: 0 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  border-radius: 4px;
  font: inherit;
  font-size: 1rem;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
  transition: background 160ms ease;
}

.primary-action {
  border: 1px solid var(--registration-green);
  background: var(--registration-green);
  color: #fff;
}

.secondary-action {
  border: 1px solid #9eb3ab;
  background: transparent;
  color: var(--registration-green-dark);
}

.primary-action:hover:not(:disabled),
.primary-action:focus-visible {
  background: var(--registration-green-dark);
}

.secondary-action:hover:not(:disabled),
.secondary-action:focus-visible {
  background: #edf5f1;
}

.primary-action:focus-visible,
.secondary-action:focus-visible {
  outline: 3px solid rgba(8, 116, 90, 0.22);
  outline-offset: 3px;
}

.primary-action:disabled,
.secondary-action:disabled {
  cursor: not-allowed;
  opacity: 0.58;
  transform: none;
  box-shadow: none;
}

.spinner {
  width: 17px;
  height: 17px;
  border: 2px solid rgba(255, 255, 255, 0.42);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 700ms linear infinite;
}

.success-panel {
  position: relative;
  z-index: 1;
  width: min(760px, calc(100% - 40px));
  margin: clamp(54px, 10vh, 110px) auto;
  padding: clamp(38px, 7vw, 72px);
}

.success-panel h1 {
  font-size: 1.75rem;
}

.success-mark {
  width: 58px;
  height: 58px;
  margin-bottom: 28px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #dceee5;
  color: var(--registration-green-dark);
}

.success-mark svg {
  width: 32px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.4;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.success-details {
  margin-top: 30px;
  padding-block: 5px;
  border-block: 1px solid var(--registration-line);
}

.success-actions {
  margin-top: 34px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 940px) {
  .work-layout {
    grid-template-columns: 1fr;
    gap: 16px;
    margin-top: 12px;
  }

  .welcome-layout {
    min-height: auto;
    grid-template-columns: 1fr;
    gap: 42px;
    margin-top: 42px;
  }

  .welcome-copy h1 {
    max-width: none;
  }

  .registration-intro,
  .journey-context {
    position: static;
    padding-top: 12px;
  }

  .registration-intro h1,
  .journey-context h1:not(.page-title) {
    max-width: none;
  }

  .context-note {
    max-width: 66ch;
  }
}

@media (max-width: 700px) {
  .registration-header {
    padding: 14px;
  }

  .brand-link span {
    display: none;
  }

  .sign-in-link {
    font-size: 0.82rem;
  }

  .welcome-layout,
  .setup-layout,
  .work-layout {
    width: min(100% - 24px, 1220px);
    margin-bottom: 38px;
  }

  .welcome-layout {
    margin-top: 28px;
  }

  .welcome-copy h1 {
    font-size: 1.5rem;
  }

  .welcome-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .welcome-actions .primary-action,
  .welcome-actions .secondary-action {
    width: 100%;
  }

  .welcome-aside {
    padding: 28px 24px;
  }

  .setup-layout {
    margin-top: 24px;
  }

  .setup-heading {
    margin-top: 20px;
  }

  .setup-heading h1 {
    font-size: 1.5rem;
  }

  .role-options {
    grid-template-columns: 1fr;
  }

  .role-option {
    min-height: 0;
    grid-template-columns: auto 1fr auto;
    grid-template-rows: 1fr;
    align-items: center;
    gap: 18px;
  }

  .pathway-choice {
    min-height: 108px;
    padding: 22px;
  }

  .pathway-choice__arrow {
    display: none;
  }

  .registration-intro h1,
  .journey-context h1:not(.page-title),
  .success-panel h1 {
    font-size: 1.5rem;
  }

  .pathway-option {
    min-height: 112px;
    grid-template-columns: 1fr auto;
    gap: 6px 14px;
  }

  .pathway-option__role {
    grid-column: 1 / -1;
  }

  .pathway-option__copy small {
    max-width: 50ch;
  }

  .step-bar {
    padding-inline: 10px;
  }

  .step-navigation ol {
    min-width: 0;
    width: 100%;
    flex-wrap: wrap;
  }

  .step-navigation button {
    padding-inline: 10px;
  }

  .step-navigation__label {
    display: none !important;
  }

  .step-navigation button.current .step-navigation__label {
    display: inline !important;
  }

  form {
    padding: 27px 20px 30px;
  }

  .step-content {
    min-height: 360px;
  }

  .field-grid,
  .choice-row {
    grid-template-columns: 1fr;
  }

  .section-divider--with-action,
  .template-download {
    flex-direction: column;
  }

  .csv-totals {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .csv-totals div:nth-child(2) {
    border-right: 0;
  }

  .csv-totals div:nth-child(-n + 2) {
    border-bottom: 1px solid var(--registration-line);
  }

  .form-footer .primary-action,
  .form-footer .secondary-action {
    flex: 1 1 0;
  }

  .success-panel {
    width: min(100% - 24px, 760px);
    margin-top: 42px;
    padding: 34px 24px;
  }

  .success-actions {
    align-items: stretch;
    flex-direction: column;
  }
}

@media (max-width: 440px) {
  .pathway-option__action {
    display: none;
  }

  .pathway-option {
    grid-template-columns: 1fr;
  }

  .form-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .form-footer .primary-action {
    margin-left: 0;
  }

  .review-section dl > div,
  .success-details > div {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
</style>
