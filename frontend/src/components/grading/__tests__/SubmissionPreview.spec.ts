import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SubmissionPreview from '@/components/grading/SubmissionPreview.vue'
import type { Submission, SubmissionComponent } from '@/utils/gradingAPI'

const component = (over: Partial<SubmissionComponent> = {}): SubmissionComponent => ({
  id: 2,
  code: 'POSTER',
  name: 'Poster',
  is_optional: false,
  accepts_file: true,
  accepts_text: false,
  accepts_link: false,
  order: 20,
  ...over
})

const submission = (over: Partial<Submission> = {}): Submission => ({
  id: 1,
  component: 2,
  file_url: null,
  text: '',
  link: '',
  submitted_at: '2026-09-01T10:00:00Z',
  is_late: false,
  overall_comment: '',
  ...over
})

const mountPreview = (props: Record<string, unknown>) =>
  mount(SubmissionPreview, { props: { component: component(), submission: null, ...props } })

beforeEach(() => {
  Element.prototype.setPointerCapture = vi.fn()
})

describe('what is shown for each submission shape', () => {
  it('names the component in the empty notice', () => {
    const wrapper = mountPreview({ submission: null })
    expect(wrapper.text()).toContain('No submission uploaded for Poster.')
  })

  it('renders SAQ answers as question blocks, not a raw dump', () => {
    const wrapper = mountPreview({
      component: component({ code: 'SAQ', name: 'Short Answer Questions' }),
      submission: submission({
        answers: [{ prompt: 'What does it do?', answer: 'Measures lead.' }],
        text: 'flattened'
      })
    })
    expect(wrapper.find('.submission-preview__question').text()).toBe('What does it do?')
    expect(wrapper.find('.submission-preview__answer-text').text()).toBe('Measures lead.')
    expect(wrapper.find('pre').exists()).toBe(false)
  })

  it('falls back to the flattened text when no per-question blocks exist', () => {
    const wrapper = mountPreview({ submission: submission({ text: 'Plain text entry.' }) })
    expect(wrapper.find('pre').text()).toBe('Plain text entry.')
  })

  it('offers a prototype link with its own Open action', () => {
    const wrapper = mountPreview({
      submission: submission({ link: 'https://example.com/demo' })
    })
    const link = wrapper.find('.submission-preview__link')
    expect(link.attributes('href')).toBe('https://example.com/demo')
    expect(link.attributes('rel')).toBe('noreferrer')
  })

  it('previews a PDF in a frame with the sidebar hints appended', () => {
    const wrapper = mountPreview({
      submission: submission({ file_url: '/media/posters/entry.pdf', file_name: 'entry.pdf' })
    })
    const frame = wrapper.find('iframe')
    expect(frame.attributes('src')).toContain('/media/posters/entry.pdf#navpanes=0&pagemode=none')
    expect(wrapper.text()).toContain('Open')
    expect(wrapper.text()).toContain('Download')
  })

  it('refuses to iframe a non-PDF and offers a labelled download instead', () => {
    const wrapper = mountPreview({
      component: component({ code: 'PROTOTYPE', name: 'Prototype' }),
      submission: submission({ file_url: '/media/protos/model.stl', file_name: 'model.stl' })
    })
    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.find('.submission-preview__no-preview').text()).toContain('model.stl')
  })

  it('prefers the attachment download URL when the server offers one', () => {
    const wrapper = mountPreview({
      submission: submission({
        file_url: '/media/posters/entry.pdf',
        file_download_url: '/api/v1/submissions/files/9/download/'
      })
    })
    const download = wrapper.findAll('a').find((a) => a.text().includes('Download'))!
    expect(download.attributes('href')).toContain('/api/v1/submissions/files/9/download/')
  })
})

describe('the submitted stamp and markers', () => {
  it('marks a late entry as late', () => {
    expect(mountPreview({ submission: submission({ is_late: true }) }).text()).toContain('(late)')
    expect(mountPreview({ submission: submission() }).text()).not.toContain('(late)')
  })

  it('names the last marker, with a group icon only when several marked', () => {
    const solo = mountPreview({
      submission: submission(),
      lastGraderName: 'Ada Grader',
      graderNames: ['Ada Grader']
    })
    expect(solo.text()).toContain('Marker:')
    expect(solo.find('.submission-preview__marker-icon').exists()).toBe(false)

    const several = mountPreview({
      submission: submission(),
      lastGraderName: 'Ada Grader',
      graderNames: ['Ada Grader', 'Bob Marker']
    })
    expect(several.find('.submission-preview__marker-icon').exists()).toBe(true)
  })

  it('builds the tooltip per criterion when markers differ by part', () => {
    const wrapper = mountPreview({
      submission: submission(),
      lastGraderName: 'Ada Grader',
      criterionMarkers: [
        { name: 'SAQ 1', marker: 'Ada Grader' },
        { name: 'SAQ 2', marker: 'Bob Marker' }
      ]
    })
    expect(wrapper.find('.submission-preview__marker').attributes('title')).toBe(
      'SAQ 1: Ada Grader\nSAQ 2: Bob Marker'
    )
  })

  it('falls back to a plain marked-by list, and to silence with no markers', () => {
    const listed = mountPreview({
      submission: submission(),
      lastGraderName: 'Ada Grader',
      graderNames: ['Ada Grader', 'Bob Marker']
    })
    expect(listed.find('.submission-preview__marker').attributes('title')).toBe(
      'Marked by: Ada Grader, Bob Marker'
    )
    const single = mountPreview({ submission: submission(), lastGraderName: 'Ada Grader' })
    expect(single.find('.submission-preview__marker').attributes('title')).toBe(
      'Marked by: Ada Grader'
    )
    expect(mountPreview({ submission: submission() }).text()).not.toContain('Marker:')
  })

  it('hides the whole stamp row when the parent hoists it', () => {
    const wrapper = mountPreview({
      submission: submission({ file_url: '/media/x.pdf' }),
      hideSubmitted: true
    })
    expect(wrapper.text()).not.toContain('Submitted')
    // The document itself still renders.
    expect(wrapper.find('iframe').exists()).toBe(true)
  })
})

describe('resizing blocks by keyboard', () => {
  it('grows and shrinks the PDF frame, never below the minimum', async () => {
    const wrapper = mountPreview({
      submission: submission({ file_url: '/media/x.pdf' })
    })
    const handle = wrapper.find('[aria-label="Resize preview height"]')
    await handle.trigger('keydown', { key: 'ArrowDown' })
    expect(wrapper.find('iframe').attributes('style')).toContain('height: 40px')
    await handle.trigger('keydown', { key: 'ArrowUp' })
    // Shrinking clamps to the minimum block height, not zero.
    expect(wrapper.find('iframe').attributes('style')).toContain('height: 240px')
  })

  it('the answers block shares the same mechanic', async () => {
    const wrapper = mountPreview({
      component: component({ code: 'SAQ' }),
      submission: submission({ answers: [{ prompt: 'Q', answer: 'A' }] })
    })
    const handle = wrapper.find('[aria-label="Resize answers height"]')
    await handle.trigger('keydown', { key: 'ArrowDown' })
    expect(wrapper.find('.submission-preview__answers').attributes('style')).toContain('height: 40px')
  })
})
