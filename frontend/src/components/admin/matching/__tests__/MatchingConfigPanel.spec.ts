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
  year_weight: '30.00',
  year_max_weight: '20.00',
  timezone_weight: '15.00',
  timezone_max_weight: '25.00',
  size_bonus_weight: '30.00',
  total_weight: '90.00',
  max_total_penalty: '45.00',
  updated_by: 1,
  created_at: '2026-10-06T10:00:00Z',
  updated_at: '2026-10-06T10:05:00Z'
}

const defaultsBlock = {
  baseScore: 100,
  maxTotalPenalty: 100,
  defaults: {
    year_weight: 8.0,
    year_max_weight: 24.0,
    timezone_weight: 2.0,
    timezone_max_weight: 18.0,
    size_bonus_weight: 6.0
  }
}

const builtInActive = {
  data: null,
  weights: {
    yearWeight: 8.0,
    yearMaxPenalty: 24.0,
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
    yearMaxPenalty: 20.0,
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
        'yearMaxWeight',
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

    it('offers exactly the five scoring weights, in order', async () => {
      stubFetch({})
      wrapper = await mountPanel()

      const grid = wrapper.find('.matching-config__grid')
      expect(grid.findAll('input')).toHaveLength(5)
      expect(grid.findAll('label').map((label) => label.text())).toEqual([
        'Year',
        'Year cap',
        'Timezone',
        'Timezone cap',
        'Group size bonus'
      ])
      expect(grid.text()).not.toMatch(/country/i)
    })

    it('labels the inputs as points rather than percentages', async () => {
      stubFetch({})
      wrapper = await mountPanel()

      const suffixes = wrapper.findAll('.matching-config__suffix')
      expect(suffixes).toHaveLength(5)
      expect(suffixes.map((suffix) => suffix.text())).toEqual(Array(5).fill('pts'))
      expect(wrapper.find('.matching-config__grid').text()).not.toContain('%')
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

      expect(weightInput(wrapper, 'yearWeight').element.value).toBe('30')
      expect(weightInput(wrapper, 'yearMaxWeight').element.value).toBe('20')
      expect(weightInput(wrapper, 'timezoneWeight').element.value).toBe('15')
      expect(weightInput(wrapper, 'timezoneMaxWeight').element.value).toBe('25')
      expect(weightInput(wrapper, 'sizeBonusWeight').element.value).toBe('30')
      expect(wrapper.text()).not.toContain('built-in weighting')
    })

    it('starts a first config from the defaults, not the built-in weights', async () => {
      stubFetch({})
      wrapper = await mountPanel()

      expect(weightInput(wrapper, 'yearWeight').element.value).toBe('8')
      expect(weightInput(wrapper, 'yearMaxWeight').element.value).toBe('24')
      expect(weightInput(wrapper, 'timezoneWeight').element.value).toBe('2')
      expect(weightInput(wrapper, 'timezoneMaxWeight').element.value).toBe('18')
      expect(weightInput(wrapper, 'sizeBonusWeight').element.value).toBe('6')
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

  describe('the penalty ceiling', () => {
    it('shows what the caps can take off, and the worst case that leaves', async () => {
      stubFetch({})
      wrapper = await mountPanel()
      // The shipped defaults cap year at 24 and timezone at 18.
      expect(wrapper.text()).toContain('Penalty caps: 42 of 100')
      expect(wrapper.find('.matching-config__total-hint').text()).toContain('58')

      await weightInput(wrapper, 'yearMaxWeight').setValue('40')

      expect(wrapper.text()).toContain('Penalty caps: 58 of 100')
      expect(wrapper.find('.matching-config__total-hint').text()).toContain('42')
    })

    it('says what to change once the ceiling is exceeded', async () => {
      stubFetch({ active: () => jsonResponse(savedActive) })
      wrapper = await mountPanel()

      // Caps of 20 and 25; 90 puts them 15 past the ceiling.
      await weightInput(wrapper, 'yearMaxWeight').setValue('90')

      const hint = wrapper.find('.matching-config__total-hint').text()
      expect(hint).toContain('lower a cap by at least 15')
      expect(hint).toContain('fall below 0')
      // The instruction replaces the copy that merely restates the rule.
      expect(hint).not.toContain('may total at most')
    })

    it('counts only the caps, not the per-unit weights', async () => {
      stubFetch({ active: () => jsonResponse(savedActive) })
      wrapper = await mountPanel()

      // Huge per-unit weights: bounded by the caps, so the ceiling is untouched
      // and saving stays open.
      await weightInput(wrapper, 'yearWeight').setValue('90')
      await weightInput(wrapper, 'timezoneWeight').setValue('90')

      expect(wrapper.text()).toContain('Penalty caps: 45 of 100')
      expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()
    })

    it('lets the weights total anything at all', async () => {
      stubFetch({ active: () => jsonResponse(savedActive) })
      wrapper = await mountPanel()

      // 5 + 20 + 5 + 25 + 5 = 60, nowhere near 100, and perfectly saveable:
      // the old "must total exactly 100" rule is gone.
      for (const [key, value] of [
        ['yearWeight', '5'],
        ['timezoneWeight', '5'],
        ['sizeBonusWeight', '5']
      ] as const) {
        await weightInput(wrapper, key).setValue(value)
      }

      expect(wrapper.text()).not.toMatch(/must total/i)
      expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()
    })

    it('blocks saving once the caps could wipe out the whole base score', async () => {
      stubFetch({ active: () => jsonResponse(savedActive) })
      wrapper = await mountPanel()
      expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()

      // 90 + 25 = 115, past the 100-point ceiling.
      await weightInput(wrapper, 'yearMaxWeight').setValue('90')
      expect(wrapper.text()).toContain('Penalty caps: 115 of 100')
      expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
      // Nothing else moved to compensate.
      expect(weightInput(wrapper, 'timezoneMaxWeight').element.value).toBe('25')

      await weightInput(wrapper, 'timezoneMaxWeight').setValue('10')
      expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()
    })

    it('allows caps that land exactly on the ceiling', async () => {
      stubFetch({ active: () => jsonResponse(savedActive) })
      wrapper = await mountPanel()

      await weightInput(wrapper, 'yearMaxWeight').setValue('75')
      await weightInput(wrapper, 'timezoneMaxWeight').setValue('25')

      expect(wrapper.text()).toContain('Penalty caps: 100 of 100')
      expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()
    })

    it('flags an exceeded ceiling in the footer and ties it to the Save button', async () => {
      stubFetch({ active: () => jsonResponse(savedActive) })
      wrapper = await mountPanel()

      const total = wrapper.find('#matching-config-total')
      expect(saveButton(wrapper).attributes('aria-describedby')).toBe('matching-config-total')
      expect(total.classes()).not.toContain('matching-config__total--invalid')
      expect(total.find('.fa-triangle-exclamation').exists()).toBe(false)

      await weightInput(wrapper, 'yearMaxWeight').setValue('90')

      expect(total.classes()).toContain('matching-config__total--invalid')
      expect(total.find('.fa-triangle-exclamation').exists()).toBe(true)
      expect(total.text()).toContain('Penalty caps: 115 of 100')
      expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
    })

    it('adds fractional caps exactly', async () => {
      stubFetch({ active: () => jsonResponse(savedActive) })
      wrapper = await mountPanel()

      await weightInput(wrapper, 'yearMaxWeight').setValue('33.33')
      await weightInput(wrapper, 'timezoneMaxWeight').setValue('66.67')

      expect(wrapper.text()).toContain('Penalty caps: 100 of 100')
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
    it('saves a first config straight away, with no name to supply', async () => {
      stubFetch({})
      wrapper = await mountPanel()

      // A config has no display name: the form starts on the shipped defaults,
      // which sit inside the ceiling, and can be saved immediately.
      expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()
    })

    it('POSTs a new config the first time, with the values as entered', async () => {
      const fetchMock = stubFetch({
        create: () =>
          jsonResponse(
            {
              ...savedRow,
              id: 9,
              year_weight: '8.00',
              year_max_weight: '24.00',
              timezone_weight: '2.00',
              timezone_max_weight: '18.00',
              size_bonus_weight: '6.00'
            },
            201
          )
      })
      wrapper = await mountPanel()

      await submit(wrapper)

      const request = sent(fetchMock, 'POST')
      expect(request.url).toMatch(/\/matching\/configs\/$/)
      expect(request.headers.get('X-CSRFToken')).toBe('csrf-test')
      expect(request.body).toEqual({
        year_weight: 8,
        year_max_weight: 24,
        timezone_weight: 2,
        timezone_max_weight: 18,
        size_bonus_weight: 6
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
        year_weight: 33.33,
        year_max_weight: 20,
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

    it('shows a penalty ceiling error beside the caps', async () => {
      const message =
        'Please lower a cap by at least 15: at 115 points against a 100-point ' +
        'score, the worst pairing would fall below 0 and floor there instead ' +
        'of ranking.'
      await saveWith(() => validationError({ penalty_ceiling: [message] }))

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
