import type { InjectionKey } from 'vue'

import type { EmailCheckOutcome, EmailCheckProgress } from '@/registration/emailPrecheck'

import {
  payloadForRegistrationJourney,
  sanitizeRegistrationPayload,
  type MentorForm,
  type SupervisorForm,
  type RegistrationForms,
  type RegistrationIntakeJourney,
  type StudentIndividualForm,
  type StudentTeamForm,
  type SupervisorCsvForm,
  type SupervisorGroupForm,
  type SupervisorIndividualForm,
} from '@/registration/registration'

type SubmittedStudent<T> = Omit<T, 'emailConfirm'>

export interface StudentIndividualRegistrationRequest {
  journey: 'student_individual'
  payload: Omit<StudentIndividualForm, 'student'> & {
    student: SubmittedStudent<StudentIndividualForm['student']>
  }
}

export interface StudentTeamRegistrationRequest {
  journey: 'student_team'
  payload: Omit<StudentTeamForm, 'creator' | 'teammates'> & {
    creator: SubmittedStudent<StudentTeamForm['creator']>
    teammates: Array<SubmittedStudent<StudentTeamForm['teammates'][number]>>
  }
}

export interface SupervisorIndividualRegistrationRequest {
  journey: 'supervisor_individual'
  payload: Omit<SupervisorIndividualForm, 'student'> & {
    student: SubmittedStudent<SupervisorIndividualForm['student']>
  }
}

export interface SupervisorGroupRegistrationRequest {
  journey: 'supervisor_group'
  payload: Omit<SupervisorGroupForm, 'students'> & {
    students: Array<SubmittedStudent<SupervisorGroupForm['students'][number]>>
  }
}

export interface SupervisorCsvRegistrationRequest {
  journey: 'supervisor_csv'
  payload: SupervisorCsvForm
}

export interface MentorRegistrationRequest {
  journey: 'mentor'
  payload: { mentor: MentorForm }
}

export interface SupervisorRegistrationRequest {
  journey: 'supervisor'
  payload: { supervisor: SupervisorForm }
}

export type RegistrationRequest =
  | StudentIndividualRegistrationRequest
  | StudentTeamRegistrationRequest
  | SupervisorIndividualRegistrationRequest
  | SupervisorGroupRegistrationRequest
  | SupervisorCsvRegistrationRequest
  | MentorRegistrationRequest
  | SupervisorRegistrationRequest

export interface RegistrationReceipt {
  referenceCode: string
  journey: RegistrationIntakeJourney
  studentCount: number
  submittedAt: string
  /** A student group's code (6 digits), when one was registered. */
  groupCode?: string
  /** Someone registering themselves: sets their first password next. */
  passwordToken?: string
}

export interface RegistrationWarning {
  code: string
  field: string
  overrideField: string
  message: string
}

export type RegistrationGatewayResult =
  | { ok: true; receipt: RegistrationReceipt }
  | {
      ok: false
      message: string
      fieldErrors?: Record<string, string>
      warnings?: RegistrationWarning[]
    }

export interface RegistrationSubmitOptions {
  invitationToken?: string
  idempotencyKey?: string
  overrides?: Record<string, boolean>
  /** An admin's students' supervisor, by their email, on a supervisor
   *  journey (Management > Registration); only one that was chosen. */
  supervisorEmail?: string
}

export interface RegistrationGateway {
  supportedJourneys?: readonly RegistrationIntakeJourney[]
  submit(
    request: RegistrationRequest,
    options?: RegistrationSubmitOptions,
  ): Promise<RegistrationGatewayResult>
  /** Check the registration's email addresses before submitting it
   *  (emailPrecheck.ts), when this gateway can. Never throws. */
  checkEmails?(
    request: RegistrationRequest,
    options: Pick<RegistrationSubmitOptions, 'invitationToken' | 'overrides' | 'supervisorEmail'>,
    onProgress: (progress: EmailCheckProgress) => void,
  ): Promise<EmailCheckOutcome>
  /** An email box's check as it's left (emailFieldCheck.ts), when this
   *  gateway can: the server's results by box, or null when it can't be
   *  done. Never throws. */
  checkEmailField?(body: { journey?: string; fields: unknown[] }): Promise<Record<string, unknown> | null>
}

export const REGISTRATION_GATEWAY_KEY: InjectionKey<RegistrationGateway> =
  Symbol('registration-gateway')

export const buildRegistrationRequest = (
  journey: RegistrationIntakeJourney,
  forms: RegistrationForms,
): RegistrationRequest =>
  ({
    journey,
    payload: sanitizeRegistrationPayload(payloadForRegistrationJourney(journey, forms)),
  }) as RegistrationRequest
