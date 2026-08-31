export type ConsentStudent = {
  student: string
  parentGuardian: string
  school: string
  yearLevel: unknown
  joinpermResponseId?: string
}

const pdfEscape = (value: unknown) =>
  String(value ?? '')
    .replaceAll('\\', '\\\\')
    .replaceAll('(', '\\(')
    .replaceAll(')', '\\)')
    .replace(/[^\x20-\x7E]/g, (char) => {
      if (char === '’' || char === '‘') return "'"
      if (char === '–' || char === '—') return '-'
      return '?'
    })

const pdfString = (value: unknown) => `(${pdfEscape(value)})`

const contentStream = (row: ConsentStudent) => {
  const lines = [
    ['F1', 20, 'Guardian consent'],
    ['F1', 11, 'This record confirms parent/guardian permission for BIOTech Connect.'],
    ['F1', 12, `Student: ${row.student || 'Student'}`],
    ['F1', 12, `School: ${row.school || '-'}`],
    ['F1', 12, `Year level: ${row.yearLevel || '-'}`],
    ['F1', 12, `Parent/Guardian: ${row.parentGuardian || 'Parent/Guardian'}`],
    ['F1', 12, `Permission reference: ${row.joinpermResponseId || 'Recorded'}`],
    ['F2', 18, row.parentGuardian || 'Parent/Guardian'],
    ['F1', 10, 'Guardian signature'],
  ] as const

  const ops = [
    'BT',
    '/F1 20 Tf',
    '72 720 Td',
    `${pdfString(lines[0][2])} Tj`,
    '/F1 11 Tf',
    '0 -28 Td',
    `${pdfString(lines[1][2])} Tj`,
    '/F1 12 Tf',
    '0 -32 Td',
    `${pdfString(lines[2][2])} Tj`,
    '0 -20 Td',
    `${pdfString(lines[3][2])} Tj`,
    '0 -20 Td',
    `${pdfString(lines[4][2])} Tj`,
    '0 -20 Td',
    `${pdfString(lines[5][2])} Tj`,
    '0 -20 Td',
    `${pdfString(lines[6][2])} Tj`,
    '/F2 18 Tf',
    '0 -48 Td',
    `${pdfString(lines[7][2])} Tj`,
    '/F1 10 Tf',
    '0 -18 Td',
    `${pdfString(lines[8][2])} Tj`,
    'ET',
  ]
  return ops.join('\n')
}

const buildPdf = (streams: string[]) => {
  const objects: string[] = []
  objects.push('<< /Type /Catalog /Pages 2 0 R >>')
  const pageObjectNumbers = streams.map((_, index) => 5 + index * 2)
  objects.push(
    `<< /Type /Pages /Kids [${pageObjectNumbers.map((n) => `${n} 0 R`).join(' ')}] /Count ${streams.length} >>`,
  )
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic >>')
  streams.forEach((stream, index) => {
    const contentObjectNumber = 6 + index * 2
    objects.push(
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents ${contentObjectNumber} 0 R >>`,
    )
    objects.push(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`)
  })

  let body = '%PDF-1.4\n'
  const offsets = [0]
  objects.forEach((object, index) => {
    offsets.push(body.length)
    body += `${index + 1} 0 obj\n${object}\nendobj\n`
  })
  const xrefPos = body.length
  const lines = [`xref`, `0 ${objects.length + 1}`, `0000000000 65535 f `]
  offsets.slice(1).forEach((offset) => {
    lines.push(`${String(offset).padStart(10, '0')} 00000 n `)
  })
  body += `${lines.join('\n')}\n`
  body += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefPos}\n%%EOF\n`
  return body
}

const fileSlug = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '') || 'student'

export const downloadConsentDocuments = (rows: ConsentStudent[]) => {
  if (!rows.length) return
  const pdf = buildPdf(rows.map(contentStream))
  const blob = new Blob([pdf], { type: 'application/pdf' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download =
    rows.length === 1
      ? `guardian-consent-${fileSlug(String(rows[0].student))}.pdf`
      : 'guardian-consent.pdf'
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
