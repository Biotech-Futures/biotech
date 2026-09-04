import type { InjectionKey } from 'vue'

import {
  payloadForRegistrationJourney,
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

const cleanPayloadValue = (value: unknown, key = ''): unknown => {
  if (Array.isArray(value)) return value.map((item) => cleanPayloadValue(item))
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([entryKey, entryValue]) => {
          if (['emailConfirm', 'previewUrl', 'file'].includes(entryKey)) return false
          return !(typeof File !== 'undefined' && entryValue instanceof File)
        })
        .map(([entryKey, entryValue]) => [entryKey, cleanPayloadValue(entryValue, entryKey)]),
    )
  }
  if (typeof value === 'string') {
    const trimmed = value.trim()
    return key.toLowerCase().includes('email') ? trimmed.toLowerCase() : trimmed
  }
  return value
}

export const buildRegistrationRequest = (
  journey: RegistrationIntakeJourney,
  forms: RegistrationForms,
): RegistrationRequest =>
  ({
    journey,
    payload: cleanPayloadValue(payloadForRegistrationJourney(journey, forms)),
  }) as RegistrationRequest
