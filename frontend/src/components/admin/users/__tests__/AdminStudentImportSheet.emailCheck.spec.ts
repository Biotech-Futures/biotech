import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import AdminStudentImportSheet from '@/components/admin/users/AdminStudentImportSheet.vue'
import AdminMentorImportSheet from '@/components/admin/mentors/AdminMentorImportSheet.vue'
import * as adminApi from '@/utils/adminAPI'

let wrapper: VueWrapper | null = null

const STUDENTS = [
  'Student email address,First Name,Surname,Country,School Name,Year Level,Area(s) of Interest,Supervisor Email',
  'taken@example.test,Tai,Ken,Australia,Test High,10,Genetics,',
  'gone@example.test,Gone,Away,Australia,Test High,10,Genetics,m.somervile@example.edu',
  'fine@example.test,Fine,Row,Australia,Test High,10,Genetics,',
].join('\n')

const MENTORS = [
  'Email Address,First Name,Surname,Country,Expertise,Mentor Reason,Institution or Company,Capacity',
  'taken@example.test,Tai,Ken,Australia,Genetics,To help,Uni,2',
  'fine@example.test,Fine,Row,Australia,Genetics,To help,Uni,2',
].join('\n')

const chooseFile = async (selector: string, text: string) => {
  const input = document.body.querySelector(selector) as HTMLInputElement
  const file = new File([text], 'import.csv', { type: 'text/csv' })
  Object.defineProperty(file, 'text', { value: async () => text })
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  input.dispatchEvent(new Event('change'))
  await flushPromises()
}

const text = () => document.body.textContent ?? ''

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

describe('Import Students: each address checked before Import', () => {
  it('skips the rows the check refuses, lists the warnings, and imports the rest', async () => {
    const post = vi.spyOn(adminApi, 'adminPost').mockImplementation(async () => ({
      lookups: null,
      results: [
        { row: 2, problems: ['Account email already exists'], warnings: [] },
        {
          row: 3,
          problems: [],
          warnings: [
            { field: 'email', message: "The student's email doesn't appear to exist." },
            { field: 'supervisorEmail', message: "The supervisor's email is a letter or two off Mary's." },
          ],
        },
        { row: 4, problems: [], warnings: [] },
      ],
    }))
    const importRows = vi
      .spyOn(adminApi, 'importAdminStudents')
      .mockResolvedValue({ msg: 'Bulk import complete', data: { created: [], skipped: [] } })
    wrapper = mount(AdminStudentImportSheet, { props: { modelValue: true }, attachTo: document.body })
    await flushPromises()

    await chooseFile('#student-csv-file', STUDENTS)

    const sent = post.mock.calls[0]?.[1] as { kind: string; rows: Array<Record<string, unknown>> }
    expect(sent.kind).toBe('students')
    expect(sent.rows[1]).toMatchObject({
      row: 3, email: 'gone@example.test', firstName: 'Gone', supervisorEmail: 'm.somervile@example.edu',
    })
    expect(text()).toContain('2 ready')
    expect(text()).toContain('1 with warnings')
    expect(text()).toContain('Row 2 - taken@example.test')
    expect(text()).toContain('Account email already exists')
    const warnings = document.body.querySelector('[data-test="import-warnings"]')?.textContent ?? ''
    expect(warnings).toContain('Row 3 - gone@example.test')
    expect(warnings).toContain(
      "The student's email doesn't appear to exist. The supervisor's email is a letter or two off Mary's.",
    )

    const importButton = [...document.body.querySelectorAll('button')].find((button) =>
      button.textContent?.includes('Import 2 students'),
    ) as HTMLButtonElement
    importButton.click()
    await flushPromises()
    expect(importRows.mock.calls[0]?.[0].map((row) => row.email)).toEqual(['gone@example.test', 'fine@example.test'])
  })

  it("can't import while the lookups run, and says how far they've got", async () => {
    vi.useFakeTimers()
    try {
      vi.spyOn(adminApi, 'adminPost')
        .mockResolvedValueOnce({ results: [], lookups: { jobId: 'job-1', status: 'started', total: 3, done: 1 } })
        .mockResolvedValueOnce({ results: [], lookups: null })
      vi.spyOn(adminApi, 'adminGet').mockResolvedValue({ status: 'done', total: 3, done: 3 })
      wrapper = mount(AdminStudentImportSheet, { props: { modelValue: true }, attachTo: document.body })
      await flushPromises()

      await chooseFile('#student-csv-file', STUDENTS)

      expect(document.body.querySelector('[data-test="import-email-check"]')?.textContent).toContain(
        'Checking emails (1 of 3)...',
      )
      const importButton = [...document.body.querySelectorAll('button')].find((button) =>
        button.textContent?.includes('Import 3 students'),
      ) as HTMLButtonElement
      expect(importButton.disabled).toBe(true)

      await vi.advanceTimersByTimeAsync(1500)
      await flushPromises()
      expect(document.body.querySelector('[data-test="import-email-check"]')).toBeNull()
      expect(importButton.disabled).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('Import Mentors: each address checked before Import', () => {
  it('skips the rows the check refuses', async () => {
    const post = vi.spyOn(adminApi, 'adminPost').mockResolvedValue({
      lookups: null,
      results: [
        { row: 2, problems: ['Account email already exists'], warnings: [] },
        { row: 3, problems: [], warnings: [{ field: 'email', message: "The mentor's email couldn't be verified." }] },
      ],
    })
    wrapper = mount(AdminMentorImportSheet, { props: { modelValue: true }, attachTo: document.body })
    await flushPromises()

    await chooseFile('#mentor-csv-file', MENTORS)

    expect((post.mock.calls[0]?.[1] as { kind: string }).kind).toBe('mentors')
    expect(text()).toContain('1 ready')
    expect(text()).toContain('Row 2 - taken@example.test')
    expect(document.body.querySelector('[data-test="import-warnings"]')?.textContent).toContain(
      "The mentor's email couldn't be verified.",
    )
  })
})
