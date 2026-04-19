import { getAccessToken } from '@/utils/authTokens'

/**
 * @file csrf.ts
 * @description csrf.ts provides CSRF-related helper utilities for the frontend application. It is designed for Django session-based authentication and is responsible for reading the CSRF token from browser cookies and building request headers for authenticated API calls that require CSRF protection.
 * @author Shiqi Fang
 * @author Jiachen Ding
 * @author Qin Chen
 * @version 1.1.0
 *
 * Project: Group Based 5703 Capstone Project
 * Group: CS17-1
 * Team: CS17-1 Frontend Team
 *
 * Component Type: Frontend Utility Module
 * File Role: CSRF token and session header helper
 * Purpose: Provide reusable helper functions for extracting the CSRF token from cookies and generating safe request headers for session-based backend communication.
 * Scope: Shared by API modules, authentication logic, and any frontend request that needs CSRF-protected communication with the Django backend.
 *
 * Responsibilities:
 * - Read the CSRF token stored in browser cookies
 * - Support Django session-based authentication workflows
 * - Build consistent request headers for fetch requests
 * - Automatically attach Content-Type when appropriate
 * - Optionally attach X-CSRFToken for unsafe HTTP methods such as POST, PATCH, PUT, and DELETE
 * 
 * Dependencies:
 * - Browser document.cookie
 * - Browser Headers API
 * - Django CSRF cookie strategy
 *
 * Revision Summary:
 * - Major revisions: 1
 * - Minor revisions: 1
 *
 * Last Modified: 2026-04-04
 * Modified By: CS17-1 Frontend Team
 */

/**
 * @文件 csrf.ts
 * @描述 csrf.ts 提供前端项目中与 CSRF 相关的辅助工具函数。该文件面向 Django 的 session 认证方案，用于从浏览器 Cookie 中读取 CSRF token，并为需要 CSRF 校验的后端请求构建统一的请求头。
 * @作者 Shiqi Fang
 * @作者 Jiachen Ding
 * @作者 Qin Chen
 * @版本 1.1.0
 *
 * 项目名称: Group Based 5703 Capstone Project
 * 小组编号: CS17-1
 * 负责方向: CS17-1 Frontend Team
 *
 * 组件类型: 前端工具模块
 * 文件角色: CSRF token 与 session 请求头辅助模块
 * 主要用途: 为前端提供可复用的工具函数，用于从 Cookie 中提取 CSRF token，并为基于 session 的后端通信生成安全且统一的请求头。
 * 作用范围: 被 API 模块、认证逻辑以及所有需要通过 Django 后端进行 CSRF 保护通信的前端请求共享使用。
 *
 * 核心职责:
 * - 读取浏览器 Cookie 中存储的 CSRF token
 * - 支持 Django 的 session 认证工作流
 * - 为 fetch 请求统一构建请求头
 * - 在合适情况下自动补充 Content-Type
 * - 在 POST、PATCH、PUT、DELETE 等不安全请求中按需附加 X-CSRFToken
 * 
 * 主要依赖:
 * - 浏览器 document.cookie
 * - 浏览器 Headers API
 * - Django 的 CSRF Cookie 策略
 *
 * 修改统计:
 * - 大改次数: 1
 * - 小改次数: 1
 *
 * 最后修改时间: 2026-04-04
 * 修改人: CS17-1 Frontend Team
 */


// 从浏览器当前页面的 Cookie 字符串里，把 Django 设置的 csrftoken 取出来。 
// session负责证明用户是谁，而CSRFheader负责证明这次操作是你的页面主动发起的，不是别的网站代发的
// 比如：当你登录成功后，Django后端会给浏览器一个session coockie，之后前端请求时只要带上credentials: 'include'，后端就知道是哪个用户
// 但是，假设你访问了一个恶意网站，网站就有可能偷偷构造一个表单和请求，诱导你的浏览器向后端发送一个POST请求
// 而 Django 为了安全，通常会在浏览器里设置一个 cookie，名字叫：csrftoken
// 前端发送 POST / PATCH / DELETE 这种修改型请求时，经常需要把它放到请求头里：X-CSRFToken: <token>
export function getCSRFToken(): string | null {
  const name = 'csrftoken='

  // document.coockie可能:"csrftoken=abc123; sessionid=xyz456; theme=dark"
  // 分割后就会变成字符串数组：
  // [
  //    "csrftoken=abc123",
  //    " sessionid=xyz456",
  //    " theme=dark
  // ]

  // 这里不能用?.因为返回值不能是undefined，这个不是对象类型，一般应该返回空字符串
  const cookies = document.cookie ? document.cookie.split(';') : []

  for (const cookie of cookies) {
    // 去除空格
    const trimmed = cookie.trim()
    // startsWith('csrftoken=') 判断是不是我们要找的 token
    if (trimmed.startsWith(name)) {
      // slice(name.length) 把 csrftoken= 这一段去掉，只保留值
      // decodeURIComponent(...) 把 URL 编码的 token 解码回来
      // 因为空格放在 URL / cookie / query 这类场景里不太方便，常常会被编码成：hello%20world
      // 把“浏览器里为了安全传输而转义过的字符串”，还原回原来的正常字符。
      return decodeURIComponent(trimmed.slice(name.length))
    }
  }

  return null
}

// TS接口，用来约束buildSessionHeaders参数结构
interface BuildHeadersOptions {
  includeCSRF?: boolean
  headers?: HeadersInit
  isFormData?: boolean
}

// 统一生成适用于 Django session 请求的请求头。
// 可以把一次HTTP请求想象成寄快递，由三部分
// 1）地址，比如：POST /resources/resource-files/
// 2）header，及附加说明，告诉后端是JSON还是文件，有没有CSFR token，希望返回什么类型等，比如：
// Content-Type: application/json
// X-CSRFToken: abc123
// 3）body，也就是要提交的数据
// buildSessionHeaders就相当于请求头组装器，
// 如果是普通JSON请求就自动加Content-Type: application/json
// 如果这次请求需要 CSRF，就自动加：X-CSRFToken: <token>
export function buildSessionHeaders(options: BuildHeadersOptions = {}): Headers {
  const {

    // 这是从传入参数里拿出三个字段，并设置默认值：
    // 要不要自动加X-CSRFToken
    // 预设headers
    // 是不是文件上传
    includeCSRF = false,
    headers: initHeaders,
    isFormData = false
  } = options

  // 创建请求头容器对象
  const headers = new Headers(initHeaders)

  // 如果不是文件上传，也没有写Content-Type，就自动加，因为大多数普通接口提交的都是 JSON。
  if (!isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const accessToken = getAccessToken()
  if (accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }

  // 如果需要CSRF就按需添加
  // 一般GET请求不需要CSRF，因为只是获取数据看信息，不动后端，而POST/PATCH/DELETE这种修改服务器状态的就需要
  if (includeCSRF) {
    const csrfToken = getCSRFToken()
    if (csrfToken) {
      headers.set('X-CSRFToken', csrfToken)
    }
  }

  return headers
}
