import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ConsentPage from '../ConsentPage.vue'
import SignaturePad from '@/components/consent/SignaturePad.vue'
import { fetchConsentForm, signConsentForm } from '@/utils/consentAPI'
import type { ConsentFormData } from '@/utils/consentAPI'
import { ApiError } from '@/utils/apiError'

vi.mock('vue-router', () => ({ useRoute: () => ({ params: { token: 'tok123' } }) }))
vi.mock('@/utils/consentAPI', () => ({ fetchConsentForm: vi.fn(), signConsentForm: vi.fn() }))

const form: ConsentFormData = {
  studentName: 'Wren Ward',
  guardianFirstName: 'Pat',
  guardianLastName: 'Parent',
  expiresAt: '2026-10-22T00:00:00Z',
  supportEmail: 'support@biotechfutures.org',
  form: {
    version: '2026-09-16',
    body_html: '<p>Consent for Wren Ward.</p>',
    media_yes: 'Yes – I provide media consent.',
    media_no: 'No – I do not provide media consent.',
    declaration: 'By signing below, I confirm…'
  }
}

const linkError = (code: string, error: string) =>
  new ApiError({ error, code: `consent_link_${code}`, request_id: 'x' }, 410)

async function open() {
  const wrapper = mount(ConsentPage)
  await flushPromises()
  return wrapper
}

async function fillIn(wrapper: Awaited<ReturnType<typeof open>>) {
  await wrapper.find('[data-test="media-no"]').setValue(true)
  wrapper.findComponent(SignaturePad).vm.$emit('change', 'data:image/png;base64,SIG')
  await wrapper.find('[data-test="consent-agree"]').setValue(true)
}

describe('guardian consent page', () => {
  beforeEach(() => {
    vi.mocked(fetchConsentForm).mockReset().mockResolvedValue(form)
    vi.mocked(signConsentForm).mockReset()
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  })

  it('shows the form for the link with the guardian name filled in', async () => {
    const wrapper = await open()

    expect(fetchConsentForm).toHaveBeenCalledWith('tok123')
    expect(wrapper.find('h1').text()).toBe('Hi Pat')
    expect(wrapper.find('[data-test="consent-body"]').html()).toContain('Consent for Wren Ward.')
    expect((wrapper.find('[data-test="consent-name"]').element as HTMLInputElement).value).toBe('Pat Parent')
  })

  it('explains a link that can no longer be used', async () => {
    vi.mocked(fetchConsentForm).mockRejectedValue(linkError('expired', 'This consent link has expired.'))
    const wrapper = await open()

    const error = wrapper.find('[data-test="consent-link-error"]')
    expect(error.text()).toContain('This consent link has expired.')
    expect(error.text()).toContain('support@biotechfutures.org')
  })

  it('lists what is missing instead of submitting', async () => {
    const wrapper = await open()

    await wrapper.find('form').trigger('submit')

    expect(signConsentForm).not.toHaveBeenCalled()
    const missing = wrapper.find('[data-test="consent-missing"]').text()
    expect(missing).toContain('choose a media consent option')
    expect(missing).toContain('sign in the signature box')
    expect(missing).toContain('tick the box to confirm')
  })

  it('signs and shows the reference', async () => {
    vi.mocked(signConsentForm).mockResolvedValue({ reference: 'BTF-9', mediaConsent: false })
    const wrapper = await open()
    await fillIn(wrapper)

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(signConsentForm).toHaveBeenCalledWith('tok123', {
      guardianFullName: 'Pat Parent',
      mediaConsent: false,
      signature: 'data:image/png;base64,SIG',
      agreed: true,
      consentVersion: '2026-09-16'
    })
    const done = wrapper.find('[data-test="consent-signed"]').text()
    expect(done).toContain('BTF-9')
    expect(done).toContain('without media consent')
  })

  it('shows a form problem next to the form', async () => {
    vi.mocked(signConsentForm).mockRejectedValue(
      new ApiError({ error: 'Please sign in the signature box.', code: 'consent_form_incomplete', request_id: 'x' }, 400)
    )
    const wrapper = await open()
    await fillIn(wrapper)

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[data-test="consent-submit-error"]').text()).toBe('Please sign in the signature box.')
    expect(wrapper.find('form').exists()).toBe(true)
  })

  it('switches to the link message when the link was used meanwhile', async () => {
    vi.mocked(signConsentForm).mockRejectedValue(linkError('used', 'This consent form has already been signed. Thank you.'))
    const wrapper = await open()
    await fillIn(wrapper)

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.find('[data-test="consent-link-error"] h1').text()).toBe('Already signed')
  })
})
