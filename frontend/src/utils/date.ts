/**
 * @file date.ts
 * @description date.ts provides reusable date formatting helper utilities for the frontend application. It is responsible for converting raw date values into human-readable Australian date formats for different UI scenarios, such as standard date display, long-form date display, and announcement timestamp display.
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
 * File Role: Date formatting helper
 * Purpose: Provide reusable helper functions for formatting dates into consistent Australian-style display strings across the frontend application.
 * Scope: Shared by announcements, dashboards, resource pages, event-related components, and any frontend module that needs consistent date presentation.
 *
 * Responsibilities:
 * - Convert string or Date input values into valid JavaScript Date objects
 * - Safely handle invalid date input
 * - Format dates using Australian locale conventions
 * - Support short date display for common UI usage
 * - Support long date display with optional weekday output
 * - Provide fallback text for announcement dates when the input is invalid
 *
 * Dependencies:
 * - JavaScript Date object
 * - Number.isNaN
 * - Browser Intl and toLocaleDateString support
 * - en-AU locale formatting rules
 *
 * Revision Summary:
 * - Major revisions: 1
 * - Minor revisions: 0
 *
 * Last Modified: 2026-04-05
 * Modified By: CS17-1 Frontend Team
 */

/**
 * @文件 date.ts
 * @描述 date.ts 提供前端项目中可复用的日期格式化辅助工具函数。该文件负责将原始日期值转换为适合界面展示的澳大利亚日期格式，用于标准日期显示、长日期显示以及公告发布时间显示等不同场景。
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
 * 文件角色: 日期格式化辅助模块
 * 主要用途: 为前端提供可复用的日期格式化函数，确保整个项目中的日期展示风格统一，并符合澳大利亚地区的日期表达习惯。
 * 作用范围: 被公告模块、仪表盘页面、资源页面、活动相关组件以及所有需要统一日期展示的前端模块共享使用。
 *
 * 核心职责:
 * - 将字符串或 Date 类型输入统一转换为有效的 JavaScript Date 对象
 * - 安全处理无效日期输入
 * - 按照澳大利亚地区格式规范输出日期字符串
 * - 支持常规短日期展示
 * - 支持可选星期信息的长日期展示
 * - 在公告日期无效时提供默认回退文本
 *
 * 主要依赖:
 * - JavaScript Date 对象
 * - Number.isNaN
 * - 浏览器 Intl 与 toLocaleDateString 能力
 * - en-AU 区域日期格式规则
 *
 * 修改统计:
 * - 大改次数: 1
 * - 小改次数: 0
 *
 * 最后修改时间: 2026-04-05
 * 修改人: CS17-1 Frontend Team
 */

/**
 * Format a date value into a short Australian date string.
 * 将日期值格式化为澳大利亚风格的短日期字符串。
 *
 * This helper accepts either a string or a Date object.
 * It first normalizes the input into a Date instance.
 * If the value cannot be parsed into a valid date, it returns an empty string.
 *
 * 该函数接收 string 或 Date 两种类型的输入。
 * 它会先将输入统一转换为 Date 对象。
 * 如果输入无法解析为有效日期，则返回空字符串。
 *
 * Example output:
 * 5 Apr 2026
 *
 * @param value The source date value as a string or Date object.
 * @param value 输入的原始日期值，可以是字符串或 Date 对象。
 * @returns A short formatted Australian date string, or an empty string if invalid.
 * @returns 返回格式化后的澳大利亚短日期字符串；如果日期无效则返回空字符串。
 */

// export function 函数名(参数: 参数类型): 返回值类型
// formatDateAU('2026-04-05')，formatDateAU('2026-04-05')均合法，formatDateAU(123)不合法
export function formatDateAU(value: string | Date): string {
  // 如果输入本身已经是 Date 对象，则直接使用。
  // formatDateAU(new Date())
  const date = value instanceof Date ? value : new Date(value)

  // 检查生成的 Date 是否有效。
  // 对于合法日期，date.getTime()会返回一个数字
  // 对于无效日期，date.getTime() 会返回 NaN。整个表达式会返回空字符串
  if (Number.isNaN(date.getTime())) return ''

  // 使用澳大利亚英语地区格式化日期。
  // 输出形式为 日 + 月份缩写 + 完整年份。比如：5 Apr 2026
  return date.toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  })
}

/**
 * Format a date value into a long Australian date string.
 *
 * This helper can optionally include the weekday in the output.
 * It is useful for detailed views such as event pages, dashboards, or schedules.

 *
 * Example output without weekday:
 * 5 April 2026
 *
 * Example output with weekday:
 * Saturday, 5 April 2026
 *
 * @param value The source date value as a string or Date object.
 * @param withWeekday Whether to include the weekday in the formatted result.
 * @returns A long formatted Australian date string, or an empty string if invalid.
 */

// value表示日期，withWeekday表示显示星期，默认flase
// formatLongDateAU('2026-04-05', true)表示显示星期
export function formatLongDateAU(value: string | Date, withWeekday = false): string {

  // 将输入值统一转换为 Date 对象。
  const date = value instanceof Date ? value : new Date(value)

  // 如果日期无效，则返回空字符串。
  if (Number.isNaN(date.getTime())) return ''

  // 以澳大利亚地区的长日期格式输出。
  // 如果 withWeekday 为 true，则额外显示星期信息。
  return date.toLocaleDateString('en-AU', {
    weekday: withWeekday ? 'long' : undefined,
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

/**
 * Format a date value for announcement display.
 *
 * This function is similar to the short Australian date formatter,
 * but it provides a friendly fallback message when the date is invalid.
 *
 * Example output:
 * 5 Apr 2026
 *
 * Fallback output:
 * Recently posted
 *
 * @param value The source date value as a string or Date object.
 * @returns A short formatted date string for announcements, or a fallback message if invalid.
 */
export function formatAnnouncementDateAU(value: string | Date): string {
  // 将输入统一转换为 Date 对象。
  const date = value instanceof Date ? value : new Date(value)

  // 如果日期无效，则返回适合界面展示的默认提示文本。
  if (Number.isNaN(date.getTime())) return 'Recently posted'

  // 将有效日期格式化为适合公告卡片或公告列表的澳大利亚短日期样式。
  return date.toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  })
}