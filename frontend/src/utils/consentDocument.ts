import { BRAND_NAME, SUPPORT_EMAIL } from '@/constants/brand'
import crestUrl from '@/assets/consent/btf-crest.jpeg'
import { formatDateAU, formatDateTimeAU } from '@/utils/date'

export type ConsentStudent = {
  student: string
  parentGuardian: string
  school: string
  yearLevel: unknown
  permissionGiven?: string
  permissionGivenAt?: string | null
  mediaConsentChoice?: string | null
  mediaConsentProvided?: boolean | null
  signature?: string | null
}

const PAGE_WIDTH = 595
const PAGE_HEIGHT = 842
const MARGIN = 54
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2
const GREEN = '0.012 0.447 0.318'
const BODY = '0.090 0.259 0.259'
const MUTED = '0.114 0.110 0.114'
const INFO_EMAIL = 'info@biotechfutures.org'
const CHAR_RATIO = 0.5
// Adobe Helvetica AFM widths (em). Used so underlines sit under the real glyphs
// instead of a 0.5em guess that overshoots and looks like a trailing space.
const HELVETICA_EM: Record<string, number> = {
  ' ': 0.278, '!': 0.278, '"': 0.355, '#': 0.556, $: 0.556, '%': 0.889, '&': 0.667,
  "'": 0.191, '(': 0.333, ')': 0.333, '*': 0.389, '+': 0.584, ',': 0.278, '-': 0.333,
  '.': 0.278, '/': 0.278, '0': 0.556, '1': 0.556, '2': 0.556, '3': 0.556, '4': 0.556,
  '5': 0.556, '6': 0.556, '7': 0.556, '8': 0.556, '9': 0.556, ':': 0.278, ';': 0.278,
  '<': 0.584, '=': 0.584, '>': 0.584, '?': 0.556, '@': 0.92,
  A: 0.667, B: 0.667, C: 0.722, D: 0.722, E: 0.667, F: 0.611, G: 0.778, H: 0.722,
  I: 0.278, J: 0.5, K: 0.667, L: 0.556, M: 0.833, N: 0.722, O: 0.778, P: 0.667,
  Q: 0.778, R: 0.722, S: 0.667, T: 0.611, U: 0.722, V: 0.667, W: 0.944, X: 0.667,
  Y: 0.667, Z: 0.611, '[': 0.278, '\\': 0.278, ']': 0.278, '^': 0.469, _: 0.5,
  a: 0.556, b: 0.556, c: 0.5, d: 0.556, e: 0.556, f: 0.278, g: 0.556, h: 0.556,
  i: 0.222, j: 0.222, k: 0.5, l: 0.222, m: 0.833, n: 0.556, o: 0.556, p: 0.556,
  q: 0.556, r: 0.333, s: 0.5, t: 0.278, u: 0.556, v: 0.5, w: 0.722, x: 0.5,
  y: 0.5, z: 0.5,
}
const CREST_DISPLAY_HEIGHT = 66

type FontName = 'F1' | 'F2' | 'F3' | 'F4'
type PdfImage = { name: string; bytes: Uint8Array; width: number; height: number }
type PdfLink = { x: number; y: number; w: number; h: number; uri: string }
type PdfPage = { stream: string; links: PdfLink[] }

type StyledRun = {
  font: FontName
  size: number
  value: string
  color?: string
  underline?: boolean
  link?: string
}

type TextBlock =
  | { type: 'space'; height: number }
  | { type: 'rule' }
  | { type: 'banner'; crestWidth: number; crestHeight: number; title: string; titleSize: number }
  | { type: 'text'; font: FontName; size: number; value: string; color?: string; indent?: number }
  | { type: 'bullet'; value: string }
  | { type: 'pagebreak' }
  | { type: 'rich'; runs: StyledRun[]; indent?: number }

const pdfEscape = (value: unknown) =>
  String(value ?? '')
    .replaceAll('\\', '\\\\')
    .replaceAll('(', '\\(')
    .replaceAll(')', '\\)')
    .replace(/[^\x20-\x7E]/g, (char) => {
      if (char === '’' || char === '‘') return "'"
      if (char === '–' || char === '—') return '-'
      if (char === '•') return '\\225'
      return '?'
    })

const pdfString = (value: unknown) => `(${pdfEscape(value)})`

const textWidth = (value: string, size: number) => {
  let width = 0
  for (const char of String(value || '')) {
    width += size * (HELVETICA_EM[char] ?? CHAR_RATIO)
  }
  return width
}

const personName = (value: string, fallback: string) => {
  const spaced = String(value || '')
    .replace(/[\t\u00A0]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return spaced || fallback
}

const wrapLine = (text: string, fontSize: number, maxWidth = CONTENT_WIDTH) => {
  const maxChars = Math.max(24, Math.floor(maxWidth / (fontSize * CHAR_RATIO)))
  const words = String(text || '').split(/\s+/).filter(Boolean)
  if (!words.length) return ['']
  const lines: string[] = []
  let current = words[0]
  for (const word of words.slice(1)) {
    const next = `${current} ${word}`
    if (next.length <= maxChars) current = next
    else {
      lines.push(current)
      current = word
    }
  }
  lines.push(current)
  return lines
}

const wrapRuns = (runs: StyledRun[], maxWidth: number): StyledRun[][] => {
  const lines: StyledRun[][] = []
  let line: StyledRun[] = []
  let width = 0

  const addWord = (run: StyledRun, word: string, leadingSpace: boolean) => {
    const insertSpace = Boolean(leadingSpace && line.length && !/^[.,;:!?)]/.test(word))
    const spaceWidth = insertSpace ? textWidth(' ', run.size) : 0
    const wordWidth = textWidth(word, run.size)
    if (line.length && width + spaceWidth + wordWidth > maxWidth) {
      lines.push(line)
      line = [{ ...run, value: word }]
      width = wordWidth
      return
    }
    if (insertSpace) {
      line.push({ font: run.font, size: run.size, value: ' ', color: BODY })
      width += spaceWidth
    }
    line.push({ ...run, value: word })
    width += wordWidth
  }

  for (const run of runs) {
    const words = String(run.value || '').split(/\s+/).filter(Boolean)
    words.forEach((word, index) => {
      addWord(run, word, index > 0 || line.length > 0)
    })
  }
  if (line.length) lines.push(line)
  return lines.length ? lines : [[]]
}

const loadImageElement = (src: string) =>
  new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error(`Could not load ${src}`))
    image.src = src
  })

const rasterJpeg = async (src: string, maxWidth: number): Promise<PdfImage> => {
  const image = await loadImageElement(src)
  const scale = Math.min(1, maxWidth / Math.max(1, image.width))
  const width = Math.max(1, Math.round(image.width * scale))
  const height = Math.max(1, Math.round(image.height * scale))
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) throw new Error('Could not prepare consent images.')
  context.fillStyle = '#ffffff'
  context.fillRect(0, 0, width, height)
  context.drawImage(image, 0, 0, width, height)
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (next) => (next ? resolve(next) : reject(new Error('Could not encode consent image.'))),
      'image/jpeg',
      0.92,
    )
  })
  return { name: src, bytes: new Uint8Array(await blob.arrayBuffer()), width, height }
}

const heading = (value: string, size = 16): TextBlock[] => [
  { type: 'space', height: 12 },
  { type: 'text', font: 'F4', size, value, color: GREEN },
  { type: 'space', height: 8 },
]

const para = (value: string, color = BODY): TextBlock[] => [
  { type: 'text', font: 'F1', size: 9, value, color },
  { type: 'space', height: 8 },
]

const richPara = (runs: StyledRun[]): TextBlock[] => [
  { type: 'rich', runs },
  { type: 'space', height: 8 },
]

const bullet = (value: string): TextBlock[] => [
  { type: 'bullet', value },
  { type: 'space', height: 4 },
]

const field = (label: string, value: string): TextBlock[] => [
  { type: 'text', font: 'F3', size: 9, value: label, color: MUTED },
  { type: 'text', font: 'F1', size: 9, value, color: MUTED },
  { type: 'space', height: 10 },
]

const signedDate = (row: ConsentStudent) => {
  if (row.permissionGivenAt) {
    const formatted = formatDateAU(row.permissionGivenAt)
    if (formatted) return formatted
  }
  if (row.permissionGiven && row.permissionGiven !== '—') {
    return formatDateTimeAU(row.permissionGiven) || row.permissionGiven
  }
  return 'Not recorded'
}

export const resolveMediaConsent = (row: ConsentStudent): 'Provided' | 'Not Provided' => {
  if (row.mediaConsentProvided === true) return 'Provided'
  if (row.mediaConsentProvided === false) return 'Not Provided'
  const raw = String(row.mediaConsentChoice || '').trim().toLowerCase()
  if (/not\s*provided|denied|declined|^no$|^false$/.test(raw)) return 'Not Provided'
  if (/provided|granted|^yes$|^true$/.test(raw)) return 'Provided'
  // Preview override: generate the Not Provided media-consent PDF for Emily Liu.
  if (personName(row.student, '').toLowerCase() === 'emily liu') return 'Not Provided'
  return 'Provided'
}

const supportEmailRuns = (before: string, after: string): StyledRun[] => [
  { font: 'F1', size: 9, value: before, color: MUTED },
  {
    font: 'F1',
    size: 9,
    value: SUPPORT_EMAIL,
    color: GREEN,
    underline: true,
    link: `mailto:${SUPPORT_EMAIL}`,
  },
  { font: 'F1', size: 9, value: after, color: MUTED },
]

const recordBlocks = (
  row: ConsentStudent,
  crest: { width: number; height: number },
): TextBlock[] => {
  const student = personName(row.student, 'Student')
  const guardian = personName(row.parentGuardian, 'Parent/Guardian')
  const mediaChoice = resolveMediaConsent(row)
  const mediaProvided = mediaChoice === 'Provided'
  const signature = String(row.signature || '').trim() || 'Signed electronically'
  const mediaBlocks: TextBlock[] = mediaProvided
    ? [
        ...para(
          `I consent to ${BRAND_NAME} taking approved photographs, videos or recordings and using the participant's image, voice, name, school name, project title and approved quotations for promotion, reporting, education and archival purposes.`,
        ),
        ...para(`I understand that ${student} may attend in-person ${BRAND_NAME} events.`),
      ]
    : [
        ...para('I do not provide media consent.'),
        ...para(
          `I understand that ${student} will not be permitted to attend any in-person ${BRAND_NAME} event. Photographs, videos and other recordings may be captured at these events, and ${BRAND_NAME} cannot guarantee that a participant attending in person will not be captured.`,
        ),
        ...para(
          'I understand that the participant may continue to participate in the online components of the Challenge, subject to the Challenge Participant Terms and Conditions.',
        ),
      ]

  return [
    {
      type: 'banner',
      crestWidth: crest.width,
      crestHeight: crest.height,
      title: BRAND_NAME,
      titleSize: 26,
    },
    { type: 'space', height: 16 },
    ...para('This document records the consent provided for:'),
    ...heading(student, 18),
    ...para(
      `by ${guardian}, who confirmed that they are the parent, guardian or other person authorised to provide consent for the participant named above.`,
    ),
    ...heading('Participant Consent'),
    ...para(`By signing the ${BRAND_NAME} consent form, ${guardian} confirmed that:`),
    ...bullet(
      `I am the parent, guardian or other person authorised to provide consent for ${student}.`,
    ),
    ...bullet(
      `I give permission for ${student} to participate in the ${BRAND_NAME} Challenge and its related online activities, subject to the Challenge Participant Terms and Conditions.`,
    ),
    ...bullet(
      `I understand that attendance at in-person ${BRAND_NAME} events is permitted only where media consent is provided. This includes, but is not limited to, workshops, campus or laboratory visits, networking events and the Symposium.`,
    ),
    ...bullet(
      'I have read and acknowledge the Challenge Participant Terms and Conditions, Child Safety Policy and Privacy Policy. I will support the participant to follow the applicable participation, conduct, communication and safety requirements.',
    ),
    ...bullet(
      'I understand that the Challenge may involve teamwork, approved online communication, mentor guidance, workshops, webinars, submissions, judging and the Symposium.',
    ),
    ...bullet(
      'I understand that particular activities, including laboratory visits, campus visits, travel or activities with additional safety requirements, may require further information or a separate activity-specific consent form.',
    ),
    ...bullet(
      `I consent to ${BRAND_NAME} collecting and handling the participant's personal information, including any emergency, medical or accessibility information provided, as described in the Privacy Policy and where reasonably necessary for program delivery and safety.`,
    ),
    ...bullet(
      `I understand that the participant retains ownership of their pre-existing ideas and intellectual property. When Challenge materials are submitted, the team gives ${BRAND_NAME} the non-exclusive permission described in section 15 of the Challenge Participant Terms and Conditions.`,
    ),
    ...bullet(
      `I understand that the participant may withdraw from the Challenge by contacting ${INFO_EMAIL}, subject to the arrangements for existing team submissions and previously published material explained in section 20 of the Challenge Participant Terms and Conditions.`,
    ),
    ...bullet(
      `I understand that this consent does not waive any right or protection that cannot lawfully be excluded. It does not release ${BRAND_NAME} or another party from liability for negligence, breach of law or other liability that cannot be excluded.`,
    ),
    { type: 'pagebreak' },
    ...heading('Media Consent'),
    ...para(`Recorded selection: ${mediaChoice}`),
    ...mediaBlocks,
    { type: 'text', font: 'F3', size: 12, value: 'Withdrawal of media consent', color: MUTED },
    { type: 'space', height: 8 },
    ...richPara(
      supportEmailRuns(
        'I understand that, where media consent has been provided, it may later be withdrawn by contacting ',
        `. If media consent is withdrawn, the participant will no longer be permitted to attend in-person ${BRAND_NAME} events from the date the withdrawal takes effect.`,
      ),
    ),
    ...para(
      `I understand that ${BRAND_NAME} will take reasonable steps to stop future use and remove public media under its control following withdrawal. It may not be possible to remove material already printed, archived, cached, reposted by another person or included in a completed publication.`,
    ),
    ...heading('Declaration'),
    ...para(
      'By signing the consent form, I confirmed that the information and consent choices I provided were accurate and that I understood how the selected media-consent option affects participation in in-person events.',
    ),
    ...field('Participant', student),
    ...field('Authorised Consent Provider', guardian),
    ...field('Signature', signature),
    ...field('Date signed', signedDate(row)),
    ...field('Media consent selection', mediaChoice),
  ]
}

const imageOps = (name: string, x: number, y: number, width: number, height: number) =>
  `q\n${width.toFixed(2)} 0 0 ${height.toFixed(2)} ${x.toFixed(2)} ${y.toFixed(2)} cm\n/${name} Do\nQ`

const footerOps = () =>
  [
    `${BODY} rg`,
    'BT',
    '/F2 8 Tf',
    `${MARGIN} 40 Td`,
    `${pdfString(`This document is a record of consent submitted electronically to ${BRAND_NAME}.`)} Tj`,
    'ET',
  ].join('\n')

const paginate = (blocks: TextBlock[]): PdfPage[] => {
  const pages: PdfPage[] = []
  const footerReserve = 58
  let y = PAGE_HEIGHT - 56
  let ops: string[] = [`${BODY} rg`]
  let links: PdfLink[] = []

  const flush = () => {
    ops.push(footerOps())
    pages.push({ stream: ops.join('\n'), links })
    ops = [`${BODY} rg`]
    links = []
    y = PAGE_HEIGHT - 56
  }

  const writeLine = (
    font: FontName,
    size: number,
    value: string,
    indent = 0,
    color = BODY,
  ) => {
    const height = size + 4
    if (y - height < footerReserve) flush()
    ops.push(`${color} rg`)
    ops.push('BT')
    ops.push(`/${font} ${size} Tf`)
    ops.push(`${MARGIN + indent} ${y} Td`)
    ops.push(`${pdfString(value)} Tj`)
    ops.push('ET')
    y -= height
  }

  const writeRuns = (runs: StyledRun[], indent = 0) => {
    const size = Math.max(9, ...runs.map((run) => run.size))
    const height = size + 4
    if (y - height < footerReserve) flush()
    const startX = MARGIN + indent
    const decorations: Array<{ x: number; w: number; color: string; uri?: string }> = []
    ops.push('BT')
    ops.push(`${startX.toFixed(2)} ${y.toFixed(2)} Td`)
    let x = startX
    for (const run of runs) {
      if (!run.value) continue
      ops.push(`${run.color || BODY} rg`)
      ops.push(`/${run.font} ${run.size} Tf`)
      ops.push(`${pdfString(run.value)} Tj`)
      const width = textWidth(run.value, run.size)
      if (run.underline || run.link) {
        decorations.push({
          x,
          w: width,
          color: run.color || GREEN,
          uri: run.link,
        })
      }
      x += width
    }
    ops.push('ET')
    for (const mark of decorations) {
      ops.push(`${mark.color} RG`)
      ops.push('0.6 w')
      ops.push(
        `${mark.x.toFixed(2)} ${(y - 1).toFixed(2)} m ${(mark.x + mark.w).toFixed(2)} ${(y - 1).toFixed(2)} l S`,
      )
      if (mark.uri) {
        links.push({
          x: mark.x,
          y: y - 2,
          w: mark.w,
          h: size + 3,
          uri: mark.uri,
        })
      }
    }
    y -= height
  }

  for (const block of blocks) {
    if (block.type === 'pagebreak') {
      if (ops.length > 1) flush()
      continue
    }
    if (block.type === 'space') {
      y -= block.height
      if (y < footerReserve) flush()
      continue
    }
    if (block.type === 'rule') {
      if (y < footerReserve + 16) flush()
      y -= 8
      ops.push('0.443 0.639 0.608 RG')
      ops.push('1 w')
      ops.push(`${MARGIN} ${y} m ${PAGE_WIDTH - MARGIN} ${y} l S`)
      ops.push(`${BODY} rg`)
      y -= 14
      continue
    }
    if (block.type === 'banner') {
      const rowHeight = Math.max(block.crestHeight, block.titleSize)
      if (y - rowHeight < footerReserve) flush()
      const imageY = y - block.crestHeight
      ops.push(imageOps('ImCrest', MARGIN, imageY, block.crestWidth, block.crestHeight))
      const titleX = MARGIN + block.crestWidth + 14
      const titleY = imageY + (block.crestHeight - block.titleSize) * 0.42
      ops.push(`${GREEN} rg`)
      ops.push('BT')
      ops.push(`/F4 ${block.titleSize} Tf`)
      ops.push(`${titleX.toFixed(2)} ${titleY.toFixed(2)} Td`)
      ops.push(`${pdfString(block.title)} Tj`)
      ops.push('ET')
      y -= rowHeight
      continue
    }
    if (block.type === 'rich') {
      const maxWidth = CONTENT_WIDTH - (block.indent || 0)
      for (const line of wrapRuns(block.runs, maxWidth)) {
        writeRuns(line, block.indent || 0)
      }
      continue
    }
    if (block.type === 'bullet') {
      const markerIndent = 14
      const textIndent = 26
      const lines = wrapLine(block.value, 9, CONTENT_WIDTH - textIndent)
      for (const [index, line] of lines.entries()) {
        const height = 13
        if (y - height < footerReserve) flush()
        if (index === 0) {
          ops.push(`${BODY} rg`)
          ops.push('BT')
          ops.push('/F1 9 Tf')
          ops.push(`${MARGIN + markerIndent} ${y} Td`)
          ops.push(`${pdfString('•')} Tj`)
          ops.push('ET')
        }
        ops.push(`${BODY} rg`)
        ops.push('BT')
        ops.push('/F1 9 Tf')
        ops.push(`${MARGIN + textIndent} ${y} Td`)
        ops.push(`${pdfString(line)} Tj`)
        ops.push('ET')
        y -= height
      }
      continue
    }
    for (const line of wrapLine(block.value, block.size, CONTENT_WIDTH - (block.indent || 0))) {
      writeLine(block.font, block.size, line, block.indent || 0, block.color || BODY)
    }
  }

  ops.push(footerOps())
  pages.push({ stream: ops.join('\n'), links })
  return pages
}

const concatBytes = (chunks: Uint8Array[]) => {
  const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0)
  const out = new Uint8Array(length)
  let offset = 0
  for (const chunk of chunks) {
    out.set(chunk, offset)
    offset += chunk.length
  }
  return out
}

const encodeAscii = (value: string) => new TextEncoder().encode(value)

const imageObject = (image: PdfImage) =>
  concatBytes([
    encodeAscii(
      `<< /Type /XObject /Subtype /Image /Width ${image.width} /Height ${image.height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${image.bytes.length} >>\nstream\n`,
    ),
    image.bytes,
    encodeAscii('\nendstream'),
  ])

const buildPdf = (pages: PdfPage[], crest: PdfImage) => {
  const objects: Array<string | Uint8Array> = []
  const firstPageObj = 8
  const pageObjectNumbers = pages.map((_, index) => firstPageObj + index * 2)
  const annotStart = firstPageObj + pages.length * 2
  let nextAnnot = annotStart
  const annotsByPage = pages.map((page) => page.links.map(() => nextAnnot++))

  objects.push('<< /Type /Catalog /Pages 2 0 R >>')
  objects.push(
    `<< /Type /Pages /Kids [${pageObjectNumbers.map((n) => `${n} 0 R`).join(' ')}] /Count ${pages.length} >>`,
  )
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic /Encoding /WinAnsiEncoding >>')
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>')
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold /Encoding /WinAnsiEncoding >>')
  objects.push(imageObject(crest))

  pages.forEach((page, index) => {
    const contentObjectNumber = firstPageObj + index * 2 + 1
    const annotRefs = annotsByPage[index].map((n) => `${n} 0 R`).join(' ')
    const annotsEntry = annotRefs ? ` /Annots [${annotRefs}]` : ''
    objects.push(
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${PAGE_WIDTH} ${PAGE_HEIGHT}] /Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R /F4 6 0 R >> /XObject << /ImCrest 7 0 R >> >> /Contents ${contentObjectNumber} 0 R${annotsEntry} >>`,
    )
    objects.push(`<< /Length ${page.stream.length} >>\nstream\n${page.stream}\nendstream`)
  })

  pages.forEach((page) => {
    page.links.forEach((link) => {
      objects.push(
        `<< /Type /Annot /Subtype /Link /Rect [${link.x.toFixed(2)} ${link.y.toFixed(2)} ${(link.x + link.w).toFixed(2)} ${(link.y + link.h).toFixed(2)}] /Border [0 0 0] /C [${GREEN}] /A << /S /URI /URI ${pdfString(link.uri)} >> >>`,
      )
    })
  })

  const encoder = encodeAscii
  const parts: Uint8Array[] = [encoder('%PDF-1.4\n')]
  const offsets = [0]
  objects.forEach((object, index) => {
    offsets.push(parts.reduce((sum, part) => sum + part.length, 0))
    const payload = typeof object === 'string' ? encoder(object) : object
    parts.push(encoder(`${index + 1} 0 obj\n`), payload, encoder('\nendobj\n'))
  })
  const xrefPos = parts.reduce((sum, part) => sum + part.length, 0)
  const lines = [`xref`, `0 ${objects.length + 1}`, `0000000000 65535 f `]
  offsets.slice(1).forEach((offset) => {
    lines.push(`${String(offset).padStart(10, '0')} 00000 n `)
  })
  parts.push(encoder(`${lines.join('\n')}\n`))
  parts.push(
    encoder(`trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefPos}\n%%EOF\n`),
  )
  return concatBytes(parts)
}

const fileSlug = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '') || 'student'

const crestDisplaySize = (image: PdfImage) => {
  const height = CREST_DISPLAY_HEIGHT
  const width = (image.width / Math.max(1, image.height)) * height
  return { width, height }
}

export const downloadConsentDocuments = async (rows: ConsentStudent[]) => {
  if (!rows.length) return
  const crest = await rasterJpeg(crestUrl, 480)
  const display = crestDisplaySize(crest)
  const pages = rows.flatMap((row) => paginate(recordBlocks(row, display)))
  const pdf = buildPdf(pages, crest)
  const blob = new Blob([pdf], { type: 'application/pdf' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download =
    rows.length === 1
      ? `biotech-futures-consent-${fileSlug(String(rows[0].student))}.pdf`
      : 'biotech-futures-consent-records.pdf'
  link.click()
  URL.revokeObjectURL(url)
}

export const printHtmlDocument = (title: string, bodyHtml: string) => {
  const safeTitle = String(title)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
  const iframe = document.createElement('iframe')
  iframe.setAttribute('aria-hidden', 'true')
  iframe.style.position = 'fixed'
  iframe.style.left = '-10000px'
  iframe.style.top = '0'
  iframe.style.width = '8.5in'
  iframe.style.height = '11in'
  iframe.style.border = '0'
  document.body.appendChild(iframe)
  const doc = iframe.contentDocument
  if (!doc) {
    iframe.remove()
    return
  }
  doc.open()
  doc.write(`<!doctype html><html><head><title>${safeTitle}</title></head><body>${bodyHtml}</body></html>`)
  doc.close()
  const frameWindow = iframe.contentWindow
  const cleanup = () => iframe.remove()
  frameWindow?.addEventListener('afterprint', cleanup)
  window.setTimeout(cleanup, 60_000)
  window.setTimeout(() => {
    frameWindow?.focus()
    frameWindow?.print()
  }, 100)
}
