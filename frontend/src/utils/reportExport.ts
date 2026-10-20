import { apiErrorFromResponse } from '@/utils/apiError'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const REPORT_EXPORT_URL = `${API_BASE_URL}/api/v1/admin/analytics/reports/export/`

export type ReportType = 'participants' | 'permission' | 'login_activity' | 'announcement_delivery'
export type PageReportType = 'overview' | 'users' | 'groups' | 'messages'

export interface ReportExportForm {
  report: ReportType
  groupBy: string
  quickRange: '24h' | '7d' | '14d' | 'custom'
  startDate: string
  endDate: string
  role: string
  status: string
  countryId: string
  stateId: string
  interest: string
  permission: string
  deliveryStatus: string
}

export interface ReportCountry {
  id: number
  countryName: string
}

export interface ReportState {
  id: number
  stateName: string
  countryName: string
}

export function buildReportExportParams(form: ReportExportForm) {
  const params = new URLSearchParams({ report: form.report })
  const add = (name: string, value: string) => {
    const clean = value.trim()
    if (clean && clean !== 'all') params.set(name, clean)
  }

  if (form.report === 'participants') {
    add('group_by', form.groupBy)
    add('role', form.role)
    add('status', form.status)
    add('country_id', form.countryId)
    add('state_id', form.stateId)
    add('interest', form.interest)
    add('start_date', form.startDate)
    add('end_date', form.endDate)
  } else if (form.report === 'permission') {
    add('group_by', form.groupBy)
    add('status', form.status)
    add('country_id', form.countryId)
    add('state_id', form.stateId)
    add('permission', form.permission)
  } else if (form.report === 'login_activity') {
    addActivityRange(params, form)
    add('role', form.role)
    add('status', form.status)
    add('country_id', form.countryId)
    add('state_id', form.stateId)
  } else {
    addActivityRange(params, form)
    add('delivery_status', form.deliveryStatus)
  }

  return params
}

export function validateReportExportForm(form: ReportExportForm) {
  const usesActivityRange =
    form.report === 'login_activity' || form.report === 'announcement_delivery'

  if (usesActivityRange && form.quickRange === 'custom' && (!form.startDate || !form.endDate)) {
    return 'Start and end dates are required for a custom range.'
  }
  if (form.startDate && form.endDate && form.endDate < form.startDate) {
    return 'End date must be on or after start date.'
  }
  return null
}

export async function downloadReportCsv(params: URLSearchParams, report: ReportType | PageReportType) {
  const response = await fetch(`${REPORT_EXPORT_URL}?${params}`, {
    credentials: 'include',
  })
  if (!response.ok)
    throw await apiErrorFromResponse(response, 'The report could not be downloaded.')

  const filename = getReportExportFilename(response.headers.get('Content-Disposition'), report)
  const url = window.URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
  return filename
}

export async function loadReportLocations() {
  const [countries, states] = await Promise.all([
    getData<ReportCountry>('/api/v1/admin/user/countries/?inUse=true'),
    getData<ReportState>('/api/v1/admin/user/states/'),
  ])
  return { countries, states }
}

export function getReportExportFilename(header: string | null, report: ReportType | PageReportType) {
  const candidate = /filename="?([^";]+)"?/i.exec(header ?? '')?.[1]
  return candidate && /^[a-z0-9][a-z0-9._-]*\.csv$/i.test(candidate)
    ? candidate
    : `${report}-report.csv`
}

function addActivityRange(params: URLSearchParams, form: ReportExportForm) {
  if (form.quickRange === 'custom') {
    if (form.startDate) params.set('start_date', form.startDate)
    if (form.endDate) params.set('end_date', form.endDate)
  } else {
    params.set('range', form.quickRange)
  }
}

async function getData<T>(path: string): Promise<T[]> {
  const response = await fetch(`${API_BASE_URL}${path}`, { credentials: 'include' })
  if (!response.ok) throw await apiErrorFromResponse(response)
  const body = (await response.json()) as { data?: T[] }
  return body.data ?? []
}
