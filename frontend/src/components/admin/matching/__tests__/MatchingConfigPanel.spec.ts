import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import MatchingConfigPanel from '@/components/admin/matching/MatchingConfigPanel.vue'
import { resetCsrfToken } from '@/utils/csrf'

/**
 * Integration coverage for the student matching weights editor: the panel, its
 * composable, matchingAPI, the parsers and the real csrf module all run — only
 * `fetch` is faked, with payloads in the backend's actual shapes.
 */

const savedRow = {
  id: 7,
  name: 'Student v2',
  is_active: true,
  year_weight: '30.00',
  timezone_weight: '15.00',
  timezone_max_weight: '25.00',
  size_bonus_weight: '30.00',
  total_weight: '100.00',
  updated_by: 1,
  created_at: '2026-10-06T10:00:00Z',
  updated_at: '2026-10-06T10:05:00Z'
}

const defaultsBlock = {
  requiredTotal: '100.00',
  defaults: {
    year_weight: 20.0,
    timezone_weight: 30.0,
    timezone_max_weight: 25.0,
    size_bonus_weight: 25.0
  }
}

const builtInActive = {
  data: null,
  weights: {
    yearWeight: 8.0,
    timezoneWeight: 2.0,
    timezoneMaxPenalty: 18.0,
    sizeBonusWeight: 6.0
  },
  ...defaultsBlock
}

const savedActive = {
  data: savedRow,
  weights: {
    yearWeight: 30.0,
    timezoneWeight: 15.0,
    timezoneMaxPenalty: 25.0,
    sizeBonusWeight: 30.0
  },
  ...defaultsBlock
}

const jsonResponse = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' }
  })

const validationError = (fields: Record<string, string[]>) =>
  jsonResponse(
    { error: Object.values(fields)[0][0], code: 'invalid', request_id: 'req-1', fields },
    400
  )

type Respond = () => Response

const stubFetch = (routes: { active?: Respond; create?: Respond; update?: Respond }) => {
  const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const target = String(url)
    const method = init?.method ?? 'GET'
    if (target.includes('/services/csrf/')) {
      return Promise.resolve(jsonResponse({ csrfToken: 'csrf-test' }))
    }
    if (target.endsWith('/matching/configs/active/')) {
      return Promise.resolve((routes.active ?? (() => jsonResponse(builtInActive)))())
    }
    if (target.endsWith('/matching/configs/') && method === 'POST' && routes.create) {
      return Promise.resolve(routes.create())
    }
    if (target.endsWith('/matching/configs/7/') && method === 'PATCH' && routes.update) {
      return Promise.resolve(routes.update())
    }
    return Promise.resolve(jsonResponse({ error: 'Unexpected request' }, 500))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** The request that reached the config API with the given method. */
const sent = (fetchMock: ReturnType<typeof stubFetch>, method: string) => {
  const call = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === method)!
  const init = call[1] as RequestInit
  return {
    url: String(call[0]),
    headers: new Headers(init.headers),
    body: JSON.parse(init.body as string)
  }
}

const weightInput = (wrapper: VueWrapper, key: string) =>
  wrapper.find<HTMLInputElement>(`#matching-config-${key}`)

const saveButton = (wrapper: VueWrapper) =>
  wrapper.findAll('button').find((button) => button.text().includes('Save'))!

const mountPanel = async () => {
  const wrapper = mount(MatchingConfigPanel)
  await flushPromises()
  return wrapper
}

const submit = async (wrapper: VueWrapper) => {
  await wrapper.find('form').trigger('submit')
  await flushPromises()
}

let wrapper: VueWrapper | null = null

beforeEach(() => {
  resetCsrfToken()
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.unstubAllGlobals()
})

describe('MatchingConfigPanel', () => {
  describe('scope and help copy', () => {
    it('titles the panel and says when changes apply', async () => {
      stubFetch({})
      wrapper = await mountPanel()

      expect(wrapper.find('#matching-config-title').text()).toBe('Scoring weights')
      expect(wrapper.text()).toContain('Changes apply to the next student matching run.')
    })

    it('keeps each weight’s help in an accessible tooltip tied to its input', async () => {
      stubFetch({})
      wrapper = await mountPanel()

      for (const key of [
        'yearWeight',
        'timezoneWeight',
        'timezoneMaxWeight',
        'sizeBonusWeight'
      ]) {
        const helpId = `matching-config-${key}-help`
        const tip = wrapper.find(`#${helpId}`)
        expect(tip.attributes('role')).toBe('tooltip')
        expect(tip.text().length).toBeGreaterThan(0)
        // Still read out with the field itself.
        expect(weightInput(wrapper, key).attributes('aria-describedby')).toContain(helpId)

        // A real, focusable button opens it — and must never submit the form.
        const info = wrapper.find(`button[aria-describedby="${helpId}"]`)
        expect(info.attributes('type')).toBe('button')
        expect(info.attributes('aria-label')).toMatch(/^About the .+ weight$/)
      }
    })

    it('renders no country weight input at all', async () => {
      stubFetch({})
      wrapper = await mountPanel()

      // Country stopped scoring and only ranks ties by its pair count, so there
      // is nothing for an admin to tune and no input may appear.
      expect(weightInput(wrapper, 'countryMismatchWeight').exists()).toBe(false)
    })
  })

  describe('loading', () => {
    it('fills the form from the active config', async () => {
      stubFetch({ active: () => jsonResponse(savedActive) })
      wrapper = await mountPanel()

      expect(wrapper.find<HTMLInputElement>('#matching-config-name').element.value).toBe(
        'Student v2'
      )
      expect(weightInput(wrapper, 'yearWeight').element.value).toBe('30')
      expect(weightInput(wrapper, 'timezoneWeight').element.value).toBe('15')
      expect(weightInput(wrapper, 'timezoneMaxWeight').element.value).toBe('25')
      expect(weightInput(wrapper, 'sizeBonusWeight').element.value).toBe('30')
      expect(wrapper.text()).not.toContain('built-in weighting')
    })

    it('starts a first config from the defaults, not the built-in weights', async () => {
      stubFetch({})
      wrapper = await mountPanel()

      expect(wrapper.find<HTMLInputElement>('#matching-config-name').element.value).toBe('')
      expect(weightInput(wrapper, 'yearWeight').element.value).toBe('20')
      expect(weightInput(wrapper, 'timezoneWeight').element.value).toBe('30')
      expect(weightInput(wrapper, 'timezoneMaxWeight').element.value).toBe('25')
      expect(weightInput(wrapper, 'sizeBonusWeight').element.value).toBe('25')
    })

    it('shows the built-in values in force separately, not as percentages', async () => {
      stubFetch({})
      wrapper = await mountPanel()

      const builtin = wrapper.find('.matching-config__builtin')
      expect(builtin.text()).toContain('using its built-in weighting')
      expect(builtin.text()).toContain('not percentages')
      const values = builtin.findAll('.matching-config__builtin-value').map((row) => row.text())
      expect(values).toEqual([
        'Year8',
        'Timezone2',
        'Timezone cap18',
        'Group size bonus6'
      ])
      expect(builtin.text()).toContain(
        'Saving a configuration replaces the built-in weighting and may change student ' +
          'matching results.'
      )
    })

    it('shows a general error with a retry when loading fails', async () => {
      let attempts = 0
      stubFetch({
        active: () =>
          ++attempts === 1
            ? jsonResponse({ error: 'Server error', code: 'internal_server_error' }, 500)
            : jsonResponse(savedActive)
      })
      wrapper = await mountPanel()

      expect(wrapper.find('[role="alert"]').text()).toContain('Server error')
      expect(wrapper.find('form').exists()).toBe(false)

      await wrapper.findAll('button').find((b) => b.text() === 'Retry')!.trigger('click')
      await flushPromises()
      expect(wrapper.find('form').exists()).toBe(true)
    })

    it('explains a 403 instead of showing the form', async () => {
      stubFetch({
        active: () => jsonResponse({ error: 'Forbidden', code: 'permission_denied' }, 403)
      })
      wrapper = await mountPanel()

      expect(wrapper.find('[role="alert"]').text()).toContain('do not have permission')
      expect(wrapper.find('form').exists()).toBe(false)
    })
  })

  describe('total', () => {
    it('shows a live total against the required total', async () => {
      stubFetch({})
      wrapper = await mountPanel()
      expect(wrapper.text()).toContain('Total: 100 / 100%')

      await weightInput(wrapper, 'yearWeight').setValue('5')

      expect(wrapper.text()).toContain('Total: 85 / 100%')
      expect(wrapper.text()).toContain('must total exactly 100%')
    })

    it('blocks saving until the total is exactly 100, without rebalancing', async () => {
      stubFetch({ active: () => jsonResponse(savedActive) })
      wrapper = await mountPanel()
      expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()

      await weightInput(wrapper, 'yearWeight').setValue('35')
      expect(wrapper.text()).toContain('Total: 105 / 100%')
      expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
      // Nothing else moved to compensate.
      expect(weightInput(wrapper, 'sizeBonusWeight').element.value).toBe('30')

      await weightInput(wrapper, 'sizeBonusWeight').setValue('25')
      expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()
    })

    it('flags an invalid total in the footer and ties it to the Save button', async () => {
      stubFetch({ active: () => jsonResponse(savedActive) })
      wrapper = await mountPanel()

      const total = wrapper.find('#matching-config-total')
      expect(saveButton(wrapper).attributes('aria-describedby')).toBe('matching-config-total')
      expect(total.classes()).not.toContain('matching-config__total--invalid')
      expect(total.find('.fa-triangle-exclamation').exists()).toBe(false)

      await weightInput(wrapper, 'yearWeight').setValue('35')

      expect(total.classes()).toContain('matching-config__total--invalid')
      expect(total.find('.fa-triangle-exclamation').exists()).toBe(true)
      expect(total.text()).toContain('Total: 105 / 100%')
      expect(total.text()).toContain('must total exactly 100%')
      expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
    })

    it('adds fractional weights exactly', async () => {
      stubFetch({ active: () => jsonResponse(savedActive) })
      wrapper = await mountPanel()

      await weightInput(wrapper, 'yearWeight').setValue('33.33')
      await weightInput(wrapper, 'sizeBonusWeight').setValue('26.67')

      expect(wrapper.text()).toContain('Total: 100 / 100%')
      expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()
    })

    it('flags an empty or over-precise weight and blocks saving', async () => {
      stubFetch({ active: () => jsonResponse(savedActive) })
      wrapper = await mountPanel()

      await weightInput(wrapper, 'timezoneWeight').setValue('')
      expect(wrapper.find('#matching-config-timezoneWeight-error').text()).toContain(
        'from 0 to 100'
      )
      expect(saveButton(wrapper).attributes('disabled')).toBeDefined()

      await weightInput(wrapper, 'timezoneWeight').setValue('15.005')
      expect(wrapper.find('#matching-config-timezoneWeight-error').exists()).toBe(true)
      expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
    })
  })

  describe('saving', () => {
    it('requires a name before the first config can be saved', async () => {
      stubFetch({})
      wrapper = await mountPanel()
      expect(saveButton(wrapper).attributes('disabled')).toBeDefined()

      await wrapper.find('#matching-config-name').setValue('Student weights 2026')
      expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()
    })

    it('POSTs a new active config the first time, with the values as entered', async () => {
      const fetchMock = stubFetch({
        create: () =>
          jsonResponse(
            {
              ...savedRow,
              id: 9,
              name: 'Student weights 2026',
              year_weight: '20.00',
              timezone_weight: '30.00',
              timezone_max_weight: '25.00',
              size_bonus_weight: '25.00'
            },
            201
          )
      })
      wrapper = await mountPanel()

      await wrapper.find('#matching-config-name').setValue('Student weights 2026')
      await submit(wrapper)

      const request = sent(fetchMock, 'POST')
      expect(request.url).toMatch(/\/matching\/configs\/$/)
      expect(request.headers.get('X-CSRFToken')).toBe('csrf-test')
      expect(request.body).toEqual({
        name: 'Student weights 2026',
        year_weight: 20,
        timezone_weight: 30,
        timezone_max_weight: 25,
        size_bonus_weight: 25,
        is_active: true
      })

      // The saved config is now the one in force.
      expect(wrapper.text()).not.toContain('using its built-in weighting')
      expect(wrapper.find('[role="status"]').text()).toContain('Saved')
    })

    it('PATCHes the active config when one exists', async () => {
      const fetchMock = stubFetch({
        active: () => jsonResponse(savedActive),
        update: () =>
          jsonResponse({ ...savedRow, year_weight: '33.33', size_bonus_weight: '26.67' })
      })
      wrapper = await mountPanel()

      await weightInput(wrapper, 'yearWeight').setValue('33.33')
      await weightInput(wrapper, 'sizeBonusWeight').setValue('26.67')
      await submit(wrapper)

      const request = sent(fetchMock, 'PATCH')
      expect(request.url).toMatch(/\/matching\/configs\/7\/$/)
      expect(request.headers.get('X-CSRFToken')).toBe('csrf-test')
      expect(request.body).toEqual({
        name: 'Student v2',
        year_weight: 33.33,
        timezone_weight: 15,
        timezone_max_weight: 25,
        size_bonus_weight: 26.67
      })
      const methods = fetchMock.mock.calls.map(([, init]) => (init as RequestInit)?.method)
      expect(methods).not.toContain('POST')
      expect(weightInput(wrapper, 'yearWeight').element.value).toBe('33.33')
      expect(wrapper.find('[role="status"]').text()).toContain('Saved')
    })
  })

  describe('validation errors from the server', () => {
    const saveWith = async (response: Respond) => {
      stubFetch({ active: () => jsonResponse(savedActive), update: response })
      wrapper = await mountPanel()
      await submit(wrapper)
    }

    it('shows a name error beside the name field', async () => {
      await saveWith(() =>
        validationError({ name: ['matching config with this name already exists.'] })
      )

      const nameInput = wrapper!.find('#matching-config-name')
      expect(nameInput.attributes('aria-invalid')).toBe('true')
      expect(nameInput.attributes('aria-describedby')).toBe('matching-config-name-error')
      expect(wrapper!.find('#matching-config-name-error').text()).toBe(
        'matching config with this name already exists.'
      )
    })

    it('shows a total error beside the total', async () => {
      const message =
        'Matching weights must total exactly 100.00% (currently 90.00%, 10.00% under).'
      await saveWith(() => validationError({ weight_total: [message] }))

      expect(wrapper!.find('.matching-config__total').text()).toContain(message)
    })

    it('shows a weight error beside its input, and clears it once edited', async () => {
      await saveWith(() =>
        validationError({ year_weight: ['Ensure that there are no more than 2 decimal places.'] })
      )

      expect(wrapper!.find('#matching-config-yearWeight-error').text()).toBe(
        'Ensure that there are no more than 2 decimal places.'
      )
      expect(weightInput(wrapper!, 'yearWeight').attributes('aria-invalid')).toBe('true')

      // A new value: the server's message described the one that was sent.
      await weightInput(wrapper!, 'yearWeight').setValue('25')
      expect(wrapper!.find('#matching-config-yearWeight-error').exists()).toBe(false)
    })

    it('shows non-field errors as a general error', async () => {
      await saveWith(() => validationError({ non_field_errors: ['Something went wrong.'] }))

      expect(wrapper!.find('.matching-config__error').text()).toContain('Something went wrong.')
    })

    it('shows a server failure as a general error', async () => {
      await saveWith(() =>
        jsonResponse({ error: 'Internal server error', code: 'internal_server_error' }, 500)
      )

      expect(wrapper!.find('.matching-config__error').text()).toContain('Internal server error')
      // The form stays, with the admin's values, so they can retry.
      expect(wrapper!.find('form').exists()).toBe(true)
    })

    it('explains a 403 on save', async () => {
      await saveWith(() => jsonResponse({ error: 'Forbidden', code: 'permission_denied' }, 403))

      expect(wrapper!.find('.matching-config__error').text()).toContain('do not have permission')
    })
  })
})
