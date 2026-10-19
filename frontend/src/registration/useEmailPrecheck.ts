import { ref } from 'vue'

import type { EmailCheckOutcome, EmailCheckProgress } from '@/registration/emailPrecheck'
import type {
  RegistrationGateway,
  RegistrationRequest,
  RegistrationSubmitOptions,
} from '@/registration/registrationGateway'

/**
 * The email check run before a registration is submitted, for the page:
 * ``progress`` while it runs (null otherwise), and ``check()``, which waits
 * for it. A gateway that can't check, or any failure, simply skips it.
 */
export const useEmailPrecheck = () => {
  const progress = ref<EmailCheckProgress | null>(null)

  const check = async (
    gateway: RegistrationGateway,
    request: RegistrationRequest,
    options: Pick<RegistrationSubmitOptions, 'invitationToken' | 'overrides' | 'supervisorEmail'>,
  ): Promise<EmailCheckOutcome> => {
    if (!gateway.checkEmails) return 'skipped'
    try {
      return await gateway.checkEmails(request, options, (next) => {
        progress.value = next
      })
    } catch {
      return 'skipped'
    } finally {
      progress.value = null
    }
  }

  return { progress, check }
}
