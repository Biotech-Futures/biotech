import type { InjectionKey } from 'vue'

import {
  payloadForRegistrationJourney,
  sanitizeRegistrationPayload,
  type MentorForm,
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

export type RegistrationRequest =
  | StudentIndividualRegistrationRequest
  | StudentTeamRegistrationRequest
  | SupervisorIndividualRegistrationRequest
  | SupervisorGroupRegistrationRequest
  | SupervisorCsvRegistrationRequest
  | MentorRegistrationRequest

export interface RegistrationReceipt {
  referenceCode: string
  journey: RegistrationIntakeJourney
  studentCount: number
  submittedAt: string
  /** A student group's code (6 digits), when one was registered. */
  groupCode?: string
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

export interface RegistrationGateway {
  supportedJourneys?: readonly RegistrationIntakeJourney[]
  submit(
    request: RegistrationRequest,
    options?: {
      attachments?: Record<string, File>
      invitationToken?: string
      idempotencyKey?: string
      overrides?: Record<string, boolean>
      /** An admin's students' supervisor, by their email, on a supervisor
       *  journey (Management > Registration); only one that was chosen. */
      supervisorEmail?: string
    },
  ): Promise<RegistrationGatewayResult>
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
