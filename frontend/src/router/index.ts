/**
 * @file index.ts
 * @description index.ts is the central router entry file that creates the Vue Router instance, applies hash-based history mode, registers the predefined route table, and manages global authentication guards for route access control.
 * @author Shiqi Fang
 * @author Jiachen Ding
 * @author Qin Chen
 * @version 1.1.0
 *
 * Project: Group Based 5703 Capstone Project
 * Group: CS17-1
 * Team: Frontend
 *
 * Main Frontend Contributors:
 * - Shiqi Fang
 * - Jiachen Ding
 * - Qin Chen
 *
 * File Type: Router Configuration File
 * Route Scope: Global router entry
 * Purpose: Initialize the frontend routing system and control page access based on authentication status.
 * Structure: Router instance creation with hash history mode, predefined route injection, and global beforeEach route guard logic.
 * Responsibilities:
 * - Create and export the global Vue Router instance
 * - Register the predefined route table imported from routes.ts
 * - Apply global authentication guard logic before every route navigation
 * - Restore local authentication state and fetch user role information when required
 * - Redirect unauthenticated users to the login page and redirect authenticated users away from the login page
 * Dependencies:
 * - Vue Router
 * - Pinia Auth Store
 *
 * Revision Summary:
 * - Major revisions: 1
 * - Minor revisions: 1
 *
 * Last Modified: 2026-04-01
 * Modified By: CS17-1 Frontend Team
 * Modification Notes:
 * - Standardized the file header for the CS17-1 frontend router files
 * - Clarified the file purpose, route guard logic, and responsibility scope
 *
 * Notes:
 * - Keep comments in English.
 * - Keep naming consistent with the project convention.
 * - Update Last Modified, Modified By, and Modification Notes after meaningful changes.
 */

/**
 * @文件 index.ts
 * @描述 index.ts 是前端路由系统的核心入口文件，负责创建 Vue Router 实例、启用 hash 路由模式、注册预定义路由表，并通过全局认证守卫控制页面访问权限。
 * @作者 Shiqi Fang
 * @作者 Jiachen Ding
 * @作者 Qin Chen
 * @版本 1.1.0
 *
 * 项目名称: Group Based 5703 Capstone Project
 * 小组编号: CS17-1
 * 负责方向: Frontend
 *
 * 前端主要成员:
 * - Shiqi Fang
 * - Jiachen Ding
 * - Qin Chen
 *
 * 文件类型: 路由配置文件
 * 路由范围: 全局路由入口
 * 主要用途: 初始化前端路由系统，并根据用户认证状态控制页面访问与跳转。
 * 文件结构: 包含路由实例创建、hash 路由模式配置、路由表注入，以及全局 beforeEach 路由守卫逻辑。
 * 核心职责:
 * - 创建并导出全局 Vue Router 实例
 * - 注册从 routes.ts 导入的预定义路由表
 * - 在每次页面跳转前执行全局认证守卫逻辑
 * - 恢复本地登录状态，并在需要时补充拉取用户角色信息
 * - 将未登录用户重定向到登录页，并将已登录用户从登录页重定向到 dashboard
 * 主要依赖:
 * - Vue Router
 * - Pinia Auth Store
 *
 * 修改统计:
 * - 大改次数: 1
 * - 小改次数: 1
 *
 * 最后修改时间: 2026-04-01
 * 修改人: CS17-1 Frontend Team
 *
 * 备注:
 * - 注释内容应尽量与当前实现保持一致
 * - 命名风格应与项目整体规范保持统一
 * - 当发生结构性或功能性修改时，应同步更新最后修改时间、修改人和修改说明
 */
// 导入Vue-router里的核心函数
// createRouter作用是创建整个Vue路由实例，是整个router的入口
// createWebHashHistory 指定路由使用hash模式：/#/login，# 后面的内容是前端自己处理的，不需要后端服务器去识别每一个页面路径。

import { createRouter, createWebHashHistory } from 'vue-router'

// 注入提前写好的路由表
import routes from './routes'

// 创建router实例
const router = createRouter({
  history: createWebHashHistory(),
  routes: routes
})

// 导入认证仓库，里面保存着用户是否登录，当前用户信息，用户角色等信息
import { useAuthStore } from '../stores/auth'

// 注册全局路由前置守卫
// 每次页面跳转前，先执行这个函数global before guard
// to是将要去的目标路由，from是从哪个路由过来，next是路由放行
router.beforeEach((to, from, next) => {

  // 公开页面白名单，不需要登录也可以访问
  const publicPaths = ['/login', '/auth/callback']
  const auth = useAuthStore()

  // 不是公开页面且没有认证成功，就直接返回登陆界面
  // 情况2：如果用户没有登录，直接访问私有页面，比如：直接手动在地址栏输入/#/dashboard，或者在收藏夹直接点开保存好的地址，或者是第三方发送的链接
  if (!publicPaths.includes(to.path) && !auth.isAuthenticated) {
    next('/login')

  // 情况3：用户已经登录了但是又访问，比如：登录成功后又手动访问 /#/login，登录成功后又手动访问 /#/login
  } else if (to.path === '/login' && auth.isAuthenticated) {
    next('/dashboard')
  } else {
    next()
  }
})

// 导出router实例，供整个Vue使用
export default router
