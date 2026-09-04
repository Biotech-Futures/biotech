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
}

export type RegistrationGatewayResult =
  | { ok: true; receipt: RegistrationReceipt }
  | {
      ok: false
      message: string
      fieldErrors?: Record<string, string>
    }

export interface RegistrationGateway {
  submit(request: RegistrationRequest): Promise<RegistrationGatewayResult>
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
