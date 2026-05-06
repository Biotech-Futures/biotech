/**
 * @file storage.ts
 * @description storage.ts provides safe localStorage helper utilities for the frontend application. It is responsible for reading, writing, and removing browser localStorage values in a fault-tolerant way, while also centralizing reusable storage keys such as dashboard background preferences.
 * @author Shiqi Fang
 * @author Jiachen Ding
 * @author Qin Chen
 * @version 1.0.0
 *
 * Project: Group Based 5703 Capstone Project
 * Group: CS17-1
 * Team: CS17-1 Frontend Team
 *
 * Component Type: Frontend Utility Module
 * File Role: Safe localStorage helper
 * Purpose: Provide reusable helper functions for safely accessing browser localStorage and managing persistent frontend preference keys in a consistent way.
 * Scope: Shared by dashboard settings, UI preference persistence, theme or background selection logic, and any frontend module that needs lightweight client-side storage.
 *
 * Responsibilities:
 * - Define reusable localStorage keys for frontend preference management
 * - Safely read values from browser localStorage
 * - Safely write values into browser localStorage
 * - Safely remove values from browser localStorage
 * - Prevent runtime errors caused by restricted storage access or unavailable browser APIs
 * - Provide fallback values when storage reads fail or keys do not exist
 *
 * Dependencies:
 * - Browser window.localStorage
 * - JavaScript try-catch error handling
 * - Nullish coalescing operator
 *
 * Revision Summary:
 * - Major revisions: 1
 * - Minor revisions: 0
 *
 * Last Modified: 2026-04-06
 * Modified By: CS17-1 Frontend Team
 */

/**
 * @文件 storage.ts
 * @描述 storage.ts 提供前端项目中安全访问 localStorage 的辅助工具函数。该文件负责以容错方式读取、写入和删除浏览器 localStorage 中的数据，同时集中管理可复用的存储键名，例如 dashboard 背景偏好设置。
 * @作者 Shiqi Fang
 * @作者 Jiachen Ding
 * @作者 Qin Chen
 * @版本 1.0.0
 *
 * 项目名称: Group Based 5703 Capstone Project
 * 小组编号: CS17-1
 * 负责方向: CS17-1 Frontend Team
 *
 * 组件类型: 前端工具模块
 * 文件角色: 安全 localStorage 辅助模块
 * 主要用途: 为前端提供可复用的 localStorage 安全访问函数，并统一管理前端偏好配置相关的持久化键名。
 * 作用范围: 被 dashboard 设置、界面偏好持久化、主题或背景切换逻辑，以及所有需要轻量级客户端本地存储的前端模块共享使用。
 *
 * 核心职责:
 * - 定义可复用的 localStorage 键名，用于前端偏好设置管理
 * - 安全读取浏览器 localStorage 中的数据
 * - 安全写入浏览器 localStorage 中的数据
 * - 安全删除浏览器 localStorage 中的数据
 * - 避免因存储权限限制或浏览器 API 不可用而导致运行时错误
 * - 在读取失败或键不存在时提供默认回退值
 *
 * 主要依赖:
 * - 浏览器 window.localStorage
 * - JavaScript try-catch 异常处理机制
 * - 空值合并运算符
 *
 * 修改统计:
 * - 大改次数: 1
 * - 小改次数: 0
 *
 * 最后修改时间: 2026-04-06
 * 修改人: CS17-1 Frontend Team
 */

// DASHBOARD_BACKGROUND_KEY
// LOGIN_LANGUAGE_KEY
// safeLocalStorageGet(key,fallback)
// safeLocalStorageSet(key,value)
// safeLocalStorageRemove(key)


export const DASHBOARD_BACKGROUND_KEY = 'dashboard-background-key'
export const LOGIN_LANGUAGE_KEY = 'login-language'

// 安全读取 localStorage 的值，读不到或出错时返回 fallback。
// 使用案例：const bg = safeLocalStorageGet(DASHBOARD_BACKGROUND_KEY, 'default')
// 如果用户之前保存过背景，本地存储里有值，就返回那个值；如果没有或出错，就返回 'default'。
export function safeLocalStorageGet(key: string, fallback: string | null = null): string | null {
  try {

    // widow.localStorage表示浏览器提供的本地存储对象，浏览器里的一个小型 key-value 存储区
    // window.localStorage.setItem('theme', 'dark')
    // window.localStorage.getItem('theme')可以判断是否存在，不存在会返回null，存在会返回字符串dark
    // ??是空值合并运算符，如果左边不是null或undefined就返回左边，否则返回右边，||的话还会判断看那个字符串和0之类的，所以??更准确
    return window.localStorage.getItem(key) ?? fallback
  } catch (error) {
    return fallback
  }
}

// 保存用户选择的背景：safeLocalStorageSet(DASHBOARD_BACKGROUND_KEY, 'biotech')
export function safeLocalStorageSet(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value)
  } catch (error) {
  }
}

export function safeLocalStorageRemove(key: string): void {
  try {
    window.localStorage.removeItem(key)
  } catch (error) {
  }
}