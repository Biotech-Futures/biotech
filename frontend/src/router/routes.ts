/**
 * @file routes.ts
 * @description routes.ts is the centralized route definition file that declares all frontend page paths, route names, lazy-loaded view components, redirects, dynamic routes, and fallback navigation rules for the application.
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
 * File Type: Route Table Definition File
 * Route Scope: Frontend page mapping
 * Purpose: Provide a unified route configuration table that maps URL paths to corresponding frontend view components.
 * Structure: Route array containing root redirect, public routes, protected routes, dynamic detail routes, and wildcard fallback redirect.
 * Responsibilities:
 * - Define all frontend route paths and route names
 * - Map each route to its corresponding Vue page component
 * - Support lazy loading for page-level components
 * - Handle root path redirection and unmatched path fallback
 * - Provide dynamic route parameters for detail pages such as groups and resources
 *
 * Main Features:
 * - Centralized route definition
 * - Root path redirect to login
 * - Public and protected page routing
 * - Dynamic detail page routing
 * - Lazy-loaded page components
 * - Wildcard fallback redirect
 *
 * Dependencies:
 * - Vue Router Type Definitions
 * - Vue Page Components
 *
 * Revision Summary:
 * - Major revisions: 1
 * - Minor revisions: 1
 *
 * Last Modified: 2026-04-01
 * Modified By: CS17-1 Frontend Team
 * Modification Notes:
 * - Standardized the file header for the CS17-1 frontend router files
 * - Clarified the route table purpose, path mapping logic, and page coverage
 *
 * Notes:
 * - Keep comments in English.
 * - Keep naming consistent with the project convention.
 * - Update Last Modified, Modified By, and Modification Notes after meaningful changes.
 */

/**
 * @文件 routes.ts
 * @描述 routes.ts 是前端路由表定义文件，负责集中声明系统中的全部页面路径、路由名称、懒加载页面组件、重定向规则、动态路由以及兜底跳转规则。
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
 * 文件类型: 路由表定义文件
 * 路由范围: 前端页面映射
 * 主要用途: 提供统一的路由配置表，将 URL 路径映射到对应的前端页面组件。
 * 文件结构: 包含根路径重定向、公开页面路由、受保护页面路由、动态详情页路由以及通配兜底重定向。
 * 核心职责:
 * - 定义系统中的全部前端页面路径与路由名称
 * - 将每条路由映射到对应的 Vue 页面组件
 * - 为页面级组件提供懒加载支持
 * - 处理根路径跳转与未匹配路径兜底跳转
 * - 为 groups、resources 等详情页面提供动态参数路由支持
 *
 * 主要功能:
 * - 集中式路由定义
 * - 根路径跳转到登录页
 * - 公开页面与受保护页面的路径声明
 * - 动态详情页路由配置
 * - 页面组件懒加载
 * - 通配路径兜底跳转
 *
 * 主要依赖:
 * - Vue Router 类型定义
 * - Vue 页面组件
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

import type { RouteRecordRaw } from 'vue-router';

// 定义路由数组，每一项都是一个标准的路由对象
const routes: RouteRecordRaw[] = [

  // 访问路径/时，直接跳转到login
  { path: '/', redirect: '/login' },

  // 登录和认证回调页
  { path: '/login', name: 'login', component: () => import('@/views/LoginPage.vue') },
  { path: '/auth/callback', name: 'auth-callback', component: () => import('@/views/AuthCallbackPage.vue') },
  
  // 业务页面
  { path: '/dashboard', name: 'dashboard', component: () => import('@/views/DashboardPage.vue') },

  // 要更改！！！
  { path: '/groups', name: 'groups', component: () => import('@/views/GroupDetailPage.vue') },
  { path: '/groups/:id', name: 'group-detail', component: () => import('@/views/GroupDetailPage.vue') },
  { path: '/resources', name: 'resources', component: () => import('@/views/ResourcesPage.vue') },
  { path: '/resources/:id', name: 'resource-detail', component: () => import('@/views/ResourcesPage.vue') },
  { path: '/events', name: 'events', component: () => import('@/views/EventsPage.vue') },
  { path: '/profile', name: 'profile', component: () => import('@/views/ProfilePage.vue') },
  { path: '/admin', name: 'admin', component: () => import('@/views/AdminPage.vue') },
  { path: '/announcements', name: 'announcements', component: () => import('@/views/AnnouncementsPage.vue') },
 
  // 如果用户访问了任何没定义的路径，就统一跳到 /login。
  { path: '/:pathMatch(.*)*', redirect: '/login' }
];

export default routes;