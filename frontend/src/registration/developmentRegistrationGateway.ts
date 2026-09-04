import type {
  RegistrationGateway,
  RegistrationGatewayResult,
  RegistrationRequest,
} from '@/registration/registrationGateway'

const studentCount = (request: RegistrationRequest) => {
  switch (request.journey) {
    case 'student_individual':
    case 'supervisor_individual':
      return 1
    case 'student_team':
      return request.payload.teammates.length + 1
    case 'supervisor_group':
      return request.payload.students.length
    case 'supervisor_csv':
      return request.payload.rows.length
    case 'mentor':
      return 0
  }
}

/**
 * Development-only fixture. It exercises canonical request/result states without
 * implying authoritative validation or persistence.
 */
export const developmentRegistrationGateway: RegistrationGateway = {
  async submit(request): Promise<RegistrationGatewayResult> {
    await new Promise((resolve) => window.setTimeout(resolve, 250))
    return {
      ok: true,
      receipt: {
        referenceCode: `DEV-${Date.now().toString(36).toUpperCase()}`,
        journey: request.journey,
        studentCount: studentCount(request),
        submittedAt: new Date().toISOString(),
      },
    }
  },
}

export const createDevelopmentRegistrationGateway = (
  result: RegistrationGatewayResult,
): RegistrationGateway => ({
  async submit() {
    return result
  },
})
