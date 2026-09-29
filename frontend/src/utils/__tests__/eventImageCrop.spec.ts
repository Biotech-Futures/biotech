import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { cropEventImage, getMaximumEventCropBounds } from '@/utils/eventImageCrop'

describe('getMaximumEventCropBounds', () => {
  it('keeps an existing 4:1 image as the full crop', () => {
    expect(getMaximumEventCropBounds(1280, 320)).toEqual({
      x: 0,
      y: 0,
      width: 1280,
      height: 320
    })
  })

  it('adds equal white space on both sides of a portrait image', () => {
    expect(getMaximumEventCropBounds(400, 800)).toEqual({
      x: -1400,
      y: 0,
      width: 3200,
      height: 800
    })
  })

  it('adds equal white space above and below an extra-wide image', () => {
    expect(getMaximumEventCropBounds(2000, 200)).toEqual({
      x: 0,
      y: -150,
      width: 2000,
      height: 500
    })
  })

  it('creates the smallest 4:1 workspace for ordinary landscape images', () => {
    expect(getMaximumEventCropBounds(1600, 900)).toEqual({
      x: -1000,
      y: 0,
      width: 3600,
      height: 900
    })
  })

  // Edge cases beyond adminweb's original suite: extreme aspect ratios a real
  // upload could plausibly hit (a square avatar-style crop, or a banner/strip
  // photo far outside normal ranges). The formula is pure arithmetic with no
  // branching on magnitude, so these mainly guard against silent NaN/Infinity
  // from a future refactor rather than a known failure mode today.
  it('pads a 1x1 pixel image out to a 4:1 workspace', () => {
    expect(getMaximumEventCropBounds(1, 1)).toEqual({
      x: -1.5,
      y: 0,
      width: 4,
      height: 1
    })
  })

  it('pads height for an extremely wide image (10000x50)', () => {
    expect(getMaximumEventCropBounds(10000, 50)).toEqual({
      x: 0,
      y: -1225,
      width: 10000,
      height: 2500
    })
  })

  it('pads width for an extremely tall image (50x10000)', () => {
    expect(getMaximumEventCropBounds(50, 10000)).toEqual({
      x: -19975,
      y: 0,
      width: 40000,
      height: 10000
    })
  })
})

describe('cropEventImage', () => {
  let imageWidth = 1280
  let imageHeight = 320
  let canvasWidth = 0
  let canvasHeight = 0
  const fillRect = vi.fn()
  const drawImage = vi.fn()
  const context = {
    fillStyle: '',
    fillRect,
    drawImage,
    imageSmoothingEnabled: false,
    imageSmoothingQuality: 'low'
  }

  class FakeImage {
    naturalWidth = imageWidth
    naturalHeight = imageHeight
    onload: null | (() => void) = null
    onerror: null | (() => void) = null

    set src(_value: string) {
      this.onload?.()
    }
  }

  class FakeFile extends Blob {
    name: string
    lastModified: number

    constructor(parts: BlobPart[], name: string, options: FilePropertyBag = {}) {
      super(parts, options)
      this.name = name
      this.lastModified = options.lastModified ?? Date.now()
    }
  }

  beforeEach(() => {
    imageWidth = 1280
    imageHeight = 320
    canvasWidth = 0
    canvasHeight = 0
    fillRect.mockClear()
    drawImage.mockClear()

    vi.stubGlobal('Image', FakeImage)
    vi.stubGlobal('File', FakeFile)
    vi.stubGlobal('document', {
      createElement: vi.fn(() => ({
        get width() {
          return canvasWidth
        },
        set width(value: number) {
          canvasWidth = value
        },
        get height() {
          return canvasHeight
        },
        set height(value: number) {
          canvasHeight = value
        },
        getContext: vi.fn(() => context),
        toBlob: (callback: BlobCallback, type?: string) =>
          callback(new Blob(['cropped'], { type }))
      }))
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('always exports a 1280 by 320 WEBP file', async () => {
    const result = await cropEventImage('blob:test', { x: 0, y: 0, width: 1, height: 1 })

    expect(canvasWidth).toBe(1280)
    expect(canvasHeight).toBe(320)
    expect(result.type).toBe('image/webp')
    expect(result.name).toMatch(/^event-banner-\d+\.webp$/)
  })

  it('fills the complete output with white before drawing the image', async () => {
    await cropEventImage('blob:test', { x: 0, y: 0, width: 1, height: 1 })

    expect(context.fillStyle).toBe('#ffffff')
    expect(fillRect).toHaveBeenCalledWith(0, 0, 1280, 320)
    expect(fillRect.mock.invocationCallOrder[0]).toBeLessThan(drawImage.mock.invocationCallOrder[0])
  })

  it('centres a portrait image and leaves white space on both sides', async () => {
    imageWidth = 400
    imageHeight = 800

    await cropEventImage('blob:portrait', { x: 0, y: 0, width: 1, height: 1 })

    expect(drawImage).toHaveBeenCalledWith(
      expect.any(FakeImage),
      0,
      0,
      400,
      800,
      560,
      0,
      160,
      320
    )
  })

  it('draws the whole source when it already has the required ratio', async () => {
    await cropEventImage('blob:banner', { x: 0, y: 0, width: 1, height: 1 })

    expect(drawImage).toHaveBeenCalledWith(
      expect.any(FakeImage),
      0,
      0,
      1280,
      320,
      0,
      0,
      1280,
      320
    )
  })

  // This is the single guarantee our backend's dimension check depends on
  // (backend/apps/admin/services/event_image.py rejects anything that isn't
  // exactly 1280x320). Both OUTPUT_WIDTH/OUTPUT_HEIGHT are hardcoded canvas
  // assignments, independent of crop input, so this should hold for any
  // input — pinning it down explicitly guards against a future edit
  // accidentally making the output size input-dependent. A real (non-mocked)
  // browser round trip against the live backend was also verified manually
  // (PUT/POST both 200, naturalWidth 1280 confirmed) during the port's
  // debugging session — this test is the regression guard for that.
  it.each([
    { imageWidth: 1280, imageHeight: 320, crop: { x: 0, y: 0, width: 1, height: 1 } },
    { imageWidth: 400, imageHeight: 800, crop: { x: 0.1, y: 0.2, width: 0.3, height: 0.3 } },
    { imageWidth: 1600, imageHeight: 900, crop: { x: 0, y: 0, width: 0.05, height: 0.05 } },
    { imageWidth: 1, imageHeight: 1, crop: { x: 0, y: 0, width: 1, height: 1 } },
    { imageWidth: 10000, imageHeight: 50, crop: { x: 0.4, y: 0, width: 0.2, height: 1 } },
    { imageWidth: 50, imageHeight: 10000, crop: { x: 0, y: 0.4, width: 1, height: 0.2 } }
  ])(
    'always outputs exactly 1280x320 for a $imageWidth x $imageHeight source with crop $crop',
    async ({ imageWidth: w, imageHeight: h, crop }) => {
      imageWidth = w
      imageHeight = h

      const result = await cropEventImage('blob:test', crop)

      expect(canvasWidth).toBe(1280)
      expect(canvasHeight).toBe(320)
      expect(result.type).toBe('image/webp')
    }
  )

  it('leaves the non-overlapping side white when the crop only partially covers the image', () => {
    // Portrait 400x800 -> maximum workspace is 3200 wide, image occupies
    // x:[1400,1800] of it. Pick a crop straddling the left padding boundary:
    // sourceCrop spans x:[-100,100] in original-image pixels, so only the
    // right half (x:[0,100]) overlaps real image content.
    imageWidth = 400
    imageHeight = 800

    return cropEventImage('blob:portrait', { x: 0.40625, y: 0, width: 0.0625, height: 1 }).then(
      () => {
        expect(fillRect).toHaveBeenCalledWith(0, 0, 1280, 320)
        // Only the overlapping 100px-wide, full-height slice is drawn, scaled
        // into the right half of the canvas (dest x 640..1280) — the left
        // half (dest x 0..640) is left as the white fillRect painted it.
        expect(drawImage).toHaveBeenCalledWith(expect.any(FakeImage), 0, 0, 100, 800, 640, 0, 640, 320)
      }
    )
  })

  it('draws nothing (stays fully white) when the crop falls entirely outside the image', async () => {
    imageWidth = 400
    imageHeight = 800

    // sourceCrop spans x:[-1400,-1080], entirely left of the image (x >= 0).
    await cropEventImage('blob:portrait', { x: 0, y: 0, width: 0.1, height: 1 })

    expect(fillRect).toHaveBeenCalledWith(0, 0, 1280, 320)
    expect(drawImage).not.toHaveBeenCalled()
  })
})
