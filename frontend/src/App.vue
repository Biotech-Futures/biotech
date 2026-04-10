<template>
  <!--
    模块 1：应用根容器
    Module 1: Application root container

    功能说明：
    1. 作为整个页面组件的最外层包裹节点
    2. 区分“登录页”和“非登录页”的整体布局
    3. 承载顶部 Header、侧边栏 Sidebar、主内容区 Main Content、账号菜单面板等全部内容

    Function:
    1. Serves as the outermost wrapper of the whole page component
    2. Separates the layout between login pages and non-login pages
    3. Hosts the Header, Sidebar, Main Content, and account menu panel
  -->
  <div class="app-container">

    <!--
      模块 2：顶部导航栏 Header
      Module 2: Top header navigation

      关键条件：
      v-if="!isLoginPage"

      功能说明：
      1. 登录页不显示顶部导航栏
      2. 顶部栏包括品牌 Logo、全局搜索、用户头像入口
      3. 是平台主要的全局操作入口

      Key condition:
      v-if="!isLoginPage"

      Function:
      1. Hidden on the login page
      2. Contains brand logo, global search, and user avatar entry
      3. Acts as the main global action area of the platform
    -->
    <header class="header" v-if="!isLoginPage">
      <div class="header-content">

        <!--
          模块 2.1：Header 左侧 Logo 区
          Module 2.1: Header left logo area

          功能说明：
          1. 展示平台品牌图标和名称
          2. 点击后跳转到 /dashboard
          3. 帮助用户快速回到系统首页

          Function:
          1. Displays the platform logo and brand name
          2. Navigates to /dashboard when clicked
          3. Helps users quickly return to the main dashboard
        -->
        <div class="header-left">
          <div class="logo-section">
            <RouterLink to="/dashboard" class="logo">

              <!--
                logo
                中文：导入的品牌图片资源
                English: imported brand image asset
              -->
              <div class="logo-icon">
                <img :src="logo" alt="BIOTech Futures" />
              </div>

              <div class="logo-copy">
                <span class="logo-text">BIOTech Futures Hub</span>
                <span class="logo-subtext">Program workspace</span>
              </div>
            </RouterLink>
          </div>
        </div>

        <!--
          模块 2.2：Header 右侧工具区
          Module 2.2: Header right tools area

          功能说明：
          1. 放置全局搜索表单
          2. 放置用户头像按钮
          3. 作为用户与系统交互的高频入口

          Function:
          1. Contains the global search form
          2. Contains the user avatar button
          3. Works as a high-frequency interaction zone
        -->
        <div class="header-right">

          <!--
            模块 2.2.1：全局搜索表单
            Module 2.2.1: Global search form

            事件：
            @submit.prevent="submitSearch"

            功能说明：
            1. 支持输入关键词进行全局搜索
            2. 支持切换搜索范围 scope
            3. 提交后跳转到 /resources，并附带 query 参数

            Event:
            @submit.prevent="submitSearch"

            Function:
            1. Supports keyword-based global search
            2. Supports switching search scope
            3. Redirects to /resources with query parameters after submission
          -->
          <form class="search-shell" @submit.prevent="submitSearch">

            <!--
              子模块：搜索范围选择器
              Submodule: Search scope selector

              v-model="searchScope"

              变量说明：
              searchScope
              中文：当前搜索范围
              English: current search scope

              可选值：
              - all
              - groups
              - events
              - announcements
              - resources

              Example:
              searchScope = 'groups'
              表示只搜索小组相关内容
              Means searching only within group-related content
            -->
            <div class="search-scope-wrap">
              <select v-model="searchScope" class="search-scope" aria-label="Search scope">
                <option value="all">All</option>
                <option value="groups">Groups</option>
                <option value="events">Events</option>
                <option value="announcements">Announcements</option>
                <option value="resources">Resources</option>
              </select>
            </div>

            <!--
              子模块：搜索输入框容器
              Submodule: Search input wrapper

              动态类：
              :class="{ 'is-focused': isSearchFocused, 'has-value': !!searchQuery }"

              变量说明：
              - isSearchFocused
                中文：输入框当前是否处于聚焦状态
                English: whether the search input is currently focused

              - searchQuery
                中文：用户输入的搜索关键词
                English: user-entered search keyword

              Function:
              1. 根据聚焦和输入状态切换样式
              2. 包含搜索图标、输入框、清空按钮
            -->
            <div
              class="search-input-wrap"
              :class="{ 'is-focused': isSearchFocused, 'has-value': !!searchQuery }"
            >
              <i class="fas fa-search search-icon"></i>

              <!--
                searchInputRef
                中文：输入框 DOM 引用，用于手动 focus
                English: input DOM reference, used for programmatic focus

                @focus / @blur
                中文：同步 isSearchFocused 状态
                English: syncs the isSearchFocused state
              -->
              <input
                ref="searchInputRef"
                v-model="searchQuery"
                type="text"
                class="search-bar"
                placeholder="Search program content"
                @focus="isSearchFocused = true"
                @blur="isSearchFocused = false"
              />

              <!--
                清空按钮
                Clear button

                显示条件：
                v-if="searchQuery"

                功能说明：
                1. 仅在有输入内容时显示
                2. 点击后调用 clearSearch 清空关键词并重新聚焦输入框

                Display condition:
                v-if="searchQuery"

                Function:
                1. Only shown when input has content
                2. Calls clearSearch to clear the query and refocus the input
              -->
              <button
                v-if="searchQuery"
                type="button"
                class="search-clear-button"
                aria-label="Clear search"
                @click="clearSearch"
              >
                <i class="fas fa-times"></i>
              </button>
            </div>

            <!--
              搜索提交按钮
              Search submit button

              :disabled="isSearching || !searchQuery.trim()"

              变量说明：
              - isSearching
                中文：搜索请求是否正在进行中
                English: whether a search request is currently in progress

              禁用逻辑：
              1. 正在搜索时禁用
              2. 输入为空白时禁用

              Disabled when:
              1. A search is already in progress
              2. The query is empty after trimming
            -->
            <button class="search-submit-button" type="submit" :disabled="isSearching || !searchQuery.trim()">
              <i class="fas" :class="isSearching ? 'fa-spinner fa-spin' : 'fa-arrow-right'"></i>
            </button>
          </form>

          <!--
            模块 2.2.2：用户头像菜单入口
            Module 2.2.2: User avatar menu entry

            功能说明：
            1. 显示当前用户缩写 initials
            2. 点击后展开或关闭账号菜单
            3. 可显示红点提醒 badge

            Function:
            1. Displays current user initials
            2. Toggles the account menu on click
            3. Can show a notification badge
          -->
          <div class="header-actions">
            <div class="user-menu">
              <button
                class="user-avatar"
                ref="avatarRef"
                @click="toggleUserMenu"
                type="button"
                aria-label="Open account menu"
              >
                <!--
                  auth.initials
                  中文：当前用户名称缩写
                  English: initials of the current user

                  Example:
                  "Shiqi Fang" -> "SF"
                -->
                <span class="user-avatar-text">{{ auth.initials }}</span>

                <!--
                  hasUserMenuBadge
                  中文：是否显示头像右上角提醒红点
                  English: whether to show the notification badge on the avatar

                  常见用途：
                  1. 提示用户有未查看账户入口
                  2. 首次点击后可关闭提醒

                  Common use:
                  1. Indicates unseen account-related attention
                  2. Can be hidden after the first open
                -->
                <span v-if="hasUserMenuBadge" class="notification-badge"></span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!--
      模块 3：主布局区
      Module 3: Main layout area

      显示条件：
      v-if="!isLoginPage"

      功能说明：
      1. 非登录页使用侧边栏 + 主内容区的双栏布局
      2. 左边是导航和迷你日历
      3. 右边是页面主路由内容

      Display condition:
      v-if="!isLoginPage"

      Function:
      1. Uses a sidebar + main content two-column layout on non-login pages
      2. Left side contains navigation and mini calendar
      3. Right side contains the routed page content
    -->
    <div class="main-layout" v-if="!isLoginPage">

      <!--
        模块 3.1：侧边栏 Sidebar
        Module 3.1: Sidebar

        功能说明：
        1. 提供主导航菜单
        2. 包含迷你日历模块
        3. 在 Admin 角色下额外显示后台入口

        Function:
        1. Provides the main navigation menu
        2. Contains the mini calendar module
        3. Shows the admin entry for admin users
      -->
      <aside class="sidebar">

        <!--
          子模块：导航菜单
          Submodule: Navigation menu

          route.path 的作用：
          中文：当前路由路径，用于判断哪个菜单项应高亮
          English: current route path, used to determine which menu item is active
        -->
        <nav class="sidebar-nav">
          <ul class="sidebar-list">

            <li class="sidebar-item">
              <RouterLink
                to="/dashboard"
                class="sidebar-link"
                :class="{ active: route.path === '/dashboard' }"
              >
                <i class="fas fa-home sidebar-icon"></i>
                <span>Home</span>
              </RouterLink>
            </li>

            <li class="sidebar-item">
              <RouterLink
                to="/groups"
                class="sidebar-link"
                :class="{ active: route.path.includes('/groups') }"
              >
                <i class="fas fa-users sidebar-icon"></i>
                <span>Groups</span>
              </RouterLink>
            </li>

            <li class="sidebar-item">
              <RouterLink
                to="/events"
                class="sidebar-link"
                :class="{ active: route.path === '/events' }"
              >
                <i class="fas fa-calendar sidebar-icon"></i>
                <span>Events</span>
              </RouterLink>
            </li>

            <li class="sidebar-item">
              <RouterLink
                to="/announcements"
                class="sidebar-link"
                :class="{ active: route.path === '/announcements' }"
              >
                <i class="fas fa-bullhorn sidebar-icon"></i>
                <span>Announcements</span>
              </RouterLink>
            </li>

            <li class="sidebar-item">
              <RouterLink
                to="/resources"
                class="sidebar-link"
                :class="{ active: route.path === '/resources' }"
              >
                <i class="fas fa-book sidebar-icon"></i>
                <span>Resources</span>
              </RouterLink>
            </li>

            <!--
              auth.isAdmin
              中文：是否为管理员
              English: whether the current user is an admin

              用途：
              仅管理员显示后台入口
              Used to show the admin panel entry only for admin users
            -->
            <li class="sidebar-item" v-if="auth.isAdmin">
              <RouterLink
                to="/admin"
                class="sidebar-link"
                :class="{ active: route.path === '/admin' }"
              >
                <i class="fas fa-cog sidebar-icon"></i>
                <span>Admin Panel</span>
              </RouterLink>
            </li>
          </ul>
        </nav>

        <!--
          模块 3.2：迷你日历容器
          Module 3.2: Mini calendar container

          功能说明：
          1. 展示当前月份的小型日历
          2. 支持切换上个月、当前月、下个月
          3. 支持查看某天的事件或节假日详情
          4. Admin 用户可以进入编辑模式管理事件

          Function:
          1. Displays a compact monthly calendar
          2. Supports previous/current/next month navigation
          3. Supports opening event or holiday details for a date
          4. Admin users can enter edit mode to manage events
        -->
        <div class="mini-calendar-shell">
          <div class="mini-calendar">

            <!--
              子模块：日历顶部导航
              Submodule: Calendar top navigation

              关键变量：
              - canGoPrevMonth
                中文：是否允许切换到上个月
                English: whether the previous month is available

              - canGoNextMonth
                中文：是否允许切换到下个月
                English: whether the next month is available

              - calendarTitle
                中文：当前日历标题，如 "March 2026"
                English: formatted title of the current calendar month

              - todayLabel
                中文：今天的标签文本，如 "Tue, 31 Mar"
                English: formatted label for today
            -->
            <div class="mini-calendar-topbar">
              <button
                class="calendar-nav-button"
                :disabled="!canGoPrevMonth"
                @click="goPrevMonth"
                aria-label="Previous month"
              >
                <i class="fas fa-chevron-left"></i>
              </button>

              <div class="mini-calendar-heading">
                <div class="mini-calendar-title">{{ calendarTitle }}</div>
                <div class="mini-calendar-subtitle">{{ todayLabel }}</div>
              </div>

              <button
                class="calendar-nav-button"
                :disabled="!canGoNextMonth"
                @click="goNextMonth"
                aria-label="Next month"
              >
                <i class="fas fa-chevron-right"></i>
              </button>
            </div>

            <!--
              子模块：日历工具栏
              Submodule: Calendar toolbar

              isCurrentMonth
              中文：当前视图月份是否就是今天所在月份
              English: whether the displayed month is the actual current month

              goToCurrentMonth
              中文：回到当前月
              English: jumps back to the current month
            -->
            <div class="mini-calendar-toolbar">
              <button
                class="calendar-current-button"
                :disabled="isCurrentMonth"
                @click="goToCurrentMonth"
              >
                Current
              </button>
              <span class="range-hint">Prev • Current • Next</span>
            </div>

            <!--
              weekdayLabels
              中文：星期标题数组
              English: weekday label array

              Example:
              ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            -->
            <div class="mini-calendar-weekdays">
              <span v-for="label in weekdayLabels" :key="label">{{ label }}</span>
            </div>

            <!--
              子模块：日历日期网格
              Submodule: Calendar day grid

              calendarDays
              中文：日历每一个格子的计算结果数组
              English: computed array representing every visible calendar cell

              每个 cell 重要字段：
              Important cell fields:
              - key
                唯一键 / unique key
              - day
                日期数字，空白格为 null / day number, null for empty cells
              - dateKey
                日期键，例如 "2026-03-31" / date key such as "2026-03-31"
              - isToday
                是否为今天 / whether this is today
              - hasHoliday
                是否包含节假日 / whether it contains a holiday
              - hasEvent
                是否包含事件 / whether it contains an event
              - clickable
                是否可点击打开详情 / whether the cell can open details
            -->
            <div class="mini-calendar-grid">
              <button
                v-for="cell in calendarDays"
                :key="cell.key"
                class="mini-calendar-cell"
                :class="{
                  'is-empty': !cell.day,
                  'is-today': cell.isToday,
                  'is-holiday': cell.hasHoliday,
                  'is-event': cell.hasEvent,
                  'is-clickable': cell.clickable
                }"
                :disabled="!cell.day"
                @click="openDayDetails(cell.dateKey)"
              >
                {{ cell.day ?? '' }}
              </button>
            </div>

            <!--
              子模块：日历图例
              Submodule: Calendar legend

              功能说明：
              解释 today / holiday / event 的颜色或描边含义

              Function:
              Explains the visual meaning of today / holiday / event
            -->
            <div class="mini-calendar-legend">
              <span class="legend-item">
                <span class="legend-dot legend-today"></span>
                Today
              </span>
              <span class="legend-item">
                <span class="legend-dot legend-holiday"></span>
                Holiday
              </span>
              <span class="legend-item">
                <span class="legend-dot legend-event"></span>
                Event
              </span>
            </div>

            <!--
              子模块：管理员事件编辑入口
              Submodule: Admin event editing entry

              显示条件：
              v-if="auth.isAdmin"

              openEditor
              中文：打开日历编辑模式
              English: opens the calendar editor mode
            -->
            <div class="mini-calendar-footer" v-if="auth.isAdmin">
              <button class="calendar-edit-button" @click="openEditor">
                <i class="fas fa-pen"></i>
                <span>Edit Events</span>
              </button>
            </div>
          </div>

          <!--
            模块 3.3：日历覆盖层 Overlay
            Module 3.3: Calendar overlay

            showCalendarOverlay
            中文：是否显示覆盖层
            English: whether the overlay is visible

            overlayMode
            中文：覆盖层模式，可为 details 或 edit
            English: overlay mode, either details or edit

            作用：
            1. details 模式：查看某一天的节假日/事件详情
            2. edit 模式：管理员管理事件

            Function:
            1. details mode: show holiday/event details for a date
            2. edit mode: allow admins to manage events
          -->
          <transition name="calendar-fade">
            <div v-if="showCalendarOverlay" class="calendar-overlay">

              <!--
                覆盖层头部
                Overlay header

                selectedOverlayTitle
                中文：详情模式下显示当前选中日期的格式化标题
                English: formatted title of the selected date in details mode
              -->
              <div class="calendar-overlay-header">
                <div class="calendar-overlay-title">
                  {{ overlayMode === 'details' ? selectedOverlayTitle : 'Manage events' }}
                </div>
                <button class="calendar-close-button" @click="closeCalendarOverlay" aria-label="Close">
                  <i class="fas fa-times"></i>
                </button>
              </div>

              <!--
                详情模式
                Details mode

                selectedItems
                中文：当前选中日期下的所有项目（节假日 + 事件）
                English: all items under the selected date (holidays + events)
              -->
              <div v-if="overlayMode === 'details'" class="calendar-overlay-body">
                <template v-if="selectedItems.length">
                  <div
                    v-for="item in selectedItems"
                    :key="item.id"
                    class="overlay-card"
                    :class="item.type === 'holiday' ? 'holiday-card' : 'event-card'"
                  >
                    <div class="overlay-card-type">
                      {{ item.type === 'holiday' ? 'Holiday' : 'Event' }}
                    </div>
                    <div class="overlay-card-title">{{ item.title }}</div>
                  </div>
                </template>

                <div v-else class="overlay-empty-state">
                  No special information for this date.
                </div>
              </div>

              <!--
                编辑模式
                Edit mode

                editForm
                中文：当前编辑中的事件表单对象
                English: current editable event form object

                重要字段：
                - editForm.id
                  0 表示新建，非 0 表示编辑已有事件
                  0 means creating a new event, non-zero means editing an existing one
                - editForm.date
                  事件日期 / event date
                - editForm.title
                  事件标题 / event title
              -->
              <div v-else class="calendar-overlay-body editor-body">
                <div class="editor-readonly-note">
                  Public holidays are read-only. Only events can be edited here.
                </div>

                <!-- 事件表单 Event form -->
                <div class="editor-form">
                  <div class="form-row">
                    <label class="form-label">Date</label>
                    <input
                      v-model="editForm.date"
                      type="date"
                      class="form-input"
                      :min="minAllowedDate"
                      :max="maxAllowedDate"
                    />
                  </div>

                  <div class="form-row">
                    <label class="form-label">Event title</label>
                    <input
                      v-model="editForm.title"
                      type="text"
                      class="form-input"
                      placeholder="Enter event title and time"
                    />
                  </div>

                  <!--
                    编辑操作按钮
                    Editor action buttons

                    saveEvent
                    中文：保存当前表单事件
                    English: saves the current event form

                    startNewEvent
                    中文：重置为一个新的空事件
                    English: resets the form to create a new event
                  -->
                  <div class="editor-actions">
                    <button class="editor-primary-button" @click="saveEvent">
                      {{ editForm.id ? 'Update' : 'Add' }}
                    </button>
                    <button class="editor-secondary-button" @click="startNewEvent">
                      New
                    </button>
                  </div>
                </div>

                <!--
                  已有事件列表
                  Existing events list

                  sortedEvents
                  中文：按日期排序后的可见事件列表
                  English: visible events sorted by date
                -->
                <div class="editor-list">
                  <div class="editor-list-title">Existing events</div>

                  <div v-if="sortedEvents.length" class="editor-list-scroll">
                    <div v-for="item in sortedEvents" :key="item.id" class="editor-item">
                      <div class="editor-item-main">
                        <span class="editor-type-chip chip-event">Event</span>
                        <div class="editor-item-date">{{ item.date }}</div>
                        <div class="editor-item-title">{{ item.title }}</div>
                      </div>

                      <div class="editor-item-actions">
                        <button class="mini-action-button" @click="editExistingEvent(item)">
                          Edit
                        </button>
                        <button class="mini-action-button danger" @click="deleteEvent(item.id)">
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>

                  <div v-else class="overlay-empty-state">No events yet.</div>
                </div>
              </div>
            </div>
          </transition>
        </div>
      </aside>

      <!--
        模块 4：主内容路由出口
        Module 4: Main routed content outlet

        功能说明：
        1. 显示当前页面的核心业务内容
        2. 具体页面由 vue-router 决定

        Function:
        1. Displays the main business content of the current page
        2. The concrete page is determined by vue-router
      -->
      <main class="main-content">
        <RouterView />
      </main>
    </div>

    <!--
      模块 5：登录页单独路由出口
      Module 5: Standalone routed outlet for login page

      功能说明：
      当 isLoginPage 为 true 时，不使用 Header + Sidebar 布局，
      而是直接渲染当前登录页路由组件。

      Function:
      When isLoginPage is true, the app bypasses the Header + Sidebar layout
      and directly renders the current login route component.
    -->
    <RouterView v-else />

    <!--
      模块 6：用户账号菜单面板
      Module 6: User account menu panel

      显示条件：
      v-if="!isLoginPage && showUserMenu"

      功能说明：
      1. 点击头像后展开
      2. 展示账户摘要
      3. 提供快捷入口：Profile / Support / Upcoming events
      4. 提供退出登录按钮

      Display condition:
      v-if="!isLoginPage && showUserMenu"

      Function:
      1. Opens after clicking the avatar
      2. Shows account summary
      3. Provides quick links: Profile / Support / Upcoming events
      4. Provides a logout button
    -->
    <transition name="menu-fade">
      <div
        ref="userMenuPanelRef"
        :class="['notification-panel', { show: showUserMenu }]"
        v-if="!isLoginPage && showUserMenu"
      >
        <div class="notification-header">
          <div class="account-summary">

            <!--
              auth.initials
              中文：当前用户缩写
              English: current user initials
            -->
            <div class="account-avatar">{{ auth.initials }}</div>

            <div class="account-copy">
              <h4 class="notification-title">My account</h4>

              <!--
                auth.isAdmin
                中文：根据是否管理员显示不同账户说明
                English: shows different account descriptions based on admin role
              -->
              <p class="account-subtitle">
                {{ auth.isAdmin ? 'Administrator access' : 'Standard member access' }}
              </p>
            </div>
          </div>

          <button @click="showUserMenu = false" class="close-button account-close-button" aria-label="Close">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <!-- 快捷入口 Quick links -->
        <div class="notification-panel-section">
          <button class="panel-quick-link" type="button" @click="go('/profile')">
            <span class="panel-quick-icon"><i class="fas fa-user"></i></span>
            <span class="panel-quick-copy">
              <strong>Profile</strong>
              <small>Update your account details</small>
            </span>
          </button>

          <button class="panel-quick-link" type="button" @click="go('/contact')">
            <span class="panel-quick-icon"><i class="fas fa-headset"></i></span>
            <span class="panel-quick-copy">
              <strong>Support</strong>
              <small>Contact an administrator</small>
            </span>
          </button>

          <button class="panel-quick-link" type="button" @click="go('/events')">
            <span class="panel-quick-icon"><i class="fas fa-calendar-alt"></i></span>
            <span class="panel-quick-copy">
              <strong>Upcoming events</strong>
              <small>Open the events workspace</small>
            </span>
          </button>
        </div>

        <!--
          退出登录区域
          Logout area

          @click="auth.logout(); go('/login')"
          中文：先执行登出，再跳转到登录页
          English: logs the user out first, then redirects to the login page
        -->
        <div class="notification-panel-footer">
          <button
            class="logout-button"
            type="button"
            @click="handleLogout"
          >
            <i class="fas fa-sign-out-alt"></i>
            <span>Log out</span>
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
/*
  模块 1：基础导入与类型定义
  Module 1: Base imports and type definitions

  功能说明：
  1. 导入 Vue 组合式 API
  2. 导入路由工具
  3. 导入认证 Store
  4. 定义日历和搜索相关的数据类型

  Function:
  1. Imports Vue Composition API utilities
  2. Imports router tools
  3. Imports auth store
  4. Defines types for calendar and search data
*/
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter, RouterLink, RouterView } from 'vue-router'
import { useAuthStore } from './stores/auth'
import logo from '@/assets/btf-logo.png'

const handleLogout = async () => {
  await auth.logout()
  go('/login')
}
/*
  ItemType
  中文：日历项目类型，只允许 holiday 或 event
  English: calendar item type, only allows holiday or event
*/
type ItemType = 'holiday' | 'event'

/*
  CalendarItem
  中文：日历中单个项目的数据结构
  English: data structure for a single calendar item

  字段说明：
  - id: 唯一标识 / unique identifier
  - date: 日期字符串，格式通常为 YYYY-MM-DD / date string, usually YYYY-MM-DD
  - type: 类型，holiday 或 event / item type, holiday or event
  - title: 展示标题 / display title
*/
interface CalendarItem {
  id: number
  date: string
  type: ItemType
  title: string
}

/*
  SearchPayload
  中文：搜索请求负载结构
  English: payload structure for search requests

  字段说明：
  - query: 搜索关键词 / search keyword
  - scope: 搜索范围 / search scope
*/
interface SearchPayload {
  query: string
  scope: 'all' | 'groups' | 'events' | 'announcements' | 'resources'
}

/*
  模块 2：路由与认证基础对象
  Module 2: Route and auth base objects

  变量说明：
  - route
    中文：当前路由对象，用于读取当前页面路径
    English: current route object, used to read the current path

  - router
    中文：路由实例，用于执行页面跳转
    English: router instance, used to navigate programmatically

  - auth
    中文：认证 Store，提供当前用户身份、是否管理员、退出登录等能力
    English: auth store providing current user identity, admin flag, logout, etc.
*/
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

/*
  模块 3：页面级状态
  Module 3: Page-level state

  isLoginPage
  中文：判断当前路由是否为登录页
  English: determines whether the current route is the login page

  作用：
  - 登录页隐藏 Header 和 Sidebar
  - 非登录页显示完整后台布局

  Purpose:
  - Hide Header and Sidebar on login page
  - Show full application layout on non-login pages
*/
const isLoginPage = computed(() => route.path === '/login')

/*
  模块 4：用户菜单相关状态与行为
  Module 4: User menu state and behavior

  变量说明：
  - showUserMenu
    中文：账号菜单是否展开
    English: whether the account menu is open

  - hasUserMenuBadge
    中文：头像红点是否显示
    English: whether the avatar notification badge is shown

  - userMenuPanelRef
    中文：账号菜单面板 DOM 引用
    English: DOM ref for the account menu panel

  - avatarRef
    中文：头像按钮 DOM 引用
    English: DOM ref for the avatar button
*/
const showUserMenu = ref(false)
const hasUserMenuBadge = ref(true)
const userMenuPanelRef = ref<HTMLElement | null>(null)
const avatarRef = ref<HTMLElement | null>(null)

/*
  searchInputRef
  中文：搜索输入框 DOM 引用，用于 focus 操作
  English: DOM ref for the search input, used for focusing the input
*/
const searchInputRef = ref<HTMLInputElement | null>(null)

/*
  toggleUserMenu
  中文：
  1. 切换用户菜单显示状态
  2. 菜单一旦打开，清除红点提醒

  English:
  1. Toggles the user menu visibility
  2. Removes the badge reminder once the menu is opened
*/
const toggleUserMenu = () => {
  showUserMenu.value = !showUserMenu.value
  if (showUserMenu.value) hasUserMenuBadge.value = false
}

/*
  go
  中文：
  1. 关闭用户菜单
  2. 跳转到指定路径

  参数说明：
  - path: 目标路由路径
    path: target route path

  English:
  1. Closes the user menu
  2. Navigates to the given path
*/
const go = (path: string) => {
  showUserMenu.value = false
  router.push(path)
}

/*
  模块 5：搜索模块
  Module 5: Search module

  状态说明：
  - searchQuery
    中文：搜索关键词输入内容
    English: current search keyword

  - searchScope
    中文：当前搜索范围
    English: current search scope

  - isSearchFocused
    中文：输入框是否处于焦点状态
    English: whether the search input is focused

  - isSearching
    中文：搜索请求是否进行中
    English: whether a search request is currently running
*/
const searchQuery = ref('')
const searchScope = ref<SearchPayload['scope']>('all')
const isSearchFocused = ref(false)
const isSearching = ref(false)

/*
  focusSearch
  中文：手动聚焦搜索输入框
  English: programmatically focuses the search input
*/
const focusSearch = () => {
  searchInputRef.value?.focus()
}

/*
  buildSearchPayload
  中文：
  构建标准化搜索参数对象，统一从页面状态中提取 query 和 scope

  English:
  Builds a normalized search payload object using the current query and scope state
*/
const buildSearchPayload = (): SearchPayload => {
  return {
    query: searchQuery.value.trim(),
    scope: searchScope.value
  }
}

/*
  requestGlobalSearch
  中文：
  全局搜索接口的占位函数，当前仅返回 Promise.resolve()
  后续可替换成真实后端请求

  建议接口示例：
  GET /api/v1/search/?q=...&scope=...

  English:
  Placeholder function for future global search API integration.
  It currently returns Promise.resolve() and can later be replaced by a real backend call.

  Suggested endpoint example:
  GET /api/v1/search/?q=...&scope=...
*/
const requestGlobalSearch = async (_payload: SearchPayload) => {
  return Promise.resolve()
}

/*
  submitSearch
  中文：
  1. 构建搜索参数
  2. 如果关键词为空则直接返回
  3. 设置 loading 状态
  4. 调用搜索接口
  5. 跳转到 /resources，并附带 q 和 scope 参数
  6. 最后关闭 loading 状态

  English:
  1. Builds the search payload
  2. Returns immediately if the query is empty
  3. Enables loading state
  4. Calls the search request
  5. Redirects to /resources with q and scope query parameters
  6. Finally resets loading state
*/
const submitSearch = async () => {
  const payload = buildSearchPayload()
  if (!payload.query) return

  isSearching.value = true

  try {
    await requestGlobalSearch(payload)

    router.push({
      path: '/resources',
      query: {
        q: payload.query,
        scope: payload.scope
      }
    })
  } finally {
    isSearching.value = false
  }
}

/*
  clearSearch
  中文：
  1. 清空搜索关键词
  2. 重新聚焦输入框，方便继续输入

  English:
  1. Clears the search query
  2. Refocuses the input for continued typing
*/
const clearSearch = () => {
  searchQuery.value = ''
  focusSearch()
}

/*
  模块 6：用户菜单交互事件
  Module 6: User menu interaction handlers
*/

/*
  handleClickOutside
  中文：
  用于监听点击外部区域关闭用户菜单。
  如果点击目标既不在菜单面板内，也不在头像按钮内，则关闭菜单。

  参数：
  - event: MouseEvent

  English:
  Closes the user menu when clicking outside.
  If the click target is neither inside the menu panel nor inside the avatar button,
  the menu will be closed.

  Parameter:
  - event: MouseEvent
*/
const handleClickOutside = (event: MouseEvent) => {
  if (!showUserMenu.value) return

  const target = event.target as Node | null
  if (!target) return

  const clickedInsidePanel = userMenuPanelRef.value?.contains(target)
  const clickedAvatar = avatarRef.value?.contains(target)

  if (!clickedInsidePanel && !clickedAvatar) {
    showUserMenu.value = false
  }
}

/*
  handleKeydown
  中文：
  监听键盘按键，当用户菜单打开时按下 Escape：
  1. 关闭菜单
  2. 把焦点回到头像按钮

  参数：
  - event: KeyboardEvent

  English:
  Handles keyboard interaction.
  When the menu is open and the user presses Escape:
  1. closes the menu
  2. restores focus to the avatar button

  Parameter:
  - event: KeyboardEvent
*/
const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && showUserMenu.value) {
    showUserMenu.value = false
    avatarRef.value?.focus?.()
  }
}

/*
  模块 7：通用监听与生命周期
  Module 7: General watchers and lifecycle
*/

/*
  监听 route.fullPath
  Watch route.fullPath

  中文：
  页面发生跳转时自动关闭用户菜单，避免菜单在页面切换后仍停留

  English:
  Automatically closes the user menu when the route changes,
  preventing the menu from staying open after navigation
*/
watch(
  () => route.fullPath,
  () => {
    showUserMenu.value = false
  }
)

/*
  onMounted
  中文：
  组件挂载后注册全局 click 和 keydown 监听器

  English:
  Registers global click and keydown listeners after component mount
*/
onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
})

/*
  onBeforeUnmount
  中文：
  组件销毁前移除全局事件监听器，避免内存泄漏

  English:
  Removes global event listeners before component unmount to avoid memory leaks
*/
onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
})

/*
  模块 8：日历基础工具函数
  Module 8: Calendar base utility functions
*/

/*
  today
  中文：当前系统日期对象
  English: current system date object
*/
const today = new Date()

/*
  weekdayLabels
  中文：日历顶部的星期标签数组
  English: weekday labels shown at the top of the calendar
*/
const weekdayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

/*
  pad
  中文：把数字补成两位字符串
  例如：3 -> "03"

  参数：
  - value: number

  English:
  Pads a number into a two-digit string
  Example: 3 -> "03"

  Parameter:
  - value: number
*/
const pad = (value: number) => String(value).padStart(2, '0')

/*
  toDateKey
  中文：
  把 year、month、day 转成标准日期键 YYYY-MM-DD
  注意 month 传入的是 JS Date 风格，从 0 开始

  参数：
  - year: 年
  - month: 月，0-based
  - day: 日

  示例：
  toDateKey(2026, 2, 31) -> "2026-03-31"

  English:
  Converts year, month, and day into a standard YYYY-MM-DD date key.
  Note that month is 0-based, following JavaScript Date conventions.

  Parameters:
  - year
  - month: 0-based
  - day

  Example:
  toDateKey(2026, 2, 31) -> "2026-03-31"
*/
const toDateKey = (year: number, month: number, day: number) => {
  return `${year}-${pad(month + 1)}-${pad(day)}`
}

/*
  parseDateKey
  中文：把 YYYY-MM-DD 字符串转回 Date 对象
  English: parses a YYYY-MM-DD string back into a Date object
*/
const parseDateKey = (dateKey: string) => {
  const [year, month, day] = dateKey.split('-').map(Number)
  return new Date(year, month - 1, day)
}

/*
  monthStart
  中文：获取某个日期所在月份的第一天
  English: gets the first day of the month for a given date
*/
const monthStart = (date: Date) => new Date(date.getFullYear(), date.getMonth(), 1)

/*
  addMonths
  中文：在某个日期的基础上增减月份，并返回目标月份第一天
  English: adds or subtracts months and returns the first day of the target month
*/
const addMonths = (date: Date, delta: number) => {
  return new Date(date.getFullYear(), date.getMonth() + delta, 1)
}

/*
  模块 9：日历允许范围与当前月份
  Module 9: Calendar allowed range and current month context

  逻辑说明：
  仅允许查看“上个月、当前月、下个月”三个月范围

  Logic:
  Only allows viewing the previous month, current month, and next month
*/
const currentMonthStart = monthStart(today)
const minAllowedMonth = addMonths(currentMonthStart, -1)
const maxAllowedMonth = addMonths(currentMonthStart, 1)

/*
  minAllowedDate
  中文：允许编辑/查看的最小日期键
  English: minimum allowed date key for viewing/editing
*/
const minAllowedDate = computed(() =>
  toDateKey(minAllowedMonth.getFullYear(), minAllowedMonth.getMonth(), 1)
)

/*
  maxAllowedDate
  中文：允许编辑/查看的最大日期键
  English: maximum allowed date key for viewing/editing
*/
const maxAllowedDate = computed(() => {
  const lastDay = new Date(
    maxAllowedMonth.getFullYear(),
    maxAllowedMonth.getMonth() + 1,
    0
  )

  return toDateKey(
    lastDay.getFullYear(),
    lastDay.getMonth(),
    lastDay.getDate()
  )
})

/*
  calendarYear / calendarMonth
  中文：当前日历视图所在的年和月
  English: year and month currently displayed by the mini calendar
*/
const calendarYear = ref(today.getFullYear())
const calendarMonth = ref(today.getMonth())

/*
  calendarMonthStart
  中文：当前日历视图月份的第一天
  English: the first day of the currently displayed calendar month
*/
const calendarMonthStart = computed(() => new Date(calendarYear.value, calendarMonth.value, 1))

/*
  canGoPrevMonth
  中文：是否还能往前切换月份
  English: whether the previous month can still be navigated to
*/
const canGoPrevMonth = computed(() => {
  return calendarMonthStart.value.getTime() > minAllowedMonth.getTime()
})

/*
  canGoNextMonth
  中文：是否还能往后切换月份
  English: whether the next month can still be navigated to
*/
const canGoNextMonth = computed(() => {
  return calendarMonthStart.value.getTime() < maxAllowedMonth.getTime()
})

/*
  isCurrentMonth
  中文：当前显示月份是否就是今天所在月份
  English: whether the displayed month is the actual current month
*/
const isCurrentMonth = computed(() => {
  return (
    calendarYear.value === currentMonthStart.getFullYear() &&
    calendarMonth.value === currentMonthStart.getMonth()
  )
})

/*
  calendarTitle
  中文：日历标题，例如 "March 2026"
  English: calendar heading, for example "March 2026"
*/
const calendarTitle = computed(() => {
  return new Intl.DateTimeFormat('en-AU', {
    month: 'long',
    year: 'numeric'
  }).format(calendarMonthStart.value)
})

/*
  todayLabel
  中文：今天的辅助标题，例如 "Tue, 31 Mar"
  English: helper label for today, for example "Tue, 31 Mar"
*/
const todayLabel = computed(() => {
  return new Intl.DateTimeFormat('en-AU', {
    weekday: 'short',
    day: '2-digit',
    month: 'short'
  }).format(today)
})

/*
  模块 10：日历数据源
  Module 10: Calendar data sources

  holidaySource
  中文：节假日数据源，当前是本地静态示例数据
  English: holiday data source, currently local static sample data

  eventSource
  中文：事件数据源，当前是本地可编辑事件数据
  English: event data source, currently local editable event data
*/
const holidaySource = ref<CalendarItem[]>([
  { id: 1001, date: '2026-01-01', type: 'holiday', title: 'New Year’s Day' },
  { id: 1002, date: '2026-01-26', type: 'holiday', title: 'Australia Day' },
  { id: 1003, date: '2026-04-03', type: 'holiday', title: 'Good Friday' },
  { id: 1004, date: '2026-04-04', type: 'holiday', title: 'Easter Saturday' },
  { id: 1005, date: '2026-04-05', type: 'holiday', title: 'Easter Sunday' },
  { id: 1006, date: '2026-04-06', type: 'holiday', title: 'Easter Monday' },
  { id: 1007, date: '2026-04-25', type: 'holiday', title: 'Anzac Day' },
  { id: 1008, date: '2026-04-27', type: 'holiday', title: 'Additional Day for Anzac Day' },
  { id: 1009, date: '2026-06-08', type: 'holiday', title: 'King’s Birthday' },
  { id: 1010, date: '2026-10-05', type: 'holiday', title: 'Labour Day' },
  { id: 1011, date: '2026-12-25', type: 'holiday', title: 'Christmas Day' },
  { id: 1012, date: '2026-12-26', type: 'holiday', title: 'Boxing Day' },
  { id: 1013, date: '2026-12-28', type: 'holiday', title: 'Additional Day for Boxing Day' },
  { id: 1014, date: '2027-01-01', type: 'holiday', title: 'New Year’s Day' },
  { id: 1015, date: '2027-01-26', type: 'holiday', title: 'Australia Day' },
  { id: 1016, date: '2027-03-26', type: 'holiday', title: 'Good Friday' },
  { id: 1017, date: '2027-03-27', type: 'holiday', title: 'Easter Saturday' },
  { id: 1018, date: '2027-03-28', type: 'holiday', title: 'Easter Sunday' },
  { id: 1019, date: '2027-03-29', type: 'holiday', title: 'Easter Monday' },
  { id: 1020, date: '2027-04-25', type: 'holiday', title: 'Anzac Day' },
  { id: 1021, date: '2027-04-26', type: 'holiday', title: 'Additional Day for Anzac Day' },
  { id: 1022, date: '2027-06-14', type: 'holiday', title: 'King’s Birthday' }
])

const eventSource = ref<CalendarItem[]>([
  {
    id: 1,
    date: toDateKey(today.getFullYear(), today.getMonth(), today.getDate()),
    type: 'event',
    title: 'Team Check-in 2:30 PM'
  },
  {
    id: 2,
    date: toDateKey(today.getFullYear(), today.getMonth(), Math.min(today.getDate() + 3, 28)),
    type: 'event',
    title: 'Client Demo 10:00 AM'
  }
])

/*
  模块 11：日历可见数据计算
  Module 11: Calendar visible data computation
*/

/*
  isDateWithinAllowedWindow
  中文：判断日期是否在允许窗口内
  English: checks whether a date is inside the allowed calendar window
*/
const isDateWithinAllowedWindow = (dateKey: string) => {
  return dateKey >= minAllowedDate.value && dateKey <= maxAllowedDate.value
}

/*
  visibleHolidays
  中文：当前允许窗口内可见的节假日
  English: holidays visible within the allowed date window
*/
const visibleHolidays = computed(() => {
  return holidaySource.value.filter(item => isDateWithinAllowedWindow(item.date))
})

/*
  visibleEvents
  中文：当前允许窗口内可见的事件
  English: events visible within the allowed date window
*/
const visibleEvents = computed(() => {
  return eventSource.value.filter(item => isDateWithinAllowedWindow(item.date))
})

/*
  itemMap
  中文：
  把同一天的 holiday/event 聚合成一个 Map，key 为 dateKey，value 为该天的项目数组

  English:
  Groups holidays/events by date into a Map,
  where the key is the dateKey and the value is the array of items for that date
*/
const itemMap = computed(() => {
  const map = new Map<string, CalendarItem[]>()

  for (const item of [...visibleHolidays.value, ...visibleEvents.value]) {
    if (!map.has(item.date)) map.set(item.date, [])
    map.get(item.date)!.push(item)
  }

  return map
})

/*
  calendarDays
  中文：
  生成迷你日历的 42 个格子数据。
  其中包括：
  1. 月初前面的空白补位
  2. 当前月的所有日期
  3. 月末后的空白补位

  每个格子字段：
  - key
  - day
  - dateKey
  - isToday
  - hasHoliday
  - hasEvent
  - clickable

  English:
  Generates the 42 visible cells for the mini calendar grid.
  It includes:
  1. leading empty cells before the first day of the month
  2. all actual days in the current month
  3. trailing empty cells after the last day

  Fields in each cell:
  - key
  - day
  - dateKey
  - isToday
  - hasHoliday
  - hasEvent
  - clickable
*/
const calendarDays = computed(() => {
  const year = calendarYear.value
  const month = calendarMonth.value
  const firstDay = new Date(year, month, 1)
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const firstWeekday = (firstDay.getDay() + 6) % 7

  const cells: Array<{
    key: string
    day: number | null
    dateKey: string | null
    isToday: boolean
    hasHoliday: boolean
    hasEvent: boolean
    clickable: boolean
  }> = []

  for (let i = 0; i < firstWeekday; i++) {
    cells.push({
      key: `empty-start-${i}`,
      day: null,
      dateKey: null,
      isToday: false,
      hasHoliday: false,
      hasEvent: false,
      clickable: false
    })
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const dateKey = toDateKey(year, month, day)
    const items = itemMap.value.get(dateKey) ?? []

    cells.push({
      key: `day-${dateKey}`,
      day,
      dateKey,
      isToday:
        year === today.getFullYear() &&
        month === today.getMonth() &&
        day === today.getDate(),
      hasHoliday: items.some(item => item.type === 'holiday'),
      hasEvent: items.some(item => item.type === 'event'),
      clickable: items.length > 0
    })
  }

  while (cells.length < 42) {
    cells.push({
      key: `empty-end-${cells.length}`,
      day: null,
      dateKey: null,
      isToday: false,
      hasHoliday: false,
      hasEvent: false,
      clickable: false
    })
  }

  return cells
})

/*
  模块 12：日历覆盖层状态
  Module 12: Calendar overlay state

  - selectedDateKey
    中文：当前选中的日期键
    English: currently selected date key

  - showCalendarOverlay
    中文：是否显示覆盖层
    English: whether the calendar overlay is visible

  - overlayMode
    中文：覆盖层模式，details 或 edit
    English: overlay mode, either details or edit
*/
const selectedDateKey = ref<string | null>(null)
const showCalendarOverlay = ref(false)
const overlayMode = ref<'details' | 'edit'>('details')

/*
  selectedItems
  中文：当前选中日期下的所有项目
  English: all items under the currently selected date
*/
const selectedItems = computed(() => {
  if (!selectedDateKey.value) return []
  return itemMap.value.get(selectedDateKey.value) ?? []
})

/*
  selectedOverlayTitle
  中文：详情弹层头部的格式化日期标题
  English: formatted date title shown in the details overlay header
*/
const selectedOverlayTitle = computed(() => {
  if (!selectedDateKey.value) return 'Date details'
  const selectedDate = parseDateKey(selectedDateKey.value)
  return new Intl.DateTimeFormat('en-AU', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  }).format(selectedDate)
})

/*
  closeCalendarOverlay
  中文：关闭日历覆盖层
  English: closes the calendar overlay
*/
const closeCalendarOverlay = () => {
  showCalendarOverlay.value = false
}

/*
  openDayDetails
  中文：
  1. 如果日期为空则不处理
  2. 如果该天没有项目则不处理
  3. 设置选中日期
  4. 切换到 details 模式
  5. 打开覆盖层

  参数：
  - dateKey: string | null

  English:
  1. Returns if the date is null
  2. Returns if the date has no items
  3. Sets the selected date
  4. Switches to details mode
  5. Opens the overlay

  Parameter:
  - dateKey: string | null
*/
const openDayDetails = (dateKey: string | null) => {
  if (!dateKey) return
  const items = itemMap.value.get(dateKey) ?? []
  if (!items.length) return

  selectedDateKey.value = dateKey
  overlayMode.value = 'details'
  showCalendarOverlay.value = true
}

/*
  模块 13：日历月份导航
  Module 13: Calendar month navigation
*/

/*
  goPrevMonth
  中文：切换到上个月，并关闭覆盖层
  English: moves to the previous month and closes the overlay
*/
const goPrevMonth = () => {
  if (!canGoPrevMonth.value) return
  const prev = addMonths(calendarMonthStart.value, -1)
  calendarYear.value = prev.getFullYear()
  calendarMonth.value = prev.getMonth()
  closeCalendarOverlay()
}

/*
  goNextMonth
  中文：切换到下个月，并关闭覆盖层
  English: moves to the next month and closes the overlay
*/
const goNextMonth = () => {
  if (!canGoNextMonth.value) return
  const next = addMonths(calendarMonthStart.value, 1)
  calendarYear.value = next.getFullYear()
  calendarMonth.value = next.getMonth()
  closeCalendarOverlay()
}

/*
  goToCurrentMonth
  中文：回到当前月，并关闭覆盖层
  English: jumps back to the current month and closes the overlay
*/
const goToCurrentMonth = () => {
  calendarYear.value = currentMonthStart.getFullYear()
  calendarMonth.value = currentMonthStart.getMonth()
  closeCalendarOverlay()
}

/*
  模块 14：事件编辑器状态
  Module 14: Event editor state
*/

/*
  editForm
  中文：
  当前编辑表单对象。
  默认初始化为：
  - id: 0，表示新建
  - date: 最小允许日期
  - type: event
  - title: 空字符串

  English:
  Current event editing form object.
  Default initialization:
  - id: 0, meaning create mode
  - date: minimum allowed date
  - type: event
  - title: empty string
*/
const editForm = ref<CalendarItem>({
  id: 0,
  date: minAllowedDate.value,
  type: 'event',
  title: ''
})

/*
  sortedEvents
  中文：当前可见窗口内的事件按日期升序排序
  English: visible events sorted by date in ascending order
*/
const sortedEvents = computed(() => {
  return [...visibleEvents.value].sort((a, b) => a.date.localeCompare(b.date))
})

/*
  startNewEvent
  中文：
  重置编辑表单为“新建事件”状态。
  默认日期优先级：
  1. 如果当前 selectedDateKey 在允许窗口内，则用它
  2. 否则用当前显示月份的 1 号

  English:
  Resets the editor form into "new event" mode.
  Default date priority:
  1. use selectedDateKey if it exists and is allowed
  2. otherwise use the first day of the currently displayed month
*/
const startNewEvent = () => {
  const defaultDate =
    selectedDateKey.value && isDateWithinAllowedWindow(selectedDateKey.value)
      ? selectedDateKey.value
      : toDateKey(calendarYear.value, calendarMonth.value, 1)

  editForm.value = {
    id: 0,
    date: defaultDate,
    type: 'event',
    title: ''
  }
}

/*
  openEditor
  中文：
  1. 打开编辑模式
  2. 打开覆盖层
  3. 初始化一个新的事件表单

  English:
  1. Switches to edit mode
  2. Opens the overlay
  3. Initializes a fresh event form
*/
const openEditor = () => {
  overlayMode.value = 'edit'
  showCalendarOverlay.value = true
  startNewEvent()
}

/*
  editExistingEvent
  中文：
  把某个已有事件加载进表单进行编辑。
  强制 type 为 event，避免 holiday 被误编辑。

  参数：
  - item: CalendarItem

  English:
  Loads an existing event into the editor form.
  Forces type to be event to avoid editing holidays by mistake.

  Parameter:
  - item: CalendarItem
*/
const editExistingEvent = (item: CalendarItem) => {
  editForm.value = { ...item, type: 'event' }
}

/*
  模块 15：事件保存与删除接口占位
  Module 15: Event save/delete API placeholders

  saveCalendarEventRequest
  中文：未来可接入后端保存接口
  English: placeholder for future backend save API

  deleteCalendarEventRequest
  中文：未来可接入后端删除接口
  English: placeholder for future backend delete API

  建议接口：
  - POST /api/v1/calendar/events/
  - PATCH /api/v1/calendar/events/:id/
  - DELETE /api/v1/calendar/events/:id/
*/
const saveCalendarEventRequest = async (_event: CalendarItem) => {
  return Promise.resolve()
}

const deleteCalendarEventRequest = async (_id: number) => {
  return Promise.resolve()
}

/*
  模块 16：事件保存与删除逻辑
  Module 16: Event save and delete logic
*/

/*
  saveEvent
  中文：
  1. 读取并校验表单 title 和 date
  2. 如果为空或日期不在允许窗口内，直接返回
  3. 构造标准 payload
  4. 调用保存接口
  5. 如果 editForm.id 存在，则更新已有事件
  6. 否则新增到 eventSource
  7. 更新 selectedDateKey
  8. 重置表单为新建状态

  English:
  1. Reads and validates title and date from the form
  2. Returns if empty or outside the allowed window
  3. Builds a normalized payload
  4. Calls the save API
  5. If editForm.id exists, updates an existing event
  6. Otherwise appends a new event to eventSource
  7. Updates selectedDateKey
  8. Resets the form into create mode
*/
const saveEvent = async () => {
  const title = editForm.value.title.trim()
  const date = editForm.value.date

  if (!title || !date) return
  if (!isDateWithinAllowedWindow(date)) return

  const payload: CalendarItem = {
    id: editForm.value.id || Date.now(),
    date,
    type: 'event',
    title
  }

  await saveCalendarEventRequest(payload)

  if (editForm.value.id) {
    const index = eventSource.value.findIndex(item => item.id === editForm.value.id)
    if (index !== -1) {
      eventSource.value[index] = payload
    }
  } else {
    eventSource.value.push(payload)
  }

  selectedDateKey.value = date
  startNewEvent()
}

/*
  deleteEvent
  中文：
  1. 调用删除接口
  2. 从本地 eventSource 中删除对应事件
  3. 如果当前表单正在编辑该事件，则重置表单

  参数：
  - id: 要删除的事件 ID

  English:
  1. Calls the delete API
  2. Removes the matching event from local eventSource
  3. If the form is currently editing that event, resets the form

  Parameter:
  - id: event ID to delete
*/
const deleteEvent = async (id: number) => {
  await deleteCalendarEventRequest(id)
  eventSource.value = eventSource.value.filter(item => item.id !== id)

  if (editForm.value.id === id) {
    startNewEvent()
  }
}

/*
  监听 showCalendarOverlay
  Watch showCalendarOverlay

  中文：
  当覆盖层被打开且当前是 edit 模式时，自动初始化一个新事件表单

  English:
  When the overlay is opened and the current mode is edit,
  automatically initializes a new event form
*/
watch(showCalendarOverlay, value => {
  if (value && overlayMode.value === 'edit') {
    startNewEvent()
  }
})
</script>

<style scoped>
/*
  模块 1：全局基础重置与主题变量
  Module 1: Global reset and theme variables

  功能说明：
  1. 让 html、body、#app 占满整个可视区域
  2. 去掉默认 margin / padding
  3. 定义整套页面使用的颜色、阴影、品牌变量

  Function:
  1. Makes html, body, and #app fill the available viewport
  2. Removes default margin and padding
  3. Defines the color palette, shadows, and brand variables used by the page
*/
:global(html),
:global(body),
:global(#app) {
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 0;
}

:global(body) {
  overflow-x: hidden;
}

:deep(:root) {
  --surface-0: #ffffff;
  --surface-1: #f6fbf8;
  --surface-2: #ecf7f1;
  --surface-3: #dff1e7;

  --text-strong: #0e2a20;
  --text-main: #1d4034;
  --text-soft: #678379;

  --line-soft: rgba(10, 58, 39, 0.08);
  --line-mid: rgba(10, 58, 39, 0.14);

  --brand-900: #041f17;
  --brand-800: #063326;
  --brand-700: #0a5a40;
  --brand-600: #0f7b56;
  --brand-500: #12a86d;
  --brand-400: #19d889;
  --brand-300: #5ef0ad;

  --shadow-soft: 0 10px 30px rgba(3, 31, 22, 0.08);
  --shadow-panel: 0 18px 50px rgba(3, 31, 22, 0.2);
}

/*
  模块 2：应用主容器
  Module 2: App main container

  .app-container
  中文：页面根布局容器，负责全局背景和最小高度
  English: root layout container, responsible for global background and minimum height
*/
.app-container {
  width: 100%;
  max-width: none;
  min-height: 100vh;
  margin: 0;
  background:
    radial-gradient(circle at top left, rgba(79, 165, 127, 0.08), transparent 28%),
    linear-gradient(180deg, #fbfdfc 0%, #f7faf9 100%);
}

/*
  模块 3：Header 顶部导航区
  Module 3: Header top navigation area

  这一组样式负责：
  1. 粘性顶部导航栏
  2. 水晶/玻璃质感背景
  3. 顶部高亮、阴影、品牌氛围

  This group styles:
  1. the sticky top navigation
  2. the glass-like visual effect
  3. the glow, highlight, and brand atmosphere
*/
.header {
  position: sticky;
  top: 0;
  z-index: 20;
  overflow: hidden;
  backdrop-filter: blur(20px) saturate(155%);
  -webkit-backdrop-filter: blur(20px) saturate(155%);
  background:
    linear-gradient(
      135deg,
      rgba(117, 255, 191, 0.28) 0%,
      rgba(27, 232, 134, 0.16) 14%,
      rgba(255, 255, 255, 0.06) 22%,
      rgba(255, 255, 255, 0.02) 30%,
      transparent 44%
    ),
    radial-gradient(
      circle at 18% 18%,
      rgba(88, 255, 174, 0.34) 0%,
      rgba(27, 232, 134, 0.18) 18%,
      transparent 42%
    ),
    radial-gradient(
      circle at 82% 0%,
      rgba(36, 255, 149, 0.24) 0%,
      rgba(17, 184, 108, 0.12) 16%,
      transparent 36%
    ),
    linear-gradient(
      180deg,
      #118a5d 0%,
      #0b6b49 28%,
      #084832 68%,
      #04261c 100%
    );
  border-bottom: 1px solid rgba(187, 255, 222, 0.18);
  box-shadow:
    0 16px 38px rgba(2, 24, 17, 0.24),
    0 8px 18px rgba(2, 24, 17, 0.18),
    inset 0 1px 0 rgba(231, 255, 242, 0.26),
    inset 0 -1px 0 rgba(0, 0, 0, 0.1);
}

.header::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(
      118deg,
      transparent 0%,
      transparent 16%,
      rgba(210, 255, 229, 0.24) 24%,
      rgba(123, 255, 191, 0.12) 30%,
      transparent 40%
    );
  mix-blend-mode: screen;
  opacity: 0.95;
}

.header::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 1px;
  pointer-events: none;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(212, 255, 232, 0.88) 20%,
    rgba(126, 255, 194, 0.42) 50%,
    rgba(212, 255, 232, 0.82) 80%,
    transparent 100%
  );
}

.header-content {
  width: 100%;
  max-width: none;
  min-height: 82px;
  padding: 0 1.2rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  box-sizing: border-box;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
}

.header-left {
  gap: 1rem;
}

.header-right {
  margin-left: auto;
  gap: 0.8rem;
  flex: 0 1 auto;
  min-width: 0;
}

/*
  模块 4：Logo 品牌区
  Module 4: Logo branding area

  样式作用：
  1. 控制图标尺寸、圆角、阴影
  2. 控制品牌名和副标题排版
  3. 保持头部品牌视觉识别一致

  Style purpose:
  1. Controls icon size, radius, and shadow
  2. Controls brand name and subtitle typography
  3. Keeps the header branding visually consistent
*/
.logo-section {
  min-width: 0;
}

.logo {
  display: inline-flex;
  align-items: center;
  gap: 0.85rem;
  text-decoration: none;
}

.logo-icon {
  width: 48px;
  height: 48px;
  border-radius: 15px;
  overflow: hidden;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.96) 0%, rgba(226, 243, 235, 0.92) 100%);
  border: 1px solid rgba(255, 255, 255, 0.4);
  box-shadow:
    0 10px 26px rgba(5, 30, 22, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    inset 0 -6px 16px rgba(28, 90, 63, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.logo-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.logo-text {
  font-size: 1rem;
  font-weight: 800;
  letter-spacing: 0.01em;
  color: rgba(246, 255, 250, 0.98);
  line-height: 1.15;
  text-shadow:
    0 1px 10px rgba(0, 0, 0, 0.12),
    0 0 14px rgba(84, 255, 171, 0.1);
}

.logo-subtext {
  margin-top: 0.12rem;
  font-size: 0.72rem;
  color: rgba(202, 255, 224, 0.9);
  font-weight: 600;
  line-height: 1.2;
}

/*
  模块 5：搜索栏区域
  Module 5: Search bar area

  包含：
  - .search-shell
  - .search-scope-wrap / .search-scope
  - .search-input-wrap
  - .search-bar
  - .search-clear-button
  - .search-submit-button

  作用：
  1. 提供搜索表单的整体玻璃卡片样式
  2. 区分 scope 下拉框和关键词输入框
  3. 支持 focused / disabled / hover 等状态变化

  Includes:
  - .search-shell
  - .search-scope-wrap / .search-scope
  - .search-input-wrap
  - .search-bar
  - .search-clear-button
  - .search-submit-button

  Purpose:
  1. Styles the search form as a glass-like card
  2. Separates the scope dropdown and keyword input visually
  3. Supports focused / disabled / hover states
*/
.search-shell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem;
  border-radius: 20px;
  background:
    linear-gradient(
      180deg,
      rgba(232, 255, 243, 0.18) 0%,
      rgba(128, 255, 198, 0.08) 100%
    );
  border: 1px solid rgba(208, 255, 229, 0.18);
  box-shadow:
    0 14px 30px rgba(3, 29, 21, 0.16),
    inset 0 1px 0 rgba(255, 255, 255, 0.24),
    inset 0 -8px 18px rgba(0, 0, 0, 0.06);
  flex: 0 1 560px;
  width: 100%;
  max-width: 560px;
  min-width: 0;
}

.search-scope-wrap {
  flex: 0 0 96px;
}

.search-scope {
  width: 100%;
  height: 42px;
  padding: 0 0.85rem;
  border: none;
  border-radius: 13px;
  background: rgba(243, 248, 245, 0.92);
  color: #244136;
  font-size: 0.76rem;
  font-weight: 700;
  outline: none;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.55);
}

.search-input-wrap {
  flex: 1 1 auto;
  width: auto;
  min-width: 120px;
  max-width: 280px;
  height: 42px;
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0 0.8rem;
  border-radius: 13px;
  background: rgba(248, 251, 249, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    background 0.18s ease,
    transform 0.18s ease;
  min-width: 0;
}

.search-input-wrap.is-focused {
  background: rgba(255, 255, 255, 0.98);
  border-color: rgba(94, 240, 173, 0.45);
  box-shadow:
    0 0 0 4px rgba(94, 240, 173, 0.14),
    0 10px 22px rgba(3, 29, 21, 0.08);
}

.search-icon {
  font-size: 0.82rem;
  color: #5f766d;
  flex-shrink: 0;
}

.search-bar {
  flex: 1;
  min-width: 0;
  border: none;
  background: transparent;
  outline: none;
  color: #17382d;
  font-size: 0.86rem;
  font-weight: 700;
  caret-color: #0f7b56;
}

.search-bar::placeholder {
  color: #6f867d;
  font-weight: 600;
  opacity: 1;
}

.search-clear-button {
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 999px;
  background: #edf3f0;
  color: #5f766d;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.search-submit-button {
  width: 42px;
  height: 42px;
  border: 1px solid rgba(215, 255, 234, 0.22);
  border-radius: 13px;
  background: linear-gradient(180deg, #1ce28c 0%, #11a96d 42%, #0a6a49 78%, #064230 100%);
  color: #ffffff;
  cursor: pointer;
  box-shadow:
    0 12px 24px rgba(2, 30, 21, 0.24),
    0 0 16px rgba(28, 226, 140, 0.14),
    inset 0 1px 0 rgba(233, 255, 242, 0.34);
  transition: transform 0.18s ease, box-shadow 0.18s ease, opacity 0.18s ease;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}

.search-submit-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow:
    0 16px 30px rgba(2, 30, 21, 0.28),
    0 0 20px rgba(28, 226, 140, 0.22),
    inset 0 1px 0 rgba(240, 255, 246, 0.44);
}

.search-submit-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  box-shadow: none;
}

/*
  模块 6：头像与用户菜单触发器
  Module 6: Avatar and user menu trigger

  作用：
  1. 头像按钮立体感
  2. 通知红点位置
  3. 鼠标 hover 反馈

  Purpose:
  1. Avatar button elevation and depth
  2. Notification badge positioning
  3. Hover feedback
*/
.header-actions {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  flex-shrink: 0;
}

.user-menu {
  display: flex;
  align-items: center;
}

.user-avatar {
  position: relative;
  width: 46px;
  height: 46px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  cursor: pointer;
  background:
    radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.28), transparent 35%),
    linear-gradient(180deg, rgba(92, 170, 129, 0.92) 0%, rgba(35, 102, 71, 0.96) 100%);
  color: #ffffff;
  box-shadow:
    0 12px 28px rgba(16, 52, 35, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.18);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.user-avatar:hover {
  transform: translateY(-1px);
  box-shadow:
    0 14px 32px rgba(24, 81, 62, 0.34),
    inset 0 1px 0 rgba(255, 255, 255, 0.28);
}

.user-avatar-text {
  font-size: 0.9rem;
  font-weight: 800;
  letter-spacing: 0.03em;
}

.notification-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #ff4d4f;
  border: 2px solid #ffffff;
  box-shadow: 0 4px 10px rgba(255, 77, 79, 0.35);
}

/*
  模块 7：主布局与侧边栏
  Module 7: Main layout and sidebar

  包含：
  - .main-layout
  - .sidebar
  - .sidebar-nav
  - .sidebar-list
  - .sidebar-item
  - .sidebar-link.active / hover
  - .main-content

  作用：
  1. 建立左侧导航 + 右侧内容的整体结构
  2. 让 Sidebar 固定在视口顶部下方
  3. 控制 Sidebar 的背景、边框、滚动行为

  Includes:
  - .main-layout
  - .sidebar
  - .sidebar-nav
  - .sidebar-list
  - .sidebar-item
  - .sidebar-link.active / hover
  - .main-content

  Purpose:
  1. Creates the overall left-sidebar + right-content structure
  2. Keeps the sidebar sticky below the header
  3. Controls sidebar background, border, and scrolling behavior
*/
.main-layout {
  display: flex;
  align-items: flex-start;
  width: 100%;
  max-width: none;
  min-height: calc(100vh - 80px);
}

.sidebar {
  position: sticky;
  top: 80px;
  align-self: flex-start;
  height: calc(100vh - 80px);
  overflow-y: auto;
  flex-shrink: 0;
  background:
    linear-gradient(
      180deg,
      rgba(233, 242, 237, 0.86) 0%,
      rgba(225, 236, 230, 0.9) 100%
    );
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  display: flex;
  flex-direction: column;
  width: 248px;
  min-width: 248px;
  border-right: 1px solid rgba(39, 106, 74, 0.08);
  box-shadow:
    inset -1px 0 0 rgba(255, 255, 255, 0.35),
    0 8px 20px rgba(20, 43, 33, 0.04);
}

.sidebar-nav {
  flex: 0 0 auto;
  padding: 0.8rem 0.7rem 0.25rem;
}

.sidebar-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.sidebar-item + .sidebar-item {
  margin-top: 0.22rem;
}

.sidebar-link:hover {
  background: rgba(47, 125, 87, 0.08);
  transform: translateX(2px);
}

.sidebar-link.active {
  background: linear-gradient(180deg, rgba(31, 111, 84, 0.12) 0%, rgba(31, 111, 84, 0.08) 100%);
  color: var(--brand-700);
  box-shadow: inset 0 0 0 1px rgba(31, 111, 84, 0.08);
}

.sidebar-icon {
  width: 18px;
  text-align: center;
  font-size: 0.88rem;
}

.main-content {
  flex: 1;
  min-width: 0;
  padding: 1rem;
}

/*
  模块 8：迷你日历外壳与基础结构
  Module 8: Mini calendar shell and structural layout

  作用：
  1. 控制日历卡片在侧边栏中的布局
  2. 设置内边距、圆角、背景和阴影
  3. 建立顶部导航、工具条、网格、图例等区域

  Purpose:
  1. Positions the calendar card within the sidebar
  2. Sets padding, radius, background, and shadow
  3. Structures the topbar, toolbar, grid, legend, and footer
*/
.mini-calendar-shell {
  position: relative;
  margin: 0.15rem 0.75rem 0.85rem 0.75rem;
}

.mini-calendar {
  position: relative;
  padding: 0.9rem;
  background:
    radial-gradient(circle at top left, rgba(79, 165, 127, 0.08), transparent 28%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(244, 248, 247, 0.98) 100%);
  border: 1px solid rgba(34, 62, 58, 0.08);
  border-radius: 20px;
  box-shadow:
    0 18px 40px rgba(31, 61, 47, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.92);
}

.mini-calendar-topbar {
  display: grid;
  grid-template-columns: 30px 1fr 30px;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.45rem;
}

.calendar-nav-button,
.calendar-close-button {
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 11px;
  background: #eef4f1;
  color: #1f3d2f;
  cursor: pointer;
  transition: all 0.18s ease;
}

.calendar-nav-button:hover:not(:disabled),
.calendar-close-button:hover {
  background: #e1ebe6;
  transform: translateY(-1px);
}

.calendar-nav-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  transform: none;
}

.mini-calendar-heading {
  text-align: center;
  min-width: 0;
}

.mini-calendar-title {
  font-size: 0.96rem;
  font-weight: 800;
  color: #183429;
  line-height: 1.15;
}

.mini-calendar-subtitle {
  margin-top: 0.14rem;
  font-size: 0.69rem;
  color: #70827a;
  line-height: 1.2;
}

.mini-calendar-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.35rem;
  margin-bottom: 0.55rem;
}

.calendar-current-button {
  border: none;
  background: transparent;
  color: #2d6a4f;
  font-size: 0.72rem;
  font-weight: 800;
  cursor: pointer;
  padding: 0.18rem 0.44rem;
  border-radius: 999px;
}

.calendar-current-button:hover:not(:disabled) {
  background: rgba(45, 106, 79, 0.08);
}

.calendar-current-button:disabled {
  color: #a3b2ab;
  cursor: default;
}

.range-hint {
  font-size: 0.62rem;
  color: #7a8a84;
  font-weight: 700;
}

.mini-calendar-weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.22rem;
  margin-bottom: 0.28rem;
}

.mini-calendar-weekdays span {
  text-align: center;
  font-size: 0.61rem;
  font-weight: 800;
  color: #76867f;
  letter-spacing: 0.02em;
}

/*
  模块 9：日历网格与状态样式
  Module 9: Calendar grid and state styles

  关键状态类：
  - .is-empty
  - .is-clickable
  - .is-today
  - .is-holiday
  - .is-event

  作用：
  1. 区分普通格、空白格、可点击格
  2. 用不同描边表达今天/节假日/事件
  3. 允许多状态叠加显示

  Key state classes:
  - .is-empty
  - .is-clickable
  - .is-today
  - .is-holiday
  - .is-event

  Purpose:
  1. Distinguishes normal cells, empty cells, and clickable cells
  2. Uses different outlines for today / holiday / event
  3. Supports combined visual states
*/
.mini-calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.26rem;
}

.mini-calendar-cell {
  aspect-ratio: 1 / 1;
  border: none;
  border-radius: 999px;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  font-weight: 700;
  color: #21352d;
  cursor: default;
  transition: transform 0.16s ease, background 0.16s ease, box-shadow 0.16s ease;
}

.mini-calendar-cell.is-empty {
  visibility: hidden;
}

.mini-calendar-cell.is-clickable {
  cursor: pointer;
}

.mini-calendar-cell.is-clickable:hover {
  transform: translateY(-1px) scale(1.04);
  background: rgba(25, 59, 45, 0.04);
}

.mini-calendar-cell.is-today {
  box-shadow: inset 0 0 0 2px #2f9e44;
}

.mini-calendar-cell.is-holiday {
  box-shadow: inset 0 0 0 2px #228be6;
}

.mini-calendar-cell.is-event {
  box-shadow: inset 0 0 0 2px #e03131;
}

.mini-calendar-cell.is-today.is-holiday {
  box-shadow:
    inset 0 0 0 2px #2f9e44,
    0 0 0 2px #228be6;
}

.mini-calendar-cell.is-today.is-event {
  box-shadow:
    inset 0 0 0 2px #2f9e44,
    0 0 0 2px #e03131;
}

.mini-calendar-cell.is-holiday.is-event {
  box-shadow:
    inset 0 0 0 2px #228be6,
    0 0 0 2px #e03131;
}

.mini-calendar-cell.is-today.is-holiday.is-event {
  box-shadow:
    inset 0 0 0 2px #2f9e44,
    0 0 0 2px #228be6,
    0 0 0 4px #e03131;
}

/*
  模块 10：日历图例与编辑按钮
  Module 10: Calendar legend and edit button

  作用：
  1. 图例解释颜色语义
  2. 管理员按钮提供进入编辑模式的入口

  Purpose:
  1. The legend explains the color semantics
  2. The admin button opens the edit mode
*/
.mini-calendar-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 0.7rem;
  justify-content: center;
  margin-top: 0.8rem;
  padding-top: 0.68rem;
  border-top: 1px solid rgba(31, 61, 47, 0.08);
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.32rem;
  font-size: 0.62rem;
  color: #61716b;
  font-weight: 700;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: transparent;
}

.legend-today {
  box-shadow: inset 0 0 0 2px #2f9e44;
}

.legend-holiday {
  box-shadow: inset 0 0 0 2px #228be6;
}

.legend-event {
  box-shadow: inset 0 0 0 2px #e03131;
}

.mini-calendar-footer {
  display: flex;
  justify-content: center;
  margin-top: 0.75rem;
}

.calendar-edit-button {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border: none;
  border-radius: 14px;
  padding: 0.52rem 0.78rem;
  background: linear-gradient(180deg, #1f6f54 0%, #18513e 100%);
  color: #ffffff;
  font-size: 0.72rem;
  font-weight: 800;
  cursor: pointer;
  box-shadow: 0 10px 22px rgba(24, 81, 62, 0.24);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.calendar-edit-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 26px rgba(24, 81, 62, 0.28);
}

/*
  模块 11：日历覆盖层与详情卡片
  Module 11: Calendar overlay and detail cards

  作用：
  1. 在日历卡片内部覆盖显示详情或编辑界面
  2. 详情卡片区分 holiday 和 event
  3. 支持空状态展示

  Purpose:
  1. Displays details or editor view as an overlay inside the calendar card
  2. Distinguishes holiday and event cards visually
  3. Supports empty-state display
*/
.calendar-overlay {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at top right, rgba(79, 165, 127, 0.08), transparent 30%),
    linear-gradient(180deg, rgba(251, 253, 252, 0.99) 0%, rgba(244, 248, 247, 0.99) 100%);
  border: 1px solid rgba(34, 62, 58, 0.08);
  border-radius: 20px;
  box-shadow:
    0 18px 40px rgba(31, 61, 47, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
  padding: 0.9rem;
  display: flex;
  flex-direction: column;
  z-index: 5;
}

.calendar-overlay-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.8rem;
}

.calendar-overlay-title {
  font-size: 0.88rem;
  font-weight: 800;
  color: #183429;
  line-height: 1.2;
}

.calendar-overlay-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.overlay-card {
  border-radius: 16px;
  padding: 0.76rem;
  margin-bottom: 0.62rem;
  background: #ffffff;
  border: 1px solid rgba(31, 61, 47, 0.08);
  box-shadow: 0 10px 18px rgba(31, 61, 47, 0.06);
}

.holiday-card {
  border-left: 4px solid #228be6;
}

.event-card {
  border-left: 4px solid #e03131;
}

.overlay-card-type {
  font-size: 0.64rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #6e7f78;
  margin-bottom: 0.3rem;
}

.overlay-card-title {
  font-size: 0.82rem;
  font-weight: 700;
  color: #1f3028;
  line-height: 1.35;
}

.overlay-empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  text-align: center;
  color: #7d8d86;
  font-size: 0.78rem;
  padding: 0.8rem;
}

/*
  模块 12：事件编辑器表单与列表
  Module 12: Event editor form and list

  作用：
  1. 为管理员提供新增、更新、删除事件的界面
  2. 表单区域用于编辑单个事件
  3. 列表区域用于查看所有可见事件并执行操作

  Purpose:
  1. Provides UI for admins to add, update, and delete events
  2. The form area edits a single event
  3. The list area shows visible events and action buttons
*/
.editor-body {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}

.editor-readonly-note {
  font-size: 0.68rem;
  color: #6f8079;
  background: rgba(34, 139, 230, 0.08);
  border: 1px solid rgba(34, 139, 230, 0.16);
  border-radius: 14px;
  padding: 0.6rem 0.68rem;
  line-height: 1.35;
}

.editor-form,
.editor-list {
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(31, 61, 47, 0.08);
  border-radius: 16px;
  padding: 0.75rem;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.88);
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 0.28rem;
  margin-bottom: 0.55rem;
}

.form-label {
  font-size: 0.66rem;
  font-weight: 800;
  color: #60726b;
}

.form-input {
  width: 100%;
  border: 1px solid #d9e3df;
  border-radius: 12px;
  padding: 0.55rem 0.64rem;
  font-size: 0.74rem;
  color: #21352d;
  background: #ffffff;
  box-sizing: border-box;
  outline: none;
  transition: border-color 0.16s ease, box-shadow 0.16s ease;
}

.form-input:focus {
  border-color: rgba(31, 111, 84, 0.24);
  box-shadow: 0 0 0 4px rgba(31, 111, 84, 0.08);
}

.editor-actions {
  display: flex;
  gap: 0.45rem;
}

.editor-primary-button,
.editor-secondary-button,
.mini-action-button {
  border: none;
  border-radius: 12px;
  padding: 0.5rem 0.68rem;
  font-size: 0.71rem;
  font-weight: 800;
  cursor: pointer;
  transition: transform 0.16s ease, opacity 0.16s ease;
}

.editor-primary-button:hover,
.editor-secondary-button:hover,
.mini-action-button:hover {
  transform: translateY(-1px);
}

.editor-primary-button {
  background: #1f6f54;
  color: white;
}

.editor-secondary-button {
  background: #edf3f0;
  color: #1f3d2f;
}

.editor-list-title {
  font-size: 0.72rem;
  font-weight: 800;
  color: #183429;
  margin-bottom: 0.55rem;
}

.editor-list-scroll {
  max-height: 180px;
  overflow-y: auto;
}

.editor-item {
  display: flex;
  justify-content: space-between;
  gap: 0.55rem;
  padding: 0.58rem 0;
  border-top: 1px solid rgba(31, 61, 47, 0.08);
}

.editor-item:first-child {
  border-top: none;
  padding-top: 0;
}

.editor-item-main {
  min-width: 0;
}

.editor-type-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.18rem 0.42rem;
  border-radius: 999px;
  font-size: 0.58rem;
  font-weight: 800;
  margin-bottom: 0.26rem;
}

.chip-event {
  background: rgba(224, 49, 49, 0.12);
  color: #c92a2a;
}

.editor-item-date {
  font-size: 0.65rem;
  color: #7b8d86;
  margin-bottom: 0.18rem;
}

.editor-item-title {
  font-size: 0.73rem;
  color: #1f3028;
  line-height: 1.3;
  word-break: break-word;
}

.editor-item-actions {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.mini-action-button {
  background: #edf3f0;
  color: #1f3d2f;
}

.mini-action-button.danger {
  background: rgba(224, 49, 49, 0.1);
  color: #c92a2a;
}

/*
  模块 13：账号菜单面板
  Module 13: Account menu panel

  作用：
  1. 固定在右上角显示
  2. 展示账户摘要
  3. 提供快捷入口
  4. 提供退出按钮

  Purpose:
  1. Appears fixed near the top-right
  2. Shows account summary
  3. Provides quick links
  4. Provides logout action
*/
.notification-panel {
  position: fixed;
  top: 92px;
  right: 18px;
  width: 330px;
  max-width: calc(100vw - 24px);
  border-radius: 22px;
  overflow: hidden;
  background:
    radial-gradient(circle at top right, rgba(79, 165, 127, 0.1), transparent 30%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(246, 250, 248, 0.98) 100%);
  border: 1px solid rgba(22, 49, 38, 0.08);
  box-shadow:
    0 24px 60px rgba(18, 44, 33, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.92);
  z-index: 40;
  backdrop-filter: blur(18px);
}

.notification-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 1rem 1rem 0.85rem;
  border-bottom: 1px solid rgba(22, 49, 38, 0.08);
}

.account-summary {
  display: flex;
  align-items: center;
  gap: 0.82rem;
  min-width: 0;
}

.account-avatar {
  width: 46px;
  height: 46px;
  border-radius: 16px;
  background:
    radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.22), transparent 35%),
    linear-gradient(180deg, var(--brand-500) 0%, var(--brand-700) 100%);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  box-shadow: 0 12px 24px rgba(24, 81, 62, 0.22);
}

.account-copy {
  min-width: 0;
}

.notification-title {
  margin: 0;
  font-size: 0.95rem;
  color: var(--text-strong);
  font-weight: 800;
  line-height: 1.15;
}

.account-subtitle {
  margin: 0.2rem 0 0;
  font-size: 0.72rem;
  color: var(--text-soft);
  line-height: 1.35;
  font-weight: 600;
}

.close-button {
  background: none;
  border: none;
  color: var(--text-main);
  cursor: pointer;
}

.account-close-button {
  width: 34px;
  height: 34px;
  border-radius: 12px;
  background: #eef4f1;
  flex-shrink: 0;
}

.notification-panel-section {
  padding: 0.8rem;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.panel-quick-link {
  display: flex;
  align-items: center;
  gap: 0.72rem;
  width: 100%;
  border: none;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.86) 0%, rgba(241, 246, 244, 0.9) 100%);
  border: 1px solid rgba(22, 49, 38, 0.08);
  border-radius: 16px;
  padding: 0.78rem;
  cursor: pointer;
  text-align: left;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.panel-quick-link:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 24px rgba(18, 44, 33, 0.08);
  background: #ffffff;
}

.panel-quick-icon {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: rgba(31, 111, 84, 0.1);
  color: var(--brand-700);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.panel-quick-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.panel-quick-copy strong {
  font-size: 0.82rem;
  color: var(--text-strong);
  line-height: 1.2;
}

.panel-quick-copy small {
  margin-top: 0.16rem;
  font-size: 0.7rem;
  color: var(--text-soft);
  line-height: 1.3;
}

.notification-panel-footer {
  padding: 0 0.8rem 0.9rem;
}

.logout-button {
  width: 100%;
  border: none;
  border-radius: 16px;
  padding: 0.82rem 0.95rem;
  background: linear-gradient(180deg, #1f6f54 0%, #18513e 100%);
  color: #ffffff;
  font-weight: 800;
  font-size: 0.78rem;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.48rem;
  box-shadow: 0 12px 28px rgba(24, 81, 62, 0.24);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.logout-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 30px rgba(24, 81, 62, 0.28);
}

.notification-item-icon {
  margin-right: 0.5rem;
  color: var(--brand-700);
}

/*
  模块 14：过渡动画
  Module 14: Transition animations

  作用：
  1. 日历 overlay 和用户菜单淡入淡出
  2. 轻微位移和缩放，避免生硬

  Purpose:
  1. Fades calendar overlay and user menu in/out
  2. Adds subtle translation and scale for smoother transitions
*/
.calendar-fade-enter-active,
.calendar-fade-leave-active,
.menu-fade-enter-active,
.menu-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.calendar-fade-enter-from,
.calendar-fade-leave-to,
.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(4px) scale(0.985);
}

/*
  模块 15：响应式适配
  Module 15: Responsive layout adjustments

  断点说明：
  - 1024px：适当压缩搜索宽度、隐藏 logo 副标题
  - 768px：切换成移动端纵向布局，Sidebar 不再 sticky

  Breakpoints:
  - 1024px: reduce search width and hide the logo subtitle
  - 768px: switch to a mobile-friendly stacked layout, Sidebar is no longer sticky
*/
@media (max-width: 1024px) {
  .search-shell {
    max-width: 500px;
  }

  .search-input-wrap {
    max-width: 240px;
  }

  .logo-subtext {
    display: none;
  }
}

@media (max-width: 768px) {
  .header-content {
    flex-wrap: wrap;
    padding: 0.75rem 0.85rem;
    min-height: auto;
  }

  .header-right {
    width: 100%;
    margin-left: 0;
    justify-content: space-between;
    gap: 0.6rem;
  }

  .search-shell {
    flex: 1 1 auto;
    width: 100%;
    max-width: none;
    min-width: 0;
  }

  .search-scope-wrap {
    flex: 0 0 82px;
  }

  .search-input-wrap {
    flex: 1 1 auto;
    width: auto;
    min-width: 0;
    max-width: none;
  }

  .main-layout {
    flex-direction: column;
    min-height: auto;
  }

  .sidebar {
    position: static;
    top: auto;
    align-self: auto;
    height: auto;
    width: 100%;
    min-width: 100%;
    overflow-y: visible;
  }

  .main-content {
    width: 100%;
    padding: 0.85rem;
  }

  .mini-calendar-shell {
    margin-top: 0.5rem;
  }

  .notification-panel {
    top: 88px;
    right: 12px;
    left: 12px;
    width: auto;
    max-width: none;
  }
}
</style>