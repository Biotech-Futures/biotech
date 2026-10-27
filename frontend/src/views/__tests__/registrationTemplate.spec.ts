// Upload student details' template: an .xlsx with an example row that's never
// registered, said beside the download and left out when uploaded back.
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import RegistrationPage from '@/views/RegistrationPage.vue'
import {
  CSV_EXAMPLE_NOTE,
  CSV_EXAMPLE_ROW,
  CSV_HEADERS,
  parseRegistrationCsv,
  registrationCsvTemplate,
} from '@/registration/registration'
import { REGISTRATION_GATEWAY_KEY } from '@/registration/registrationGateway'
import { resetCsrfToken } from '@/utils/csrf'

const exampleLine = CSV_HEADERS.map((header) => {
  const value = CSV_EXAMPLE_ROW[header]
  return /[",]/.test(value) ? `"${value}"` : value
}).join(',')
const studentLine =
  'Sam,Lee,sam.lee@example.test,Example High,10,Australia,NSW,Biomedical Innovations,Pat,Lee,pat.lee@example.test'

let posted: Array<{ url: string; body: string }> = []
let templateAnswer: Response | null = null
// What each download saved, by its file name.
let saved: Array<{ name: string; blob: Blob }> = []

beforeEach(() => {
  resetCsrfToken()
  posted = []
  saved = []
  templateAnswer = new Response(new Blob(['xlsx bytes']), { status: 200 })
  vi.stubGlobal('scrollTo', vi.fn())
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url)
    if (path.includes('/services/csrf/')) return new Response(JSON.stringify({ csrfToken: 'csrf' }))
    if (path.includes('/registration/sheet/template/')) {
      posted.push({ url: path, body: String(init?.body) })
      return templateAnswer ?? new Response('{}', { status: 500 })
    }
    return new Response('{}')
  }))
  let lastBlob: Blob | null = null
  Object.assign(URL, {
    createObjectURL: vi.fn((blob: Blob) => {
      lastBlob = blob
      return 'blob:template'
    }),
    revokeObjectURL: vi.fn(),
  })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    saved.push({ name: this.download, blob: lastBlob! })
  })
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

const mountCsvStep = async () => {
  const wrapper = mount(RegistrationPage, {
    props: { mode: 'supervisor' },
    attachTo: document.body,
    global: {
      plugins: [createPinia()],
      provide: { [REGISTRATION_GATEWAY_KEY as symbol]: { submit: vi.fn() } },
      stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
    },
  })
  ;(wrapper.vm as unknown as { journey: string }).journey = 'supervisor_csv'
  await flushPromises()
  return wrapper
}

const upload = async (wrapper: VueWrapper, text: string) => {
  const input = wrapper.get('.csv-upload input').element as HTMLInputElement
  const file = new File([text], 'students.csv', { type: 'text/csv' })
  Object.defineProperty(file, 'text', { value: async () => text })
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  input.dispatchEvent(new Event('change'))
  await flushPromises()
}

const clickDownload = async (wrapper: VueWrapper) => {
  await wrapper.get('.template-download__button').trigger('click')
  await flushPromises()
}

describe('the example row', () => {
  it('is left out when uploaded back, and a file of only it is refused', () => {
    const both = parseRegistrationCsv(`${registrationCsvTemplate()}${exampleLine}\r\n${studentLine}\r\n`)
    expect(both.errors).toEqual([])
    expect(both.examples).toEqual([2])
    expect(both.rows.map((row) => row.values.email)).toEqual(['sam.lee@example.test'])

    const alone = parseRegistrationCsv(`${registrationCsvTemplate()}${exampleLine}\r\n`)
    expect(alone.errors).toEqual(["The file only has the template's example row. Add a row for each student."])
  })

  it('is said beside the download, and when an upload still has it', async () => {
    const wrapper = await mountCsvStep()
    expect(wrapper.get('[data-test="template-example-note"]').text()).toContain(
      "The template has an example row (Alex Example) to show how to fill it in. It won't be registered",
    )

    await upload(wrapper, `${registrationCsvTemplate()}${exampleLine}\r\n${studentLine}\r\n`)

    expect(wrapper.get('[data-test="template-example-left-out"]').text()).toBe(
      "Row 2 is the template's example, so it won't be registered.",
    )
    wrapper.unmount()
  })
})

describe('Download example template', () => {
  it('saves an .xlsx with the columns and the example row', async () => {
    const wrapper = await mountCsvStep()

    await clickDownload(wrapper)

    expect(JSON.parse(posted[0]!.body)).toEqual({
      header: [
        'First Name', 'Last Name', 'Email', 'School', 'Year Level', 'Country', 'State', 'Area(s) of Interest',
        'Guardian First Name', 'Guardian Last Name', 'Guardian Email',
      ],
      example: CSV_HEADERS.map((header) => CSV_EXAMPLE_ROW[header]),
      note: CSV_EXAMPLE_NOTE,
    })
    expect(saved.map((file) => file.name)).toEqual(['biotech-registration-template.xlsx'])
    wrapper.unmount()
  })

  it("saves the same as a CSV when the server can't make one", async () => {
    templateAnswer = null
    const wrapper = await mountCsvStep()

    await clickDownload(wrapper)

    expect(saved.map((file) => file.name)).toEqual(['biotech-registration-template.csv'])
    const text = await new Promise<string>((resolve) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result))
      reader.readAsText(saved[0]!.blob)
    })
    // The note has a comma, so it's quoted.
    expect(text).toBe(`${registrationCsvTemplate()}${exampleLine},"${CSV_EXAMPLE_NOTE}"\r\n`)
    // Uploaded back as it is: its example left out, and nothing else.
    expect(parseRegistrationCsv(text).examples).toEqual([2])
    wrapper.unmount()
  })
})
