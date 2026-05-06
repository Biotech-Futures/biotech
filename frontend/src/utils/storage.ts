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


// DASHBOARD_BACKGROUND_KEY
// LOGIN_LANGUAGE_KEY
// safeLocalStorageGet(key,fallback)
// safeLocalStorageSet(key,value)
// safeLocalStorageRemove(key)


export const DASHBOARD_BACKGROUND_KEY = 'dashboard-background-key'
export const LOGIN_LANGUAGE_KEY = 'login-language'

export function safeLocalStorageGet(key: string, fallback: string | null = null): string | null {
  try {

    return window.localStorage.getItem(key) ?? fallback
  } catch (error) {
    return fallback
  }
}

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
