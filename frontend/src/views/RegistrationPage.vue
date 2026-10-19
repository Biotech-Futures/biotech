<template>
  <!-- A supervisor's, in the portal: laid out as its other pages are; or
       within Management > Registration (embedded), as its cards are. -->
  <main
    class="registration-page"
    :class="{
      'registration-page--supervisor': isSupervisorMode,
      'content-area': isSupervisorMode && !embedded,
      'registration-page--embedded': embedded,
    }"
  >

    <!-- Registered: as the steps before it, every step done, with what was
         saved (public or a supervisor's alike). -->
    <div v-if="success" class="work-layout">
      <aside class="journey-context">
        <!-- A supervisor's: back to the options, as on the steps. -->
        <button
          v-if="isSupervisorMode"
          type="button"
          class="btn btn-outline back-button change-journey"
          @click="resetRegistration"
        >
          <i class="fas fa-arrow-left" aria-hidden="true"></i> Back
        </button>
        <header class="page-header">
          <h1 class="page-title">{{ selectedJourney?.title }}</h1>
          <p v-if="isSupervisorMode" class="page-subtitle">{{ selectedJourney?.description }}</p>
        </header>
      </aside>

      <section class="form-surface" aria-live="polite">
        <div class="step-bar">
          <nav class="step-navigation" aria-label="Registration progress">
            <ol>
              <li v-for="(step, index) in steps" :key="step.label">
                <span class="tab-pill complete">
                  <span>{{ index + 1 }}</span>
                  <span class="step-navigation__label">{{ step.label }}</span>
                </span>
              </li>
            </ol>
          </nav>
        </div>

        <!-- What Review showed, then when it was registered. -->
        <div class="success-body">
          <div class="success-intro">
            <!-- Registration Complete, or a mentor's Application received, ticked. -->
            <h3>
              {{ successHeading }}
              <i class="fas fa-circle-check success-check" aria-hidden="true"></i>
            </h3>
            <p class="success-note">{{ successNote }}</p>
          </div>
          <div class="review-step">
            <div
              v-for="(section, sectionIndex) in reviewSections"
              :key="section.title"
              class="review-section"
            >
              <h3>{{ section.title }}</h3>
              <dl>
                <div
                  v-for="item in section.items"
                  :key="item.label"
                  :class="{ 'review-row--joined': item.joinNext }"
                >
                  <dt>{{ item.label }}</dt>
                  <dd v-if="item.parts" class="review-parts">
                    <span v-for="(part, index) in item.parts" :key="index">{{ part }}</span>
                  </dd>
                  <dd v-else-if="item.copy" class="review-copy">
                    <span>{{ item.value }}</span>
                    <button
                      type="button"
                      class="btn btn-outline btn-sm"
                      @click="copyGroupCode(item.copy)"
                    >
                      <i
                        :class="groupCodeCopied ? 'fas fa-check' : 'fas fa-copy'"
                        aria-hidden="true"
                      ></i>
                      {{ groupCodeCopied ? 'Copied' : 'Copy' }}
                    </button>
                  </dd>
                  <dd v-else>{{ item.value || 'Not provided' }}</dd>
                </div>
                <!-- When, as the last section's last row. -->
                <div v-if="sectionIndex === reviewSections.length - 1">
                  <dt>Registration completed</dt>
                  <dd>{{ formatDayMonthTime(success.submittedAt) }}</dd>
                </div>
              </dl>
            </div>
          </div>

          <!-- A supervisor's: another of the same (Back above goes to the
               options). Someone registering themselves: what happens next,
               and sign in. -->
          <footer class="form-footer">
            <button
              v-if="isSupervisorMode"
              type="button"
              class="primary-action"
              @click="startAnotherRegistration"
            >
              {{ anotherLabel }}
            </button>
            <template v-else>
              <p class="form-footer-note">
                We will contact you after we set up and activate your account
              </p>
              <RouterLink to="/login" class="primary-action">Return to sign in</RouterLink>
            </template>
          </footer>
        </div>
      </section>
    </div>

    <!-- Closed by its dates (Management > Registration): to the
         public, but for a late link; to a supervisor, unless let register
         after them. -->
    <section v-else-if="registrationClosed" class="setup-layout" aria-labelledby="closed-title">
      <RouterLink v-if="!isSupervisorMode" to="/login" class="btn btn-outline back-button setup-back">
        <i class="fas fa-arrow-left" aria-hidden="true"></i> Back
      </RouterLink>
      <header class="page-header">
        <h1 id="closed-title" class="page-title">Registration is closed</h1>
      </header>
      <p v-if="isSupervisorMode" class="supervisor-guidance">
        Registration has closed, so students can't be registered here. If you need to register
        more students, contact <a :href="`mailto:${SUPPORT_EMAIL}`">BIOTech Support</a>.
      </p>
      <p v-else class="supervisor-guidance">
        Registration isn't open at the moment. If you have a late link, use it to register, or
        contact <a :href="`mailto:${SUPPORT_EMAIL}`">BIOTech Support</a>.
      </p>
    </section>

    <section
      v-else-if="!journey && selectionStage === 'role'"
      class="setup-layout"
      aria-labelledby="role-title"
    >
      <!-- Back to the login page, where Register now comes from. -->
      <RouterLink to="/login" class="btn btn-outline back-button setup-back">
        <i class="fas fa-arrow-left" aria-hidden="true"></i> Back
      </RouterLink>
      <header class="page-header">
        <h1 id="role-title" class="page-title">Who are you registering as?</h1>
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
          <span class="btn btn-outline btn-sm role-option__arrow" aria-hidden="true">
            Continue <i class="fas fa-chevron-right"></i>
          </span>
        </button>
      </div>
      <p class="setup-signin">
        Already have an account? <RouterLink to="/login">Sign in</RouterLink>
      </p>
      <p v-if="!invitationToken" class="supervisor-guidance">
        If you are a supervisor, please
        contact <a :href="`mailto:${SUPPORT_EMAIL}`">BIOTech Support</a> for an invitation.
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
        class="btn btn-outline back-button setup-back"
        @click="backToRoleSelection"
      >
        <i class="fas fa-arrow-left" aria-hidden="true"></i> Back to Roles
      </button>
      <!-- The platform's own page heading (a supervisor's with its subtext). -->
      <header class="page-header">
        <h1 id="pathway-title" class="page-title">{{ pathwayHeading }}</h1>
        <p v-if="isSupervisorMode" class="page-subtitle">
          Register students individually, as a group or from a CSV.
        </p>
      </header>
      <!-- A student: whether they have a group, as cards like the roles'. -->
      <div v-if="isStudentPathway" class="role-options">
        <button
          v-for="option in studentPathwayOptions"
          :key="option.value"
          type="button"
          class="role-option"
          @click="selectJourney(option.value)"
        >
          <span class="role-option__icon" aria-hidden="true">
            <svg v-if="option.value === 'student_team'" viewBox="0 0 32 32">
              <circle cx="16" cy="9" r="4" />
              <path d="M9 25c.6-5 3-7.5 7-7.5s6.4 2.5 7 7.5" />
              <circle cx="7" cy="12" r="3" />
              <path d="M2.5 24c.4-3.5 2-5.5 4.5-5.5 1.2 0 2.2.4 3 1.2" />
              <circle cx="25" cy="12" r="3" />
              <path d="M29.5 24c-.4-3.5-2-5.5-4.5-5.5-1.2 0-2.2.4-3 1.2" />
            </svg>
            <svg v-else viewBox="0 0 32 32">
              <circle cx="16" cy="10" r="5" />
              <path d="M7 27c.7-6 3.8-9 9-9s8.3 3 9 9" />
            </svg>
          </span>
          <span class="role-option__copy">
            <strong>{{ option.title }}</strong>
            <small>{{ option.description }}</small>
          </span>
          <span class="btn btn-outline btn-sm role-option__arrow" aria-hidden="true">
            Continue <i class="fas fa-chevron-right"></i>
          </span>
        </button>
      </div>
      <div v-else class="pathway-choices">
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
          class="btn btn-outline back-button change-journey"
          @click="changeJourney"
        >
          <i class="fas fa-arrow-left" aria-hidden="true"></i> Back
        </button>
        <!-- The platform's own page heading; a supervisor's with the option's
             description under it. -->
        <header class="page-header">
          <h1 class="page-title">{{ selectedJourney?.title }}</h1>
          <p v-if="isSupervisorMode" class="page-subtitle">{{ selectedJourney?.description }}</p>
          <!-- Register one student: who was just registered, the form empty
               again for the next. -->
          <p v-if="registeredNote" class="registered-note" role="status" data-test="registered-note">
            <i class="fas fa-circle-check" aria-hidden="true"></i>
            {{ registeredNote }}
          </p>
        </header>
      </aside>

      <section class="form-surface">
        <!-- The steps, with what * means at the right. -->
        <div class="step-bar">
          <!-- Register one student on its own has a single step: nothing to show. -->
          <nav v-if="steps.length > 1" class="step-navigation" aria-label="Registration progress">
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
          <!-- Not on Review, which has no fields. -->
          <p v-if="!isReviewStep" class="form-required-note">
            Fields marked <span class="required-mark">*</span> are required.
          </p>
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
          <EmailCheckProgress v-if="emailCheckProgress" :progress="emailCheckProgress" />
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
            <strong>Information to review</strong>
            <ul>
              <li v-for="message in errorMessages" :key="message">{{ message }}</li>
            </ul>
          </div>

          <section class="step-content" :aria-labelledby="stepHeadingId">
            <h2 :id="stepHeadingId" ref="stepHeadingRef" class="sr-only" tabindex="-1">
              {{ currentStepDefinition.title }}
            </h2>

            <!-- An admin (Management > Registration): their students'
                 supervisor first, if they have one, before the students: an
                 existing supervisor, found by email. -->
            <div v-if="adminChoosesSupervisor && currentStep === 0" class="step-stack admin-supervisor">
              <div class="section-divider section-divider--first">
                <h3>Supervisor</h3>
                <p>If the students have a supervisor, search for them by email.</p>
              </div>
              <SupervisorSearchField
                id="admin-supervisor-email"
                v-model="forms.adminSupervisorEmail"
                label="Supervisor email"
                :supervisors="registrationSupervisors"
                :error="errors.supervisorEmail"
              />
            </div>

            <template v-if="journey === 'student_individual'">
              <RegistrationStudentEditor
                v-if="currentStep === 0"
                v-model:student="forms.studentIndividual.student"
                prefix="studentIndividual.student"
                section="identity"
                :errors="errors"
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
                <div class="section-divider section-divider--first">
                  <h3>Supervisor</h3>
                  <p>If you have a supervisor, fill in their details.</p>
                </div>
                <div class="field-grid">
                  <RegistrationTextField
                    id="student-individual-supervisor-first"
                    v-model="forms.studentIndividual.supervisor.firstName"
                    label="Supervisor first name"
                    :error="errors['studentIndividual.supervisor.firstName']"
                  />
                  <RegistrationTextField
                    id="student-individual-supervisor-last"
                    v-model="forms.studentIndividual.supervisor.lastName"
                    label="Supervisor last name"
                    :error="errors['studentIndividual.supervisor.lastName']"
                  />
                  <RegistrationTextField
                    id="student-individual-supervisor-email"
                    v-model="forms.studentIndividual.supervisor.email"
                    label="Supervisor email"
                    type="email"
                    :error="errors['studentIndividual.supervisor.email']"
                    wide
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
              />

              <div v-else-if="currentStep === 2" class="step-stack">
                <!-- Join a registered group by the code its creator shared, or
                     create one (all below). -->
                <div class="group-join" aria-live="polite">
                  <span class="group-code__label">Join a group</span>
                  <p>Got a code from your group? Enter it to join them.</p>
                  <div class="field-grid">
                    <RegistrationTextField
                      id="student-team-join-code"
                      v-model="forms.studentTeam.joinCode"
                      label="Group code"
                      placeholder="6-digit code"
                      autocomplete="off"
                      :hint="joinHint"
                      :error="joinError"
                    />
                  </div>
                  <div class="group-join__actions">
                    <button
                      type="button"
                      class="primary-action"
                      :disabled="isSubmitting"
                      @click="continueJoining"
                    >
                      Continue
                    </button>
                  </div>
                </div>
                <template v-if="!joiningGroup">
                  <div class="or-divider" role="separator">or</div>
                  <!-- The group's code, held for it while registering, to save and share. -->
                  <div class="group-code" aria-live="polite">
                    <span class="group-code__label">Group code</span>
                    <template v-if="forms.studentTeam.groupCode">
                      <p>Save this code for future reference and share it with your teammates.</p>
                      <div class="group-code__row">
                        <span class="group-code__value">{{ forms.studentTeam.groupCode }}</span>
                        <button
                          type="button"
                          class="btn btn-outline btn-sm"
                          @click="copyGroupCode()"
                        >
                          <i
                            :class="groupCodeCopied ? 'fas fa-check' : 'fas fa-copy'"
                            aria-hidden="true"
                          ></i>
                          {{ groupCodeCopied ? 'Copied' : 'Copy' }}
                        </button>
                      </div>
                      <p>It's held for you for 24 hours until you register.</p>
                    </template>
                    <p v-else>
                      {{
                        groupCodeLoading
                          ? 'Getting your group code…'
                          : 'Your group code will be shown once you register.'
                      }}
                    </p>
                  </div>
                  <!-- The group's supervisor, on a line below its code. -->
                  <div class="section-divider">
                    <h3>Supervisor</h3>
                    <p>If you have a supervisor, fill in their details.</p>
                  </div>
                  <div class="field-grid">
                    <RegistrationTextField
                      id="student-team-supervisor-first"
                      v-model="forms.studentTeam.supervisor.firstName"
                      label="Supervisor first name"
                      :error="errors['studentTeam.supervisor.firstName']"
                    />
                    <RegistrationTextField
                      id="student-team-supervisor-last"
                      v-model="forms.studentTeam.supervisor.lastName"
                      label="Supervisor last name"
                      :error="errors['studentTeam.supervisor.lastName']"
                    />
                    <RegistrationTextField
                      id="student-team-supervisor-email"
                      v-model="forms.studentTeam.supervisor.email"
                      label="Supervisor email"
                      type="email"
                      :error="errors['studentTeam.supervisor.email']"
                      wide
                    />
                  </div>
                  <!-- Its members: Member 1 (the student), then the others. -->
                  <div class="section-divider">
                    <h3>Group members</h3>
                    <p>There may be up to 5 students per group.</p>
                  </div>
                  <div class="student-entry student-entry--first creator-summary">
                    <div class="student-entry__heading">
                      <h3>Member 1 (You)</h3>
                      <button type="button" class="btn btn-outline btn-sm" @click="goToStep(0)">
                        <i class="fas fa-pen" aria-hidden="true"></i> Edit your details
                      </button>
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
                        type="button"
                        class="btn btn-outline-danger btn-sm"
                        @click="removeStudentTeammate(index)"
                      >
                        <i class="fas fa-trash-can" aria-hidden="true"></i> Remove
                      </button>
                    </div>
                    <RegistrationStudentEditor
                      v-model:student="forms.studentTeam.teammates[index]"
                      :prefix="`studentTeam.teammates.${index}`"
                      section="teammate"
                      :errors="errors"
                      allow-guardian-defer
                    />
                  </div>
                </template>
              </div>

              <div v-else-if="currentStep === 1" class="step-stack">
                <RegistrationStudentEditor
                  v-model:student="forms.studentTeam.creator"
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
              <!-- With students added (Add student), each in turn, all in one group. -->
              <div v-if="currentStep === 0" class="step-stack">
                <!-- Headed Student 1 once students are added, or under an
                     admin's Supervisor (its line between them). -->
                <div
                  :class="{
                    'student-entry student-entry--first':
                      forms.supervisorIndividual.extraStudents.length || adminChoosesSupervisor,
                  }"
                >
                  <div
                    v-if="forms.supervisorIndividual.extraStudents.length || adminChoosesSupervisor"
                    class="student-entry__heading"
                  >
                    <h3>Student 1</h3>
                  </div>
                  <RegistrationStudentEditor
                    v-model:student="forms.supervisorIndividual.student"
                    prefix="supervisorIndividual.student"
                    section="full"
                    :errors="errors"
                    allow-guardian-defer
                  />
                </div>
                <div
                  v-for="(student, index) in forms.supervisorIndividual.extraStudents"
                  :key="`extra-student-${index}`"
                  class="student-entry"
                >
                  <div class="student-entry__heading">
                    <h3>Student {{ index + 2 }}</h3>
                    <button
                      type="button"
                      class="btn btn-outline-danger btn-sm"
                      @click="removeExtraStudent(index)"
                    >
                      <i class="fas fa-trash-can" aria-hidden="true"></i> Remove
                    </button>
                  </div>
                  <RegistrationStudentEditor
                    v-model:student="forms.supervisorIndividual.extraStudents[index]"
                    :prefix="`supervisorIndividual.extraStudents.${index}`"
                    section="full"
                    :errors="errors"
                    allow-guardian-defer
                  />
                </div>
              </div>
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
                <!-- Add student is in the footer, beside Continue. -->
                <div class="section-divider section-divider--first">
                  <h3>Students</h3>
                  <p>
                    Enter 2–5 complete student records. Guardian details can be deferred for the
                    student’s private follow-up journey.
                  </p>
                </div>
                <div
                  v-for="(student, index) in forms.supervisorGroup.students"
                  :key="`group-student-${index}`"
                  class="student-entry"
                >
                  <div class="student-entry__heading">
                    <h3>Student {{ index + 1 }}</h3>
                    <!-- A group always has Students 1 and 2; only those after can go. -->
                    <button
                      v-if="index >= 2"
                      type="button"
                      class="btn btn-outline-danger btn-sm"
                      @click="removeSupervisorGroupStudent(index)"
                    >
                      <i class="fas fa-trash-can" aria-hidden="true"></i> Remove
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
                <!-- What the file needs, as Upload Guardian Details on My Students words it:
                     the heading with the template beside it, then the rules at full width. -->
                <div class="template-download">
                  <div class="template-download__head">
                    <h3>Upload student details</h3>
                    <!-- The app's own outline button, on one line. -->
                    <button
                      type="button"
                      class="btn btn-outline template-download__button"
                      @click="downloadCsvTemplate"
                    >
                      <i class="fas fa-download" aria-hidden="true"></i> Download example template
                    </button>
                  </div>
                  <p>
                    .xlsx or .csv, one row per student<br />
                    <code>first_name</code>, <code>last_name</code>, <code>email</code>,<br />
                    <code>school</code>, <code>year_level</code>, <code>country</code>,<br />
                    <code>state</code>, <code>interests</code>,<br />
                    <code>guardian_first_name</code>, <code>guardian_last_name</code>,
                    <code>guardian_email</code>
                  </p>
                  <p>
                    Column headers must match exactly and need to be in order.<br />
                    If <code>country</code> is Australia, <code>state</code> is mandatory.<br />
                    Otherwise <code>state</code> is optional.<br />
                    Fields <code>interests</code>, <code>guardian_first_name</code>,
                    <code>guardian_last_name</code> and <code>guardian_email</code> are optional.<br />
                    Extra columns and rows are ignored.
                  </p>
                </div>
                <label class="csv-upload">
                  <span
                    >Choose completed .xlsx or .csv
                    <span class="required-mark" aria-hidden="true">*</span></span
                  >
                  <input
                    type="file"
                    accept=".csv,text/csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    :aria-invalid="Boolean(errors['supervisorCsv.file'])"
                    @change="handleCsvUpload"
                  />
                  <small v-if="forms.supervisorCsv.fileName">
                    Loaded {{ forms.supervisorCsv.fileName }} ·
                    {{ forms.supervisorCsv.rows.length }} student rows
                  </small>
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
                  Choose Edit to correct any student details here. Validation updates as you
                  type, without re-uploading. Review-required rows can be included for authoritative
                  review. Invalid rows must be fixed or explicitly excluded.
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
                  <p v-if="isCsvRowExcluded(editingCsvRow.rowNumber)" class="preview-guidance">
                    This row is still excluded. Clear its exclusion checkbox to include it after
                    correcting the details.
                  </p>
                  <RegistrationCsvRowEditor
                    :key="editingCsvRow.rowNumber"
                    :row="editingCsvRow"
                    :errors="{
                      ...editingCsvRow.fieldErrors,
                      ...csvServerFieldsByRow[editingCsvRow.rowNumber],
                    }"
                    @update:values="updateCsvRow(editingCsvRow, $event)"
                  />
                  <footer class="csv-editor-footer">
                    <button type="button" class="primary-action" @click="closeCsvEditor">
                      Done editing
                    </button>
                  </footer>
                </section>
                <!-- The file's rows, as the portal's other tables: each row's status
                     (and what's wrong), then Edit and Exclude. -->
                <AppDataTable
                  class="csv-table"
                  :columns="CSV_TABLE_COLUMNS"
                  :rows="csvTableRows"
                  row-key="rowNumber"
                  :selectable="false"
                  :default-sort="{ key: 'rowNumber', direction: 'asc' }"
                  :row-class="(row) => ({ 'is-excluded': isCsvRowExcluded(toCsvRow(row).rowNumber) })"
                  :action-headings="['Actions']"
                  search-placeholder="Name or email"
                  empty-message="No student rows in this file."
                >
                  <template #cell-status="{ row }">
                    <strong :class="`csv-status csv-status--${toCsvRow(row).category}`">
                      {{ csvCategoryLabel(toCsvRow(row).category) }}
                    </strong>
                    <ul v-if="csvRowIssues(toCsvRow(row)).length" class="csv-issues">
                      <li v-for="issue in csvRowIssues(toCsvRow(row))" :key="issue">{{ issue }}</li>
                    </ul>
                  </template>
                  <template #actions="{ row }">
                    <div class="csv-row-actions">
                      <button
                        type="button"
                        :id="`csv-edit-${toCsvRow(row).rowNumber}`"
                        class="btn btn-sm btn-outline"
                        :aria-label="`Edit row ${toCsvRow(row).rowNumber}`"
                        :aria-expanded="editingCsvRowNumber === toCsvRow(row).rowNumber"
                        aria-controls="csv-row-editor"
                        @click="editCsvRow(toCsvRow(row).rowNumber)"
                      >
                        Edit
                      </button>
                      <label class="exclude-row">
                        <input
                          type="checkbox"
                          :aria-label="`Exclude row ${toCsvRow(row).rowNumber}`"
                          :checked="isCsvRowExcluded(toCsvRow(row).rowNumber)"
                          @change="toggleCsvRow(toCsvRow(row).rowNumber)"
                        />
                        Exclude
                      </label>
                    </div>
                  </template>
                </AppDataTable>
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
                  wide
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
                <!-- In Australia, its State (required, a dropdown of its states
                     and territories); elsewhere a Region (optional). -->
                <RegistrationTextField
                  id="mentor-state"
                  v-model="forms.mentor.state"
                  :label="stateLabel(forms.mentor.country)"
                  :options="mentorStateOptions.length ? mentorStateOptions : undefined"
                  :placeholder="mentorStateOptions.length ? 'Select a state' : undefined"
                  :error="errors['mentor.state']"
                  :required="isAustralia(forms.mentor.country)"
                  :optional="!isAustralia(forms.mentor.country)"
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
                    :options="STUDY_YEAR_OPTIONS"
                    placeholder="Select a year"
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
                    :wide="!['undergraduate', 'postgraduate'].includes(forms.mentor.affiliation)"
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
                <RegistrationAvailabilityField
                  id="mentor-availability"
                  v-model="forms.mentor.availability"
                  prefix="mentor.availability"
                  :errors="errors"
                />
                <RegistrationTextField
                  id="mentor-background"
                  v-model="forms.mentor.background"
                  label="Relevant background"
                  hint="Describe experience that would help you support a student group."
                  :error="errors['mentor.background']"
                  :max-words="MENTOR_MAX_WORDS"
                  multiline
                  required
                  wide
                />
                <RegistrationTextField
                  id="mentor-motivation"
                  v-model="forms.mentor.motivation"
                  label="Why would you like to mentor?"
                  :error="errors['mentor.motivation']"
                  :max-words="MENTOR_MAX_WORDS"
                  multiline
                  required
                  wide
                />
                <RegistrationTextField
                  id="mentor-approach"
                  v-model="forms.mentor.mentoringApproach"
                  label="How would you mentor BIOTech groups?"
                  :error="errors['mentor.mentoringApproach']"
                  :max-words="MENTOR_MAX_WORDS"
                  multiline
                  required
                  wide
                />
              </div>

            </template>

            <div v-if="isReviewStep" class="review-step">
              <div v-for="section in reviewSections" :key="section.title" class="review-section">
                <h3>{{ section.title }}</h3>
                <dl>
                  <div
                    v-for="item in section.items"
                    :key="item.label"
                    :class="{ 'review-row--joined': item.joinNext }"
                  >
                    <dt>{{ item.label }}</dt>
                    <dd v-if="item.parts" class="review-parts">
                      <span v-for="(part, index) in item.parts" :key="index">{{ part }}</span>
                    </dd>
                    <dd v-else-if="item.copy" class="review-copy">
                      <span>{{ item.value }}</span>
                      <button
                        type="button"
                        class="btn btn-outline btn-sm"
                        @click="copyGroupCode(item.copy)"
                      >
                        <i
                          :class="groupCodeCopied ? 'fas fa-check' : 'fas fa-copy'"
                          aria-hidden="true"
                        ></i>
                        {{ groupCodeCopied ? 'Copied' : 'Copy' }}
                      </button>
                    </dd>
                    <dd v-else>{{ item.value || 'Not provided' }}</dd>
                  </div>
                </dl>
              </div>
            </div>
          </section>

          <!-- On the right; the steps above go back, and Back to the
               options. A group's students are added here. -->
          <footer class="form-footer">
            <!-- Before Add student: on Register one student, and on Register a
                 student group's Students step. -->
            <p
              v-if="
                (journey === 'supervisor_individual' && currentStep === 0) ||
                (journey === 'supervisor_group' && currentStep === 1)
              "
              class="form-footer-note"
            >
              Adding a student will put them in the same group
            </p>
            <button
              v-if="journey === 'supervisor_individual' && currentStep === 0"
              type="button"
              class="secondary-action"
              :disabled="isSubmitting || forms.supervisorIndividual.extraStudents.length >= 4"
              @click="addExtraStudent"
            >
              Add student
            </button>
            <button
              v-if="journey === 'supervisor_group' && currentStep === 1"
              type="button"
              class="secondary-action"
              :disabled="isSubmitting || forms.supervisorGroup.students.length >= 5"
              @click="addSupervisorGroupStudent"
            >
              Add student
            </button>
            <button
              v-if="journey === 'student_team' && currentStep === 2 && !joiningGroup"
              type="button"
              class="secondary-action"
              :disabled="isSubmitting || forms.studentTeam.teammates.length >= 4"
              @click="addStudentTeammate"
            >
              Add member
            </button>
            <!-- Joining a group, its own Continue (by its code) is the step's. -->
            <button
              v-if="!(journey === 'student_team' && currentStep === 2 && joiningGroup)"
              type="submit"
              class="primary-action"
              :disabled="isSubmitting"
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

import RegistrationAvailabilityField from '@/components/registration/RegistrationAvailabilityField.vue'
import RegistrationInterestSelector from '@/components/registration/RegistrationInterestSelector.vue'
import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'
import RegistrationCsvRowEditor from '@/components/registration/RegistrationCsvRowEditor.vue'
import SupervisorSearchField from '@/components/registration/SupervisorSearchField.vue'
import { fetchRegistrationSupervisors, type RegistrationSupervisor } from '@/utils/managementAPI'
import RegistrationStudentEditor from '@/components/registration/RegistrationStudentEditor.vue'
import RegistrationTextField from '@/components/registration/RegistrationTextField.vue'
import { SUPPORT_EMAIL } from '@/constants/brand'
import { loadRegistrationOpen, useRegistrationOpen } from '@/composables/useRegistrationOpen'
import { earliestRegistrationErrorStep } from '@/registration/registrationErrorNavigation'
import {
  checkGroupCode,
  GROUP_CODE_PATTERN,
  holdGroupCode,
  type GroupCodeCheck,
} from '@/registration/groupCode'
import { clearDraft, readDraft, saveDraft } from '@/registration/registrationDraft'
import { useCountryOptions, useStateOptions } from '@/registration/useLocationOptions'
import { useEmailPrecheck } from '@/registration/useEmailPrecheck'
import EmailCheckProgress from '@/components/registration/EmailCheckProgress.vue'
import { formatDayMonthTime } from '@/utils/date'
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
  countWords,
  findCrossRoleEmailConflicts,
  hasSupervisor,
  isAustralia,
  isBlankStudent,
  isValidRegistrationEmail,
  parseRegistrationCsv,
  registrationCsvTemplate,
  MENTOR_MAX_WORDS,
  revalidateRegistrationCsvRows,
  stateLabel,
  supervisorSummary,
  WEEKDAY_NAMES,
  type AvailabilitySlot,
  type CsvCategory,
  type CsvHeader,
  type CsvRow,
  type GuardianDetails,
  type MentorForm,
  type RegistrationJourney,
  type StudentDetails,
  type SupervisorDetails,
  type SupervisorGroupForm,
} from '@/registration/registration'
import { isXlsx, sheetAsCsv } from '@/registration/registrationSheet'

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
type SelectionStage = 'role' | 'pathway'

interface RoleOption {
  value: RegistrationRole
  title: string
  description: string
}

interface ReviewSection {
  title: string
  // ``parts``, when given, are shown in columns that line up row to row.
  // ``joinNext``: the next row is about the same person, with no line between.
  // ``copy``: text its Copy button copies (a group's code).
  items: Array<{
    label: string
    value: string
    parts?: string[]
    joinNext?: boolean
    copy?: string
  }>
}

// A group member's rows on Review: their name and email, then their
// guardian's (when given), as one.
const memberRows = (label: string, student: StudentDetails, guardianOf = label) => {
  const member = {
    label,
    value: `${studentName(student)} · ${student.email}`,
    parts: [studentName(student), student.email],
  }
  if (student.guardianDeferred) return [member]
  const guardian = [guardianName(student.guardian), student.guardian.email]
  return [
    { ...member, joinNext: true },
    { label: `${guardianOf} (Guardian)`, value: guardian.join(' · '), parts: guardian },
  ]
}

// A member's row on Review: their name, email and guardian, in columns.
const memberParts = (student: StudentDetails) => [
  studentName(student),
  student.email,
  `Guardian ${student.guardianDeferred ? 'deferred' : 'provided'}`,
]

const MAX_PHOTO_BYTES = 5 * 1024 * 1024
const MAX_CSV_BYTES = 2 * 1024 * 1024
const initialInvitationToken =
  new URLSearchParams(window.location.hash.split('?')[1] || window.location.search).get('invite') ||
  undefined
const allowedPhotoTypes = new Set(['image/jpeg', 'image/png', 'image/webp'])
const emailLikePattern = /\b[^\s@]+@[^\s@]+\.[^\s@]+\b/i
const guardianContactExplanation =
  'Your nominated guardian must provide permission through the existing guardian consent process before you can access most features of the program. Registration saves their contact details. It does not send a permission email or record consent.'

const roleOptions: RoleOption[] = [
  {
    value: 'student',
    title: 'Student',
    description: 'Register yourself or create a group with teammates.',
  },
  {
    value: 'supervisor',
    title: 'Supervisor or teacher',
    description: 'Register students individually, as a group or from a CSV.',
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
    description: 'Enter your own details.',
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
    description: 'Register a group of 2-5 students, including yourself.',
    steps: [
      {
        label: 'Your details',
        title: 'Start with your details',
        description: 'You will be Member 1 of this group.',
      },
      {
        label: 'Your profile',
        title: 'Complete your own details first',
        description: 'Add your school, location, interests, profile and guardian contact.',
      },
      {
        label: 'Group',
        title: 'Build your group',
        description: 'Add 1–4 other members, your supervisor and your group interests.',
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
    // Registered straight from the one step: no Review, and no confirmation
    // page (see registeredNote). With students added, Review and the
    // confirmation page as a group's (see steps).
    steps: [
      {
        label: 'Student',
        title: 'Add the student',
        description: 'Guardian contact may be supplied now or deferred.',
      },
    ],
  },
  {
    value: 'supervisor_group',
    role: 'Supervisor / teacher',
    title: 'Register a student group',
    description: 'Create a pre-formed group with 2-5 complete student entries.',
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
    title: 'Upload student details',
    description:
      'Use the prescribed template, parse it locally and resolve row issues before save.',
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
        label: 'Mentoring',
        title: 'How you would mentor',
        description: 'Choose interests, capacity, availability and tell us about yourself.',
      },
      {
        label: 'Review',
        title: 'Review the mentor registration',
        description: 'Submission does not activate matching access.',
      },
    ],
  },
]

// A student mentor's year at university.
const STUDY_YEAR_OPTIONS = [
  { value: '1', label: 'Year 1' },
  { value: '2', label: 'Year 2' },
  { value: '3', label: 'Year 3' },
  { value: '4', label: 'Year 4' },
  { value: '5+', label: 'Year 5 or later' },
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
    /** Within another page (Management > Registration): its own padding,
     *  background and height, not a page's. */
    embedded?: boolean
  }>(),
  { mode: 'canonical', embedded: false },
)
const isSupervisorMode = computed(() => props.mode === 'supervisor')
// An admin registering students (Management > Registration) chooses their
// students' supervisor, from every supervisor.
const SUPERVISOR_JOURNEYS: RegistrationJourney[] = ['supervisor_individual', 'supervisor_group', 'supervisor_csv']
const adminChoosesSupervisor = computed(
  () => props.embedded && Boolean(journey.value && SUPERVISOR_JOURNEYS.includes(journey.value)),
)
const registrationSupervisors = ref<RegistrationSupervisor[]>([])
if (props.embedded) {
  fetchRegistrationSupervisors()
    .then((supervisors) => (registrationSupervisors.value = supervisors))
    .catch(() => {
      // Left to the server to check the email, then.
    })
}
const chosenSupervisor = computed(() => {
  const email = forms.adminSupervisorEmail.trim().toLowerCase()
  return email ? registrationSupervisors.value.find((item) => item.email.toLowerCase() === email) : undefined
})
// Management > Registration: closed by the year's dates, the public
// can't register themselves (a late link still can), nor supervisors register
// their students, unless let register after them.
const { openNow: publicRegistrationOpen, canRegisterStudents } = useRegistrationOpen()
void loadRegistrationOpen(true)
const invitationToken = computed(() =>
  props.invitationToken === undefined ? initialInvitationToken : props.invitationToken || undefined,
)
const injectedGateway = inject(REGISTRATION_GATEWAY_KEY, null)
// Checking the email addresses before submitting, when the gateway can.
const { progress: emailCheckProgress, check: checkEmails } = useEmailPrecheck()
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
// The public registration's progress, kept in this tab (registrationDraft.ts):
// what was typed back first, its role, option and step once they're declared.
const draft = isSupervisorMode.value ? null : readDraft(invitationToken.value)
if (draft) {
  const blank = createRegistrationForms()
  forms.studentIndividual = { ...blank.studentIndividual, ...draft.forms.studentIndividual }
  forms.studentTeam = { ...blank.studentTeam, ...draft.forms.studentTeam }
  forms.mentor = { ...blank.mentor, ...draft.forms.mentor }
}
// The countries, and in Australia its states, from the database, for the
// mentor's dropdowns.
const mentorCountryOptions = useCountryOptions()
const mentorStateOptions = useStateOptions(() => forms.mentor.country)
watch(
  () => forms.mentor.country,
  (country, before) => {
    if (country !== before) forms.mentor.state = ''
  },
)
const journey = ref<RegistrationJourney | null>(null)
const selectionStage = ref<SelectionStage>(isSupervisorMode.value ? 'pathway' : 'role')
const selectedRole = ref<RegistrationRole | null>(isSupervisorMode.value ? 'supervisor' : null)
const currentStep = ref(0)
const maxReachedStep = ref(0)
if (draft) {
  journey.value = draft.journey
  selectionStage.value = draft.selectionStage as SelectionStage
  selectedRole.value = draft.selectedRole as RegistrationRole | null
  currentStep.value = draft.currentStep
  maxReachedStep.value = draft.maxReachedStep
}
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
// Register one student, once registered: "Registration successful: Amy Chen
// (amy@example.com) is registered." Gone when they leave it.
const registeredNote = ref('')

// Create a student group, or join one by the code its creator shared:
// checked as it's typed. Joining, the group's own details aren't asked for.
const joiningGroup = computed(() => forms.studentTeam.joinCode.trim() !== '')
const JOIN_CODE_MISSING = 'No group has this code. Check it with your group.'
const JOIN_CODE_FULL = 'This group already has 5 members.'
const joinCheck = ref<{ code: string; result: GroupCodeCheck | null }>({ code: '', result: null })
let joinCheckTimer: number | undefined
watch(
  () => forms.studentTeam.joinCode.trim(),
  (code) => {
    window.clearTimeout(joinCheckTimer)
    joinCheck.value = { code, result: null }
    // A new code: what was said of the last one goes.
    delete clientErrors['studentTeam.joinCode']
    delete serverFieldErrors['studentTeam.joinCode']
    if (!GROUP_CODE_PATTERN.test(code)) return
    joinCheckTimer = window.setTimeout(async () => {
      const result = await checkGroupCode(code)
      if (forms.studentTeam.joinCode.trim() === code) joinCheck.value = { code, result }
    }, 300)
  },
  { immediate: true },
)
const joinCheckResult = computed(() =>
  joinCheck.value.code === forms.studentTeam.joinCode.trim() ? joinCheck.value.result : null,
)
const joinHint = computed(() => {
  if (!GROUP_CODE_PATTERN.test(forms.studentTeam.joinCode.trim())) return undefined
  const result = joinCheckResult.value
  if (!result) return 'Checking the code…'
  return result.state === 'found'
    ? `You will join this group when you register. It has ${result.members} of 5 members.`
    : undefined
})
const joinError = computed(
  () =>
    errors.value['studentTeam.joinCode'] ||
    (joinCheckResult.value?.state === 'missing'
      ? JOIN_CODE_MISSING
      : joinCheckResult.value?.state === 'full'
        ? JOIN_CODE_FULL
        : undefined),
)

// Create a student group: its code held when its Group step opens (once per
// registration), to show and copy there.
const groupCodeLoading = ref(false)
const groupCodeCopied = ref(false)
watch(
  () => journey.value === 'student_team' && currentStep.value === 2 && !joiningGroup.value,
  async (onGroupStep) => {
    if (!onGroupStep || groupCodeLoading.value) return
    // A code still held (a restored one too) is kept; one whose hold has run
    // out is let go for a new one.
    const team = forms.studentTeam
    const stillHeld =
      team.groupCodeToken && Date.parse(team.groupCodeExpiresAt) > Date.now()
    if (stillHeld) return
    team.groupCode = ''
    team.groupCodeToken = ''
    team.groupCodeExpiresAt = ''
    groupCodeLoading.value = true
    const held = await holdGroupCode()
    groupCodeLoading.value = false
    if (held) {
      team.groupCode = held.code
      team.groupCodeToken = held.token
      team.groupCodeExpiresAt = held.expiresAt
    }
  },
  { immediate: true },
)

// The group's code (on the Group step), or the one given on Review.
const copyGroupCode = async (code = forms.studentTeam.groupCode) => {
  try {
    await navigator.clipboard.writeText(code)
    groupCodeCopied.value = true
    window.setTimeout(() => {
      groupCodeCopied.value = false
    }, 2000)
  } catch {
    groupCodeCopied.value = false
  }
}
const stepHeadingRef = ref<HTMLElement | null>(null)
const errorSummaryRef = ref<HTMLElement | null>(null)

const selectedJourney = computed(() =>
  journey.value ? journeyOptions.find((option) => option.value === journey.value) : undefined,
)
const registrationClosed = computed(
  () =>
    !invitationToken.value &&
    (isSupervisorMode.value ? !canRegisterStudents.value : !publicRegistrationOpen.value),
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
  journey.value === 'mentor' ? 'Application received' : 'Registration Complete',
)
const successNote = computed(() =>
  journey.value === 'mentor'
    ? 'Your application is pending administrator review.'
    : 'Guardian consent is still required before full registration.',
)
// Register one student with students added: reviewed, then confirmed on
// the saved registration's page, until they're removed again.
const ADDED_STUDENTS_REVIEW = {
  label: 'Review',
  title: 'Review the student registration',
  description: 'Check the record before saving.',
}
const steps = computed(() => {
  const own = selectedJourney.value?.steps || []
  return journey.value === 'supervisor_individual' && forms.supervisorIndividual.extraStudents.length
    ? [...own, ADDED_STUDENTS_REVIEW]
    : own
})
// Every journey's last step is Review, but Register one student's on its own.
const isReviewStepIndex = (index: number) => steps.value[index]?.label === 'Review'
const isReviewStep = computed(() => isReviewStepIndex(currentStep.value))
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
    // One student, a group, or a CSV upload of many.
    return journeyOptions.filter((option) =>
      ['supervisor_individual', 'supervisor_group', 'supervisor_csv'].includes(option.value),
    )
  }
  return journeyOptions.filter((option) => option.value === 'mentor')
})
// A student registering themselves (not by a link, which is for one student
// only): whether they have a group.
const isStudentPathway = computed(
  () => !isSupervisorMode.value && !invitationToken.value && selectedRole.value === 'student',
)
const studentPathwayOptions: { value: RegistrationJourney; title: string; description: string }[] = [
  {
    value: 'student_team',
    title: 'I have a group',
    description: 'Make a group of 2-5 students or join one.',
  },
  {
    value: 'student_individual',
    title: "I don't have a group",
    description: 'Register on your own.',
  },
]
const pathwayHeading = computed(() =>
  isSupervisorMode.value
    ? 'Register students'
    : isStudentPathway.value
      ? 'Do you have a group?'
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
  const field = warning.field.endsWith('.school')
    ? 'School'
    : warning.field.endsWith('.guardian.email')
      ? 'Guardian email'
      : 'Student email'
  const csvRow = /^supervisorCsv\.rows\.(\d+)\./.exec(warning.field)
  if (csvRow) return `CSV row ${includedCsvRows.value[Number(csvRow[1])]?.rowNumber} - ${field}`
  const student = /^supervisorGroup\.students\.(\d+)\./.exec(warning.field)
  if (student) return `Student ${Number(student[1]) + 1} - ${field}`
  const extra = /^supervisorIndividual\.extraStudents\.(\d+)\./.exec(warning.field)
  if (extra) return `Student ${Number(extra[1]) + 2} - ${field}`
  if (
    warning.field.startsWith('supervisorIndividual.student.') &&
    forms.supervisorIndividual.extraStudents.length
  )
    return `Student 1 - ${field}`
  const teammate = /^studentTeam\.teammates\.(\d+)\./.exec(warning.field)
  if (teammate) return `Member ${Number(teammate[1]) + 2} - ${field}`
  return warning.field.startsWith('studentTeam.creator.') ? `Member 1 (You) - ${field}` : field
}
const editingCsvRow = computed(() =>
  forms.supervisorCsv.rows.find((row) => row.rowNumber === editingCsvRowNumber.value),
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
// "09:30" as "9:30 am".
const clockTime = (time: string) => {
  const [hours = 0, minutes = 0] = time.split(':').map(Number)
  return `${hours % 12 || 12}:${String(minutes).padStart(2, '0')} ${hours < 12 ? 'am' : 'pm'}`
}

// A mentor's weekly times on Review: each one given in full.
const availabilitySummary = (slots: AvailabilitySlot[]) =>
  slots
    .filter((slot) => slot.weekday && slot.start && slot.end)
    .map(
      (slot) =>
        `${WEEKDAY_NAMES[Number(slot.weekday)]} ${clockTime(slot.start)} – ${clockTime(slot.end)}`,
    )
    .join(' · ')

// A student group's teammates as registered: those left empty aren't.
const filledTeammates = computed(() =>
  forms.studentTeam.teammates.filter((student) => !isBlankStudent(student)),
)
// An admin's (Management > Registration): their students' supervisor, first.
const reviewSections = computed<ReviewSection[]>(() =>
  adminChoosesSupervisor.value
    ? [
        {
          title: 'Supervisor',
          items: [
            {
              label: 'Supervisor',
              value: chosenSupervisor.value
                ? `${chosenSupervisor.value.name} · ${chosenSupervisor.value.email}`
                : forms.adminSupervisorEmail.trim() || 'None',
            },
          ],
        },
        ...journeyReviewSections.value,
      ]
    : journeyReviewSections.value,
)

const journeyReviewSections = computed<ReviewSection[]>(() => {
  switch (journey.value) {
    case 'student_individual': {
      const form = forms.studentIndividual
      return [
        {
          title: 'Student',
          items: [
            { label: 'Name', value: studentName(form.student) },
            { label: 'Email', value: form.student.email },
            { label: 'School', value: form.student.school },
            {
              label: 'Year',
              value: form.student.yearLevel ? `Year ${form.student.yearLevel}` : '',
            },
            { label: 'Country', value: form.student.country },
            { label: stateLabel(form.student.country), value: form.student.state },
            { label: 'Interests', value: interestSummary(form.student.interests) },
          ],
        },
        {
          title: 'Support',
          items: [
            {
              label: 'Supervisor',
              value: supervisorSummary(form.supervisor),
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
      // Joining a group: its code, and the student.
      if (joiningGroup.value)
        return [
          {
            title: 'Group',
            items: [
              {
                label: success.value ? 'Joined group' : 'Joining group',
                value: success.value?.groupCode || forms.studentTeam.joinCode.trim(),
              },
            ],
          },
          {
            title: 'People',
            items: [
              {
                label: 'You',
                value: `${studentName(forms.studentTeam.creator)} · ${forms.studentTeam.creator.email}`,
                parts: [studentName(forms.studentTeam.creator), forms.studentTeam.creator.email],
              },
              { label: 'Guardian', value: guardianName(forms.studentTeam.creator.guardian) },
            ],
          },
        ]
      return [
        {
          title: 'Group',
          items: [
            {
              label: 'Group code',
              // Held 24 hours while registering; once registered, for 4 months.
              value: success.value
                ? `${success.value.groupCode || forms.studentTeam.groupCode} (held for 4 months)`
                : forms.studentTeam.groupCode
                  ? `${forms.studentTeam.groupCode} (held for 24 hours until you register)`
                  : 'Given once you register',
              // To copy, once there is one.
              copy: success.value?.groupCode || forms.studentTeam.groupCode || undefined,
            },
          ],
        },
        // As on the Group step: its supervisor (optional) after its code.
        {
          title: 'Supervisor',
          items: [
            {
              label: 'Name',
              value: `${forms.studentTeam.supervisor.firstName} ${forms.studentTeam.supervisor.lastName}`.trim(),
            },
            { label: 'Email', value: forms.studentTeam.supervisor.email.trim() },
          ],
        },
        {
          title: 'People',
          // Each member, then their guardian (when given), with a line
          // between members only.
          items: [
            ...memberRows('Member 1 (You)', forms.studentTeam.creator, 'Member 1'),
            ...filledTeammates.value.flatMap((student, index) =>
              memberRows(`Member ${index + 2}`, student),
            ),
          ],
        },
      ]
    case 'supervisor_individual':
      if (forms.supervisorIndividual.extraStudents.length) {
        const students = [
          forms.supervisorIndividual.student,
          ...forms.supervisorIndividual.extraStudents,
        ]
        return [
          {
            title: 'Group members',
            items: students.map((student, index) => ({
              label: `Student ${index + 1}`,
              value: memberParts(student).join(' · '),
              parts: memberParts(student),
            })),
          },
        ]
      }
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
          title: 'Group members',
          items: forms.supervisorGroup.students.map((student, index) => ({
            label: `Student ${index + 1}`,
            value: memberParts(student).join(' · '),
            parts: memberParts(student),
          })),
        },
      ]
    // As Register a student group's: each student registered (not those
    // excluded), with their email and whether their guardian's given. A
    // guardian is only kept with all three of their columns.
    case 'supervisor_csv':
      return [
        {
          title: 'Students',
          items: includedCsvRows.value.map(({ values }, index) => {
            const parts = [
              `${values.first_name} ${values.last_name}`.trim() || 'Not provided',
              values.email,
              `Guardian ${
                values.guardian_first_name && values.guardian_last_name && values.guardian_email
                  ? 'provided'
                  : 'deferred'
              }`,
            ]
            return { label: `Student ${index + 1}`, value: parts.join(' · '), parts }
          }),
        },
      ]
    case 'mentor':
      return [
        {
          title: 'Mentor',
          items: [
            { label: 'Name', value: `${forms.mentor.firstName} ${forms.mentor.lastName}` },
            { label: 'Email', value: forms.mentor.email },
            { label: 'Country', value: forms.mentor.country },
            { label: stateLabel(forms.mentor.country), value: forms.mentor.state },
          ],
        },
        {
          title: 'Affiliation',
          items: [
            {
              label: 'Affiliation',
              value:
                mentorAffiliations.find((option) => option.value === forms.mentor.affiliation)
                  ?.label || '',
            },
            ...(forms.mentor.affiliation === 'industry'
              ? [{ label: 'Company or organisation', value: forms.mentor.company }]
              : [{ label: 'University or institution', value: forms.mentor.institution }]),
            ...(['undergraduate', 'postgraduate'].includes(forms.mentor.affiliation)
              ? [
                  {
                    label: 'Current year of study',
                    value:
                      STUDY_YEAR_OPTIONS.find((option) => option.value === forms.mentor.universityYear)
                        ?.label || forms.mentor.universityYear,
                  },
                ]
              : []),
            ...(forms.mentor.affiliation !== 'industry'
              ? [{ label: 'Field of study or research', value: forms.mentor.fieldOfStudy }]
              : []),
          ],
        },
        {
          title: 'Mentoring',
          items: [
            { label: 'Interests', value: interestSummary(forms.mentor.interests) },
            {
              label: 'Capacity',
              value: `${forms.mentor.capacity} group${forms.mentor.capacity === '1' ? '' : 's'}`,
            },
            { label: 'Availability', value: availabilitySummary(forms.mentor.availability) },
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

// A nominated supervisor is optional: none at all, or their name and email.
const validateSupervisor = (supervisor: SupervisorDetails, prefix: string) => {
  if (!hasSupervisor(supervisor)) return
  requireValue(`${prefix}.firstName`, supervisor.firstName, 'Enter the supervisor first name.')
  requireValue(`${prefix}.lastName`, supervisor.lastName, 'Enter the supervisor last name.')
  validateEmail(`${prefix}.email`, supervisor.email, 'Supervisor email')
}

// Each student's email is given once (no confirming it), as on a supervisor's.
const validateStudentIdentity = (student: StudentDetails, prefix: string) => {
  requireValue(`${prefix}.firstName`, student.firstName, 'Enter the student first name.')
  requireValue(`${prefix}.lastName`, student.lastName, 'Enter the student last name.')
  validateEmail(`${prefix}.email`, student.email, 'Student email')
}

// A student's Areas of Interest are optional.
const validateStudentProfile = (student: StudentDetails, prefix: string) => {
  requireValue(`${prefix}.school`, student.school, 'Enter the student school.')
  requireValue(`${prefix}.yearLevel`, student.yearLevel, 'Select the student year level.')
  requireValue(`${prefix}.country`, student.country, 'Enter the student country.')
  if (isAustralia(student.country))
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

// A supervisor's students: all of each one's details on one step.
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
  // An admin's students' supervisor, on the first step: one of the list, if any.
  if (
    adminChoosesSupervisor.value &&
    step === 0 &&
    forms.adminSupervisorEmail.trim() &&
    registrationSupervisors.value.length &&
    !chosenSupervisor.value
  )
    clientErrors.supervisorEmail = 'Choose a supervisor from the list.'

  if (journey.value === 'student_individual') {
    if (step === 0)
      validateStudentIdentity(forms.studentIndividual.student, 'studentIndividual.student')
    if (step === 1)
      validateStudentProfile(forms.studentIndividual.student, 'studentIndividual.student')
    if (step === 2) {
      validateSupervisor(forms.studentIndividual.supervisor, 'studentIndividual.supervisor')
      validateGuardian(forms.studentIndividual.student, 'studentIndividual.student', false)
    }
  } else if (journey.value === 'student_team') {
    if (step === 0) validateStudentIdentity(forms.studentTeam.creator, 'studentTeam.creator')
    if (step === 1) {
      validateStudentProfile(forms.studentTeam.creator, 'studentTeam.creator')
      validateGuardian(forms.studentTeam.creator, 'studentTeam.creator', false)
    }
    if (step === 2 && joiningGroup.value) {
      // Joining: a 6-digit code of a group with room.
      const result = joinCheckResult.value
      if (!GROUP_CODE_PATTERN.test(forms.studentTeam.joinCode.trim()))
        clientErrors['studentTeam.joinCode'] = 'Enter the 6-digit group code.'
      else if (result?.state === 'missing') clientErrors['studentTeam.joinCode'] = JOIN_CODE_MISSING
      else if (result?.state === 'full') clientErrors['studentTeam.joinCode'] = JOIN_CODE_FULL
    } else if (step === 2) {
      validateSupervisor(forms.studentTeam.supervisor, 'studentTeam.supervisor')
      // Up to 5 with them: teammates may also join later by the code.
      if (forms.studentTeam.teammates.length > 4) {
        clientErrors['studentTeam.size'] = 'A group can have up to 5 students, including you.'
      }
      // Every member's school, year and location, as Member 1's. A member
      // left empty isn't asked for (nor registered).
      forms.studentTeam.teammates.forEach((student, index) => {
        if (isBlankStudent(student)) return
        validateStudentIdentity(student, `studentTeam.teammates.${index}`)
        validateStudentProfile(student, `studentTeam.teammates.${index}`)
        validateGuardian(student, `studentTeam.teammates.${index}`)
      })
    }
  } else if (journey.value === 'supervisor_individual') {
    if (step === 0) {
      validateStudentFull(forms.supervisorIndividual.student, 'supervisorIndividual.student')
      forms.supervisorIndividual.extraStudents.forEach((student, index) =>
        validateStudentFull(student, `supervisorIndividual.extraStudents.${index}`),
      )
    }
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
      if (isAustralia(forms.mentor.country))
        requireValue('mentor.state', forms.mentor.state, 'Enter your state.')
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
      requireValue(
        'mentor.mentoringApproach',
        forms.mentor.mentoringApproach,
        'Tell us how you would mentor BIOTech groups.',
      )
      // Each written answer is 150 words at most.
      for (const field of ['background', 'motivation', 'mentoringApproach'] as const) {
        if (countWords(forms.mentor[field]) > MENTOR_MAX_WORDS)
          clientErrors[`mentor.${field}`] = `Keep this to ${MENTOR_MAX_WORDS} words or fewer.`
      }
      // A time given in full (day, from, to), ending after it starts.
      forms.mentor.availability.forEach((slot, index) => {
        const given = [slot.weekday, slot.start, slot.end].filter(Boolean).length
        if (!given) return
        if (given < 3) clientErrors[`mentor.availability.${index}`] = 'Choose a day and both times.'
        else if (slot.end <= slot.start)
          clientErrors[`mentor.availability.${index}`] = 'End after it starts.'
      })
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

// How far the steps already filled in reach (from earlier in this session):
// each step whose details pass, in turn, opens the next. Checked quietly.
const furthestFilledStep = () => {
  const at = currentStep.value
  let reached = 0
  for (let index = 0; index < steps.value.length - 1; index += 1) {
    currentStep.value = index
    if (!validateCurrentStep()) break
    reached = index + 1
  }
  currentStep.value = at
  clearErrors()
  return reached
}

const selectJourney = (value: RegistrationJourney) => {
  journey.value = value
  currentStep.value = 0
  // Steps already filled in (kept from earlier) can be gone to straight away.
  maxReachedStep.value = furthestFilledStep()
  clearErrors()
  clearServerErrors()
  serverError.value = ''
  focusStep()
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
  leaveCsvEditor()
  registeredNote.value = ''
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
      : 'role'
  scrollToTop()
}

const goToStep = (index: number) => {
  leaveCsvEditor()
  if (index > maxReachedStep.value || index === currentStep.value) return
  currentStep.value = index
  clearErrors()
  serverError.value = ''
  focusStep()
}

const continueJourney = async () => {
  leaveCsvEditor()
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
  const lastStep = steps.value.length - 1
  // Every step with fields: all but Review, or all of them with no Review.
  const fieldSteps = isReviewStepIndex(lastStep) ? lastStep : lastStep + 1
  for (let index = 0; index < fieldSteps; index += 1) {
    currentStep.value = index
    if (!validateCurrentStep()) {
      await nextTick()
      await focusErrors()
      return false
    }
  }
  currentStep.value = lastStep
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

// Continue by a group's code (the join's own Continue): one is needed.
const continueJoining = () => {
  if (!joiningGroup.value) {
    clientErrors['studentTeam.joinCode'] = 'Enter the 6-digit group code.'
    return
  }
  handlePrimaryAction()
}

const addStudentTeammate = () => {
  if (forms.studentTeam.teammates.length < 4) {
    forms.studentTeam.teammates.push(createPendingPeer())
  }
}

const removeStudentTeammate = (index: number) => {
  if (forms.studentTeam.teammates.length > 0) {
    forms.studentTeam.teammates.splice(index, 1)
    reindexStudentErrors('studentTeam.teammates', index)
  }
}

const addSupervisorGroupStudent = () => {
  if (forms.supervisorGroup.students.length < 5) {
    forms.supervisorGroup.students.push(createStudent({ deferGuardian: true }))
  }
}

// Register one student's Add student: another student on the same page, up
// to 5 in all, registered together as one group (see oneStudentAsGroup).
const addExtraStudent = () => {
  if (forms.supervisorIndividual.extraStudents.length < 4) {
    forms.supervisorIndividual.extraStudents.push(createStudent({ deferGuardian: true }))
  }
}

const removeExtraStudent = (index: number) => {
  forms.supervisorIndividual.extraStudents.splice(index, 1)
}

// Register one student with students added: sent as a supervisor's group of
// them all, its interests every area of interest they were given (a group's
// members have none of their own).
const oneStudentAsGroup = (): SupervisorGroupForm => {
  const students = [forms.supervisorIndividual.student, ...forms.supervisorIndividual.extraStudents]
  return {
    students: students.map((student) => ({ ...student, interests: [] })),
    interests: [...new Set(students.flatMap((student) => student.interests))],
  }
}

// That group's server paths back to the page's: student 0 is Student 1, the
// rest the students added.
const fromOneStudentGroup = (path: string) => {
  const student = /^supervisorGroup\.students\.(\d+)(.*)$/.exec(path)
  if (student) {
    const index = Number(student[1])
    return index === 0
      ? `supervisorIndividual.student${student[2]}`
      : `supervisorIndividual.extraStudents.${index - 1}${student[2]}`
  }
  if (path === 'supervisorGroup.interests') return 'supervisorIndividual.student.interests'
  return path.replace(/^supervisorGroup\./, 'supervisorIndividual.')
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
    clientErrors['supervisorCsv.file'] = 'Choose a file no larger than 2 MB.'
    return
  }
  // An .xlsx comes back from the server as CSV text, then is checked as a CSV is.
  const xlsx = isXlsx(file)
  try {
    const result = parseRegistrationCsv(xlsx ? await sheetAsCsv(file) : await file.text())
    if (result.errors.length) {
      csvFileErrors.value = result.errors
      return
    }
    forms.supervisorCsv.fileName = file.name
    forms.supervisorCsv.rows = result.rows
  } catch (error) {
    csvFileErrors.value = [
      xlsx
        ? error instanceof Error
          ? error.message
          : 'This .xlsx could not be read. Try saving and uploading it again.'
        : 'The browser could not read this CSV. Try saving and uploading it again.',
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
  await nextTick()
  document.getElementById(`csv-edit-${rowNumber}`)?.focus()
}

// Leaving Preview (Back, a step, Continue or Submit) with a row open closes
// it: its changes are already in the row, made as they're typed.
const leaveCsvEditor = () => {
  editingCsvRowNumber.value = null
}

const updateCsvRow = (row: CsvRow, values: CsvRow['values']) => {
  clearCsvServerErrors(row)
  row.values = values
  refreshCsvRows()
}

const csvCategoryLabel = (category: CsvCategory) =>
  category === 'review-required' ? 'Review required' : category === 'invalid' ? 'Invalid' : 'Valid'

// The file's rows on Preview, by row number; the status column has what's wrong too.
const CSV_TABLE_COLUMNS: DataTableColumn[] = [
  { key: 'rowNumber', label: 'Row', type: 'number' },
  { key: 'student', label: 'Student' },
  { key: 'email', label: 'Email' },
  // Only as wide as it needs: "Valid" on its own is narrow (see .csv-issues).
  { key: 'status', label: 'Status' },
]
const csvTableRows = computed(() =>
  forms.supervisorCsv.rows.map((row) => ({
    rowNumber: row.rowNumber,
    student: `${row.values.first_name} ${row.values.last_name}`.trim() || 'Missing',
    email: row.values.email || 'Missing',
    status: csvCategoryLabel(row.category),
    row,
  })),
)
const toCsvRow = (row: Record<string, unknown>) => row.row as CsvRow

const submitRegistration = async () => {
  if (!journey.value || isSubmitting.value) return
  leaveCsvEditor()
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
  registeredNote.value = ''
  isSubmitting.value = true
  try {
    const asGroup =
      journey.value === 'supervisor_individual' &&
      forms.supervisorIndividual.extraStudents.length > 0
    const request = asGroup
      ? buildRegistrationRequest('supervisor_group', {
          ...forms,
          supervisorGroup: oneStudentAsGroup(),
        })
      : buildRegistrationRequest(journey.value, forms)
    // An admin's students' supervisor goes with it (Management > Registration).
    const supervisorEmail = adminChoosesSupervisor.value ? forms.adminSupervisorEmail.trim() : ''
    const signature = JSON.stringify({ request, overrides: warningOverrides.value, supervisorEmail })
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
    // Any address found not to exist then comes back as a warning to correct
    // or confirm. Skipped whenever it can't be done; never holds this up.
    await checkEmails(registrationGateway, request, {
      invitationToken: invitationToken.value,
      overrides: { ...warningOverrides.value },
      supervisorEmail: supervisorEmail || undefined,
    })
    const result = await registrationGateway.submit(request, {
      attachments,
      invitationToken: invitationToken.value,
      idempotencyKey: submissionKey,
      overrides: { ...warningOverrides.value },
      supervisorEmail: supervisorEmail || undefined,
    })
    clearServerErrors()
    if (!result.ok) {
      if (result.warnings?.length) {
        registrationWarnings.value = asGroup
          ? result.warnings.map((warning) => ({
              ...warning,
              field: fromOneStudentGroup(warning.field),
            }))
          : result.warnings
        Object.keys(warningAcknowledgements).forEach((key) => delete warningAcknowledgements[key])
        await nextTick()
        warningSummaryRef.value?.scrollIntoView?.({ block: 'center' })
        warningSummaryRef.value?.focus()
        return
      }
      const fieldErrors = asGroup
        ? Object.fromEntries(
            Object.entries(result.fieldErrors || {}).map(([path, message]) => [
              fromOneStudentGroup(path),
              message,
            ]),
          )
        : result.fieldErrors || {}
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
    if (journey.value === 'supervisor_individual' && !asGroup) {
      // On its own: straight back to an empty form, saying who was registered.
      const { student } = forms.supervisorIndividual
      const who = `${studentName(student)} (${student.email.trim()})`
      startAnotherRegistration()
      registeredNote.value = `Registration successful: ${who} is registered.`
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
  // Within Management > Registration (Back, another registration): the page
  // stays where it is, under the Registration Dates card.
  if (props.embedded) return
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  window.scrollTo({ top: 0, behavior: reducedMotion ? 'auto' : 'smooth' })
}

const resetRegistration = () => {
  registeredNote.value = ''
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

// A supervisor's next registration of the same kind, from its first step.
const startAnotherRegistration = () => {
  const again = isSupervisorMode.value ? journey.value : null
  resetRegistration()
  if (again) selectJourney(again)
}

const ANOTHER_LABELS: Partial<Record<RegistrationJourney, string>> = {
  supervisor_individual: 'Register Another Student',
  supervisor_group: 'Register Another Group',
  supervisor_csv: 'Upload Another CSV',
}
const anotherLabel = computed(() => (journey.value && ANOTHER_LABELS[journey.value]) || 'Register Another')

watch(invitationToken, resetRegistration)

// A restored registration: its steps open as far as they were reached, or
// as far as what's filled in reaches.
if (draft && journey.value) {
  maxReachedStep.value = Math.max(maxReachedStep.value, furthestFilledStep())
}

// Keep the public registration's progress as it's made (a moment after each
// change), and let it go once registered.
let draftTimer: ReturnType<typeof setTimeout> | undefined
if (!isSupervisorMode.value) {
  watch(
    [forms, journey, selectionStage, selectedRole, currentStep, maxReachedStep, success],
    () => {
      clearTimeout(draftTimer)
      if (success.value) {
        clearDraft()
        return
      }
      draftTimer = setTimeout(() => {
        saveDraft({
          invitationToken: invitationToken.value,
          journey: journey.value,
          selectionStage: selectionStage.value,
          selectedRole: selectedRole.value,
          currentStep: currentStep.value,
          maxReachedStep: maxReachedStep.value,
          forms: {
            studentIndividual: forms.studentIndividual,
            studentTeam: forms.studentTeam,
            mentor: forms.mentor,
          },
        })
      }, 250)
    },
    { deep: true },
  )
}
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
  /* The screen below the site's top bar. */
  min-height: calc(100vh - 4.375rem);
  min-height: calc(100dvh - 4.375rem);
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

/* Within Management > Registration: in its card, as tall as it needs. */
.registration-page--embedded {
  min-height: 0;
  background: transparent;
}

/* Headed as Management's cards below a page's first: a plain title with its
   hint under it, not a page's. */
.registration-page--embedded .page-header {
  margin-bottom: 1rem;
}

.registration-page--embedded .page-title {
  margin: 0 0 1rem;
  font-size: 1.05rem;
  font-weight: 600;
}

.registration-page--embedded .page-subtitle {
  font-size: 0.9rem;
}

/* Not held at the top of the screen, inside a card. */
.registration-page--embedded .journey-context {
  position: static;
  padding-top: 0;
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

/* Every step as wide, 2rem below the site's top bar (as the portal's pages
   are padded). */
.setup-layout {
  position: relative;
  z-index: 1;
  width: min(980px, calc(100% - 40px));
  margin: 2rem auto 72px;
}

/* However many roles there are, they fill the row. */
.role-options {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
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

/* Continue, as on the other option cards: the whole card is the button.
   Pointing at the card fills it with light green, left to right. */
.role-option__arrow,
.pathway-choice__arrow {
  background-color: transparent;
  background-image: linear-gradient(var(--light-green), var(--light-green));
  background-position: left center;
  background-repeat: no-repeat;
  background-size: 0% 100%;
  transition:
    background-size 0.3s ease,
    border-color 0.3s ease;
}

.role-option__arrow {
  justify-self: start;
}

.role-option:hover .role-option__arrow,
.role-option:focus-visible .role-option__arrow {
  background-color: transparent;
  background-size: 100% 100%;
  border-color: var(--dark-green);
}

/* Lined up under the cards, as the rest of the page is. */
.setup-signin {
  margin: 30px 0 0;
  color: var(--registration-muted);
}

.setup-signin a {
  color: var(--registration-green-dark);
  font-weight: 700;
}

.supervisor-guidance {
  margin: 12px 0 0;
  color: var(--registration-muted);
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

/* As the sign-up page's cards: the row stays as it is, its Continue fills. */
.pathway-choice:hover,
.pathway-choice:focus-visible {
  outline: none;
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
  color: var(--registration-muted);
  font-size: 0.88rem;
  line-height: 1.5;
}

/* The platform's small outline button (as Group Marking's Next); the whole
   card is the button, so pointing at the card is pointing at it (it fills
   as the role cards' Continue does). */
.pathway-choice__arrow {
  flex: 0 0 auto;
}

.pathway-choice:hover .pathway-choice__arrow,
.pathway-choice:focus-visible .pathway-choice__arrow {
  background-color: transparent;
  background-size: 100% 100%;
  border-color: var(--dark-green);
}

/* The page heading's own space below it, then the form. */
.work-layout {
  width: min(980px, calc(100% - 40px));
  margin-top: 2rem;
  margin-bottom: 72px;
  grid-template-columns: 1fr;
  gap: 0;
}

.work-layout .journey-context {
  position: static;
  padding: 0;
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
.journey-context h1:not(.page-title) {
  max-width: none;
  margin: 0 0 16px;
  color: var(--registration-ink);
  font-size: 1.75rem;
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.025em;
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
.form-surface {
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
.step-navigation .tab-pill > span {
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

.step-navigation .tab-pill.complete > span {
  border-color: var(--registration-green);
  background: var(--registration-green);
  color: #fff;
}

/* On the open step's green, the number in white. */
.step-navigation .tab-pill.current > span {
  border-color: #fff;
  background: #fff;
  color: var(--dark-green);
}

/* Once registered, the steps are only a record: not links. */
.step-navigation span.tab-pill,
.step-navigation span.tab-pill:hover {
  background: transparent;
  color: var(--text-muted);
  cursor: default;
}

/* A step that can't be gone to yet faded; the open one keeps its green (its
   white label would vanish on a clear background), faded too while a CSV
   row is being edited. */
.step-navigation button:disabled {
  cursor: not-allowed;
  opacity: 0.52;
}

.step-navigation button:disabled:not(.active) {
  background: transparent;
}

form,
.success-body {
  padding: clamp(24px, 3vw, 32px);
}

.success-intro {
  margin-bottom: 32px;
}

.success-intro h3 {
  margin: 0;
  color: var(--registration-ink);
  font-size: 1.25rem;
  font-weight: 600;
}

/* A little taller than the heading's capitals, on its baseline. */
.success-check {
  margin-left: 0.4rem;
  color: var(--success);
  font-size: 0.8em;
  vertical-align: 0;
}

.success-note {
  margin: 7px 0 0;
  color: var(--registration-muted);
  font-size: 0.9rem;
  line-height: 1.55;
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
.exclude-row input {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
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
.exclude-row input:focus-visible {
  outline: 3px solid rgba(8, 116, 90, 0.22);
  outline-offset: 3px;
}

/* A student group's code, to save and share: its label as a field's, the
   code large, Copy beside it. */
.group-code,
.group-join {
  display: grid;
  gap: 8px;
}

/* "OR" between the group code and its members, on a line either side. */
.or-divider {
  display: flex;
  align-items: center;
  gap: 16px;
  color: var(--registration-muted);
  font-size: 0.85rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.or-divider::before,
.or-divider::after {
  content: '';
  flex: 1;
  border-top: 1px solid var(--registration-line);
}

/* As big as the step's section headings (e.g. Group members). */
.group-code__label {
  color: var(--registration-ink);
  font-size: 1.25rem;
  font-weight: 600;
}

.group-code__row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.group-code__value {
  color: var(--dark-green);
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.group-join__actions {
  display: flex;
  justify-content: flex-end;
}

.group-code p,
.group-join p {
  margin: 0;
  color: var(--registration-muted);
  font-size: 0.86rem;
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
  margin: 7px 0 0;
  color: var(--registration-muted);
  font-size: 0.84rem;
  line-height: 1.52;
}

/* The file's columns and rules, as Grading's Upload marks words them: each
   column name as code. */
.template-download p + p {
  margin-top: 0.75rem;
}

.template-download code {
  padding: 0.05rem 0.3rem;
  border-radius: 4px;
  background: var(--bg-light);
  font-size: 0.82rem;
}

.section-divider--with-action,
.template-download__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

/* The heading, with the template on the right (below it when narrow). */
.template-download__head {
  align-items: center;
  flex-wrap: wrap;
}

.template-download__button {
  flex: 0 0 auto;
  white-space: nowrap;
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

/* Register one student's Student 1, headed once students are added, and a
   student group's Member 1, right under Group members: no line above. */
.student-entry--first {
  padding-top: 0;
  border-top: 0;
}

/* An admin's students' supervisor (Management > Registration), then a line
   and the rest of the step, as far apart as its sections are. */
.admin-supervisor {
  margin-bottom: 28px;
  padding-bottom: 28px;
  border-bottom: 1px solid var(--registration-line);
}

.student-entry__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
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

.upload-step {
  display: grid;
  gap: 30px;
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

/* Headed as Register one student's sections are. */
.csv-row-editor h3 {
  margin: 0;
  color: var(--registration-ink);
  font-size: 1.25rem;
  font-weight: 600;
}

/* Done editing, on the right as the form's own buttons are. */
.csv-editor-footer {
  display: flex;
  justify-content: flex-end;
}

/* What's wrong with a row, under its status: wrapping at 16rem, so the
   column is only wider than its status when a row has something wrong. */
.csv-issues {
  max-width: 16rem;
  white-space: normal;
  margin: 6px 0 0;
  padding-left: 16px;
  color: var(--registration-muted);
  font-size: 0.8rem;
  line-height: 1.4;
}

/* An excluded row, faded and struck through. */
.csv-table :deep(tr.is-excluded) {
  opacity: 0.52;
  text-decoration: line-through;
}

/* Edit, then Exclude, on one line. */
.csv-row-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
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
  display: flex;
  align-items: center;
  gap: 7px;
  color: #803530;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
}

/* The options with no lines between them, as Areas of Interest's. */
.affiliation-options {
  margin-top: 20px;
  display: grid;
  gap: 20px;
}

.affiliation-options label {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--registration-ink);
  font-size: 0.88rem;
  cursor: pointer;
}

.affiliation-options input {
  flex: 0 0 auto;
  width: 1.125rem;
  height: 1.125rem;
  margin: 0;
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

.review-section dl {
  margin: 0;
}

.review-section dl > div {
  padding: 13px 0;
  display: grid;
  grid-template-columns: minmax(130px, 0.48fr) minmax(0, 1fr);
  gap: 20px;
  border-bottom: 1px solid var(--registration-line);
}

.review-section dl > div:last-child {
  border-bottom: 0;
}

/* A row followed by more about the same person (a member's guardian): no
   line between them. */
.review-section dl > div.review-row--joined {
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

/* A member's name, email and guardian: columns as wide on every row, so
   they line up. */
.review-parts {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.6fr) minmax(0, 1fr);
  gap: 16px;
}

.review-parts span {
  overflow-wrap: anywhere;
}

/* A group's code with its Copy button beside it. */
.review-copy {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

/* Its label level with it, as the button makes the row taller. */
.review-section dl > div:has(.review-copy) {
  align-items: center;
}

/* Too narrow for columns: one under another. */
@media (max-width: 700px) {
  .review-parts {
    grid-template-columns: 1fr;
    gap: 2px;
  }
}

/* Sections apart by the step's own gap, with no line between them. */
.review-section {
  padding-bottom: 0;
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

/* Register one student's, under its description. */
.registered-note {
  margin: 0.75rem 0 0;
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  color: var(--success);
  font-weight: 600;
  line-height: 1.5;
}

.form-required-note {
  margin: 0 0 0 auto;
  color: var(--registration-muted);
  font-size: 0.78rem;
  white-space: nowrap;
}

/* On the right: Continue or Submit, with Add student before it on a
   group's Students step and on Register one student, with a note before it. */
.form-footer {
  margin-top: 46px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 18px;
}

/* Just left of the button it's about, in italics. */
.form-footer-note {
  margin: 0;
  color: var(--registration-muted);
  font-size: 0.85rem;
  font-style: italic;
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
  .setup-layout,
  .work-layout {
    width: min(100% - 24px, 1220px);
    margin-bottom: 38px;
  }

  .setup-layout {
    margin-top: 24px;
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
  .journey-context h1:not(.page-title) {
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

  .step-navigation .tab-pill {
    padding-inline: 10px;
  }

  .step-navigation__label {
    display: none !important;
  }

  .step-navigation .tab-pill.current .step-navigation__label,
  .step-navigation span.tab-pill .step-navigation__label {
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

  .review-section dl > div {
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
