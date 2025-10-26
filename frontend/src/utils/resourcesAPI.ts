import { apiRequest } from './apiClient'

// ============= Resources API =============

export interface ResourceType {
  id: number
  type_name: string
  type_description: string
}

export interface Resource {
  id: number
  resource_name: string
  resource_description: string
  resource_type_detail?: ResourceType | null
  upload_datetime: string
  uploader: {
    id: number
    first_name: string
    last_name: string
    email: string
  }
  visible_roles: Array<{
    id: number
    role_name: string
  }>
  deleted_flag?: boolean
}

export interface CreateResourceData {
  resource_name: string
  resource_description: string
  resource_type_id?: number | null
  role_ids?: number[]
}

/**
 * Fetch all resources
 * GET /resources/resource-files/
 */
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
  return apiRequest(endpoint)
}

/**
 * Fetch a single resource by ID
 * GET /resources/resource-files/{id}/
 */
export async function fetchResource(id: number): Promise<Resource> {
  return apiRequest(`/resources/resource-files/${id}/`)
}

/**
 * Create a new resource
 * POST /resources/resource-files/
 */
export async function createResource(data: CreateResourceData): Promise<Resource> {
  return apiRequest('/resources/resource-files/', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/**
 * Update a resource
 * PATCH /resources/resource-files/{id}/
 */
export async function updateResource(id: number, data: Partial<CreateResourceData>): Promise<Resource> {
  return apiRequest(`/resources/resource-files/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

/**
 * Delete a resource (soft delete)
 * DELETE /resources/resource-files/{id}/
 */
export async function deleteResource(id: number): Promise<void> {
  return apiRequest(`/resources/resource-files/${id}/`, {
    method: 'DELETE',
  })
}

/**
 * Fetch all resource types
 * This endpoint may need to be created on the backend if not already available
 */
export async function fetchResourceTypes(): Promise<ResourceType[]> {
  // For now, return hardcoded types. Can be replaced with backend endpoint later
  return [
    { id: 1, type_name: 'document', type_description: 'Document resources' },
    { id: 2, type_name: 'guide', type_description: 'Step-by-step guides' },
    { id: 3, type_name: 'video', type_description: 'Video recordings' },
    { id: 4, type_name: 'template', type_description: 'Templates and boilerplates' },
  ]
}
