// Add user's email boxes, checked as each is left (user/email-check/): what
// saving refuses is shown under the box and stops it; a warning is shown to
// confirm before saving.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'

import AdminUserFormSheet from '../AdminUserFormSheet.vue'
import { checkAdminUserEmails, createAdminUser } from '@/utils/adminAPI'

vi.mock('@/utils/adminAPI', async () => ({
  ...(await vi.importActual<typeof import('@/utils/adminAPI')>('@/utils/adminAPI')),
  checkAdminUserEmails: vi.fn(),
  createAdminUser: vi.fn(),
  updateAdminUser: vi.fn(),
  setAdminUserActive: vi.fn(),
}))

let wrapper: VueWrapper | null = null

const openSheet = async () => {
  wrapper = mount(AdminUserFormSheet, {
    props: {
      modelValue: false, userNoun: 'user', user: null, isSupervisorMode: false,
      countries: [], states: [], supervisors: [],
    },
    global: { stubs: { Teleport: true } },
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  return wrapper
}

const leave = async (selector: string, value: string) => {
  await wrapper!.get(selector).setValue(value)
  await wrapper!.get(selector).trigger('blur')
  await flushPromises()
}

const submit = async () => {
  await wrapper!.get('form').trigger('submit')
  await flushPromises()
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(createAdminUser).mockResolvedValue({ msg: 'ok', data: { id: 9 } } as never)
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe("Add user's email check", () => {
  it('shows what saving refuses under the box, and saves nothing until it is corrected', async () => {
    vi.mocked(checkAdminUserEmails).mockResolvedValue({
      email: { ok: false, severity: 'hard', code: 'email_refused', message: 'Account email already exists' },
    })
    await openSheet()
    await wrapper!.get('#f-first').setValue('Jo')
    await wrapper!.get('#f-last').setValue('Lee')

    await leave('#f-email', 'taken@example.test')

    expect(checkAdminUserEmails).toHaveBeenCalledWith([
      { field: 'email', kind: 'account', email: 'taken@example.test', firstName: 'Jo', lastName: 'Lee', userId: undefined },
    ])
    expect(wrapper!.get('.admin-users-form__field-error').text()).toBe('Account email already exists')
    expect(wrapper!.get('#f-email').attributes('aria-invalid')).toBe('true')

    await submit()
    expect(createAdminUser).not.toHaveBeenCalled()

    vi.mocked(checkAdminUserEmails).mockResolvedValue({ email: { ok: true } })
    await leave('#f-email', 'jo.lee@example.test')
    expect(wrapper!.find('.admin-users-form__field-error').exists()).toBe(false)
  })

  it('asks for a warning to be confirmed before saving', async () => {
    vi.mocked(checkAdminUserEmails).mockResolvedValue({
      email: {
        ok: false, severity: 'soft',
        warnings: [{ code: 'email_invalid', message: "This email address couldn't be verified." }],
      },
    })
    await openSheet()
    await wrapper!.get('#f-first').setValue('Jo')
    await wrapper!.get('#f-last').setValue('Lee')
    await leave('#f-email', 'jo@unsure.test')

    expect(wrapper!.get('.email-check-note--warning').text()).toContain("couldn't be verified")
    await submit()
    expect(createAdminUser).not.toHaveBeenCalled()
    expect(wrapper!.get('.admin-users-form__error').text()).toBe('Correct the email address, or tick to confirm it.')

    await wrapper!.get('[data-test="f-email-confirm"]').setValue(true)
    await submit()
    expect(createAdminUser).toHaveBeenCalledTimes(1)
  })

  it('saves as before when the check is unreachable', async () => {
    vi.mocked(checkAdminUserEmails).mockRejectedValue(new Error('offline'))
    await openSheet()
    await wrapper!.get('#f-first').setValue('Jo')
    await wrapper!.get('#f-last').setValue('Lee')
    await leave('#f-email', 'jo@example.test')

    await submit()
    expect(createAdminUser).toHaveBeenCalledTimes(1)
  })
})
