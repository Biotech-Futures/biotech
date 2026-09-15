import { BRAND_NAME } from '@/constants/brand'
import crestUrl from '@/assets/consent/btf-crest.jpeg'
import nixonUrl from '@/assets/consent/signature-william-nixon.jpg'
import aaronsUrl from '@/assets/consent/signature-joshua-aarons.png'
import { formatDateTimeAU } from '@/utils/date'

export type ConsentStudent = {
  student: string
  parentGuardian: string
  school: string
  yearLevel: unknown
  permissionGiven?: string
  permissionGivenAt?: string | null
}

const PAGE_WIDTH = 595
const PAGE_HEIGHT = 842
const MARGIN = 54
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2
const GREEN = '0.012 0.447 0.318'
const BODY = '0.090 0.259 0.259'

type PdfImage = { name: string; bytes: Uint8Array; width: number; height: number }

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

const wrapLine = (text: string, fontSize: number) => {
  const maxChars = Math.max(24, Math.floor(CONTENT_WIDTH / (fontSize * 0.5)))
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
      (next) => (next ? resolve(next) : reject(new Error('Could not encode signature image.'))),
      'image/jpeg',
      0.92,
    )
  })
  return { name: src, bytes: new Uint8Array(await blob.arrayBuffer()), width, height }
}

type TextBlock =
  | { type: 'space'; height: number }
  | { type: 'rule' }
  | { type: 'image'; key: 'crest'; displayWidth: number; displayHeight: number }
  | { type: 'text'; font: 'F1' | 'F2' | 'F3' | 'F4'; size: number; value: string; color?: string; indent?: number }

const recordBlocks = (row: ConsentStudent): TextBlock[] => {
  const student = row.student || 'Student'
  const guardian = row.parentGuardian || 'Parent/Guardian'
  const grantedAt =
    formatDateTimeAU(row.permissionGivenAt) ||
    (row.permissionGiven && row.permissionGiven !== '—' ? row.permissionGiven : '')
  return [
    { type: 'image', key: 'crest', displayWidth: 72, displayHeight: 72 },
    { type: 'space', height: 8 },
    { type: 'text', font: 'F4', size: 22, value: BRAND_NAME, color: GREEN },
    { type: 'space', height: 18 },
    {
      type: 'text',
      font: 'F1',
      size: 9,
      value: 'This document records the consent provided for:',
    },
    { type: 'space', height: 14 },
    { type: 'text', font: 'F4', size: 18, value: 'Name', color: GREEN },
    { type: 'space', height: 6 },
    { type: 'text', font: 'F1', size: 11, value: student },
    { type: 'space', height: 16 },
    { type: 'text', font: 'F4', size: 16, value: 'Participant Consent', color: GREEN },
    { type: 'space', height: 6 },
    { type: 'text', font: 'F1', size: 11, value: guardian },
    { type: 'space', height: 16 },
    { type: 'text', font: 'F4', size: 16, value: 'Media Consent', color: GREEN },
    { type: 'space', height: 6 },
    { type: 'text', font: 'F2', size: 18, value: guardian },
    ...(grantedAt
      ? ([
          { type: 'space', height: 8 },
          { type: 'text', font: 'F1', size: 11, value: grantedAt },
        ] as TextBlock[])
      : []),
  ]
}

const imageOps = (name: string, x: number, y: number, width: number, height: number) =>
  `q\n${width.toFixed(2)} 0 0 ${height.toFixed(2)} ${x.toFixed(2)} ${y.toFixed(2)} cm\n/${name} Do\nQ`

const footerOps = (nixon: PdfImage, aarons: PdfImage) => {
  const sigHeight = 42
  const nixonWidth = (nixon.width / nixon.height) * sigHeight
  const aaronsWidth = (aarons.width / aarons.height) * sigHeight
  const leftX = MARGIN
  const rightX = PAGE_WIDTH - MARGIN - aaronsWidth
  const sigY = 78
  return [
    imageOps('ImNixon', leftX, sigY, nixonWidth, sigHeight),
    imageOps('ImAarons', rightX, sigY, aaronsWidth, sigHeight),
    `${BODY} rg`,
    'BT',
    '/F1 8 Tf',
    `${leftX} 64 Td`,
    `${pdfString('Mr William Nixon')} Tj`,
    '0 -11 Td',
    `${pdfString('Chair 2025')} Tj`,
    'ET',
    'BT',
    '/F1 8 Tf',
    `${rightX} 64 Td`,
    `${pdfString('Mr Joshua Aarons')} Tj`,
    '0 -11 Td',
    `${pdfString('Chair 2025')} Tj`,
    'ET',
  ].join('\n')
}

const paginate = (blocks: TextBlock[], images: { crest: PdfImage; nixon: PdfImage; aarons: PdfImage }) => {
  const pages: string[] = []
  const footerReserve = 130
  let y = PAGE_HEIGHT - 56
  let ops: string[] = [`${BODY} rg`]

  const flush = () => {
    ops.push(footerOps(images.nixon, images.aarons))
    pages.push(ops.join('\n'))
    ops = [`${BODY} rg`]
    y = PAGE_HEIGHT - 56
  }

  const writeLine = (
    font: 'F1' | 'F2' | 'F3' | 'F4',
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

  for (const block of blocks) {
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
    if (block.type === 'image') {
      if (y - block.displayHeight < footerReserve) flush()
      y -= block.displayHeight
      ops.push(imageOps('ImCrest', MARGIN, y, block.displayWidth, block.displayHeight))
      y -= 8
      continue
    }
    for (const line of wrapLine(block.value, block.size)) {
      writeLine(block.font, block.size, line, block.indent || 0, block.color || BODY)
    }
  }

  ops.push(footerOps(images.nixon, images.aarons))
  pages.push(ops.join('\n'))
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

const buildPdf = (streams: string[], images: { crest: PdfImage; nixon: PdfImage; aarons: PdfImage }) => {
  const objects: Array<string | Uint8Array> = []
  objects.push('<< /Type /Catalog /Pages 2 0 R >>')
  const pageObjectNumbers = streams.map((_, index) => 10 + index * 2)
  objects.push(
    `<< /Type /Pages /Kids [${pageObjectNumbers.map((n) => `${n} 0 R`).join(' ')}] /Count ${streams.length} >>`,
  )
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic /Encoding /WinAnsiEncoding >>')
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>')
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold /Encoding /WinAnsiEncoding >>')
  objects.push(imageObject(images.crest))
  objects.push(imageObject(images.nixon))
  objects.push(imageObject(images.aarons))
  streams.forEach((stream, index) => {
    const contentObjectNumber = 11 + index * 2
    objects.push(
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${PAGE_WIDTH} ${PAGE_HEIGHT}] /Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R /F4 6 0 R >> /XObject << /ImCrest 7 0 R /ImNixon 8 0 R /ImAarons 9 0 R >> >> /Contents ${contentObjectNumber} 0 R >>`,
    )
    objects.push(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`)
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

export const downloadConsentDocuments = async (rows: ConsentStudent[]) => {
  if (!rows.length) return
  const [crest, nixon, aarons] = await Promise.all([
    rasterJpeg(crestUrl, 220),
    rasterJpeg(nixonUrl, 420),
    rasterJpeg(aaronsUrl, 520),
  ])
  const images = { crest, nixon, aarons }
  const streams = rows.flatMap((row) => paginate(recordBlocks(row), images))
  const pdf = buildPdf(streams, images)
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
