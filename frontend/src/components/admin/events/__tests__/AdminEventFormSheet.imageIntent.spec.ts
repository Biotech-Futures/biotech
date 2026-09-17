// Tests the "what gets sent for eventImage" logic in AdminEventFormSheet.vue's
// submitForm — the Vue-admin equivalent of adminweb's
// buildEventUpdateWithImageIntent (adminweb/src/lib/event-image-update.ts).
//
// IMPORTANT: unlike adminweb, our port never extracted this into a standalone
// pure function — the intent logic (existingEventImage / imageRemoved state,
// see AdminEventFormSheet.vue) is inlined directly in submitForm. These are
// therefore component-level tests (mount EventsPage, drive the real form,
// inspect what payload the mocked API functions receive) rather than unit
// tests of an isolated function.
//
// The "untouched" and "explicit Remove" cases below originally failed against
// this same spec — the port initially conflated "the field admins type a
// replacement URL into" with "the event's current banner", so every save
// re-sent the existing value (silently undoing a Remove, and in local dev
// actively wiping the banner on totally unrelated edits, since a resent
// relative dev-mode path fails extract_event_image_key's safety check in
// backend/apps/events/image_storage.py — a pre-existing backend gap, out of
// scope for this porting task, flagged separately). Fixed by giving the Vue
// form its own `existingEventImage` (display-only) and
// `imageRemoved` (explicit intent) state, mirroring adminweb's
// existingImageUrl / editImageRemoved split in event.tsx. These tests are now
// regression guards for that fix, not open bug reports.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { defineComponent } from 'vue'
import EventsPage from '@/views/EventsPage.vue'
import { useAuthStore } from '@/stores/auth'
import * as eventsApi from '@/utils/eventsAPI'
import * as adminApi from '@/utils/adminAPI'

vi.mock('vue-router', () => ({
  useRoute: vi.fn(() => ({ params: {}, name: 'events' })),
  useRouter: vi.fn(() => ({ push: vi.fn() }))
}))

// A stand-in for the real EventImageCropDialog. The real one needs
// Image/canvas mocking (covered separately in eventImageCrop.spec.ts) — here
// we only care what AdminEventFormSheet does with the File once the dialog
// hands one back, so a button that emits 'confirm' with a fake File is enough.
const CropDialogStub = defineComponent({
  props: ['modelValue', 'file'],
  emits: ['confirm', 'cancel'],
  // `new File(...)` can't live inline in the template: Vue's compiler runs
  // inline handler expressions through a `with(_ctx)` block and only lets a
  // small fixed whitelist of globals (Math, Date, JSON, ...) through
  // unresolved — `File` isn't on it, so `new File(...)` there silently
  // resolves to `new undefined(...)`. Constructing it in a method sidesteps
  // the compiled-template scope entirely.
  methods: {
    confirmCrop() {
      this.$emit('confirm', new File(['cropped'], 'event-banner-123.webp', { type: 'image/webp' }))
    }
  },
  template: `
    <div v-if="modelValue" class="stub-crop-dialog">
      <button type="button" class="stub-crop-confirm" @click="confirmCrop">confirm crop</button>
    </div>
  `
})

// A local dev backend resolves a stored blob key to a relative path (see
// backend/apps/common/storage.py LocalContainerStorage.url — plain Django
// FileSystemStorage, no host). This is what an admin actually sees/round-trips
// in local dev, unlike the absolute https:// URL used elsewhere in the suite.
const EXISTING_RELATIVE_IMAGE = '/media/event-images/existing123.webp'

const mockEventWithImage: eventsApi.BackendEvent = {
  id: 201,
  event_name: 'Existing Banner Event',
  description: 'Has a banner already.',
  start_datetime: '2026-11-01T09:00:00Z',
  ends_datetime: '2026-11-01T11:00:00Z',
  event_format: 'in_person',
  event_type: 'workshop',
  location: 'Room 1',
  location_link: null,
  event_image: EXISTING_RELATIVE_IMAGE,
  event_timezone: 'Australia/Sydney',
  accepted: false
} as eventsApi.BackendEvent

const adminUser = {
  id: 1,
  email: 'admin@example.com',
  first_name: 'Alex',
  last_name: 'Admin',
  current_role_name: 'admin'
} as never

let wrapper: VueWrapper | null = null

describe('AdminEventFormSheet — image update intent (port of buildEventUpdateWithImageIntent)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())

    // jsdom doesn't implement the Blob URL APIs; AdminEventFormSheet calls
    // these when a crop is confirmed (to preview the file) and unmounted.
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:mock-url'),
      revokeObjectURL: vi.fn()
    })

    vi.spyOn(eventsApi, 'fetchEvents').mockResolvedValue({
      results: [mockEventWithImage],
      count: 1,
      next: null
    } as any)
    vi.spyOn(eventsApi, 'fetchMyEventRsvps').mockResolvedValue({} as any)
    vi.spyOn(adminApi, 'fetchAdminEventMetaRoles').mockResolvedValue([])
    vi.spyOn(adminApi, 'fetchAdminEventTargets').mockResolvedValue({ groupIds: [], roleIds: [] })
    vi.spyOn(adminApi, 'updateAdminEvent').mockResolvedValue({ id: 201, eventName: 'x' } as any)
    vi.spyOn(adminApi, 'createAdminEvent').mockResolvedValue({ id: 999, eventName: 'x' } as any)
    vi.spyOn(adminApi, 'uploadAdminEventImage').mockResolvedValue({ id: 201 } as any)
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
    vi.restoreAllMocks()
  })

  const mountAndOpenEdit = async () => {
    const auth = useAuthStore()
    auth.user = adminUser

    wrapper = mount(EventsPage, {
      global: {
        stubs: { RouterLink: true, EventImageCropDialog: CropDialogStub },
        mocks: {
          $route: { params: {}, name: 'events' },
          $router: { push: vi.fn() }
        }
      },
      attachTo: document.body
    })
    await flushPromises()

    await wrapper.findAll('.event-card-more-btn')[0].trigger('click')
    await flushPromises()
    const editItem = wrapper
      .findAll('.event-card-dropdown-item')
      .find((el) => el.text().includes('Edit'))
    await editItem?.trigger('click')
    await flushPromises()

    const dialog = document.body.querySelector('.admin-sheet') as HTMLElement
    expect(dialog).not.toBeNull()
    return dialog
  }

  const submit = async (dialog: HTMLElement) => {
    const form = dialog.querySelector('form') as HTMLFormElement
    form.dispatchEvent(new Event('submit'))
    await flushPromises()
  }

  it('does not optimistically send the new image on the PUT — it uploads separately only after the crop is confirmed', async () => {
    const dialog = await mountAndOpenEdit()

    const fileInput = dialog.querySelector('.admin-event-file-input') as HTMLInputElement
    const file = new File(['abc'], 'banner.png', { type: 'image/png' })
    Object.defineProperty(fileInput, 'files', { value: [file] })
    fileInput.dispatchEvent(new Event('change'))
    await flushPromises()

    // Crop dialog stub should now be open; confirm it.
    const confirmBtn = document.body.querySelector('.stub-crop-confirm') as HTMLButtonElement
    expect(confirmBtn).not.toBeNull()
    confirmBtn.click()
    await flushPromises()

    await submit(dialog)

    expect(adminApi.updateAdminEvent).toHaveBeenCalledTimes(1)
    const [, payload] = (adminApi.updateAdminEvent as any).mock.calls[0]
    expect(payload).not.toHaveProperty('eventImage')

    // The cropped file is sent via the dedicated upload endpoint, after the
    // PUT resolves — never folded into the PUT payload itself.
    expect(adminApi.uploadAdminEventImage).toHaveBeenCalledWith(
      201,
      expect.objectContaining({ name: 'event-banner-123.webp', type: 'image/webp' })
    )
  })

  // Spec (matching adminweb's buildEventUpdateWithImageIntent): editing an
  // event without touching its banner must not re-send the image field at
  // all, so an untouched banner can never be affected by the save.
  //
  // Previously failed: submitForm sent `payload.eventImage =
  // form.eventImage.trim()` whenever a file wasn't selected, and
  // `form.eventImage` was populated from the existing banner on open — so it
  // re-sent the *current* value on every save that didn't touch the image,
  // even when nothing changed. Fixed by no longer pre-filling
  // `form.eventImage` with the banner at all (see `existingEventImage` in
  // AdminEventFormSheet.vue, and its `initForm`).
  //
  // That resend was not just redundant-but-harmless: in local dev the stored
  // value is a relative path like "/media/event-images/xxx.webp" (Django's
  // plain FileSystemStorage.url(), see backend/apps/common/storage.py). Fed
  // back into extract_event_image_key() (backend/apps/events/image_storage.py),
  // that relative path fails `_is_safe_key` (it contains "/") and normalizes
  // to None — so resending it would have WIPED the banner. extract_event_image_key
  // itself is still fragile against a relative-path resend from any caller;
  // this fix only means the Vue form no longer triggers it. Out of scope for
  // this porting task to fix directly — flagged separately for whoever owns
  // that backend function.
  it('omits eventImage entirely when the banner is left untouched', async () => {
    const dialog = await mountAndOpenEdit()

    const nameInput = dialog.querySelector('#ev-name') as HTMLInputElement
    nameInput.value = 'Renamed, banner untouched'
    nameInput.dispatchEvent(new Event('input'))

    await submit(dialog)

    expect(adminApi.updateAdminEvent).toHaveBeenCalledTimes(1)
    const [, payload] = (adminApi.updateAdminEvent as any).mock.calls[0]
    expect(payload).not.toHaveProperty('eventImage')
  })

  // Spec: clicking Remove and saving must explicitly clear the banner
  // (eventImage: null), not merely stop displaying it locally.
  //
  // Previously failed: clearImage() only set `form.eventImage = ''`, which
  // is indistinguishable from "field is empty because untouched" — the same
  // `if (form.eventImage) { ... }`-shaped guard that caused the bug above
  // meant a removal was never actually sent either, so the banner survived
  // on the server, contradicting what the UI had just shown the admin (an
  // empty preview). Fixed with an explicit `imageRemoved` flag, set only by
  // clearImage() and cleared by picking a replacement — mirrors adminweb's
  // separate `editImageRemoved` boolean (event.tsx), which is exactly what
  // this scenario needs: "removed" as its own signal, not "field is falsy".
  it('sends eventImage: null after an explicit Remove', async () => {
    const dialog = await mountAndOpenEdit()

    const removeBtn = dialog.querySelector('.admin-event-remove-btn') as HTMLButtonElement
    expect(removeBtn).not.toBeNull()
    removeBtn.click()
    await flushPromises()

    await submit(dialog)

    expect(adminApi.updateAdminEvent).toHaveBeenCalledTimes(1)
    const [, payload] = (adminApi.updateAdminEvent as any).mock.calls[0]
    expect(payload).toHaveProperty('eventImage', null)
  })
})
