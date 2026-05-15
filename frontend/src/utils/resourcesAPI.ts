/**
 * @file resources.ts
 * @description resources.ts defines the resource-related API layer for the frontend application. It encapsulates request handling, resource data typing, and CRUD operations for the resource module. The file is designed to work with Django session-based authentication and integrates CSRF-aware request headers for state-changing operations.
 * @author Shiqi Fang
 * @author Jiachen Ding
 * @author Qin Chen
 * @version 1.1.0
 *
 * Project: Group Based 5703 Capstone Project
 * Group: CS17-1
 * Team: CS17-1 Frontend Team
 *
 * Component Type: Frontend API Module
 * File Role: Resource API and request wrapper module
 * Purpose: Provide reusable typed API functions for fetching, creating, updating, and deleting resource records, while keeping frontend pages separated from low-level fetch details.
 * Scope: Shared by pages and components that need access to the resource library, resource details, resource creation, resource updates, or resource deletion workflows.
 *
 * Responsibilities:
 * - Define TypeScript interfaces for resource-related backend data
 * - Encapsulate the common request flow for resource endpoints
 * - Support session-based authenticated communication with the backend
 * - Automatically attach request headers required for JSON and CSRF-protected operations
 * - Provide typed functions for resource list retrieval, single-resource retrieval, creation, update, and deletion
 * - Support optional query-based filtering, searching, ordering, and pagination for resource lists

 * Dependencies:
 * - Frontend CSRF/session header helper
 * - Browser fetch API
 * - Browser URLSearchParams API
 * - Django resource endpoints
 *
 * Revision Summary:
 * - Major revisions: 1
 * - Minor revisions: 1
 *
 * Last Modified: 2026-04-04
 * Modified By: CS17-1 Frontend Team
 */

import { buildSessionHeaders, ensureCsrfCookie } from './csrf'
import { apiErrorFromResponse } from './apiError'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export function buildResourceUrl(pathOrUrl: string): string {
  if (/^https?:\/\//i.test(pathOrUrl)) {
    return pathOrUrl
  }
  return `${API_BASE_URL}${pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`}`
}

interface RequestOptions extends RequestInit {
  includeCSRF?: boolean
}

async function apiRequest<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { includeCSRF, headers: initHeaders, method = 'GET', body, ...fetchOptions } = options

  const upperMethod = method.toUpperCase()

  const isFormData = body instanceof FormData

  const shouldIncludeCSRF = includeCSRF ?? !['GET', 'HEAD', 'OPTIONS'].includes(upperMethod)

  if (shouldIncludeCSRF) {
    const csrfReady = await ensureCsrfCookie(API_BASE_URL)
    if (!csrfReady) {
      throw new Error('Could not initialize a secure session. Please refresh and try again.')
    }
  }

  const headers = buildSessionHeaders({
    includeCSRF: shouldIncludeCSRF,
    headers: initHeaders,
    isFormData,
  })

  const response = await fetch(buildResourceUrl(endpoint), {
    ...fetchOptions,
    method: upperMethod,
    body,
    headers,
    credentials: 'include',
  })

  if (!response.ok) {
    const apiError = await apiErrorFromResponse(
      response,
      `HTTP ${response.status}: ${response.statusText}`,
    )

    if (apiError.code === 'not_authenticated') {
      apiError.message = 'Unauthenticated. Please sign in again.'
      apiError.body.error = apiError.message
    }

    throw apiError
  }

  if (response.status === 204) {
    return undefined as T
  }

  const contentType = response.headers.get('Content-Type') || ''
  if (contentType.includes('application/json')) {
    return response.json() as Promise<T>
  }

  return undefined as T
}

export interface ResourceType {
  id: number
  type_name: string
  type_description: string
}

export interface Resource {
  id: number
  name: string
  description: string
  type_name?: string | null
  resource_type_detail?: ResourceType | null
  kind: 'file' | 'page' | string
  file_mime_type?: string | null
  file_size?: number | null
  uploaded_at: string
  uploader_name?: string | null
  uploader?: {
    id: number
    first_name: string
    last_name: string
    email: string
  } | null
  file_name?: string | null
  access_url?: string | null
  download_url?: string | null
  storage_status?: 'unavailable' | 'external_url' | 'managed_key' | string
  visible_roles?: Array<{
    id: number
    role_name: string
  }>
  deleted_at?: string | null
}

export interface ResourceAccess {
  resource_id: number
  kind: 'file' | 'page' | string
  storage_status: string
  access_mode: string
  access_url: string | null
  download_url: string | null
  external_url: string | null
  file_name: string | null
  file_mime_type: string | null
  file_size: number | null
  detail: string | null
}

export async function fetchResources(params?: {
  search?: string
  role?: string
  uploader_id?: number
  order?: 'newest' | 'oldest' | 'name'
  page?: number
  page_size?: number
}): Promise<{ results: Resource[]; count: number }> {
  const queryParams = new URLSearchParams()

  if (params?.search) queryParams.append('search', params.search)
  if (params?.role) queryParams.append('role', params.role)
  if (params?.uploader_id) queryParams.append('uploader_id', params.uploader_id.toString())
  if (params?.order) queryParams.append('order', params.order)
  if (params?.page) queryParams.append('page', params.page.toString())
  if (params?.page_size) queryParams.append('page_size', params.page_size.toString())

  const endpoint = `/resources/resource-files/${queryParams.toString() ? `?${queryParams}` : ''}`

  return apiRequest<{ results: Resource[]; count: number }>(endpoint)
}

export async function fetchAllResources(params?: Omit<Parameters<typeof fetchResources>[0], 'page' | 'page_size'>): Promise<Resource[]> {
  const pageSize = 100
  const firstPage = await fetchResources({ ...params, page: 1, page_size: pageSize })
  const resources = [...firstPage.results]
  const totalPages = Math.ceil(firstPage.count / pageSize)

  for (let page = 2; page <= totalPages; page += 1) {
    const nextPage = await fetchResources({ ...params, page, page_size: pageSize })
    resources.push(...nextPage.results)
  }

  return resources
}

export async function fetchResourceAccess(resourceId: number): Promise<ResourceAccess> {
  return apiRequest<ResourceAccess>(`/resources/resource-files/${resourceId}/access/`)
}
