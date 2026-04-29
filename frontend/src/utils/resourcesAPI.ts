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

/**
 * @文件 resources.ts
 * @描述 resources.ts 定义了前端应用中与资源模块相关的 API 层逻辑，用于封装请求处理、资源数据类型以及资源模块的增删改查操作。该文件面向 Django 的 session 认证方案，并在修改型请求中结合支持 CSRF 的请求头机制。
 * @作者 Shiqi Fang
 * @作者 Jiachen Ding
 * @作者 Qin Chen
 * @版本 1.1.0
 *
 * 项目名称: Group Based 5703 Capstone Project
 * 小组编号: CS17-1
 * 负责方向: CS17-1 Frontend Team
 *
 * 组件类型: 前端 API 模块
 * 文件角色: 资源接口与请求封装模块
 * 主要用途: 为前端提供可复用、带类型约束的资源模块接口函数，用于获取资源列表、查看资源详情、创建资源、更新资源和删除资源，同时将页面逻辑与底层 fetch 细节解耦。
 * 作用范围: 被所有需要访问资源库、资源详情、资源创建、资源更新或资源删除流程的页面与组件共享使用。
 *
 * 核心职责:
 * - 定义与资源模块相关的 TypeScript 数据接口
 * - 封装资源接口的统一请求流程
 * - 支持基于 session 的后端认证通信
 * - 为 JSON 请求和 CSRF 保护请求自动补充所需请求头
 * - 提供带类型约束的资源列表查询、单个资源获取、创建、更新与删除函数
 * - 支持资源列表的查询参数过滤、搜索、排序与分页功能

 * 主要依赖:
 * - 前端 CSRF / session 请求头辅助模块
 * - 浏览器 fetch API
 * - 浏览器 URLSearchParams API
 * - Django 资源模块后端接口
 *
 * 修改统计:
 * - 大改次数: 1
 * - 小改次数: 1
 *
 * 最后修改时间: 2026-04-04
 * 修改人: CS17-1 Frontend Team
 */

// 导入csrf.ts中的工具函数，用来构建请求头：一是自动补 Content-Type，二是自动补 Content-Type
import { buildSessionHeaders } from './csrf'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// 接口继承浏览器原生fetch并额外添加自定义字段
// 因为原生 fetch 并不知道你项目里的 CSRF 逻辑，要自己扩展一个参数，告诉系统：这次要不要强制带 CSRF
// RequestInit 是浏览器原生 fetch 支持的参数类型。
interface RequestOptions extends RequestInit {
  includeCSRF?: boolean
}

// 统一封装发请求，接收endpoint接口路径和potions请求配置，最后返回一个promise
// <T>表示TS的泛型，这个函数可以适配不同的返回类型
// endpoint是接口路径
// options是前端代码自己传递给参数对象
// 比如：{
//          includeCSRF: shouldIncludeCSRF,
//          headers: initHeaders，
//          isFormData
//      }
// 获取要传输信息的格式要求，然后统一进行处理，最后用外置函数打包
async function apiRequest<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {

  // 从传入参数中拆解出这些字段
  // 除了写出来的这些，其余的配置全部放进fetchOptions
  const {
    includeCSRF,
    headers: initHeaders,
    method = 'GET',
    body,
    ...fetchOptions
  } = options

  // 请求统一转为大写，比如“POST”“GET”等
  const upperMethod = method.toUpperCase()

  // 判断是不是FormData，也就是上传文件
  const isFormData = body instanceof FormData

  // 判断是否要代CSRF
  // ??是空值合并运算符，意思是左边不是null就用左边，否则右边
  const shouldIncludeCSRF =
    includeCSRF ?? !['GET', 'HEAD', 'OPTIONS'].includes(upperMethod)

  // 构建header
  // 前面先计算好这次请求要不要CSRF，是不是文件，有没有预设header，最后把这些打包成对象给buildSessionHeaders
  // 再将headers放进请求options，最后交给浏览器原生fetch发送请求
  const headers = buildSessionHeaders({
    includeCSRF: shouldIncludeCSRF,
    headers: initHeaders,
    isFormData
  })

  // 实际执行HTTP请求，利用浏览器原生内置的API：fetch，本质上就是前端用来发送HTTP请求的内置工具
  // 调用fetch，就是为了把前端的数据和请求信息发给后端，再把后端的返回结果response接收
  // 比如你在前端里向获取用户信息，获取资源列表，提交表单，删除数据，上传文件，都需要通过HTTP请求发送给后端
  // `${API_BASE_URL}${endpoint}`URL拼接，比如：http://localhost:8000/resources/resource-files/
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...fetchOptions,
    method: upperMethod,
    body,
    headers,
    credentials: 'include'
  })

  // 请求失败
  if (!response.ok) {
    // 比如，HTTP 404: Not Found
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`

    try {
      const errorData = await response.json()
      errorMessage = errorData.error || errorData.detail || errorMessage
    } catch {
      try {
        const text = await response.text()
        if (text) errorMessage = text
      } catch {
      }
    }

    if (response.status === 401) {
      throw new Error('Unauthenticated. Please sign in again.')
    }

    if (response.status === 403) {
      throw new Error('Access denied or CSRF validation failed.')
    }

    throw new Error(errorMessage)
  }

  if (response.status === 204) {
    return undefined as T
  }

  // 如果返回的是JSON就解析
  const contentType = response.headers.get('Content-Type') || ''
  if (contentType.includes('application/json')) {
    return response.json() as Promise<T>
  }

  return undefined as T
}

// 定义resource模块的数据类型，告诉后端返回的资源样式以及创建资源时需要的数据以及类型
// 前端基于后端接口的数据格式， 自定义出来的类型描述
// 例如后端返回一个JSON：
// {
//      "id": 1,
//      "resource_name": "Guide A",
//      "resource_description": "Intro guide"，
//      "upload_datetime": "2026-04-05T10:00:00Z"
// }
// 前端就需要一个interface来描述

// 资源类型
export interface ResourceType {
  id: number
  type_name: string
  type_description: string
}

// 资源本体（后端返回）
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

// 给后端看的精简版资源
export interface CreateResourceData {
  resource_name: string
  resource_description: string
  resource_type_id?: number | null
  role_ids?: number[]
}

// 一组前端的 API service functions，用来和后端的资源接口通信。
// 1.获取资源列表，支持搜索、按角色过滤、按上传者过滤、排序、分页。
// 首先接收一个可选参数params，里面可以携带查询条件。?:表示参数可选，比如：fetchResources({ search: 'AI', page: 1 })
// search：搜索关键词
// role：按角色筛选
// uploader_id：按上传者筛选
// order：排序方式
// page：第几页
// page_size：每页多少条
export async function fetchResources(params?: {
  search?: string
  role?: string
  uploader_id?: number
  order?: 'newest' | 'oldest' | 'name'
  page?: number
  page_size?: number
  // 返回值类型是promise，里面包裹着{ results: Resource[]; count: number }
}): Promise<{ results: Resource[]; count: number }> {
  // 专门用于拼接URL查询参数，比如：search=AI&page=1&page_size=10
  // fetchResources({ search: 'python' })————>search=python
  const queryParams = new URLSearchParams()

  if (params?.search) queryParams.append('search', params.search)
  if (params?.role) queryParams.append('role', params.role)
  if (params?.uploader_id) queryParams.append('uploader_id', params.uploader_id.toString())
  if (params?.order) queryParams.append('order', params.order)
  if (params?.page) queryParams.append('page', params.page.toString())
  if (params?.page_size) queryParams.append('page_size', params.page_size.toString())

  // 构造后端地址，比如：/resources/resource-files/?search=AI&page=1
  const endpoint = `/resources/resource-files/${queryParams.toString() ? `?${queryParams}` : ''}`
  // 调用apiRequest，只有endpoint一个参数传递，options={}所以默认是空，可以不传
  // 因为method默认是‘GET’，所以无需传输options
  return apiRequest<{ results: Resource[]; count: number }>(endpoint)
}

// 2.获取某一个资源详情
// 通过资源的 id 获取单个资源详情。返回的是一个 Resource 对象，而不是数组。
export async function fetchResource(id: number): Promise<Resource> {
  return apiRequest<Resource>(`/resources/resource-files/${id}/`)
}

// 3.新建资源
// 传入的数据类型是 CreateResourceData，返回新创建后的资源对象 Resource。
export async function createResource(data: CreateResourceData): Promise<Resource> {
  return apiRequest<Resource>('/resources/resource-files/', {
    method: 'POST',
    body: JSON.stringify(data)
  })
}

// 4.更新资源
// 更新指定 ID 的资源。PUT一般是整体替换，PATCH是只改传输的字段
export async function updateResource(
  id: number,
  data: Partial<CreateResourceData>
): Promise<Resource> {
  return apiRequest<Resource>(`/resources/resource-files/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data)
  })
}

// 5.删除资源
// 返回 Promise<void> 表示前端不关心返回实体数据，只关心请求是否成功
export async function deleteResource(id: number): Promise<void> {
  return apiRequest<void>(`/resources/resource-files/${id}/`, {
    method: 'DELETE'
  })
}

// 6.获取资源类型列表
export async function fetchResourceTypes(): Promise<ResourceType[]> {
  return [
    { id: 1, type_name: 'document', type_description: 'Document resources' },
    { id: 2, type_name: 'guide', type_description: 'Step-by-step guides' },
    { id: 3, type_name: 'video', type_description: 'Video recordings' },
    { id: 4, type_name: 'template', type_description: 'Templates and boilerplates' }
  ]
}