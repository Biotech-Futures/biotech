import { describe, expect, it } from 'vitest'

import {
  createDevelopmentRegistrationGateway,
  developmentRegistrationGateway,
} from '@/registration/developmentRegistrationGateway'
import { createRegistrationForms } from '@/registration/registration'
import { buildRegistrationRequest } from '@/registration/registrationGateway'

describe('registration gateway contract', () => {
  it('sanitizes confirmation fields, file-like values, preview URLs, and email casing', () => {
    const forms = createRegistrationForms()
    forms.studentIndividual.student.email = ' Student@Example.com '
    forms.studentIndividual.student.emailConfirm = 'Student@example.com'
    forms.studentIndividual.student.profilePhoto = {
      name: 'profile.png',
      type: 'image/png',
      size: 2048,
    }
    Object.assign(forms.studentIndividual.student, {
      previewUrl: 'blob:local-preview',
      file: new File(['photo'], 'profile.png', { type: 'image/png' }),
    })

    const request = buildRegistrationRequest('student_individual', forms)
    const serialized = JSON.stringify(request)

    expect(request.journey).toBe('student_individual')
    if (request.journey !== 'student_individual') throw new Error('Unexpected request journey')
    expect(request.payload.student.email).toBe('student@example.com')
    expect(serialized).not.toContain('emailConfirm')
    expect(serialized).not.toContain('previewUrl')
    expect(serialized).not.toContain('"file"')
    expect(request.payload.student.profilePhoto).toEqual({
      name: 'profile.png',
      type: 'image/png',
      size: 2048,
    })
  })

  it('returns a journey-specific development receipt without claiming persistence', async () => {
    const forms = createRegistrationForms()
    const result = await developmentRegistrationGateway.submit(
      buildRegistrationRequest('student_team', forms),
    )

    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.receipt.journey).toBe('student_team')
      expect(result.receipt.studentCount).toBe(2)
      expect(result.receipt.referenceCode).toMatch(/^DEV-/)
    }
  })

  it('can represent authoritative field errors from a future backend adapter', async () => {
    const gateway = createDevelopmentRegistrationGateway({
      ok: false,
      message: 'Review the highlighted information.',
      fieldErrors: { 'mentor.email': 'This address is already registered.' },
    })

    const result = await gateway.submit(
      buildRegistrationRequest('mentor', createRegistrationForms()),
    )

    expect(result).toEqual({
      ok: false,
      message: 'Review the highlighted information.',
      fieldErrors: { 'mentor.email': 'This address is already registered.' },
    })
  })

  it('omits signed-in supervisor identity and all client-only confirmation values', () => {
    const forms = createRegistrationForms()
    forms.supervisorIndividual.student.emailConfirm = 'student@example.com'
    forms.supervisorGroup.students[0].emailConfirm = 'one@example.com'

    const individual = buildRegistrationRequest('supervisor_individual', forms)
    const group = buildRegistrationRequest('supervisor_group', forms)
    const csv = buildRegistrationRequest('supervisor_csv', forms)

    expect(individual.payload).not.toHaveProperty('supervisor')
    expect(group.payload).not.toHaveProperty('supervisor')
    expect(csv.payload).not.toHaveProperty('supervisor')
    expect(JSON.stringify(individual)).not.toContain('emailConfirm')
    expect(JSON.stringify(group)).not.toContain('emailConfirm')
  })
})
