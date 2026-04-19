/**
 * @file auth.ts
 * @description auth.ts defines the central authentication store for the frontend application. It manages the current user state, session-based authentication status, local persistence, and role-related derived state used across the platform.
 * @author Shiqi Fang
 * @author Jiachen Ding
 * @author Qin Chen
 * @version 1.1.0
 *
 * Project: Group Based 5703 Capstone Project
 * Group: CS17-1
 * Team: CS17-1 Frontend Team
 *
 * Component Type: Pinia Store
 * File Role: Global authentication state manager
 * Purpose: Provide a unified frontend authentication store for session-based login state, current user data, and derived permission-related status.
 * Scope: Shared across all pages and components that need access to login state, user profile data, or role-based frontend rendering.
 *
 * Responsibilities:
 * - Store and manage the current authenticated user data for the frontend
 * - Synchronize frontend login state with the backend session through the current-user endpoint
 * - Persist user state in localStorage for refresh recovery
 * - Restore cached login state when the application is reloaded
 * - Provide derived authentication and role-related state for page rendering and permission checks
 *
 * Authentication Strategy:
 * - Session-based authentication
 * - Backend session is identified through cookie transmission
 * - Frontend current-user synchronization is handled through fetchUserData
 *
 * Dependencies:
 * - Pinia
 * - Browser localStorage
 * - Backend session endpoint
 * - CSRF header helper for logout requests
 *
 * Revision Summary:
 * - Major revisions: 1
 * - Minor revisions: 1
 *
 * Last Modified: 2026-04-04
 * Modified By: CS17-1 Frontend Team
 */

/**
 * @文件 auth.ts
 * @描述 auth.ts 定义了前端应用中的统一认证状态仓库，用于管理当前用户信息、基于 session 的登录状态、本地持久化，以及在整个系统中复用的角色派生状态。
 * @作者 Shiqi Fang
 * @作者 Jiachen Ding
 * @作者 Qin Chen
 * @版本 1.1.0
 *
 * 项目名称: Group Based 5703 Capstone Project
 * 小组编号: CS17-1
 * 负责方向: CS17-1 Frontend Team
 *
 * 组件类型: Pinia Store
 * 文件角色: 全局认证状态管理模块
 * 主要用途: 为系统提供统一的前端认证状态管理，维护基于 session 的登录状态、当前用户信息以及角色相关派生结果。
 * 作用范围: 被所有需要访问登录状态、用户资料或基于角色进行页面渲染的页面与组件共享使用。
 *
 * 核心职责:
 * - 存储并管理前端当前已登录用户的信息
 * - 通过当前用户接口将前端登录状态与后端 session 保持同步
 * - 将用户状态持久化到 localStorage 以支持刷新恢复
 * - 在应用重新加载时恢复本地缓存的用户状态
 * - 为页面渲染和权限判断提供认证相关与角色相关的派生状态
 *
 * 认证方式:
 * - 基于 session 的认证方案
 * - 后端 session 通过 cookie 进行身份识别
 * - 前端通过 fetchUserData 完成当前用户状态同步
 *
 * 主要依赖:
 * - Pinia
 * - 浏览器 localStorage
 * - 后端 session 用户信息接口
 * - 用于登出请求的 CSRF 请求头工具
 *
 * 修改统计:
 * - 大改次数: 1
 * - 小改次数: 1
 *
 * 最后修改时间: 2026-04-04
 * 修改人: CS17-1 Frontend Team
 */

// 从 Pinia 中导入 defineStore
// 定义一个全局可复用的状态仓库，也就是整个前端项目里很多页面都能共用的一块数据中心
// 例如：登录用户信息、是否登录、当前角色，这些都适合放在这里统一管理
import { defineStore } from 'pinia'

// 导入构建会话请求头的工具函数，给需要校验身份的请求补上合适的请求头
// 这里主要用于退出登录这种会修改后端状态的请求
// 因为 Django 的 session 认证通常除了 cookie，还可能要求携带 CSRF 相关请求头
import { buildSessionHeaders } from '@/utils/csrf'
import { clearAuthTokens, getRefreshToken, saveAuthTokens } from '@/utils/authTokens'

// 定义后端接口基础地址，优先读取 Vite 环境变量中的配置，如果没有配置，就默认使用本地 Django 开发服务器地址
// 例如：开发环境下可能是 http://localhost:8000，部署环境下可能会在 .env 中配置成正式域名
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// 定义当前登录用户的数据结构，约束 user 对象里应该有哪些字段，方便 TypeScript 做类型检查
// 这里按当前后端 UserSerializer 的返回结构定义
interface User {

  // 用户在后端数据库中的主键 id
  id: number

  email: string
  first_name: string
  last_name: string

  // 用户状态
  status?: boolean

  // 当前生效角色的 id
  current_role_id?: number | null

  // 当前生效角色的名称
  current_role_name?: string | null

  // Django 内置 staff 标记
  is_staff?: boolean

  // Django 内置 superuser 标记
  is_superuser?: boolean

  // 用户所属 track
  // 当前后端 serializer 返回的是外键 id
  // 一般表示项目方向，学科方向等
  track?: number | null

  // 用户所属 state
  // 当前后端 serializer 返回的是外键 id
  state?: number | null

  // 学生用户对应的家长或监护人名字
  pg_firstname?: string | null

  // 学生用户对应的家长或监护人姓氏
  pg_lastname?: string | null

  // 学生当前年级
  // 按后端模型约束，通常是 9、10、11、12 这样的字符串值
  year_lvl?: string | null

  // 学生所在学校名称
  school_name?: string | null

  // 学生是否具有加入项目的许可
  join_perm?: boolean | null

  // 导师背景字段
  // 当前后端 serializer 返回的是关联对象的 id
  ment_bg?: number | null

  // 导师所属机构名称
  ment_inst?: string | null

  // 导师成为导师的原因说明
  ment_reason?: string | null
}

async function parseResponseJson(response: Response): Promise<any> {
  try {
    return await response.json()
  } catch {
    return null
  }
}

function resolveApiError(data: any, fallback: string): string {
  return data?.detail || data?.error || data?.message || fallback
}

// 将后端返回的“原始角色”统一归一化，最终只会返回：admin、teacher、student
function resolveNormalizedRole(user: User | null): 'admin' | 'teacher' | 'student' {
  // 先把当前角色名转成小写字符串，方便后面统一比较
  const rawRole = String(user?.current_role_name || '').toLowerCase()

  // 第一类：管理员角色判断
  // 类比java语法：if (user != null && user.isStaff() == true)
  if (
    user?.is_staff === true ||
    user?.is_superuser === true ||
    ['admin', 'administrator', 'local_admin', 'global_admin', 'local administrator', 'global administrator'].includes(rawRole)
  ) {
    return 'admin'
  }
  // 第二类：教师或导师角色判断
  if (['teacher', 'mentor', 'supervisor'].includes(rawRole)) {
    return 'teacher'
  }
  // 其余情况统一当成 student
  return 'student'
}

// 定义一个名为 auth 的全局认证仓库
// const authStore = useAuthStore()
//
// 常见使用场景：
// 1. 登录成功后，把用户信息写进去
// 2. 页面刷新后，从本地缓存恢复用户信息
// 3. dashboard、header、profile 等页面读取当前用户和角色状态
export const useAuthStore = defineStore('auth', {

  // state 用来定义这份 store 最原始的状态数据
  // 这里是真正存放当前用户数据的地方，本质上都是把数据放进 Pinia 这份全局响应式状态里的 user 字段。
  state: () => ({
    user: null as User | null,
    initialized: false
  }),

  // getters 是“基于原始状态计算出来的派生结果”
  // 它的作用很像 Vue 里的 computed
  //
  // 为什么要用 getters：
  // 1. 避免页面里重复写判断逻辑
  // 2. 页面直接拿现成结果，更清晰
  // 3. 以后规则变化时，只改 store，不用到处改组件
  getters: {
    // 判断当前前端是否“有用户对象”
    isAuthenticated: (s) => s.initialized && !!s.user,

    // 生成用户头像用的姓名缩写
    // 例子：Shiqi Fang -> SF
    initials: (s) => {
      // 没有用户时，返回占位符
      if (!s.user) return '—'

      // 取名字首字母
      // 拼接后转成大写
      // 如果名字首字母都拿不到，就回退为邮箱首字母
      const first = s.user.first_name?.[0] || ''
      const last = s.user.last_name?.[0] || ''
      return (first + last).toUpperCase() || s.user.email[0].toUpperCase()
    },

    // 返回统一归一化后的角色
    normalizedRole: (s) => {
      return resolveNormalizedRole(s.user)
    },

    // 判断当前用户是否应被视为管理员
    isAdmin: (s) => {
      return resolveNormalizedRole(s.user) === 'admin'
    },

    // 判断当前用户是否属于教师或导师这一大类
    isTeacher: (s) => {
      return resolveNormalizedRole(s.user) === 'teacher'
    },

    // 返回更适合页面展示的用户名
    displayName: (s) => {
      const fullName = `${s.user?.first_name || ''} ${s.user?.last_name || ''}`.trim()
      return fullName || s.user?.email || 'User'
    },

    // 返回页面展示用的 track 文本，如果 track 没有值，就退回到 state，如果 state 也没有，就显示 General
    // 注意：
    // 1.当前后端 serializer 对 track 和 state 返回的通常是外键值
    // 2.如果后续后端改成返回名称，这里可以再改为直接显示文本
    displayTrack: (s) => {
      return String(s.user?.track ?? s.user?.state ?? 'General')
    },

    // 返回页面展示用的组织名称
    // mentor 优先显示 institution
    // student 优先显示 school_name
    // 如果两者都没有，则使用默认文案 BIOTech Futures
    organizationLabel: (s) => {
      return s.user?.ment_inst || s.user?.school_name || 'BIOTech Futures'
    },

    // 返回给界面展示的角色标题文本
    // 例如：
    // admin   -> Administrator
    // teacher -> Teacher / Mentor
    // student -> Student
    roleLabel: (s) => {
      const role = resolveNormalizedRole(s.user)

      if (role === 'admin') return 'Administrator'
      if (role === 'teacher') return 'Teacher / Mentor'
      return 'Student'
    }
  },

  // actions 用来写“会做事的逻辑”
  // 比如：
  // 1. 调后端接口
  // 2. 修改状态
  // 3. 处理登录、退出、恢复本地缓存这些动作

  actions: {
    // 从后端接口获取当前已登录用户信息，并同步到前端 store 中
    // 使用场景：
    // 1. 用户验证码登录成功后，调用它同步用户信息
    // 2. 应用初始化时，调用它确认当前 session 是否仍有效
    //
    // 调用例子：
    // const authStore = useAuthStore()
    // const user = await authStore.fetchUserData()
    // if (user) {
    //   router.replace('/dashboard')
    // }
    // 调用接口
    async refreshAccessToken() {
      const refreshToken = getRefreshToken()
      if (!refreshToken) {
        return false
      }

      try {
        const response = await fetch(`${API_BASE_URL}/api/token/refresh/`, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            refresh: refreshToken
          })
        })

        const data = await parseResponseJson(response)
        if (!response.ok || !data?.access) {
          clearAuthTokens()
          return false
        }

        saveAuthTokens({
          access: data.access,
          refresh: data.refresh || refreshToken
        })
        return true
      } catch (error) {
        console.error('Failed to refresh access token:', error)
        clearAuthTokens()
        return false
      }
    },

    async fetchUserData() {
      const requestCurrentUser = () => fetch(`${API_BASE_URL}/api/v1/users/me/`, {
        credentials: 'include',
        headers: buildSessionHeaders()
      })

      try {
        let response = await requestCurrentUser()

        if (response.status === 401 && await this.refreshAccessToken()) {
          response = await requestCurrentUser()
        }

        console.log('GET /api/v1/users/me/ status:', response.status)

        const parsedData = await parseResponseJson(response)
        console.log('GET /api/v1/users/me/ payload:', parsedData)

        if (response.ok) {
          this.user = parsedData
          localStorage.setItem('auth.user', JSON.stringify(parsedData))
          return parsedData
        }

        if (response.status === 401) {
          clearAuthTokens()
        }

        this.user = null
        localStorage.removeItem('auth.user')
      } catch (error) {
        console.error('Failed to fetch user data:', error)
        this.user = null
        localStorage.removeItem('auth.user')
      }

      return null
    },

    async initializeAuth() {
      try {
        this.hydrate()
        await this.fetchUserData()
      } finally {
        this.initialized = true
      }
    },

    // 在别的地方已经拿到了完整 userData
    // 那就不需要立刻再调用 fetchUserData 去请求一次后端
    //
    // 应用例子：
    // 登录接口直接返回了用户信息：
    // authStore.loginWithUser(userData)
    async loginWithPassword(email: string, password: string) {
      clearAuthTokens()

      const response = await fetch(`${API_BASE_URL}/api/token/`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          email,
          password
        })
      })

      const data = await parseResponseJson(response)
      if (!response.ok) {
        throw new Error(resolveApiError(data, 'Email or password is incorrect.'))
      }

      if (!data?.access) {
        throw new Error('Login succeeded but no access token was returned.')
      }

      saveAuthTokens({
        access: data.access,
        refresh: data.refresh
      })

      const user = await this.fetchUserData()
      if (!user) {
        clearAuthTokens()
        throw new Error('Login succeeded, but the current user profile could not be loaded.')
      }

      this.initialized = true
      return user
    },

    loginWithUser(userData: User) {
      // 更新当前响应式用户状态
      this.user = userData
      this.initialized = true

      try {
        // 同步写入本地缓存，保证刷新后还能恢复
        localStorage.setItem('auth.user', JSON.stringify(userData))
      } catch {}
    },

    // 调用后端退出登录接口，并清空前端本地登录状态
    //
    // 这一步做了两件事：
    // 1. 通知后端销毁 session
    // 2. 清掉前端 store 和本地缓存里的 user
    //
    // 为什么 finally 里也要清空：
    // 因为即使后端请求失败，前端也通常希望“退出当前页面态”
    // 否则用户界面会残留旧登录信息，容易造成混乱
    //
    // 调用例子：
    // await authStore.logout()
    // router.replace('/login')
    async logout() {
      try {
        await fetch(`${API_BASE_URL}/services/logout/`, {
          // 使用 POST 是因为退出登录会修改服务器端状态
          method: 'POST',

          // 带上 cookie，后端才知道要销毁哪一个 session
          credentials: 'include',

          // 加上 CSRF 保护请求头
          // 因为这是一个非 GET 的敏感操作
          headers: buildSessionHeaders({
            includeCSRF: true
          })
        })
      } catch (error) {
        // 如果后端退出失败，在控制台记录日志
        console.error('Failed to log out from backend session:', error)
      } finally {
        // 无论后端请求成功还是失败，前端都清空当前用户状态
        this.user = null
        this.initialized = true
        clearAuthTokens()

        try {
          // 删除浏览器本地缓存里的用户数据
          // 防止刷新后又错误地恢复出旧登录态
          localStorage.removeItem('auth.user')
        } catch {}
      }
    },

    // 从 localStorage 中恢复之前缓存的用户信息
    //
    // 这个函数只负责“前端恢复”
    // 它并不会主动去问后端 session 现在还在不在
    //
    // 所以要注意：
    // hydrate 能做的是把上一次保存的用户快照重新放回 store
    // 但它不能单独证明后端 session 还有效
    //
    // 常见使用方式：
    // 应用启动时先 hydrate()
    // 然后再 fetchUserData() 去和后端真实状态做一次同步
    hydrate() {
      try {
        // 从本地存储中读取序列化后的用户字符串
        const rawUser = localStorage.getItem('auth.user')

        if (rawUser) {
          // 把字符串解析回对象，再写回 store
          // 例如：
          // '{"id":1,"first_name":"Shiqi","last_name":"Fang"}'
          // 解析后变成真正的对象
          this.user = JSON.parse(rawUser)
        }
      } catch {}
    }
  }
})
