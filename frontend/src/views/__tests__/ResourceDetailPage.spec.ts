import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import ResourceDetailPage from '@/views/ResourceDetailPage.vue'
import AdminRecordedSessionFields from '@/components/admin/resources/AdminRecordedSessionFields.vue'
import * as resourcesApi from '@/utils/resourcesAPI'
import { useRoute } from 'vue-router'

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: vi.fn(() => ({ params: { id: '201' }, name: 'resource-detail', query: {} })),
  useRouter: vi.fn(() => ({ push: mockPush }))
}))

describe('ResourceDetailPage & Recorded Session', () => {
  let wrapper: VueWrapper | null = null

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
      wrapper = null
    }
    vi.restoreAllMocks()
  })

  it('goes back to the library, at its row', async () => {
    vi.spyOn(resourcesApi, 'fetchResource').mockResolvedValue({ id: 201, name: 'Guide', kind: 'page' } as never)
    vi.spyOn(resourcesApi, 'fetchResourceAccess').mockResolvedValue(null as never)
    vi.mocked(useRoute).mockReturnValueOnce({ params: { id: '201' }, name: 'resource-detail', query: {} } as never)

    wrapper = mount(ResourceDetailPage)
    await flushPromises()
    expect(wrapper.get('.back-button').text()).toBe('Back to resources')
    await wrapper.get('.back-button').trigger('click')
    // Which the Resources page brings into view.
    expect(mockPush).toHaveBeenLastCalledWith({ name: 'resources', query: { resource: '201' } })
  })

  it('renders regular resource without slides download button when has_slides is false', async () => {
    vi.spyOn(resourcesApi, 'fetchResource').mockResolvedValue({
      id: 201,
      name: 'Workshop Video',
      description: 'Introductory workshop',
      kind: 'file',
      type_name: 'Workshop',
      file_mime_type: 'video/mp4',
      file_size: 10 * 1024 * 1024,
      uploaded_at: '2026-03-01T10:00:00Z',
      file_name: 'workshop.mp4',
      has_slides: false
    })

    vi.spyOn(resourcesApi, 'fetchResourceAccess').mockResolvedValue({
      resource_id: 201,
      kind: 'file',
      storage_status: 'managed_key',
      access_mode: 'managed_file',
      access_url: '/resources/resource-files/201/access/',
      download_url: '/resources/resource-files/201/download/',
      external_url: null,
      file_name: 'workshop.mp4',
      file_mime_type: 'video/mp4',
      file_size: 10 * 1024 * 1024,
      detail: null,
      has_slides: false,
      slides_download_url: null
    })

    wrapper = mount(ResourceDetailPage)
    await flushPromises()

    expect(wrapper.text()).toContain('Workshop Video')
    expect(wrapper.text()).toContain('Download')
    expect(wrapper.text()).not.toContain('Download Slides')
    expect(wrapper.find('video.preview-media').exists()).toBe(true)
  })

  it('renders secondary Download Slides button when has_slides is true on recorded session', async () => {
    vi.spyOn(resourcesApi, 'fetchResource').mockResolvedValue({
      id: 201,
      name: 'Keynote Session',
      description: 'Full recording with slides',
      kind: 'file',
      type_name: 'Recorded Session',
      file_mime_type: 'video/mp4',
      file_size: 50 * 1024 * 1024,
      uploaded_at: '2026-03-01T10:00:00Z',
      file_name: 'keynote.mp4',
      has_slides: true,
      slides_mime_type: 'application/pdf',
      slides_file_size: 2 * 1024 * 1024,
      slides_download_url: '/resources/resource-files/201/download/?field=slides'
    })

    vi.spyOn(resourcesApi, 'fetchResourceAccess').mockResolvedValue({
      resource_id: 201,
      kind: 'file',
      storage_status: 'managed_key',
      access_mode: 'managed_file',
      access_url: '/resources/resource-files/201/access/',
      download_url: '/resources/resource-files/201/download/',
      external_url: null,
      file_name: 'keynote.mp4',
      file_mime_type: 'video/mp4',
      file_size: 50 * 1024 * 1024,
      detail: null,
      has_slides: true,
      slides_mime_type: 'application/pdf',
      slides_file_size: 2 * 1024 * 1024,
      slides_download_url: '/resources/resource-files/201/download/?field=slides'
    })

    wrapper = mount(ResourceDetailPage)
    await flushPromises()

    expect(wrapper.text()).toContain('Keynote Session')
    expect(wrapper.text()).toContain('Download')
    expect(wrapper.text()).toContain('Download Slides')
    expect(wrapper.text()).toContain('Slides')
    expect(wrapper.text()).toContain('PDF (2.0 MB)')

    // Primary preview remains video, slides are not previewed natively
    expect(wrapper.find('video.preview-media').exists()).toBe(true)
    expect(wrapper.find('iframe[title="PDF preview"]').exists()).toBe(false)

    // Test clicking download slides triggers link creation
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const slidesBtn = wrapper.findAll('button').find((b) => b.text().includes('Download Slides'))
    expect(slidesBtn).toBeDefined()
    await slidesBtn!.trigger('click')
    expect(clickSpy).toHaveBeenCalled()
  })
})

describe('AdminRecordedSessionFields', () => {
  let wrapper: VueWrapper | null = null

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
      wrapper = null
    }
  })

  it('renders video and slides inputs with appropriate labels and hints', () => {
    wrapper = mount(AdminRecordedSessionFields, {
      props: {
        isEditing: false,
        videoFile: null,
        slidesFile: null,
        needsOversizeAck: false,
        acknowledgedOversized: false
      }
    })

    expect(wrapper.text()).toContain('Session Video Recording')
    expect(wrapper.text()).toContain('Presentation Slides (Optional)')
    expect(wrapper.text()).toContain('MP4, WebM, MOV')
    expect(wrapper.text()).toContain('PDF only')
  })

  it('validates and rejects non-PDF file for slides', async () => {
    wrapper = mount(AdminRecordedSessionFields, {
      props: {
        isEditing: false,
        videoFile: null,
        slidesFile: null,
        needsOversizeAck: false,
        acknowledgedOversized: false
      }
    })

    const nonPdfFile = new File(['text'], 'slides.txt', { type: 'text/plain' })
    const slidesInput = wrapper.find('#admin-resource-slides-file')

    Object.defineProperty(slidesInput.element, 'files', {
      value: [nonPdfFile],
      configurable: true
    })
    await slidesInput.trigger('change')

    expect(wrapper.text()).toContain('Presentation slides must be a PDF file')
    expect(wrapper.emitted('update:slides-file')?.[0]).toEqual([null])
  })

  it('accepts PDF file for slides and emits update', async () => {
    wrapper = mount(AdminRecordedSessionFields, {
      props: {
        isEditing: false,
        videoFile: null,
        slidesFile: null,
        needsOversizeAck: false,
        acknowledgedOversized: false
      }
    })

    const pdfFile = new File(['%PDF-1.4'], 'deck.pdf', { type: 'application/pdf' })
    const slidesInput = wrapper.find('#admin-resource-slides-file')

    Object.defineProperty(slidesInput.element, 'files', {
      value: [pdfFile],
      configurable: true
    })
    await slidesInput.trigger('change')

    expect(wrapper.text()).not.toContain('Presentation slides must be a PDF file')
    expect(wrapper.emitted('update:slides-file')?.[0]).toEqual([pdfFile])
  })
})
