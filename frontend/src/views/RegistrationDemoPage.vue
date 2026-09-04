<template>
  <main
    class="registration-page"
    :class="{ 'registration-page--supervisor': isSupervisorMode }"
  >
    <div class="page-atmosphere" aria-hidden="true"></div>

    <header v-if="!isSupervisorMode && !isUiTest" class="registration-header">
      <RouterLink to="/login" class="brand-link" aria-label="BIOTech Connect home">
        <img :src="logo" :alt="BRAND_NAME" />
        <span>{{ BRAND_CONNECT }}</span>
      </RouterLink>
      <RouterLink to="/login" class="sign-in-link">Already registered? Sign in</RouterLink>
    </header>

    <div
      v-if="usingDevelopmentAdapter && !isDemo && !isUiTest"
      class="development-notice"
      role="status"
    >
      <strong>Development preview</strong>
      <span>Submissions are simulated in this browser and are not persisted.</span>
    </div>

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
      <div v-if="isDemo" class="simulated-workflows">
        <h2>Shown in the demo, not executed</h2>
        <ul>
          <li v-for="workflow in selectedJourney?.simulations" :key="workflow">{{ workflow }}</li>
        </ul>
      </div>
      <div class="success-actions">
        <button type="button" class="primary-action" @click="resetRegistration">
          Start another journey
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
        <p>
          Register for the BIOTech Futures Challenge, build your team, or volunteer as a mentor.
          We’ll guide you through only the details relevant to you.
        </p>
        <div class="welcome-actions">
          <button type="button" class="primary-action welcome-primary" @click="beginRegistration">
            Register now
          </button>
          <RouterLink to="/login" class="secondary-action">Sign in</RouterLink>
        </div>
        <button v-if="isDemo" type="button" class="invitation-link" @click="openGuardianInvitation">
          Have a guardian consent invitation?
          <span>Continue with your link →</span>
        </button>
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
          <li>
            {{
              isDemo
                ? 'Choose whether you’re a student, supervisor, or mentor.'
                : 'Choose whether you’re a student or mentor.'
            }}
          </li>
          <li>Complete a guided form with clear progress.</li>
          <li>Review everything before you submit.</li>
        </ul>
        <div v-if="isDemo" class="vision-note">
          <strong>Local vision demo</strong>
          <p>
            Submissions save locally. Emails, invitations, consent documents, review decisions, and
            matching are demonstrated but not sent.
          </p>
        </div>
      </aside>
    </section>

    <section
      v-else-if="!journey && selectionStage === 'role'"
      class="setup-layout"
      aria-labelledby="role-title"
    >
      <button type="button" class="setup-back" @click="selectionStage = 'welcome'">← Back</button>
      <div class="setup-progress" aria-label="Registration setup progress">
        <div class="setup-progress__copy">
          <span>Registration setup</span>
          <strong>Step 1 of 2</strong>
        </div>
        <div class="setup-progress__track" aria-hidden="true">
          <span style="width: 50%"></span>
        </div>
      </div>
      <header class="setup-heading">
        <h1 id="role-title">Who are you registering as?</h1>
        <p>Choose the role that best describes you. You can go back before submitting.</p>
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
    </section>

    <section
      v-else-if="!journey && selectionStage === 'pathway'"
      class="setup-layout"
      :class="{ 'setup-layout--supervisor': isSupervisorMode }"
      aria-labelledby="pathway-title"
    >
      <button
        v-if="!isSupervisorMode"
        type="button"
        class="setup-back"
        @click="backToRoleSelection"
      >
        ← Back to roles
      </button>
      <div v-if="!isSupervisorMode" class="setup-progress" aria-label="Registration setup progress">
        <div class="setup-progress__copy">
          <span>Registration setup</span>
          <strong>Step 2 of 2</strong>
        </div>
        <div class="setup-progress__track" aria-hidden="true">
          <span style="width: 100%"></span>
        </div>
      </div>
      <header
        class="setup-heading"
        :class="{ 'setup-heading--supervisor': isSupervisorMode }"
      >
        <h1 id="pathway-title">{{ pathwayHeading }}</h1>
        <p>{{ pathwayDescription }}</p>
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
          <span class="pathway-choice__arrow" aria-hidden="true">Continue →</span>
        </button>
      </div>
    </section>

    <div v-else class="work-layout">
      <aside class="journey-context">
        <button type="button" class="change-journey" @click="changeJourney">
          {{ isUiTest ? 'Restart this test journey' : '← Change registration type' }}
        </button>
        <h1>{{ selectedJourney?.title }}</h1>
        <p>{{ selectedJourney?.description }}</p>
      </aside>

      <section class="form-surface">
        <div
          class="form-progress"
          role="progressbar"
          aria-label="Registration progress"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-valuenow="progressPercent"
        >
          <div class="form-progress__copy">
            <span>{{ selectedJourney?.role }} registration</span>
            <strong>{{ progressPercent }}% complete</strong>
          </div>
          <div class="form-progress__track">
            <span :style="{ width: `${progressPercent}%` }"></span>
          </div>
        </div>
        <nav class="step-navigation" aria-label="Registration progress">
          <ol>
            <li v-for="(step, index) in steps" :key="step.label">
              <button
                type="button"
                :class="{ current: currentStep === index, complete: index < currentStep }"
                :disabled="index > maxReachedStep"
                :aria-current="currentStep === index ? 'step' : undefined"
                @click="goToStep(index)"
              >
                <span>{{ index + 1 }}</span>
                <span class="step-navigation__label">{{ step.label }}</span>
              </button>
            </li>
          </ol>
        </nav>

        <form novalidate :aria-busy="isSubmitting" @submit.prevent="handlePrimaryAction">
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
            <header class="step-header">
              <p>{{ currentStep + 1 }} of {{ steps.length }}</p>
              <h2 :id="stepHeadingId" ref="stepHeadingRef" tabindex="-1">
                {{ currentStepDefinition.title }}
              </h2>
              <span>{{ currentStepDefinition.description }}</span>
            </header>

            <template v-if="journey === 'student_individual'">
              <RegistrationStudentEditor
                v-if="currentStep === 0"
                :student="forms.studentIndividual.student"
                prefix="studentIndividual.student"
                section="identity"
                :errors="errors"
                require-email-confirm
              />

              <RegistrationStudentEditor
                v-else-if="currentStep === 1"
                :student="forms.studentIndividual.student"
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
                        value="school"
                      />
                      <span>
                        <strong>Existing school supervisor</strong>
                        <small
                          >A teacher or school staff member already supporting the challenge.</small
                        >
                      </span>
                    </label>
                    <label>
                      <input
                        v-model="forms.studentIndividual.supervisorMode"
                        type="radio"
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
                  A parent-supervisor confirms their email and may view this student’s high-level
                  status and update school, year, interests, and profile photo. This does not create
                  teacher or administrator access, reveal guardian records or consent PDFs, or
                  authorize consent. Consent still uses the guardian’s recipient-bound link.
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
                    Required for individual self-registration. Saving these details does not record
                    consent.
                  </p>
                </div>
                <RegistrationStudentEditor
                  :student="forms.studentIndividual.student"
                  prefix="studentIndividual.student"
                  section="guardian"
                  :errors="errors"
                />
              </div>
            </template>

            <template v-else-if="journey === 'student_team'">
              <RegistrationStudentEditor
                v-if="currentStep === 0"
                :student="forms.studentTeam.creator"
                prefix="studentTeam.creator"
                section="identity"
                :errors="errors"
                require-email-confirm
              />

              <div v-else-if="currentStep === 2" class="step-stack">
                <RegistrationInterestSelector
                  id="student-team-interests"
                  v-model="forms.studentTeam.interests"
                  label="Team interests"
                  description="Choose one or more areas the team would like to explore together."
                  :error="errors['studentTeam.interests']"
                />
                <div class="section-divider section-divider--with-action">
                  <div>
                    <h3>Teammates</h3>
                    <p>
                      Add 1–4 teammates for a total team size of 2–5. Each person receives their own
                      action journey and completes their own guardian flow.
                    </p>
                  </div>
                  <button
                    type="button"
                    class="small-action"
                    :disabled="forms.studentTeam.teammates.length >= 4"
                    @click="addStudentTeammate"
                  >
                    Add teammate
                  </button>
                </div>

                <div
                  v-for="(teammate, index) in forms.studentTeam.teammates"
                  :key="`teammate-${index}`"
                  class="student-entry"
                >
                  <div class="student-entry__heading">
                    <h3>Teammate {{ index + 1 }}</h3>
                    <button
                      v-if="forms.studentTeam.teammates.length > 1"
                      type="button"
                      @click="removeStudentTeammate(index)"
                    >
                      Remove
                    </button>
                  </div>
                  <RegistrationStudentEditor
                    :student="teammate"
                    :prefix="`studentTeam.teammates.${index}`"
                    section="teammate"
                    :errors="errors"
                    require-email-confirm
                  />
                </div>
              </div>

              <div v-else-if="currentStep === 1" class="step-stack">
                <RegistrationStudentEditor
                  :student="forms.studentTeam.creator"
                  prefix="studentTeam.creator"
                  section="profile"
                  :errors="errors"
                  show-optional-profile
                  :preview-url="photoPreviews['studentTeam.creator']"
                  @photo-selected="
                    handlePhoto(forms.studentTeam.creator, 'studentTeam.creator', $event)
                  "
                  @remove-photo="removePhoto(forms.studentTeam.creator, 'studentTeam.creator')"
                />
                <div class="section-divider">
                  <h3>Creator’s supervisor</h3>
                  <p>
                    Choose an existing school supervisor or a parent supporting only this student.
                  </p>
                </div>
                <fieldset class="choice-fieldset">
                  <legend>Supervisor type</legend>
                  <div class="choice-row">
                    <label>
                      <input
                        v-model="forms.studentTeam.supervisorMode"
                        type="radio"
                        value="school"
                      />
                      <span>
                        <strong>Existing school supervisor</strong>
                        <small
                          >A teacher or school staff member already supporting the challenge.</small
                        >
                      </span>
                    </label>
                    <label>
                      <input
                        v-model="forms.studentTeam.supervisorMode"
                        type="radio"
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
                  <h3>Creator’s guardian contact</h3>
                  <p>
                    This can be deferred in the team pathway. Every teammate supplies their own
                    guardian details privately; the team creator never sees those details or consent
                    documents.
                  </p>
                </div>
                <RegistrationStudentEditor
                  :student="forms.studentTeam.creator"
                  prefix="studentTeam.creator"
                  section="guardian"
                  :errors="errors"
                  allow-guardian-defer
                />
              </div>
            </template>

            <template v-else-if="journey === 'supervisor_individual'">
              <RegistrationStudentEditor
                v-if="currentStep === 0"
                :student="forms.supervisorIndividual.student"
                prefix="supervisorIndividual.student"
                section="full"
                :errors="errors"
                allow-guardian-defer
                require-email-confirm
              />

              <div v-else-if="currentStep === 1" class="step-stack">
                <fieldset class="choice-fieldset">
                  <legend>Future group preference</legend>
                  <p class="fieldset-help">
                    This student is being registered without a pre-formed team.
                  </p>
                  <div class="choice-row">
                    <label>
                      <input
                        v-model="forms.supervisorIndividual.groupingPreference"
                        type="radio"
                        value="school_only"
                      />
                      <span>
                        <strong>School-only grouping</strong>
                        <small>Prefer teammates from this student’s school.</small>
                      </span>
                    </label>
                    <label>
                      <input
                        v-model="forms.supervisorIndividual.groupingPreference"
                        type="radio"
                        value="cross_school"
                      />
                      <span>
                        <strong>Cross-school grouping</strong>
                        <small>Allow grouping with students from other schools.</small>
                      </span>
                    </label>
                  </div>
                </fieldset>
                <div class="scope-explanation">
                  If guardian details were deferred, the student’s own action journey would collect
                  them before consent. The registration records that required next step without
                  granting full registration.
                </div>
              </div>
            </template>

            <template v-else-if="journey === 'supervisor_group'">
              <div v-if="currentStep === 0" class="step-stack">
                <RegistrationInterestSelector
                  id="supervisor-group-interests"
                  v-model="forms.supervisorGroup.interests"
                  label="Group interests"
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
                    :student="student"
                    :prefix="`supervisorGroup.students.${index}`"
                    section="full"
                    :errors="errors"
                    allow-guardian-defer
                    require-email-confirm
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
                      Keep the column names unchanged. Separate multiple interests with a vertical
                      bar (|). Guardian fields may be left blank.
                    </p>
                  </div>
                  <button type="button" class="secondary-action" @click="downloadCsvTemplate">
                    Download example template
                  </button>
                </div>
                <label class="csv-upload">
                  <span>Choose completed CSV <span aria-hidden="true">*</span></span>
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
                  Review-required rows can be included for authoritative review. Invalid rows block
                  submission until you correct and re-upload the file, or explicitly exclude each
                  invalid row.
                </p>
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
                          <ul v-if="row.issues.length">
                            <li v-for="issue in row.issues" :key="issue">{{ issue }}</li>
                          </ul>
                          <label v-if="row.category === 'invalid'" class="exclude-row">
                            <input
                              type="checkbox"
                              :checked="isCsvRowExcluded(row.rowNumber)"
                              @change="toggleCsvRow(row.rowNumber)"
                            />
                            Exclude this invalid row
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
                  label="Phone"
                  type="tel"
                  autocomplete="tel"
                  optional
                />
                <RegistrationTextField
                  id="mentor-country"
                  v-model="forms.mentor.country"
                  label="Country"
                  :error="errors['mentor.country']"
                  required
                />
                <RegistrationTextField
                  id="mentor-state"
                  v-model="forms.mentor.state"
                  label="State or region"
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
                  description="Choose the areas where you could support a student team."
                  :error="errors['mentor.interests']"
                />
                <label class="select-field">
                  <span>Capacity <span aria-hidden="true">*</span></span>
                  <select
                    id="mentor-capacity"
                    v-model="forms.mentor.capacity"
                    :aria-invalid="Boolean(errors['mentor.capacity'])"
                    :aria-describedby="
                      errors['mentor.capacity'] ? 'mentor-capacity-error' : undefined
                    "
                    required
                  >
                    <option value="" disabled>Select team capacity</option>
                    <option v-for="count in ['1', '2', '3', '4', '5']" :key="count" :value="count">
                      {{ count }} {{ count === '1' ? 'team' : 'teams' }}
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
                  hint="Describe experience that would help you support a student team."
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

            <template v-else-if="isDemo && journey === 'guardian_consent'">
              <div v-if="currentStep === 0" class="step-stack">
                <div class="invitation-preview">
                  <dl>
                    <div>
                      <dt>Invitation reference</dt>
                      <dd>{{ forms.guardianConsent.invitationReference }}</dd>
                    </div>
                    <div>
                      <dt>Named student</dt>
                      <dd>{{ forms.guardianConsent.studentName }}</dd>
                    </div>
                    <div>
                      <dt>Form wording</dt>
                      <dd>{{ forms.guardianConsent.wordingVersion }}</dd>
                    </div>
                  </dl>
                </div>
                <div class="scope-explanation">
                  This is a preview using a demonstration invitation. Production access must resolve
                  a recipient-bound invitation to one named student. Exact consent wording, policy
                  links, approver, and enabled version remain approval controlled.
                </div>
                <div class="field-grid">
                  <RegistrationTextField
                    id="guardian-invitation-reference"
                    v-model="forms.guardianConsent.invitationReference"
                    label="Invitation reference"
                    :error="errors['guardianConsent.invitationReference']"
                    readonly
                    required
                  />
                  <RegistrationTextField
                    id="guardian-student-name"
                    v-model="forms.guardianConsent.studentName"
                    label="Named student"
                    :error="errors['guardianConsent.studentName']"
                    readonly
                    required
                  />
                </div>
              </div>

              <div v-else-if="currentStep === 1" class="step-stack">
                <div class="field-grid">
                  <RegistrationTextField
                    id="guardian-first"
                    v-model="forms.guardianConsent.guardianFirstName"
                    label="Guardian first name"
                    :error="errors['guardianConsent.guardianFirstName']"
                    required
                  />
                  <RegistrationTextField
                    id="guardian-last"
                    v-model="forms.guardianConsent.guardianLastName"
                    label="Guardian last name"
                    :error="errors['guardianConsent.guardianLastName']"
                    required
                  />
                  <RegistrationTextField
                    id="guardian-email"
                    v-model="forms.guardianConsent.guardianEmail"
                    label="Guardian email"
                    type="email"
                    :error="errors['guardianConsent.guardianEmail']"
                    required
                  />
                  <RegistrationTextField
                    id="guardian-phone"
                    v-model="forms.guardianConsent.phone"
                    label="Phone"
                    type="tel"
                    optional
                  />
                  <label class="select-field">
                    <span>Relationship <span aria-hidden="true">*</span></span>
                    <select
                      id="guardian-consent-relationship"
                      v-model="forms.guardianConsent.relationship"
                      :aria-invalid="Boolean(errors['guardianConsent.relationship'])"
                      :aria-describedby="
                        errors['guardianConsent.relationship']
                          ? 'guardian-consent-relationship-error'
                          : undefined
                      "
                      required
                    >
                      <option value="" disabled>Select a relationship</option>
                      <option>Parent</option>
                      <option>Legal guardian</option>
                      <option>Other</option>
                    </select>
                    <span
                      v-if="errors['guardianConsent.relationship']"
                      id="guardian-consent-relationship-error"
                      class="inline-error"
                    >
                      {{ errors['guardianConsent.relationship'] }}
                    </span>
                  </label>
                  <RegistrationTextField
                    v-if="forms.guardianConsent.relationship === 'Other'"
                    id="guardian-relationship-other"
                    v-model="forms.guardianConsent.relationshipOther"
                    label="Describe the relationship"
                    :error="errors['guardianConsent.relationshipOther']"
                    required
                  />
                </div>
              </div>

              <div v-else-if="currentStep === 2" class="step-stack">
                <div class="consent-copy">
                  <h3>Participation acknowledgement</h3>
                  <p>
                    I acknowledge the named student’s participation in the BIOTech Futures
                    Challenge, including online and potentially in-person activities. This preview
                    stands in for the fuller approved safety, privacy, intellectual-property, and
                    participation wording required in production.
                  </p>
                  <label class="attestation-control">
                    <input
                      v-model="forms.guardianConsent.participationAcknowledged"
                      type="checkbox"
                      :aria-invalid="Boolean(errors['guardianConsent.participationAcknowledged'])"
                      :aria-describedby="
                        errors['guardianConsent.participationAcknowledged']
                          ? 'guardian-participation-error'
                          : undefined
                      "
                      required
                    />
                    <span>I acknowledge and agree to the participation statement above.</span>
                  </label>
                  <span
                    v-if="errors['guardianConsent.participationAcknowledged']"
                    id="guardian-participation-error"
                    class="inline-error"
                  >
                    {{ errors['guardianConsent.participationAcknowledged'] }}
                  </span>
                </div>

                <fieldset
                  class="choice-fieldset"
                  :aria-invalid="Boolean(errors['guardianConsent.mediaConsent'])"
                  :aria-describedby="
                    errors['guardianConsent.mediaConsent'] ? 'guardian-media-error' : undefined
                  "
                >
                  <legend>Media consent</legend>
                  <p class="fieldset-help">Choose Yes or No. No option is selected by default.</p>
                  <div class="choice-row">
                    <label>
                      <input
                        v-model="forms.guardianConsent.mediaConsent"
                        type="radio"
                        value="yes"
                        :aria-invalid="Boolean(errors['guardianConsent.mediaConsent'])"
                        required
                      />
                      <span>
                        <strong>Yes</strong>
                        <small>I give media consent for the named student.</small>
                      </span>
                    </label>
                    <label>
                      <input
                        v-model="forms.guardianConsent.mediaConsent"
                        type="radio"
                        value="no"
                        :aria-invalid="Boolean(errors['guardianConsent.mediaConsent'])"
                        required
                      />
                      <span>
                        <strong>No</strong>
                        <small>I do not give media consent for the named student.</small>
                      </span>
                    </label>
                  </div>
                  <span
                    v-if="errors['guardianConsent.mediaConsent']"
                    id="guardian-media-error"
                    class="inline-error"
                  >
                    {{ errors['guardianConsent.mediaConsent'] }}
                  </span>
                </fieldset>
                <div class="scope-explanation">
                  Choosing No does not prevent online participation. It may affect eligibility for
                  in-person events; the final event policy and production consequence wording remain
                  subject to client approval.
                </div>
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
              <div class="review-boundary">
                <strong>{{ isDemo ? 'Before you save' : 'Before you submit' }}</strong>
                <p v-if="isDemo">
                  This sends a structured vision-demo record to the local BIOTech service. It does
                  not execute production email, invitations, guardian consent documents,
                  administrator decisions, or matching.
                </p>
                <p v-else-if="journey === 'mentor'">
                  These browser checks provide initial feedback only. Your application remains
                  pending safeguarding and administrator review after submission.
                </p>
                <p v-else>
                  These browser checks provide initial feedback only. Guardian consent is still
                  required before every student can complete registration. The registration service
                  will perform authoritative validation when connected.
                </p>
              </div>
            </div>
          </section>

          <footer class="form-footer">
            <button type="button" class="secondary-action" :disabled="isSubmitting" @click="goBack">
              {{ currentStep === 0 ? 'Back to registration type' : 'Back' }}
            </button>
            <p>Fields marked * are required.</p>
            <button type="submit" class="primary-action" :disabled="isSubmitting">
              <span v-if="isSubmitting" class="spinner" aria-hidden="true"></span>
              {{
                isSubmitting
                  ? isDemo
                    ? 'Saving locally…'
                    : 'Submitting…'
                  : currentStep === steps.length - 1
                    ? isDemo
                      ? 'Save demo registration'
                      : 'Submit registration'
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
import { computed, inject, nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import logo from '@/assets/btf-logo.png'
import RegistrationInterestSelector from '@/components/registration/RegistrationInterestSelector.vue'
import RegistrationStudentEditor from '@/components/registration/RegistrationStudentEditor.vue'
import RegistrationTextField from '@/components/registration/RegistrationTextField.vue'
import { BRAND_CONNECT, BRAND_NAME } from '@/constants/brand'
import { developmentRegistrationGateway } from '@/registration/developmentRegistrationGateway'
import { earliestRegistrationErrorStep } from '@/registration/registrationErrorNavigation'
import {
  buildRegistrationRequest,
  REGISTRATION_GATEWAY_KEY,
  type RegistrationGateway,
  type RegistrationReceipt,
} from '@/registration/registrationGateway'
import {
  createRegistrationForms,
  createStudent,
  findCrossRoleEmailConflicts,
  isValidRegistrationEmail,
  parseRegistrationCsv,
  registrationCsvTemplate,
  type CsvCategory,
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
  simulations: string[]
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
const allowedPhotoTypes = new Set(['image/jpeg', 'image/png', 'image/webp'])
const emailLikePattern = /\b[^\s@]+@[^\s@]+\.[^\s@]+\b/i

const roleOptions: RoleOption[] = [
  {
    value: 'student',
    title: 'Student',
    description: 'Register yourself or create a team with classmates.',
  },
  {
    value: 'supervisor',
    title: 'Supervisor or teacher',
    description: 'Register students individually, as a group, or from a CSV.',
  },
  {
    value: 'mentor',
    title: 'Mentor',
    description: 'Apply to support student teams with your expertise.',
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
    simulations: [
      'Student email confirmation',
      'Guardian recipient-bound invitation and consent',
      'Registration review and downstream group matching',
    ],
  },
  {
    value: 'student_team',
    role: 'Student',
    title: 'Create a student team',
    description: 'Start a team of 2–5 and invite each teammate into their own action journey.',
    steps: [
      {
        label: 'Creator',
        title: 'Start with your details',
        description: 'You will be the team creator for this registration.',
      },
      {
        label: 'Your profile',
        title: 'Complete your own details first',
        description: 'Add your school, profile, supervisor, and guardian contact before the team.',
      },
      {
        label: 'Team',
        title: 'Build your team',
        description: 'Choose team interests and add 1–4 teammates.',
      },
      {
        label: 'Review',
        title: 'Review the team registration',
        description: 'Check the intended team before saving.',
      },
    ],
    simulations: [
      'Individual teammate action links',
      'Private guardian flows for every student',
      'Group readiness and existing Mentor Matching handoff',
    ],
  },
  {
    value: 'supervisor_individual',
    role: 'Supervisor / teacher',
    title: 'Register one student',
    description: 'Add one ungrouped student and record their future grouping preference.',
    steps: [
      {
        label: 'Student',
        title: 'Add the student',
        description: 'Guardian contact may be supplied now or deferred.',
      },
      {
        label: 'Grouping',
        title: 'Set the grouping preference',
        description: 'Choose how this ungrouped student may be placed later.',
      },
      {
        label: 'Review',
        title: 'Review the student registration',
        description: 'Check the record before saving.',
      },
    ],
    simulations: [
      'Student action and status link',
      'Guardian detail reminder and consent invitation',
      'Supervisor action summary and automatic grouping',
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
        description: 'Choose the shared interest preferences.',
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
    simulations: [
      'Individual student action links',
      'Per-student guardian reminders and consent',
      'Group readiness and supervisor summary',
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
    simulations: [
      'Student action links for approved rows',
      'Pending review routing for review-required rows',
      'Import summary and notification ledger',
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
    simulations: [
      'Restricted safeguarding/compliance review',
      'Administrator approval or decline',
      'Eligibility handoff to existing Mentor Matching',
    ],
  },
  {
    value: 'guardian_consent',
    role: 'Guardian preview',
    title: 'Preview guardian consent',
    description: 'Review a recipient-bound consent journey for one named student.',
    steps: [
      {
        label: 'Invitation',
        title: 'Confirm the invitation context',
        description: 'Production access is bound to a recipient and named student.',
      },
      {
        label: 'Guardian',
        title: 'Your guardian details',
        description: 'Identify your relationship to the named student.',
      },
      {
        label: 'Consent',
        title: 'Record participation and media choices',
        description: 'Participation and media are separate decisions.',
      },
      {
        label: 'Review',
        title: 'Review the consent preview',
        description: 'Exact production wording and version remain approval controlled.',
      },
    ],
    simulations: [
      'Recipient-bound invitation validation',
      'Guardian receipt and scoped consent document',
      'Student and supervisor status notifications',
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
    mode?: 'canonical' | 'demo' | 'supervisor' | 'ui-test'
    initialJourney?: RegistrationJourney | null
  }>(),
  { mode: 'canonical', initialJourney: null },
)
const isDemo = computed(() => props.mode === 'demo')
const isUiTest = computed(() => props.mode === 'ui-test')
const isSupervisorMode = computed(() => props.mode === 'supervisor')
const injectedGateway = inject(REGISTRATION_GATEWAY_KEY, null)
const unavailableGateway: RegistrationGateway = {
  async submit() {
    return {
      ok: false,
      message: 'Registration submission is not configured in this environment.',
    }
  },
}
const forceDevelopmentAdapter = isDemo.value || isUiTest.value
const usingDevelopmentAdapter =
  forceDevelopmentAdapter || (!injectedGateway && import.meta.env.DEV)
const registrationGateway = forceDevelopmentAdapter
  ? developmentRegistrationGateway
  : injectedGateway || (usingDevelopmentAdapter ? developmentRegistrationGateway : unavailableGateway)
const forms = reactive(createRegistrationForms())
const journey = ref<RegistrationJourney | null>(props.initialJourney)
const selectionStage = ref<SelectionStage>(
  isSupervisorMode.value ? 'pathway' : props.initialJourney ? 'pathway' : 'welcome',
)
const selectedRole = ref<RegistrationRole | null>(
  props.initialJourney?.startsWith('supervisor_')
    ? 'supervisor'
    : props.initialJourney?.startsWith('student_')
      ? 'student'
      : props.initialJourney === 'mentor'
        ? 'mentor'
        : isSupervisorMode.value
          ? 'supervisor'
          : null,
)
const currentStep = ref(0)
const maxReachedStep = ref(0)
const errors = reactive<Record<string, string>>({})
const csvFileErrors = ref<string[]>([])
const photoPreviews = reactive<Record<string, string>>({})
const serverError = ref('')
const isSubmitting = ref(false)
const success = ref<RegistrationReceipt | null>(null)
const stepHeadingRef = ref<HTMLElement | null>(null)
const errorSummaryRef = ref<HTMLElement | null>(null)

const selectedJourney = computed(() =>
  journey.value ? journeyOptions.find((option) => option.value === journey.value) : undefined,
)
const visibleRoleOptions = computed(() =>
  isDemo.value ? roleOptions : roleOptions.filter((role) => role.value !== 'supervisor'),
)
const successHeading = computed(() =>
  usingDevelopmentAdapter
    ? journey.value === 'mentor'
      ? 'Application preview complete'
      : 'Registration preview complete'
    : journey.value === 'mentor'
      ? 'Application received'
      : 'Registration details received',
)
const successMessage = computed(() => {
  if (isDemo.value) return 'This local development submission was saved with reference'
  if (journey.value === 'mentor') {
    return 'Your application is pending safeguarding and administrator review. Reference'
  }
  return 'Guardian consent is still required before full registration. Reference'
})
const steps = computed(() => selectedJourney.value?.steps || [])
const progressPercent = computed(() =>
  steps.value.length ? Math.round(((currentStep.value + 1) / steps.value.length) * 100) : 0,
)
const roleJourneyOptions = computed(() => {
  if (selectedRole.value === 'student') {
    return journeyOptions.filter((option) =>
      ['student_individual', 'student_team'].includes(option.value),
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
const pathwayDescription = computed(() =>
  selectedRole.value === 'student'
    ? 'Register individually or start a team with classmates.'
    : 'Choose the method that matches the students you are registering today.',
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
const errorMessages = computed(() => [...new Set(Object.values(errors))])
const includedCsvRows = computed(() =>
  forms.supervisorCsv.rows.filter(
    (row) => !forms.supervisorCsv.excludedRowNumbers.includes(row.rowNumber),
  ),
)
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
                  : 'Existing school supervisor',
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
          title: 'Team',
          items: [
            { label: 'Total students', value: String(forms.studentTeam.teammates.length + 1) },
            { label: 'Interests', value: interestSummary(forms.studentTeam.interests) },
          ],
        },
        {
          title: 'People',
          items: [
            {
              label: 'Creator',
              value: `${studentName(forms.studentTeam.creator)} · ${forms.studentTeam.creator.email}`,
            },
            ...forms.studentTeam.teammates.map((student, index) => ({
              label: `Teammate ${index + 1}`,
              value: `${studentName(student)} · ${student.email}`,
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
            {
              label: 'Grouping preference',
              value:
                forms.supervisorIndividual.groupingPreference === 'school_only'
                  ? 'School only'
                  : 'Cross-school',
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
              value: `${forms.mentor.capacity} team${forms.mentor.capacity === '1' ? '' : 's'}`,
            },
            { label: 'Safeguarding status', value: 'Pending administrator review' },
            { label: 'Matching access', value: 'Not activated by this submission' },
          ],
        },
      ]
    case 'guardian_consent':
      return [
        {
          title: 'Invitation and guardian',
          items: [
            { label: 'Reference', value: forms.guardianConsent.invitationReference },
            { label: 'Student', value: forms.guardianConsent.studentName },
            {
              label: 'Guardian',
              value: `${forms.guardianConsent.guardianFirstName} ${forms.guardianConsent.guardianLastName}`,
            },
            {
              label: 'Relationship',
              value:
                forms.guardianConsent.relationship === 'Other'
                  ? forms.guardianConsent.relationshipOther
                  : forms.guardianConsent.relationship,
            },
          ],
        },
        {
          title: 'Choices',
          items: [
            {
              label: 'Participation',
              value: forms.guardianConsent.participationAcknowledged
                ? 'Acknowledged'
                : 'Not acknowledged',
            },
            { label: 'Media', value: forms.guardianConsent.mediaConsent === 'yes' ? 'Yes' : 'No' },
            { label: 'Wording version', value: forms.guardianConsent.wordingVersion },
          ],
        },
      ]
    default:
      return []
  }
})

const clearErrors = () => {
  Object.keys(errors).forEach((key) => delete errors[key])
}

const requireValue = (key: string, value: string, message: string) => {
  const trimmed = value.trim()
  if (!trimmed) {
    errors[key] = message
    return
  }
  if (!key.toLowerCase().includes('email') && emailLikePattern.test(trimmed)) {
    errors[key] = 'Enter a name or description here, not an email address.'
  }
}

const validateEmail = (key: string, value: string, label: string) => {
  requireValue(key, value, `Enter the ${label.toLowerCase()}.`)
  if (value.trim() && !isValidRegistrationEmail(value))
    errors[key] = `Enter a valid ${label.toLowerCase()}.`
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
      errors[`${prefix}.emailConfirm`] = 'The student email addresses do not match.'
    }
  }
}

const validateStudentProfile = (student: StudentDetails, prefix: string) => {
  requireValue(`${prefix}.school`, student.school, 'Enter the student school.')
  requireValue(`${prefix}.yearLevel`, student.yearLevel, 'Select the student year level.')
  requireValue(`${prefix}.country`, student.country, 'Enter the student country.')
  if (!student.interests.length)
    errors[`${prefix}.interests`] = 'Choose at least one student interest.'
  if (student.pronouns === 'Other') {
    requireValue(`${prefix}.pronounsOther`, student.pronounsOther, 'Enter the student pronouns.')
  }
}

const validateGuardian = (student: StudentDetails, prefix: string) => {
  if (student.guardianDeferred) return
  const guardian = student.guardian
  requireValue(`${prefix}.guardian.firstName`, guardian.firstName, 'Enter the guardian first name.')
  requireValue(`${prefix}.guardian.lastName`, guardian.lastName, 'Enter the guardian last name.')
  validateEmail(`${prefix}.guardian.email`, guardian.email, 'Guardian email')
  requireValue(
    `${prefix}.guardian.relationship`,
    guardian.relationship,
    'Select the guardian relationship.',
  )
  if (guardian.relationship === 'Other') {
    requireValue(
      `${prefix}.guardian.relationshipOther`,
      guardian.relationshipOther,
      'Describe the guardian relationship.',
    )
  }
}

const validateStudentFull = (student: StudentDetails, prefix: string) => {
  validateStudentIdentity(student, prefix, true)
  validateStudentProfile(student, prefix)
  validateGuardian(student, prefix)
}

const validateCrossRoleEmails = () => {
  if (!journey.value) return
  const conflicts = findCrossRoleEmailConflicts(journey.value, forms)
  conflicts.forEach((message, index) => {
    errors[`emailConflict.${index}`] = message
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
      validateGuardian(forms.studentIndividual.student, 'studentIndividual.student')
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
      validateGuardian(forms.studentTeam.creator, 'studentTeam.creator')
    }
    if (step === 2) {
      if (!forms.studentTeam.interests.length) {
        errors['studentTeam.interests'] = 'Choose at least one team interest.'
      }
      if (forms.studentTeam.teammates.length < 1 || forms.studentTeam.teammates.length > 4) {
        errors['studentTeam.size'] = 'A student-created team must include 1–4 teammates.'
      }
      forms.studentTeam.teammates.forEach((student, index) =>
        validateStudentIdentity(student, `studentTeam.teammates.${index}`, true),
      )
    }
  } else if (journey.value === 'supervisor_individual') {
    if (step === 0)
      validateStudentFull(forms.supervisorIndividual.student, 'supervisorIndividual.student')
  } else if (journey.value === 'supervisor_group') {
    if (step === 0) {
      if (!forms.supervisorGroup.interests.length) {
        errors['supervisorGroup.interests'] = 'Choose at least one group interest.'
      }
    }
    if (step === 1) {
      if (forms.supervisorGroup.students.length < 2 || forms.supervisorGroup.students.length > 5) {
        errors['supervisorGroup.size'] = 'A supervisor group must include 2–5 students.'
      }
      forms.supervisorGroup.students.forEach((student, index) =>
        validateStudentFull(student, `supervisorGroup.students.${index}`),
      )
    }
  } else if (journey.value === 'supervisor_csv') {
    if (step === 0 && !forms.supervisorCsv.rows.length) {
      errors['supervisorCsv.file'] = 'Upload a CSV that contains at least one student row.'
    }
    if (step === 1) {
      if (!includedCsvRows.value.length) {
        errors['supervisorCsv.rows'] = 'Keep at least one student row in the import.'
      }
      if (csvCounts.value.invalid) {
        errors['supervisorCsv.invalid'] =
          'Correct and re-upload, or explicitly exclude, every invalid row before continuing.'
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
        errors['mentor.interests'] = 'Choose at least one relevant interest.'
      requireValue(
        'mentor.capacity',
        forms.mentor.capacity,
        'Select how many teams you can support.',
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
        errors['mentor.attestation'] =
          'Acknowledge the compliance review and complete the attestation.'
      }
      if (!forms.mentor.attestation) {
        errors['mentor.attestation'] =
          'Acknowledge the compliance review and complete the attestation.'
      }
    }
  } else if (journey.value === 'guardian_consent') {
    if (step === 0) {
      requireValue(
        'guardianConsent.invitationReference',
        forms.guardianConsent.invitationReference,
        'Enter the invitation reference.',
      )
      requireValue(
        'guardianConsent.studentName',
        forms.guardianConsent.studentName,
        'Enter the named student.',
      )
    }
    if (step === 1) {
      requireValue(
        'guardianConsent.guardianFirstName',
        forms.guardianConsent.guardianFirstName,
        'Enter the guardian first name.',
      )
      requireValue(
        'guardianConsent.guardianLastName',
        forms.guardianConsent.guardianLastName,
        'Enter the guardian last name.',
      )
      validateEmail(
        'guardianConsent.guardianEmail',
        forms.guardianConsent.guardianEmail,
        'Guardian email',
      )
      requireValue(
        'guardianConsent.relationship',
        forms.guardianConsent.relationship,
        'Select the guardian relationship.',
      )
      if (forms.guardianConsent.relationship === 'Other') {
        requireValue(
          'guardianConsent.relationshipOther',
          forms.guardianConsent.relationshipOther,
          'Describe the guardian relationship.',
        )
      }
    }
    if (step === 2) {
      if (!forms.guardianConsent.participationAcknowledged) {
        errors['guardianConsent.participationAcknowledged'] =
          'Acknowledge participation to continue.'
      }
      requireValue(
        'guardianConsent.mediaConsent',
        forms.guardianConsent.mediaConsent,
        'Choose Yes or No for media consent.',
      )
    }
  }

  validateCrossRoleEmails()
  return !Object.keys(errors).length
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

const openGuardianInvitation = () => {
  selectedRole.value = null
  selectJourney('guardian_consent')
}

const changeJourney = () => {
  if (isUiTest.value && props.initialJourney) {
    resetRegistration()
    return
  }
  journey.value = null
  currentStep.value = 0
  maxReachedStep.value = 0
  clearErrors()
  serverError.value = ''
  selectionStage.value =
    isSupervisorMode.value || selectedRole.value === 'student' || selectedRole.value === 'supervisor'
      ? 'pathway'
      : selectedRole.value === 'mentor'
        ? 'role'
        : 'welcome'
  scrollToTop()
}

const goToStep = (index: number) => {
  if (index > maxReachedStep.value || index === currentStep.value) return
  currentStep.value = index
  clearErrors()
  serverError.value = ''
  focusStep()
}

const goBack = () => {
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
  if (!validateCurrentStep()) {
    await focusErrors()
    return
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
    forms.studentTeam.teammates.push(createStudent({ deferGuardian: true }))
  }
}

const removeStudentTeammate = (index: number) => {
  if (forms.studentTeam.teammates.length > 1) forms.studentTeam.teammates.splice(index, 1)
}

const addSupervisorGroupStudent = () => {
  if (forms.supervisorGroup.students.length < 5) {
    forms.supervisorGroup.students.push(createStudent({ deferGuardian: true }))
  }
}

const removeSupervisorGroupStudent = (index: number) => {
  if (forms.supervisorGroup.students.length > 2) forms.supervisorGroup.students.splice(index, 1)
}

const handlePhoto = (student: StudentDetails, prefix: string, file: File) => {
  delete errors[`${prefix}.profilePhoto`]
  if (!allowedPhotoTypes.has(file.type)) {
    removePhoto(student, prefix)
    errors[`${prefix}.profilePhoto`] = 'Choose a JPG, PNG, or WebP image.'
    return
  }
  if (file.size > MAX_PHOTO_BYTES) {
    removePhoto(student, prefix)
    errors[`${prefix}.profilePhoto`] = 'Choose an image no larger than 5 MB.'
    return
  }
  if (photoPreviews[prefix]) URL.revokeObjectURL(photoPreviews[prefix])
  photoPreviews[prefix] = URL.createObjectURL(file)
  student.profilePhoto = { name: file.name, type: file.type, size: file.size }
}

const removePhoto = (student: StudentDetails, prefix: string) => {
  if (photoPreviews[prefix]) URL.revokeObjectURL(photoPreviews[prefix])
  delete photoPreviews[prefix]
  student.profilePhoto = null
  delete errors[`${prefix}.profilePhoto`]
}

const handleCsvUpload = async (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  csvFileErrors.value = []
  forms.supervisorCsv.rows = []
  forms.supervisorCsv.excludedRowNumbers = []
  forms.supervisorCsv.fileName = ''
  delete errors['supervisorCsv.file']
  if (!file) return
  if (file.size > MAX_CSV_BYTES) {
    errors['supervisorCsv.file'] = 'Choose a CSV no larger than 2 MB.'
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
  const existing = forms.supervisorCsv.excludedRowNumbers.indexOf(rowNumber)
  if (existing >= 0) forms.supervisorCsv.excludedRowNumbers.splice(existing, 1)
  else forms.supervisorCsv.excludedRowNumbers.push(rowNumber)
}

const csvCategoryLabel = (category: CsvCategory) =>
  category === 'review-required' ? 'Review required' : category === 'invalid' ? 'Invalid' : 'Valid'

const submitRegistration = async () => {
  if (!journey.value || journey.value === 'guardian_consent' || isSubmitting.value) return
  if (!(await validateJourneyBeforeSubmit())) return
  serverError.value = ''
  isSubmitting.value = true
  try {
    const result = await registrationGateway.submit(buildRegistrationRequest(journey.value, forms))
    if (!result.ok) {
      const fieldErrors = result.fieldErrors || {}
      Object.assign(errors, fieldErrors)
      serverError.value = result.message
      const errorStep = earliestRegistrationErrorStep(journey.value, Object.keys(fieldErrors))
      if (errorStep !== null) currentStep.value = errorStep
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
  Object.values(photoPreviews).forEach((url) => URL.revokeObjectURL(url))
  Object.keys(photoPreviews).forEach((key) => delete photoPreviews[key])
  Object.assign(forms, createRegistrationForms())
  journey.value = props.initialJourney
  selectedRole.value = props.initialJourney?.startsWith('supervisor_')
    ? 'supervisor'
    : props.initialJourney?.startsWith('student_')
      ? 'student'
      : props.initialJourney === 'mentor'
        ? 'mentor'
        : isSupervisorMode.value
          ? 'supervisor'
          : null
  selectionStage.value =
    isSupervisorMode.value || props.initialJourney ? 'pathway' : 'welcome'
  currentStep.value = 0
  maxReachedStep.value = 0
  success.value = null
  serverError.value = ''
  csvFileErrors.value = []
  clearErrors()
  scrollToTop()
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

onBeforeUnmount(() => {
  Object.values(photoPreviews).forEach((url) => URL.revokeObjectURL(url))
})
</script>

<style scoped>
.registration-page {
  --registration-ink: #143f39;
  --registration-muted: #526d67;
  --registration-green: #08745a;
  --registration-green-dark: #075642;
  --registration-line: #d8e2dd;
  --registration-field-line: #bdcec7;
  position: relative;
  min-height: 100vh;
  min-height: 100dvh;
  overflow: hidden;
  background: #f5f2e9;
  color: var(--registration-ink);
  font-family: Arial, Helvetica, sans-serif;
}

.registration-page,
.registration-page * {
  box-sizing: border-box;
}

.registration-page--supervisor {
  --registration-ink: var(--text-main, #253730);
  --registration-muted: var(--text-soft, #66756f);
  --registration-green: var(--dark-green, #017151);
  --registration-green-dark: var(--dark-green, #017151);
  --registration-line: var(--line-mid, rgba(14, 31, 25, 0.14));
  min-height: auto;
  overflow: visible;
  background: var(--bg-light, #f8f9fa);
  font-family: inherit;
}

.registration-page--supervisor .page-atmosphere {
  display: none;
}

.registration-page--supervisor .setup-layout,
.registration-page--supervisor .work-layout {
  width: min(100%, 1080px);
  margin-right: auto;
  margin-bottom: 32px;
  margin-left: auto;
}

.registration-page--supervisor .pathway-choices,
.registration-page--supervisor .form-surface {
  border-color: var(--line-mid, rgba(14, 31, 25, 0.14));
  border-radius: 12px;
  background: var(--white, #fff);
  box-shadow: var(--shadow-soft, 0 12px 28px rgba(7, 17, 15, 0.06));
}

.registration-page--supervisor .pathway-choice {
  min-height: 88px;
  padding: 18px 22px;
}

.registration-page--supervisor .pathway-choice:hover,
.registration-page--supervisor .pathway-choice:focus-visible {
  background: var(--light-green, #e9f5ef);
}

.registration-page--supervisor .work-layout .journey-context h1 {
  max-width: none;
  font-size: clamp(1.6rem, 3vw, 2.25rem);
  line-height: 1.15;
  letter-spacing: -0.025em;
}

.page-atmosphere {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at 7% 10%, rgba(85, 145, 132, 0.18), transparent 30rem),
    radial-gradient(circle at 96% 2%, rgba(232, 210, 126, 0.22), transparent 28rem);
}

.registration-header {
  position: relative;
  z-index: 2;
  width: min(1220px, calc(100% - 40px));
  margin: 0 auto;
  padding: 24px 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.development-notice {
  position: relative;
  z-index: 2;
  width: min(1220px, calc(100% - 40px));
  margin: 0 auto;
  padding: 10px 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  border: 1px solid #c5d5ce;
  border-radius: 10px;
  background: #edf5f0;
  color: var(--registration-muted);
  font-size: 0.82rem;
}

.development-notice strong {
  color: var(--registration-green-dark);
}

.brand-link,
.sign-in-link {
  color: var(--registration-ink);
  text-decoration: none;
}

.brand-link {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  font-size: 1.02rem;
  font-weight: 800;
}

.brand-link img {
  width: 42px;
  height: 42px;
  object-fit: contain;
}

.sign-in-link {
  font-size: 0.9rem;
  font-weight: 750;
}

.sign-in-link:hover,
.sign-in-link:focus-visible {
  color: var(--registration-green);
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
  max-width: 10ch;
  margin: 0 0 24px;
  color: var(--registration-ink);
  font-size: clamp(3rem, 7vw, 5.8rem);
  line-height: 0.96;
  letter-spacing: -0.045em;
}

.welcome-copy > p {
  max-width: 60ch;
  margin: 0;
  color: var(--registration-muted);
  font-size: 1.08rem;
  line-height: 1.7;
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

.invitation-link {
  margin-top: 28px;
  padding: 0;
  display: grid;
  gap: 4px;
  border: 0;
  background: transparent;
  color: var(--registration-muted);
  font: inherit;
  font-size: 0.88rem;
  text-align: left;
  cursor: pointer;
}

.invitation-link span {
  color: var(--registration-green-dark);
  font-weight: 800;
}

.invitation-link:hover span,
.invitation-link:focus-visible span {
  text-decoration: underline;
  text-underline-offset: 4px;
}

.invitation-link:focus-visible {
  outline: 3px solid rgba(8, 116, 90, 0.22);
  outline-offset: 6px;
}

.welcome-aside {
  padding: clamp(30px, 5vw, 48px);
  border: 1px solid rgba(20, 63, 57, 0.13);
  border-radius: 24px;
  background: #fffefa;
  box-shadow: 0 28px 68px rgba(29, 62, 56, 0.11);
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

.setup-back {
  padding: 4px 0;
  border: 0;
  background: transparent;
  color: var(--registration-green-dark);
  font: inherit;
  font-size: 0.88rem;
  font-weight: 800;
  cursor: pointer;
}

.setup-back:hover,
.setup-back:focus-visible {
  text-decoration: underline;
  text-underline-offset: 4px;
}

.setup-progress {
  margin-top: 30px;
}

.setup-progress__copy,
.form-progress__copy {
  margin-bottom: 9px;
  display: flex;
  justify-content: space-between;
  gap: 20px;
  color: var(--registration-muted);
  font-size: 0.82rem;
}

.setup-progress__copy strong,
.form-progress__copy strong {
  color: var(--registration-green-dark);
}

.setup-progress__track,
.form-progress__track {
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: #dbe5e0;
}

.setup-progress__track span,
.form-progress__track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--registration-green);
}

.setup-heading {
  margin: 50px 0 34px;
}

.setup-heading h1 {
  max-width: 15ch;
  margin: 0;
  font-size: clamp(2.4rem, 6vw, 4.25rem);
  line-height: 1;
  letter-spacing: -0.04em;
}

.setup-heading p {
  max-width: 58ch;
  margin: 16px 0 0;
  color: var(--registration-muted);
  font-size: 1rem;
  line-height: 1.6;
}

.setup-layout.setup-layout--supervisor {
  margin-top: 28px;
}

.setup-heading.setup-heading--supervisor {
  margin: 20px 0 24px;
}

.setup-heading--supervisor h1 {
  max-width: none;
  font-size: clamp(1.75rem, 3vw, 2.5rem);
  line-height: 1.15;
  letter-spacing: -0.025em;
}

.setup-heading--supervisor p {
  margin-top: 8px;
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
  border-radius: 18px;
  background: #fffefa;
  color: inherit;
  text-align: left;
  cursor: pointer;
  box-shadow: 0 16px 38px rgba(29, 62, 56, 0.07);
  transition:
    border-color 160ms ease,
    transform 160ms ease,
    box-shadow 160ms ease;
}

.role-option:hover,
.role-option:focus-visible {
  border-color: var(--registration-green);
  outline: none;
  transform: translateY(-3px);
  box-shadow: 0 22px 44px rgba(29, 62, 56, 0.12);
}

.role-option:focus-visible {
  box-shadow:
    0 22px 44px rgba(29, 62, 56, 0.12),
    0 0 0 3px rgba(8, 116, 90, 0.2);
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
  font-weight: 800;
}

.setup-signin {
  margin: 30px 0 0;
  color: var(--registration-muted);
  text-align: center;
}

.setup-signin a {
  color: var(--registration-green-dark);
  font-weight: 800;
}

.pathway-choices {
  overflow: hidden;
  border: 1px solid rgba(20, 63, 57, 0.14);
  border-radius: 20px;
  background: #fffefa;
  box-shadow: 0 24px 58px rgba(29, 62, 56, 0.09);
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

.pathway-choice__arrow {
  flex: 0 0 auto;
  color: var(--registration-green-dark);
  font-size: 0.86rem;
  font-weight: 800;
}

.work-layout {
  width: min(980px, calc(100% - 40px));
  grid-template-columns: 1fr;
  gap: 26px;
}

.work-layout .journey-context {
  position: static;
  padding: 0;
}

.work-layout .journey-context h1 {
  max-width: 18ch;
  margin: 18px 0 10px;
  font-size: clamp(2rem, 4vw, 3.2rem);
}

.form-progress {
  padding: 24px clamp(24px, 4vw, 48px) 18px;
  border-bottom: 1px solid var(--registration-line);
  background: #fffefa;
}

.registration-intro,
.journey-context {
  position: sticky;
  top: 30px;
  padding-top: 26px;
}

.registration-intro h1,
.journey-context h1,
.success-panel h1 {
  max-width: 12ch;
  margin: 0 0 20px;
  color: var(--registration-ink);
  font-size: clamp(2.6rem, 5vw, 4.9rem);
  line-height: 0.98;
  letter-spacing: -0.04em;
}

.journey-context h1 {
  margin-top: 24px;
  font-size: clamp(2.25rem, 4vw, 3.8rem);
}

.registration-intro > p,
.journey-context > p,
.success-panel > p {
  max-width: 54ch;
  margin: 0;
  color: var(--registration-muted);
  font-size: 1rem;
  line-height: 1.7;
}

.vision-note,
.context-note {
  margin-top: 30px;
  padding: 20px 0;
  border-block: 1px solid rgba(8, 116, 90, 0.22);
}

.vision-note strong,
.context-note strong {
  color: var(--registration-green-dark);
  font-size: 0.9rem;
}

.vision-note p,
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
  border-radius: 20px;
  background: #fffefa;
  box-shadow: 0 28px 68px rgba(29, 62, 56, 0.11);
}

.pathway-heading {
  padding: clamp(28px, 4vw, 44px);
  border-bottom: 1px solid var(--registration-line);
}

.pathway-heading h2 {
  margin: 0;
  color: var(--registration-ink);
  font-size: clamp(1.65rem, 3vw, 2.3rem);
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
  font-weight: 800;
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
  font-weight: 800;
  white-space: nowrap;
}

.change-journey {
  padding: 4px 0;
  border: 0;
  background: transparent;
  color: var(--registration-green-dark);
  font: inherit;
  font-size: 0.84rem;
  font-weight: 800;
  cursor: pointer;
}

.change-journey:hover,
.change-journey:focus-visible {
  text-decoration: underline;
  text-underline-offset: 4px;
}

.step-navigation {
  overflow-x: auto;
  padding: 0 clamp(24px, 4vw, 48px);
  border-bottom: 1px solid var(--registration-line);
  background: #f8faf7;
}

.step-navigation ol {
  min-width: max-content;
  margin: 0;
  padding: 0;
  display: flex;
  list-style: none;
}

.step-navigation li {
  display: flex;
}

.step-navigation button {
  min-height: 78px;
  padding: 0 18px;
  display: flex;
  align-items: center;
  gap: 9px;
  border: 0;
  border-bottom: 3px solid transparent;
  background: transparent;
  color: #6a7d77;
  font: inherit;
  font-size: 0.82rem;
  font-weight: 750;
  cursor: pointer;
}

.step-navigation button > span {
  width: 25px;
  height: 25px;
  display: grid;
  place-items: center;
  border: 1px solid #aebdb7;
  border-radius: 50%;
  font-size: 0.74rem;
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

.step-navigation button.current {
  border-bottom-color: var(--registration-green);
  color: var(--registration-ink);
}

.step-navigation button.current > span,
.step-navigation button.complete > span {
  border-color: var(--registration-green);
  background: var(--registration-green);
  color: #fff;
}

.step-navigation button:focus-visible {
  outline: 3px solid rgba(8, 116, 90, 0.22);
  outline-offset: -4px;
}

.step-navigation button:disabled {
  cursor: not-allowed;
  opacity: 0.52;
}

form {
  padding: clamp(28px, 5vw, 54px);
}

.step-content {
  min-height: 440px;
}

.step-header {
  margin-bottom: 36px;
}

.step-header p {
  margin: 0 0 7px;
  color: var(--registration-green-dark);
  font-size: 0.78rem;
  font-weight: 800;
}

.step-header h2 {
  max-width: 22ch;
  margin: 0;
  color: var(--registration-ink);
  font-size: clamp(1.75rem, 4vw, 2.7rem);
  line-height: 1.08;
  letter-spacing: -0.03em;
}

.step-header h2:focus {
  outline: none;
}

.step-header > span {
  max-width: 68ch;
  margin-top: 10px;
  display: block;
  color: var(--registration-muted);
  font-size: 0.92rem;
  line-height: 1.55;
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
  font-weight: 800;
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
  border-radius: 12px;
  background: #fffefa;
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

.scope-explanation,
.review-boundary {
  padding: 17px 18px;
  border: 1px solid #bdd8cc;
  border-radius: 12px;
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
.consent-copy h3,
.simulated-workflows h2,
.review-section h3 {
  margin: 0;
  color: var(--registration-ink);
  font-size: 1rem;
}

.section-divider p,
.template-download p,
.consent-copy p {
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
  border-radius: 10px;
  background: transparent;
  color: var(--registration-green-dark);
  font: inherit;
  font-size: 0.82rem;
  font-weight: 800;
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
  padding: 3px;
  border: 0;
  background: transparent;
  color: #8b302b;
  font: inherit;
  font-size: 0.8rem;
  font-weight: 750;
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
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
  border-radius: 14px;
  background: #f8faf7;
  text-align: center;
}

.csv-upload > span {
  color: var(--registration-ink);
  font-size: 0.94rem;
  font-weight: 800;
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
  border-radius: 10px;
  background: #fffefa;
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
  display: flex;
  justify-content: space-between;
  color: var(--registration-ink);
  font-size: 0.9rem;
  font-weight: 750;
}

.select-field small {
  color: var(--registration-muted);
  font-size: 0.78rem;
  font-weight: 500;
}

.select-field select {
  width: 100%;
  min-height: 50px;
  padding: 0 42px 0 15px;
  border: 1px solid var(--registration-field-line);
  border-radius: 12px;
  outline: none;
  background: #fffefa;
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

.consent-copy {
  padding-bottom: 30px;
  display: grid;
  gap: 16px;
  border-bottom: 1px solid var(--registration-line);
}

.invitation-preview {
  padding-block: 8px;
  border-block: 1px solid var(--registration-line);
}

.invitation-preview dl,
.review-section dl,
.success-details {
  margin: 0;
}

.invitation-preview dl > div,
.review-section dl > div,
.success-details > div {
  padding: 13px 0;
  display: grid;
  grid-template-columns: minmax(130px, 0.48fr) minmax(0, 1fr);
  gap: 20px;
  border-bottom: 1px solid var(--registration-line);
}

.invitation-preview dl > div:last-child,
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

.review-boundary p {
  margin: 5px 0 0;
}

.error-summary,
.server-error {
  margin-bottom: 28px;
  padding: 16px 18px;
  display: grid;
  gap: 5px;
  border: 1px solid #dfb4af;
  border-radius: 12px;
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

.form-footer {
  margin-top: 46px;
  padding-top: 24px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 18px;
  border-top: 1px solid var(--registration-line);
}

.form-footer p {
  margin: 0;
  color: var(--registration-muted);
  font-size: 0.78rem;
  text-align: center;
}

.primary-action,
.secondary-action {
  min-height: 48px;
  padding: 0 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  border-radius: 11px;
  font: inherit;
  font-size: 0.9rem;
  font-weight: 800;
  text-decoration: none;
  cursor: pointer;
  transition:
    transform 160ms ease,
    background 160ms ease,
    box-shadow 160ms ease;
}

.primary-action {
  border: 1px solid var(--registration-green);
  background: var(--registration-green);
  color: #fff;
  box-shadow: 0 10px 22px rgba(8, 116, 90, 0.2);
}

.secondary-action {
  border: 1px solid #9eb3ab;
  background: transparent;
  color: var(--registration-green-dark);
}

.primary-action:hover:not(:disabled),
.primary-action:focus-visible {
  transform: translateY(-1px);
  background: var(--registration-green-dark);
  box-shadow: 0 14px 28px rgba(8, 116, 90, 0.24);
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
  max-width: 14ch;
  font-size: clamp(2.5rem, 6vw, 4.4rem);
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

.simulated-workflows {
  margin-top: 30px;
}

.simulated-workflows ul {
  margin: 10px 0 0;
  padding-left: 20px;
  color: var(--registration-muted);
  font-size: 0.88rem;
  line-height: 1.65;
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
    gap: 34px;
    margin-top: 12px;
  }

  .welcome-layout {
    min-height: auto;
    grid-template-columns: 1fr;
    gap: 42px;
    margin-top: 42px;
  }

  .welcome-copy h1 {
    max-width: 12ch;
  }

  .registration-intro,
  .journey-context {
    position: static;
    padding-top: 12px;
  }

  .registration-intro h1,
  .journey-context h1 {
    max-width: 15ch;
  }

  .context-note {
    max-width: 66ch;
  }
}

@media (max-width: 700px) {
  .registration-header {
    width: min(100% - 28px, 1220px);
    padding-block: 18px;
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
    font-size: clamp(2.7rem, 14vw, 4rem);
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
    margin-top: 38px;
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
  .journey-context h1,
  .success-panel h1 {
    font-size: clamp(2.35rem, 12vw, 3.6rem);
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

  .step-navigation {
    padding-inline: 10px;
  }

  .step-navigation ol {
    min-width: 0;
    width: 100%;
    justify-content: space-around;
  }

  .step-navigation button {
    min-height: 66px;
    padding-inline: 8px;
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

  .form-footer {
    grid-template-columns: 1fr 1fr;
  }

  .form-footer p {
    grid-column: 1 / -1;
    grid-row: 1;
  }

  .form-footer .primary-action,
  .form-footer .secondary-action {
    width: 100%;
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
    grid-template-columns: 1fr;
  }

  .form-footer p {
    grid-column: auto;
  }

  .invitation-preview dl > div,
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
