<template>
  <!--
    最外层页面容器
    作用：
    1. 作为整个 Dashboard 页面的根节点
    2. 承载全局页面布局类名
    3. 通过 :style="dashboardThemeStyle" 动态注入主题样式
       例如：
       - 切换不同背景主题时，这里可能改变背景渐变、主色调、阴影色
  -->
  <div class="content-area dashboard-page-shell" :style="dashboardThemeStyle">

    <!--
      页面内部主包裹层
      作用：
      1. 限制内容最大宽度
      2. 统一控制内容的内边距、居中方式、纵向排列
      3. 作为所有 Dashboard 功能区块的直接父容器
    -->
    <div class="dashboard-page-inner">

      <!--
        背景装饰元素 1
        作用：
        - 提供视觉氛围，不承载业务逻辑
        - 通常表现为发光圆球、模糊渐变球等
      -->
      <div class="dashboard-backdrop-orb orb-one"></div>

      <!--
        背景装饰元素 2
        作用：
        - 与 orb-one 配合形成层次感
        - 一般通过不同位置、大小、透明度制造高级感
      -->
      <div class="dashboard-backdrop-orb orb-two"></div>

      <!--
        背景网格层
        作用：
        - 增强页面科技感/结构感
        - 常见于管理后台、数据看板、平台型产品
      -->
      <div class="dashboard-backdrop-grid"></div>

      <!--
        粒子效果层
        作用：
        - 用于叠加粒子、轻微动态背景、浮动光点等
        - 纯展示层，不直接参与业务
      -->
      <div class="dashboard-particle-layer"></div>

      <!--
        Hero 区域外层 section
        作用：
        - 展示 Dashboard 的最核心欢迎区
        - 一般放用户身份信息、当前阶段、重点入口、轮播展示等
      -->
      <section class="dashboard-hero-shell">

        <!--
          Hero 主卡片
          作用：
          1. 作为头部欢迎模块的主要视觉承载体
          2. 包含主题切换入口、欢迎文案、角色信息、展示轮播、关键指标
        -->
        <div class="dashboard-hero-card">

          <!--
            主题切换侧边控制区
            作用：
            - 提供主题/背景切换入口
            - 允许用户切换当前 Dashboard 的视觉风格
          -->
          <div class="dashboard-theme-rail">

            <!--
              主题切换按钮
              作用：
              - 点击后展开/收起主题面板
            相关引用：
            - ref="themeTriggerRef"
              作用：保存按钮 DOM 引用
              常见用途：
              1. 配合点击外部关闭逻辑
              2. 做定位或焦点控制
            相关方法：
            - toggleThemeRail
              作用：切换 isThemeRailOpen 的布尔值
              常见逻辑：
              isThemeRailOpen = !isThemeRailOpen
            -->
            <button
              ref="themeTriggerRef"
              type="button"
              class="theme-rail-trigger"
              @click.stop="toggleThemeRail"
            >
              <!-- 调色盘图标，仅作视觉提示 -->
              <i class="fas fa-palette"></i>
              <!-- 按钮文字，说明这是主题设置入口 -->
              <span>Theme</span>
            </button>

            <!--
              主题面板展开/收起动画
              作用：
              - 提高交互自然度
              - 使用 theme-rail-panel 过渡名称对应 CSS transition 动画
            -->
            <transition name="theme-rail-panel">

              <!--
                主题面板主体
                显示条件：
                - v-if="isThemeRailOpen"
                  当主题面板处于打开状态时显示
                相关变量：
                - isThemeRailOpen
                  类型：Boolean
                  含义：当前主题列表面板是否展开
                  示例：
                  true  -> 显示主题列表
                  false -> 隐藏主题列表
                - ref="themeRailRef"
                  用途：保存面板 DOM 引用，用于点击外部关闭等逻辑
              -->
              <div
                v-if="isThemeRailOpen"
                ref="themeRailRef"
                class="theme-rail-panel"
                @click.stop
              >

                <!--
                  主题选项列表容器
                  作用：
                  - 包裹所有可选背景主题按钮
                -->
                <div class="theme-rail-list">

                  <!--
                    单个主题按钮
                    数据来源：
                    - backgroundOptions
                      类型通常是数组
                      例如：
                      [
                        { key: 'emerald', label: 'Emerald' },
                        { key: 'midnight', label: 'Midnight' },
                        { key: 'biotech', label: 'Biotech' }
                      ]
                      用途：定义所有可切换的主题项
                    相关变量：
                    - item.key
                      唯一标识主题，例如 'emerald'
                    - item.label
                      展示给用户的主题名称，例如 'Emerald'
                    - selectedBackgroundKey
                      当前已选中的主题 key
                      例如：
                      'emerald' / 'midnight'
                    相关方法：
                    - handleBackgroundChange(item.key)
                      作用：切换当前主题
                      可能还会同步到 localStorage，确保刷新后保留主题
                  -->
                  <button
                    v-for="item in backgroundOptions"
                    :key="item.key"
                    type="button"
                    class="theme-rail-item simple-theme-item"
                    :class="{ active: selectedBackgroundKey === item.key }"
                    @click="handleBackgroundChange(item.key)"
                  >
                    {{ item.label }}
                  </button>
                </div>
              </div>
            </transition>
          </div>

          <!--
            Hero 主体区
            作用：
            - 左侧放欢迎信息与身份信息
            - 右侧放轮播展示卡片
          -->
          <div class="dashboard-hero-main">

            <!--
              Hero 左侧文案区
              作用：
              - 用于向用户传递当前页面最重要的身份、时间、状态和引导信息
            -->
            <div class="dashboard-hero-copy">

              <!--
                眉标题与组织名一行
                作用：
                - 通常展示小标题和平台归属信息
              -->
              <div class="hero-eyebrow-row">

                <!--
                  heroEyebrow
                  含义：Hero 区顶部的小标题
                  示例：
                  - 'Dashboard'
                  - 'Student Workspace'
                  - 'Mentor Console'
                -->
                <span class="hero-eyebrow">{{ heroEyebrow }}</span>

                <!--
                  organizationLabel
                  含义：组织/平台名称
                  示例：
                  - 'BIOTech Futures Hub'
                  - 'Global Mentoring Platform'
                -->
                <span class="hero-org">{{ organizationLabel }}</span>
              </div>

              <!--
                欢迎标题
                displayName
                含义：当前登录用户的显示名称
                示例：
                - 'Shiqi'
                - 'Alex Chen'
                - 'Dr. Brown'
                作用：
                - 增强个性化体验
                - 帮用户确认当前登录身份
              -->
              <h1 class="hero-title">Welcome back, {{ displayName }}</h1>

              <!--
                次级信息文本
                作用：
                - 汇总展示当前日期、所属 Track、当前 Role
                相关变量：
                - currentDateText
                  示例：'31 Mar 2026'
                - displayTrack
                  含义：用户当前所属培养路径/项目方向
                  示例：
                  'Entrepreneurship'
                  'Research'
                  'Leadership'
                - roleLabel
                  含义：当前用户角色名称
                  示例：
                  'Student'
                  'Mentor'
                  'Supervisor'
                  'Administrator'
              -->
              <p class="dashboard-subtext">
                {{ currentDateText }} · Track: {{ displayTrack }} · Role: {{ roleLabel }}
              </p>

              <!--
                Hero 主消息文案
                heroMessage
                含义：根据角色、阶段、状态动态生成的欢迎语/提醒语
                示例：
                - 'You have two mentoring tasks pending this week.'
                - 'Your team review closes on Friday.'
                - 'Review platform activity and pending approvals.'
                作用：
                - 让不同角色看到定制化提示
              -->
              <p class="dashboard-hero-message">
                {{ heroMessage }}
              </p>

              <!--
                顶部状态标签容器
                作用：
                - 展示若干重点状态信息
                - 常用于快速扫描当前系统状态
                数据来源：
                - headerHighlights
                  类型通常为数组
                  例如：
                  [
                    { key: 'cohort', label: 'Cohort Active' },
                    { key: 'mentors', label: '12 Mentors Online' },
                    { key: 'deadline', label: 'Review due Friday' }
                  ]
              -->
              <div class="hero-highlight-wrap">
                <span
                  v-for="item in headerHighlights"
                  :key="item.key"
                  class="status-pill"
                >
                  {{ item.label }}
                </span>
              </div>
            </div>

            <!--
              Hero 右侧展示区
              作用：
              - 放一个轮播展示卡片
              - 用于展示平台亮点、活动、图片、官方资讯等
            -->
            <div class="dashboard-hero-aside">

              <!--
                当存在当前展示项时才渲染展示卡片
                activeShowcaseItem
                含义：当前轮播激活的展示对象
                类型通常是对象，例如：
                {
                  id: 1,
                  title: 'Global Innovation Summit',
                  summary: 'Explore upcoming biotech-led initiatives...',
                  image: 'https://...',
                  link: 'https://...'
                }
              -->
              <div
                v-if="activeShowcaseItem"
                class="showcase-card"
                @mouseenter="stopShowcaseAutoplay"
                @mouseleave="startShowcaseAutoplay"
              >
                <!--
                  鼠标进入卡片时停止自动轮播
                  stopShowcaseAutoplay
                  作用：
                  - 防止用户阅读时自动切换内容
                  鼠标离开时恢复轮播
                  startShowcaseAutoplay
                  作用：
                  - 继续自动切换展示项
                -->

                <!-- 轮播头部：标题说明 + 左右切换按钮 -->
                <div class="showcase-heading-row">
                  <div>
                    <!-- 小标题 -->
                    <div class="showcase-kicker">BIOTECH HIGHLIGHTS</div>

                    <!-- 次说明 -->
                    <div class="showcase-mini-label">Official-style image and info rotation</div>
                  </div>

                  <!--
                    左右切换控制区
                    相关方法：
                    - goToPrevShowcase：切换到上一项
                    - goToNextShowcase：切换到下一项
                  -->
                  <div class="showcase-controls">
                    <button type="button" class="showcase-nav-btn" @click="goToPrevShowcase">
                      <i class="fas fa-chevron-left"></i>
                    </button>
                    <button type="button" class="showcase-nav-btn" @click="goToNextShowcase">
                      <i class="fas fa-chevron-right"></i>
                    </button>
                  </div>
                </div>

                <!--
                  轮播主体切换动画
                  mode="out-in"
                  作用：
                  - 先让旧内容离开，再显示新内容
                  - 避免图片和文字同时闪动
                -->
                <transition name="showcase-fade" mode="out-in">

                  <!--
                    当前轮播项主体
                    :key="activeShowcaseItem.id"
                    作用：
                    - 告诉 Vue 当前展示项发生变化时要重新渲染并触发过渡
                  -->
                  <div :key="activeShowcaseItem.id" class="showcase-body">

                    <!--
                      展示图片区域
                      activeShowcaseItem.image
                      含义：当前轮播项的背景图地址
                      用法：
                      backgroundImage: `url(...)`
                    -->
                    <div
                      class="showcase-image"
                      :style="{ backgroundImage: `url(${activeShowcaseItem.image})` }"
                    >
                      <!-- 图片遮罩层，提升文字对比度 -->
                      <div class="showcase-image-overlay"></div>
                    </div>

                    <!-- 展示文案区 -->
                    <div class="showcase-copy">

                      <!-- 当前轮播项标题 -->
                      <h3 class="showcase-title">{{ activeShowcaseItem.title }}</h3>

                      <!-- 当前轮播项摘要 -->
                      <p class="showcase-summary">{{ activeShowcaseItem.summary }}</p>

                      <!--
                        底部区域：轮播点 + Explore 按钮
                      -->
                      <div class="showcase-footer">

                        <!--
                          轮播圆点容器
                          数据来源：
                          - biotechShowcaseItems
                            所有轮播项数组
                          - activeShowcaseIndex
                            当前轮播索引
                            例如：
                            0 表示第一项
                            1 表示第二项
                        -->
                        <div class="showcase-dots">
                          <button
                            v-for="(item, index) in biotechShowcaseItems"
                            :key="item.id || index"
                            type="button"
                            class="showcase-dot"
                            :class="{ active: index === activeShowcaseIndex }"
                            @click="goToShowcase(index)"
                          ></button>
                        </div>

                        <!--
                          Explore 按钮
                          相关方法：
                          - openShowcaseLink(activeShowcaseItem)
                            作用：打开当前轮播项关联链接
                            可能逻辑：
                            window.open(activeShowcaseItem.link, '_blank')
                        -->
                        <button
                          type="button"
                          class="showcase-link-btn"
                          @click="openShowcaseLink(activeShowcaseItem)"
                        >
                          Explore
                          <i class="fas fa-arrow-right"></i>
                        </button>
                      </div>
                    </div>
                  </div>
                </transition>
              </div>
            </div>
          </div>

          <!--
            Hero 底部指标区
            作用：
            - 用三格摘要方式展示当前用户最重要的三个关键信息
            - 属于“快速浏览”信息层
          -->
          <div class="hero-bottom-metrics">

            <!-- Workspace 指标 -->
            <div class="hero-metric">
              <span class="hero-metric-label">Workspace</span>

              <!--
                roleLabel
                这里表示当前工作空间归属角色
                例如：
                Student / Mentor / Admin
              -->
              <strong class="hero-metric-value">{{ roleLabel }}</strong>
            </div>

            <!-- Track 指标 -->
            <div class="hero-metric">
              <span class="hero-metric-label">Track</span>

              <!--
                displayTrack
                表示当前培养路径或项目分组
              -->
              <strong class="hero-metric-value">{{ displayTrack }}</strong>
            </div>

            <!-- 下一里程碑指标 -->
            <div class="hero-metric">
              <span class="hero-metric-label">Next milestone</span>

              <!--
                progressSnapshot.nextMilestone
                含义：进度快照对象中的下一目标名称
                progressSnapshot 可能结构示例：
                {
                  completionRate: 68,
                  completedTasks: 17,
                  totalTasks: 25,
                  currentWeek: 'Week 7',
                  nextMilestone: 'Mid-term Review',
                  nextMilestoneDate: '2026-04-08'
                }
              -->
              <strong class="hero-metric-value">{{ progressSnapshot.nextMilestone }}</strong>
            </div>
          </div>
        </div>
      </section>

      <!--
        错误提示条
        显示条件：
        - v-if="loadError"
        含义：
        - 当 Dashboard 数据加载失败、接口报错、解析异常时展示
        变量：
        - loadError
          类型：String
          示例：
          'Failed to load dashboard data.'
          'Unable to fetch current user profile.'
      -->
      <div v-if="loadError" class="dashboard-alert">
        <i class="fas fa-circle-info"></i>
        <span>{{ loadError }}</span>
      </div>

      <!--
        第一块内容区：摘要卡片区
        作用：
        - 用多个统计摘要卡片展示核心业务指标
        - 适合给用户建立“我当前的整体状态”的第一印象
      -->
      <section class="dashboard-section">
        <div class="dashboard-section-grid summary-grid">

          <!--
            单个摘要卡片
            数据来源：
            - summaryWidgets
              类型通常为数组
              每个元素示例：
              {
                key: 'groups',
                title: 'Active Groups',
                value: 6,
                subtext: '2 need attention',
                icon: 'fas fa-users',
                accent: 'emerald'
              }
            变量说明：
            - item.key
              卡片唯一键
            - item.icon
              图标类名
            - item.title
              卡片标题
            - item.value
              主值，例如数字或状态值
            - item.subtext
              对主值的补充说明
            - item.accent
              强调色标识，用于决定卡片视觉风格
            方法：
            - getAccentClass(item.accent)
              作用：把 accent 值转成 CSS 类名
              例如：
              'emerald' -> 'accent-emerald'
          -->
          <article
            v-for="item in summaryWidgets"
            :key="item.key"
            class="summary-card"
            :class="getAccentClass(item.accent)"
          >
            <div class="summary-card-top">
              <div class="summary-icon-wrap">
                <i :class="item.icon"></i>
              </div>
              <span class="summary-label">{{ item.title }}</span>
            </div>

            <div class="summary-card-value">{{ item.value }}</div>
            <div class="summary-card-subtext">{{ item.subtext }}</div>
          </article>
        </div>
      </section>

      <!--
        第二块内容区：行动中心 + 进度快照
        作用：
        - 左边：引导用户快速进入最重要任务
        - 右边：用可视化方式展示当前整体进度
      -->
      <section class="dashboard-section">
        <div class="dashboard-section-grid two-col-layout">

          <!--
            行动中心卡片
            作用：
            - 汇总优先操作入口
            - 让用户少思考，直接点击执行下一步
          -->
          <article class="surface-card feature-card action-card">
            <div class="surface-card-header">
              <div>
                <p class="surface-kicker">Priority</p>

                <!--
                  actionCenterTitle
                  含义：行动中心标题
                  可能根据角色变化
                  示例：
                  - 'Action Center'
                  - 'Mentor Tasks'
                  - 'Admin Queue'
                -->
                <h3 class="surface-card-title">{{ actionCenterTitle }}</h3>
              </div>
            </div>

            <!--
              行动项列表
              数据来源：
              - actionCenter
                类型通常为数组
                示例：
                [
                  {
                    key: 'review',
                    label: 'Review pending matches',
                    helper: '3 items require approval'
                  }
                ]
            -->
            <div class="action-center-list">
              <button
                v-for="action in actionCenter"
                :key="action.key"
                type="button"
                class="action-center-item"
                @click="handleActionClick(action)"
              >
                <span class="action-center-content">

                  <!-- action.label：主操作名称 -->
                  <span class="action-center-main">{{ action.label }}</span>

                  <!-- action.helper：辅助说明，告诉用户点进去会做什么 -->
                  <span class="action-center-helper">{{ action.helper }}</span>
                </span>

                <span class="action-center-arrow">
                  <i class="fas fa-arrow-right"></i>
                </span>
              </button>
            </div>
          </article>

          <!--
            进度快照卡片
            作用：
            - 用圆环、进度条、关键字段概括当前项目/培养计划完成情况
          -->
          <article class="surface-card feature-card progress-card">
            <div class="surface-card-header">
              <div>
                <p class="surface-kicker">Overview</p>
                <h3 class="surface-card-title">Progress Snapshot</h3>
              </div>
            </div>

            <div class="progress-layout">

              <!--
                左侧圆环区域
                progressCircleStyle
                含义：圆环的动态样式
                常见做法：
                - conic-gradient 根据 completionRate 生成圆环填充效果
                示例：
                {
                  background: `conic-gradient(#38b2ac 0% 68%, rgba(...) 68% 100%)`
                }
              -->
              <div class="progress-ring-shell">
                <div class="progress-ring" :style="progressCircleStyle">
                  <div class="progress-ring-inner">

                    <!-- 当前完成百分比 -->
                    <div class="progress-value">{{ progressSnapshot.completionRate }}%</div>

                    <!-- 固定标签 -->
                    <div class="progress-label">Completion</div>
                  </div>
                </div>
              </div>

              <!-- 右侧进度明细 -->
              <div class="progress-details">

                <!-- 已完成任务数 / 总任务数 -->
                <div class="progress-detail-row">
                  <span>Tasks</span>
                  <strong>{{ progressSnapshot.completedTasks }}/{{ progressSnapshot.totalTasks }}</strong>
                </div>

                <!-- 当前阶段 -->
                <div class="progress-detail-row">
                  <span>Current stage</span>
                  <strong>{{ progressSnapshot.currentWeek }}</strong>
                </div>

                <!-- 下一里程碑 -->
                <div class="progress-detail-row">
                  <span>Next milestone</span>
                  <strong>{{ progressSnapshot.nextMilestone }}</strong>
                </div>

                <!--
                  下一里程碑日期
                  formatEventDate(progressSnapshot.nextMilestoneDate)
                  作用：
                  - 把原始日期格式化成更适合展示的文本
                  示例：
                  '2026-04-08' -> '08 Apr 2026'
                -->
                <div class="progress-detail-row">
                  <span>Due</span>
                  <strong>{{ formatDateAU(progressSnapshot.nextMilestoneDate) || 'TBC' }}</strong>
                </div>

                <!--
                  线性进度条
                  progressPercentStyle
                  含义：进度条填充样式
                  典型示例：
                  { width: '68%' }
                -->
                <div class="progress-bar-shell">
                  <div class="progress-bar-fill" :style="progressPercentStyle"></div>
                </div>
              </div>
            </div>
          </article>
        </div>
      </section>

      <!--
        第三块内容区：下一事件 + 公告
        作用：
        - 左边突出最近事件
        - 右边展示最近公告更新
      -->
      <section class="dashboard-section">
        <div class="dashboard-section-grid two-col-layout">

          <!-- 下一事件卡片 -->
          <article class="surface-card">
            <div class="surface-card-header">
              <div>
                <p class="surface-kicker">Calendar</p>
                <h3 class="surface-card-title">Next Event</h3>
              </div>

              <!-- 跳转到完整事件页 -->
              <RouterLink to="/events" class="surface-link">Open calendar</RouterLink>
            </div>

            <!--
              当存在 nextEvent 时显示事件详情
              nextEvent 可能示例：
              {
                title: 'Mentor Matching Session',
                date: '2026-04-06',
                time: '14:00 - 15:30',
                mode: 'Online',
                location: 'Zoom Room A'
              }
            -->
            <div v-if="nextEvent" class="event-detail-card">

              <!--
                日期徽章
                formatEventDate(nextEvent.date).split(' ')
                作用：
                - 把格式化日期拆成“日期主体”和“剩余部分”
                例如：
                '06 Apr 2026' 拆成：
                [0] => '06'
                [1...] => 'Apr 2026'
              -->
              <div class="event-date-badge">
                <span class="event-date-day">{{ nextEventDateParts.day }}</span>
                <span class="event-date-rest">{{ nextEventDateParts.rest }}</span>
              </div>

              <div class="event-content">
                <!-- 事件标题 -->
                <div class="event-title">{{ nextEvent.title }}</div>

                <!-- 事件时间与模式 -->
                <div class="event-meta-row">
                  <span><i class="fas fa-clock"></i>{{ nextEvent.time || 'Time TBC' }}</span>
                  <span><i class="fas fa-layer-group"></i>{{ nextEvent.mode || 'Hybrid' }}</span>
                </div>

                <!-- 事件地点 -->
                <div class="event-meta-row location-row">
                  <span><i class="fas fa-location-dot"></i>{{ nextEvent.location || 'Location TBC' }}</span>
                </div>

                <!--
                  按角色显示不同按钮文案
                  相关变量：
                  - isAdmin
                    是否平台管理员
                  - isTeacher
                    是否导师/教师角色
                  逻辑：
                  平台管理员 -> Manage event
                  导师 -> Open session
                  其他 -> View event
                -->
                <div class="event-actions">
                  <RouterLink to="/events" class="primary-chip">
                    {{ isAdmin ? 'Manage event' : isTeacher ? 'Open session' : 'View event' }}
                  </RouterLink>
                </div>
              </div>
            </div>

            <!-- 无事件时的空状态 -->
            <div v-else class="empty-state">
              <i class="fas fa-calendar-xmark"></i>
              <p>No upcoming event is available yet.</p>
            </div>
          </article>

          <!-- 公告卡片 -->
          <article class="surface-card">
            <div class="surface-card-header">
              <div>
                <p class="surface-kicker">Updates</p>

                <!--
                  announcementsSectionTitle
                  含义：公告区标题
                  可能根据角色不同变化
                  示例：
                  - 'Announcements'
                  - 'Platform Updates'
                  - 'Latest Notices'
                -->
                <h3 class="surface-card-title">{{ announcementsSectionTitle }}</h3>
              </div>
              <RouterLink to="/announcements" class="surface-link">View all</RouterLink>
            </div>

            <!-- announcementsPreview：公告预览数组 -->
            <div v-if="announcementsPreview.length" class="list-stack">
              <RouterLink
                v-for="announcement in announcementsPreview"
                :key="announcement.id || getAnnouncementTitle(announcement)"
                to="/announcements"
                class="list-row premium-row"
              >
                <div class="list-row-icon announcement-icon">
                  <i class="fas fa-bullhorn"></i>
                </div>

                <div class="list-row-content">
                  <!-- 获取公告标题 -->
                  <div class="list-row-title">{{ getAnnouncementTitle(announcement) }}</div>

                  <!--
                    getAnnouncementMeta(announcement)
                    先取原始时间信息，再由 formatAnnouncementDate 格式化
                  -->
                  <div class="list-row-meta">{{ formatAnnouncementDateAU(getAnnouncementMeta(announcement)) }}</div>

                  <!-- 获取公告摘要 -->
                  <div class="list-row-description">{{ getAnnouncementSnippet(announcement) }}</div>
                </div>

                <div class="list-row-tail">
                  <i class="fas fa-chevron-right"></i>
                </div>
              </RouterLink>
            </div>

            <!-- 无公告时的空状态 -->
            <div v-else class="empty-state">
              <i class="fas fa-bell-slash"></i>
              <p>No recent announcements are available yet.</p>
            </div>
          </article>
        </div>
      </section>

      <!--
        第四块内容区：小组预览
        作用：
        - 展示当前用户最相关的几个小组
        - 帮助快速进入小组详情
      -->
      <section class="dashboard-section">
        <article class="surface-card">
          <div class="surface-card-header">
            <div>
              <p class="surface-kicker">Groups</p>
              <h3 class="surface-card-title">{{ groupsSectionTitle }}</h3>
            </div>
            <RouterLink to="/groups" class="surface-link">View all</RouterLink>
          </div>

          <!-- groupsPreview：小组预览数据 -->
          <div v-if="groupsPreview.length" class="groups-grid">
            <RouterLink
              v-for="group in groupsPreview"
              :key="group.id || getGroupName(group)"
              :to="group.id ? '/groups/' + group.id : '/groups'"
              class="group-card-link"
            >
              <div class="group-card-surface">

                <!-- 小组卡片顶部：头像组 + 外链提示 -->
                <div class="group-card-top">
                  <div class="group-avatars">

                    <!--
                      主头像
                      getInitials(getGroupName(group))
                      作用：
                      - 从小组名称中提取首字母
                      示例：
                      'Bio Leaders' -> 'BL'
                    -->
                    <div class="group-avatar primary-avatar">
                      {{ getInitials(getGroupName(group)) }}
                    </div>

                    <!--
                      次头像
                      getGroupSecondaryLabel(group)
                      含义：
                      - 用简短文字补充小组信息
                      可能是小组类型、导师简称、方向标签等
                    -->
                    <div class="group-avatar secondary-avatar">
                      {{ getGroupSecondaryLabel(group) }}
                    </div>

                    <!--
                      第三头像
                      显示“除前两位之外还有多少成员”
                      例如总人数 5，则显示 +3
                    -->
                    <div class="group-avatar tertiary-avatar">
                      +{{ Math.max(getGroupMemberCount(group) - 2, 0) }}
                    </div>
                  </div>

                  <span class="group-open-indicator">
                    <i class="fas fa-arrow-up-right-from-square"></i>
                  </span>
                </div>

                <!-- 小组名 -->
                <div class="group-name">{{ getGroupName(group) }}</div>

                <!--
                  小组元信息
                  - 成员数量
                  - 负责人
                -->
                <div class="group-meta">{{ getGroupMemberCount(group) }} members · Lead: {{ getGroupLead(group) }}</div>
              </div>
            </RouterLink>
          </div>

          <!-- 无小组时空状态 -->
          <div v-else class="empty-state">
            <i class="fas fa-users-slash"></i>
            <p>No group is available yet.</p>
          </div>
        </article>
      </section>

      <!--
        第五块内容区：资源库 + 清单
        作用：
        - 左边展示资源入口
        - 右边展示当前建议处理的 checklist
      -->
      <section class="dashboard-section">
        <div class="dashboard-section-grid two-col-layout">

          <!-- 资源库卡片 -->
          <article class="surface-card">
            <div class="surface-card-header">
              <div>
                <p class="surface-kicker">Library</p>
                <h3 class="surface-card-title">{{ resourcesSectionTitle }}</h3>
              </div>
              <RouterLink to="/resources" class="surface-link">View all</RouterLink>
            </div>

            <!-- resourcesPreview：资源预览数组 -->
            <div v-if="resourcesPreview.length" class="resource-grid">
              <RouterLink
                v-for="resource in resourcesPreview"
                :key="resource.id || getResourceTitle(resource)"
                :to="resource.id ? '/resources/' + resource.id : '/resources'"
                class="resource-card-link"
              >
                <div class="resource-card-surface">

                  <!--
                    资源图标
                    getResourceIcon(resource.type)
                    根据资源类型返回不同图标
                    示例：
                    pdf -> fas fa-file-pdf
                    video -> fas fa-video
                    article -> fas fa-newspaper
                  -->
                  <div class="resource-icon">
                    <i :class="getResourceIcon(resource.type)"></i>
                  </div>

                  <div class="resource-content">
                    <!-- 资源标题 -->
                    <div class="resource-title">{{ getResourceTitle(resource) }}</div>

                    <!--
                      资源元信息
                      getResourceCategory(resource)
                      例如：
                      'Guide'
                      'Template'
                      'Case Study'
                      getResourceMeta(resource)
                      例如：
                      '2 days ago'
                      '31 Mar 2026'
                    -->
                    <div class="resource-meta">
                      {{ getResourceCategory(resource) }} · Updated {{ getResourceMeta(resource) }}
                    </div>
                  </div>
                </div>
              </RouterLink>
            </div>

            <!-- 无资源时空状态 -->
            <div v-else class="empty-state">
              <i class="fas fa-folder-open"></i>
              <p>No resource is available yet.</p>
            </div>
          </article>

          <!-- 清单卡片 -->
          <article class="surface-card">
            <div class="surface-card-header">
              <div>
                <p class="surface-kicker">Checklist</p>
                <h3 class="surface-card-title">{{ checklistSectionTitle }}</h3>
              </div>
            </div>

            <!--
              checklistItems：清单项数组
              典型元素示例：
              {
                key: 'profile',
                title: 'Complete your profile',
                meta: 'Required before mentor matching',
                to: '/profile'
              }
            -->
            <div class="list-stack">
              <RouterLink
                v-for="item in checklistItems"
                :key="item.key"
                :to="item.to"
                class="list-row premium-row checklist-row"
              >
                <div class="list-row-icon checklist-icon">
                  <i class="fas fa-list-check"></i>
                </div>

                <div class="list-row-content">
                  <div class="list-row-title">{{ item.title }}</div>
                  <div class="list-row-meta">{{ item.meta }}</div>
                </div>

                <div class="list-row-tail">
                  <i class="fas fa-chevron-right"></i>
                </div>
              </RouterLink>
            </div>
          </article>
        </div>
      </section>

      <!--
        第六块内容区：时间线
        作用：
        - 用于展示项目/培养流程中的阶段路线图
        - 帮用户理解当前所处阶段与后续节点
      -->
      <section class="dashboard-section">
        <article class="surface-card">
          <div class="surface-card-header">
            <div>
              <p class="surface-kicker">Roadmap</p>
              <h3 class="surface-card-title">Program Timeline</h3>
            </div>
          </div>

          <!--
            时间线列表
            数据来源：
            - timelineItems
              类型通常为数组
              示例：
              [
                { key: 'wk1', label: '01', title: 'Onboarding', status: 'Completed' },
                { key: 'wk2', label: '02', title: 'Team Matching', status: 'In Progress' },
                { key: 'wk3', label: '03', title: 'Pitch Review', status: 'Upcoming' }
              ]
            变量说明：
            - item.label
              显示在线路上的简短编号或阶段号
            - item.title
              阶段名称
            - item.status
              阶段状态
              常见值：
              'Completed'
              'In Progress'
              'Upcoming'
            方法：
            - getTimelineStatusClass(item.status)
              把状态映射为不同样式类
          -->
          <div class="timeline-list">
            <div
              v-for="item in timelineItems"
              :key="item.key"
              class="timeline-item"
              :class="getTimelineStatusClass(item.status)"
            >
              <div class="timeline-rail-line"></div>
              <div class="timeline-badge">{{ item.label }}</div>
              <div class="timeline-content">
                <div class="timeline-title">{{ item.title }}</div>
                <div class="timeline-status">{{ item.status }}</div>
              </div>
            </div>
          </div>
        </article>
      </section>

      <!--
        页面全局加载状态
        显示条件：
        - v-if="isLoading"
        含义：
        - 当 Dashboard 初始化加载中时显示遮罩式/悬浮式 loading 提示
        变量：
        - isLoading
          类型：Boolean
          示例：
          true  -> 正在加载
          false -> 加载完成
      -->
      <div v-if="isLoading" class="dashboard-loading">
        <div class="loading-ring"></div>
        <span>Loading dashboard...</span>
      </div>
    </div>
  </div>
</template>
<script setup>
// Import reactive utilities from Vue
// 1.ref是响应式变量，也就是这个值变了，页面里用到它的地方会自动更新。
//    在 script 里取值要用 .value。
//    在 template 里通常不用写 .value，Vue 会解包。
// 2.computed是用来创建一个依赖其他响应式数据自动计算出来的值
//    本质上是一个会跟着依赖变化自动重新计算的响应式结果。
//    const fullName = computed(() => {return firstName.value + ' ' + lastName.value})
// 3.onMounted 表示：组件已经挂载到页面上之后执行的代码，当需要“页面出现后再做某件事”时，就用它。
//    也就是页面相关的 DOM 已经渲染出来了，这时候可以：获取 DOM，调接口，读取浏览器本地存储等
// 4.onBeforeUnmount 表示：组件即将从页面移除之前执行的代码，一般用来做清理工作。
//    如果在页面里开启了：定时器，事件监听，WebSocket，第三方库实例，那么组件销毁前最好把它们清掉
// 5.watch 用来监听某个响应式数据的变化，一旦变化，就执行指定的逻辑。
// 6.nextTick 表示：等 Vue 把这次数据更新引起的 DOM 渲染完成后，再执行代码
//    因为 Vue 更新数据后，不一定立刻马上改 DOM，很多时候是“异步批量更新”的。
//    所以如果刚改完数据，就立刻去拿 DOM，可能拿到的是“旧的页面状态”。
// 7.DOM：Document Object Model，中文一般叫 文档对象模型
//    浏览器把 HTML 页面“读进去以后”，在内存里整理成的一棵树状结构。
//    这棵树里的每一个标签、文字、属性，都会变成一个“节点对象”，JavaScript 就可以通过这些对象去：
//    找到页面元素，修改文字，改样式，添加或删除内容，监听点击等事件
//    Document
//      └── html
//            └── body
//                  └── div#app
//                      ├── h1
//                          └── "Hello"
//                      └── p
//                          └── "This is a paragraph."

import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'

// Import router utilities
// 1.RouterLink 是 Vue 里专门用来做页面内跳转链接的组件。
//    <RouterLink to="/login">Go to Login</RouterLink>点击后跳到 /login 页面。
//    <a href="/login">Go to Login</a>同样也是跳转，但是会导致浏览器重新加载页面
// 2.useRouter 是一个函数，用来拿到当前项目的 router 对象。
//    拿到这个对象后，就可以在 JavaScript 代码里主动控制跳转，而不是只能点链接跳。
//    比如：登录成功后跳首页，注册成功后跳登录页，点击按钮后跳某个详情页，提交表单后跳
/* 
      <script setup>
      import { useRouter } from 'vue-router'

      const router = useRouter()

      function handleLoginSuccess() {
        router.push('/dashboard')
      }
      <script>不要写正确的会导致编译出错，比如这里正确语法应该是script前面有个/

      <template>
        <button @click="handleLoginSuccess">Login</button>
      </template> 
*/
import { RouterLink, useRouter } from 'vue-router'

// Import Pinia helpers
// 1.从 pinia 导入 storeToRefs。pinia 是 Vue 常用的状态管理库。
//    可以把它理解成一个“全局数据仓库”，专门存放多个页面都可能要用的数据：用户信息，登录状态
// 2.storeToRefs 的作用是：把 Pinia store 里的响应式状态拆成一个个 ref，方便直接使用，同时保持响应式。
//    比如：const authStore = useAuthStore()，里面有user，token，isLoggedIn
//    const { user, isLoggedIn } = storeToRefs(authStore)不用这个函数可能出错
import { storeToRefs } from 'pinia'

// Import authentication store
// 1.auth前端中专门管理用户认证状态的模块，
//    它通常会调用后端接口，
//    并把返回的 token、用户信息、登录状态统一保存下来，
//    供整个应用使用
// 2.而这个useAuthAtore：通常就是 auth 文件里定义并导出的一个函数，类似于类一样提供了方法
import { useAuthStore } from '@/stores/auth'

// Import mock data
// 引入虚拟数据，需要替换成API
import {
  mockGroups,
  mockResources,
  mockAnnouncements,
  mockEvents,
  mockDashboardTimeline,
  mockBiotechShowcaseItems
} from '@/data/mock'

import { formatDateAU, formatLongDateAU, formatAnnouncementDateAU } from '@/utils/date'
import { getResourceIcon } from '@/utils/resource'
import { getInitials } from '@/utils/string'
import { DASHBOARD_BACKGROUND_KEY, safeLocalStorageGet, safeLocalStorageSet } from '@/utils/storage'
import {
  DASHBOARD_BACKGROUND_OPTIONS,
  DASHBOARD_DEFAULT_BACKGROUND_KEY
} from '@/data/dashboard_background'
import { getTimelineStatusClass, getAccentClass } from '@/utils/ui'

const router = useRouter()
const auth = useAuthStore()
const {
  isAdmin,
  isTeacher,
  displayName,
  displayTrack,
  organizationLabel,
  roleLabel,
  normalizedRole
} = storeToRefs(auth)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Core state
const isLoading = ref(false)
const loadError = ref('')

// Main dashboard data
const groups = ref(Array.isArray(mockGroups) ? [...mockGroups] : [])
const resources = ref(Array.isArray(mockResources) ? [...mockResources] : [])
const announcements = ref(Array.isArray(mockAnnouncements) ? [...mockAnnouncements] : [])
const events = ref(Array.isArray(mockEvents) ? [...mockEvents] : [])

// Dashboard-specific state
const dashboardSummary = ref({
  activeGroups: groups.value.length,
  upcomingEvents: events.value.length,
  resources: resources.value.length,
  announcements: announcements.value.length
})

const adminWorkflow = ref({
  pendingMatches: 5,
  pendingReassignments: 2,
  pendingApprovals: 4,
  draftBulkMessages: 1
})

const progressSnapshot = ref({
  completionRate: 42,
  completedTasks: 3,
  totalTasks: 7,
  currentWeek: 'Week 3',
  nextMilestone: 'Check-in #1',
  nextMilestoneDate: '2026-03-28'
})

const nextEventDateParts = computed(() => {
  const formatted = formatDateAU(nextEvent.value?.date || '') || 'TBC'
  const parts = formatted.split(' ')
  return {
    day: parts[0] || 'TBC',
    rest: parts.slice(1).join(' ')
  }
})

const actionCenter = ref([])
const checklistItems = ref([])

const timelineItems = ref(
  Array.isArray(mockDashboardTimeline) ? [...mockDashboardTimeline] : []
)

const backgroundOptions = DASHBOARD_BACKGROUND_OPTIONS

const selectedBackground = computed(() => {
  return backgroundOptions.find(item => item.key === selectedBackgroundKey.value) || backgroundOptions[0]
})

const isThemeRailOpen = ref(false)
const themeRailRef = ref<HTMLElement | null>(null)
const themeTriggerRef = ref<HTMLElement | null>(null)

const selectedBackgroundKey = ref(
  safeLocalStorageGet(DASHBOARD_BACKGROUND_KEY, DASHBOARD_DEFAULT_BACKGROUND_KEY)
    || DASHBOARD_DEFAULT_BACKGROUND_KEY
)

const dashboardThemeStyle = computed(() => {
  return {
    '--dashboard-bg-image': `url("${selectedBackground.value.image}")`
  }
})

const biotechShowcaseItems = ref(
  Array.isArray(mockBiotechShowcaseItems) ? [...mockBiotechShowcaseItems] : []
)

const activeShowcaseIndex = ref(0)
let showcaseInterval = null

const activeShowcaseItem = computed(() => {
  if (!biotechShowcaseItems.value.length) return null
  return biotechShowcaseItems.value[activeShowcaseIndex.value] || biotechShowcaseItems.value[0]
})

// Header display
const currentDateText = computed(() => {
  return formatLongDateAU(new Date(), true)
})

const heroMessage = computed(() => {
  if (isAdmin.value) {
    return 'Review operational workload, monitor matching, and process critical platform actions from one unified dashboard.'
  }

  if (isTeacher.value) {
    return 'Track mentoring sessions, group activity, and support materials through a cleaner and more practical workspace.'
  }

  return 'Stay focused on your next event, active group, and current milestones with a dashboard designed for fast decisions.'
})

const headerHighlights = computed(() => {
  if (isAdmin.value) {
    return [
      { key: 'groups', label: `${dashboardSummary.value.activeGroups} active groups` },
      { key: 'matches', label: `${adminWorkflow.value.pendingMatches} pending matches` },
      { key: 'approvals', label: `${adminWorkflow.value.pendingApprovals} approvals` }
    ]
  }

  if (isTeacher.value) {
    return [
      { key: 'groups', label: `${dashboardSummary.value.activeGroups} mentoring groups` },
      { key: 'events', label: `${dashboardSummary.value.upcomingEvents} upcoming sessions` },
      { key: 'progress', label: `${progressSnapshot.value.completionRate}% progress` }
    ]
  }

  return [
    { key: 'groups', label: `${dashboardSummary.value.activeGroups} active groups` },
    { key: 'events', label: `${dashboardSummary.value.upcomingEvents} upcoming events` },
    { key: 'tasks', label: `${progressSnapshot.value.completedTasks}/${progressSnapshot.value.totalTasks} tasks done` }
  ]
})

const heroEyebrow = computed(() => {
  if (isAdmin.value) return 'Platform Operations'
  if (isTeacher.value) return 'Mentor Workspace'
  return 'Student Workspace'
})

// Derived data
const announcementsCount = computed(() => announcements.value.length)
const resourcesCount = computed(() => resources.value.length)
const groupsCount = computed(() => groups.value.length)

const nextEvent = computed(() => {
  return events.value[0] || null
})

const announcementsPreview = computed(() => {
  return announcements.value.slice(0, 3)
})

const resourcesPreview = computed(() => {
  return filterResourcesByRole(resources.value).slice(0, 6)
})

const groupsPreview = computed(() => {
  return groups.value.slice(0, isAdmin.value ? 4 : 3)
})

const progressPercentStyle = computed(() => {
  const value = Math.max(0, Math.min(100, Number(progressSnapshot.value.completionRate || 0)))
  return {
    width: `${value}%`
  }
})

const progressCircleStyle = computed(() => {
  const value = Math.max(0, Math.min(100, Number(progressSnapshot.value.completionRate || 0)))
  return {
    background: `conic-gradient(#60a5fa 0deg ${value * 3.6}deg, rgba(148, 163, 184, 0.14) ${value * 3.6}deg 360deg)`
  }
})

const summaryWidgets = computed(() => {
  if (isAdmin.value) {
    return [
      {
        key: 'groups',
        title: 'Active Groups',
        value: dashboardSummary.value.activeGroups,
        subtext: 'Current mentoring groups across the platform',
        icon: 'fas fa-users',
        accent: 'blue'
      },
      {
        key: 'events',
        title: 'Upcoming Events',
        value: dashboardSummary.value.upcomingEvents,
        subtext: nextEvent.value ? `Next: ${nextEvent.value.title}` : 'No upcoming event',
        icon: 'fas fa-calendar-days',
        accent: 'violet'
      },
      {
        key: 'matches',
        title: 'Pending Matches',
        value: adminWorkflow.value.pendingMatches,
        subtext: 'Items waiting for mentor allocation review',
        icon: 'fas fa-arrows-rotate',
        accent: 'teal'
      },
      {
        key: 'approvals',
        title: 'Open Approvals',
        value: adminWorkflow.value.pendingApprovals,
        subtext: 'Requests that need admin action',
        icon: 'fas fa-badge-check',
        accent: 'amber'
      }
    ]
  }

  if (isTeacher.value) {
    return [
      {
        key: 'groups',
        title: 'My Groups',
        value: dashboardSummary.value.activeGroups,
        subtext: 'Groups currently assigned to you',
        icon: 'fas fa-users',
        accent: 'blue'
      },
      {
        key: 'events',
        title: 'Upcoming Sessions',
        value: dashboardSummary.value.upcomingEvents,
        subtext: nextEvent.value ? `Next: ${nextEvent.value.title}` : 'No upcoming session',
        icon: 'fas fa-calendar-check',
        accent: 'violet'
      },
      {
        key: 'resources',
        title: 'Mentor Resources',
        value: resourcesCount.value,
        subtext: 'Guides, rubrics, and support materials',
        icon: 'fas fa-book-open',
        accent: 'teal'
      },
      {
        key: 'updates',
        title: 'Announcements',
        value: announcementsCount.value,
        subtext: 'Latest program communication',
        icon: 'fas fa-bullhorn',
        accent: 'rose'
      }
    ]
  }

  return [
    {
      key: 'groups',
      title: 'My Groups',
      value: dashboardSummary.value.activeGroups,
      subtext: 'Your current mentoring spaces',
      icon: 'fas fa-users',
      accent: 'blue'
    },
    {
      key: 'events',
      title: 'Upcoming Events',
      value: dashboardSummary.value.upcomingEvents,
      subtext: nextEvent.value ? `Next: ${nextEvent.value.title}` : 'No upcoming event',
      icon: 'fas fa-calendar-star',
      accent: 'violet'
    },
    {
      key: 'tasks',
      title: 'Tasks Completed',
      value: `${progressSnapshot.value.completedTasks}/${progressSnapshot.value.totalTasks}`,
      subtext: 'Your progress in the current program cycle',
      icon: 'fas fa-circle-check',
      accent: 'teal'
    },
    {
      key: 'resources',
      title: 'Resources',
      value: resourcesCount.value,
      subtext: 'Materials available to you',
      icon: 'fas fa-book',
      accent: 'amber'
    }
  ]
})

const groupsSectionTitle = computed(() => {
  if (isAdmin.value) return `Active Mentoring Groups (${groupsCount.value})`
  if (isTeacher.value) return `My Mentoring Groups (${groupsCount.value})`
  return `My Active Groups (${groupsCount.value})`
})

const resourcesSectionTitle = computed(() => {
  if (isAdmin.value) return 'Resource Library Snapshot'
  if (isTeacher.value) return 'Mentor Resources'
  return 'Learning Resources'
})

const announcementsSectionTitle = computed(() => {
  if (isAdmin.value) return 'Latest Broadcasts'
  if (isTeacher.value) return 'Program Updates'
  return 'Recent Announcements'
})

const actionCenterTitle = computed(() => {
  if (isAdmin.value) return 'Action Center'
  if (isTeacher.value) return 'Mentor Action Center'
  return 'My Action Center'
})

const checklistSectionTitle = computed(() => {
  if (isAdmin.value) return 'Admin Queue'
  if (isTeacher.value) return 'Mentoring Checklist'
  return 'My Next Steps'
})

// Data loading
async function fetchJson(url) {
  const response = await fetch(url, {
    method: 'GET',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json'
    }
  })

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }

  return response.json()
}

async function loadDashboardData() {
  isLoading.value = true
  loadError.value = ''

  try {
    await Promise.all([
      loadSummary(),
      loadGroups(),
      loadResources(),
      loadAnnouncements(),
      loadEvents(),
      loadAdminWorkflow(),
      loadProgress(),
      loadActionCenter(),
      loadChecklist(),
    ])
  } catch (error) {
    console.error('Dashboard loading error:', error)
    loadError.value = 'Some live dashboard data could not be loaded. Mock fallback is being used where available.'
  } finally {
    isLoading.value = false
  }
}

async function loadSummary() {
  try {
    const data = await fetchJson(`${API_BASE_URL}/api/v1/dashboard/summary/`)
    dashboardSummary.value = {
      activeGroups: Number(data?.active_groups ?? groups.value.length),
      upcomingEvents: Number(data?.upcoming_events ?? events.value.length),
      resources: Number(data?.resources ?? resources.value.length),
      announcements: Number(data?.announcements ?? announcements.value.length)
    }
  } catch (error) {
    dashboardSummary.value = {
      activeGroups: groups.value.length,
      upcomingEvents: events.value.length,
      resources: resources.value.length,
      announcements: announcements.value.length
    }
  }
}

async function loadGroups() {
  try {
    const data = await fetchJson(`${API_BASE_URL}/api/v1/groups/my/`)
    if (Array.isArray(data)) {
      groups.value = data
      return
    }

    if (Array.isArray(data?.results)) {
      groups.value = data.results
    }
  } catch (error) {
    groups.value = Array.isArray(mockGroups) ? [...mockGroups] : []
  }
}

async function loadResources() {
  try {
    const data = await fetchJson(`${API_BASE_URL}/api/v1/resources/`)
    if (Array.isArray(data)) {
      resources.value = data
      return
    }

    if (Array.isArray(data?.results)) {
      resources.value = data.results
    }
  } catch (error) {
    resources.value = Array.isArray(mockResources) ? [...mockResources] : []
  }
}

async function loadAnnouncements() {
  try {
    const data = await fetchJson(`${API_BASE_URL}/api/v1/announcements/`)
    if (Array.isArray(data)) {
      announcements.value = data
      return
    }

    if (Array.isArray(data?.results)) {
      announcements.value = data.results
    }
  } catch (error) {
    announcements.value = Array.isArray(mockAnnouncements) ? [...mockAnnouncements] : []
  }
}

async function loadEvents() {
  try {
    const data = await fetchJson(`${API_BASE_URL}/api/v1/events/upcoming/`)
    if (Array.isArray(data)) {
      events.value = data
      return
    }

    if (Array.isArray(data?.results)) {
      events.value = data.results
    }
  } catch (error) {
    events.value = Array.isArray(mockEvents) ? [...mockEvents] : []
  }
}

async function loadAdminWorkflow() {
  if (!isAdmin.value) return

  try {
    const data = await fetchJson(`${API_BASE_URL}/api/v1/admin/workflow/summary/`)
    adminWorkflow.value = {
      pendingMatches: Number(data?.pending_matches ?? 5),
      pendingReassignments: Number(data?.pending_reassignments ?? 2),
      pendingApprovals: Number(data?.pending_approvals ?? 4),
      draftBulkMessages: Number(data?.draft_bulk_messages ?? 1)
    }
  } catch (error) {
    adminWorkflow.value = {
      pendingMatches: 5,
      pendingReassignments: 2,
      pendingApprovals: 4,
      draftBulkMessages: 1
    }
  }
}

async function loadProgress() {
  try {
    const data = await fetchJson(`${API_BASE_URL}/api/v1/dashboard/progress/`)
    progressSnapshot.value = {
      completionRate: Number(data?.completion_rate ?? 42),
      completedTasks: Number(data?.completed_tasks ?? 3),
      totalTasks: Number(data?.total_tasks ?? 7),
      currentWeek: data?.current_week || 'Week 3',
      nextMilestone: data?.next_milestone || 'Check-in #1',
      nextMilestoneDate: data?.next_milestone_date || '2026-03-28'
    }
  } catch (error) {
    progressSnapshot.value = {
      completionRate: 42,
      completedTasks: 3,
      totalTasks: 7,
      currentWeek: 'Week 3',
      nextMilestone: 'Check-in #1',
      nextMilestoneDate: '2026-03-28'
    }
  }
}

async function loadActionCenter() {
  try {
    const data = await fetchJson(`${API_BASE_URL}/api/v1/dashboard/action-center/`)
    if (Array.isArray(data)) {
      actionCenter.value = data
      return
    }

    if (Array.isArray(data?.results)) {
      actionCenter.value = data.results
      return
    }

    actionCenter.value = buildFallbackActionCenter()
  } catch (error) {
    actionCenter.value = buildFallbackActionCenter()
  }
}

async function loadChecklist() {
  try {
    const data = await fetchJson(`${API_BASE_URL}/api/v1/dashboard/checklist/`)
    if (Array.isArray(data)) {
      checklistItems.value = data
      return
    }

    if (Array.isArray(data?.results)) {
      checklistItems.value = data.results
      return
    }

    checklistItems.value = buildFallbackChecklist()
  } catch (error) {
    checklistItems.value = buildFallbackChecklist()
  }
}

// Showcase data loader

async function loadBiotechShowcase() {
  // You can replace this endpoint with your own backend proxy
  // Example return format:
  // [{ id, title, summary, image, link }]
  try {
    const data = await fetchJson(`${API_BASE_URL}/api/v1/public/biotech-showcase/`)

    if (Array.isArray(data) && data.length) {
      biotechShowcaseItems.value = data
      activeShowcaseIndex.value = 0
      restartShowcaseAutoplay()
      return
    }

    if (Array.isArray(data?.results) && data.results.length) {
      biotechShowcaseItems.value = data.results
      activeShowcaseIndex.value = 0
      restartShowcaseAutoplay()
    }
  } catch (error) {
    restartShowcaseAutoplay()
  }
}

function handleBackgroundChange(nextKey) {
  selectedBackgroundKey.value = nextKey
  safeLocalStorageSet(DASHBOARD_BACKGROUND_KEY, nextKey)
  isThemeRailOpen.value = false
}

function toggleThemeRail() {
  isThemeRailOpen.value = !isThemeRailOpen.value
}

function closeThemeRail() {
  isThemeRailOpen.value = false
}

function handleClickOutside(event) {
  if (!isThemeRailOpen.value) return

  const clickedInsidePanel = themeRailRef.value?.contains(event.target)
  const clickedTrigger = themeTriggerRef.value?.contains(event.target)

  if (!clickedInsidePanel && !clickedTrigger) {
    closeThemeRail()
  }
}

function handleEscapeClose(event) {
  if (event.key === 'Escape') {
    closeThemeRail()
  }
}

// Showcase autoplay
function goToNextShowcase() {
  if (!biotechShowcaseItems.value.length) return
  activeShowcaseIndex.value = (activeShowcaseIndex.value + 1) % biotechShowcaseItems.value.length
}

function goToPrevShowcase() {
  if (!biotechShowcaseItems.value.length) return
  activeShowcaseIndex.value =
    (activeShowcaseIndex.value - 1 + biotechShowcaseItems.value.length) % biotechShowcaseItems.value.length
}

function goToShowcase(index) {
  if (index < 0 || index >= biotechShowcaseItems.value.length) return
  activeShowcaseIndex.value = index
  restartShowcaseAutoplay()
}

function startShowcaseAutoplay() {
  stopShowcaseAutoplay()

  if (biotechShowcaseItems.value.length <= 1) return

  showcaseInterval = window.setInterval(() => {
    goToNextShowcase()
  }, 5000)
}

function stopShowcaseAutoplay() {
  if (showcaseInterval) {
    window.clearInterval(showcaseInterval)
    showcaseInterval = null
  }
}

function restartShowcaseAutoplay() {
  stopShowcaseAutoplay()
  startShowcaseAutoplay()
}

// Fallback builders
function buildFallbackActionCenter() {
  if (isAdmin.value) {
    return [
      {
        key: 'review-matches',
        label: 'Review pending matches',
        helper: `${adminWorkflow.value.pendingMatches} items waiting`,
        type: 'route',
        to: '/groups'
      },
      {
        key: 'process-approvals',
        label: 'Process approvals',
        helper: `${adminWorkflow.value.pendingApprovals} approvals open`,
        type: 'route',
        to: '/groups'
      },
      {
        key: 'open-reassignments',
        label: 'Open reassignment queue',
        helper: `${adminWorkflow.value.pendingReassignments} requests`,
        type: 'route',
        to: '/groups'
      }
    ]
  }

  if (isTeacher.value) {
    return [
      {
        key: 'open-session',
        label: 'Open next session',
        helper: nextEvent.value ? nextEvent.value.title : 'No session scheduled',
        type: 'route',
        to: '/events'
      },
      {
        key: 'open-groups',
        label: 'Review my groups',
        helper: `${groupsCount.value} groups assigned`,
        type: 'route',
        to: '/groups'
      },
      {
        key: 'open-mentor-resources',
        label: 'Open mentor resources',
        helper: `${resourcesCount.value} resources available`,
        type: 'route',
        to: '/resources'
      }
    ]
  }

  return [
    {
      key: 'join-event',
      label: 'Open next event',
      helper: nextEvent.value ? nextEvent.value.title : 'No event scheduled',
      type: 'route',
      to: '/events'
    },
    {
      key: 'open-group',
      label: 'Open my active group',
      helper: `${groupsCount.value} groups available`,
      type: 'route',
      to: '/groups'
    },
    {
      key: 'continue-task',
      label: 'Continue my next task',
      helper: `${progressSnapshot.value.nextMilestone} ahead`,
      type: 'route',
      to: '/resources'
    }
  ]
}

function buildFallbackChecklist() {
  if (isAdmin.value) {
    return [
      {
        key: 'matches',
        title: 'Mentor matching queue',
        meta: `${adminWorkflow.value.pendingMatches} items need review`,
        to: '/groups'
      },
      {
        key: 'approvals',
        title: 'Open approval requests',
        meta: `${adminWorkflow.value.pendingApprovals} records pending`,
        to: '/groups'
      },
      {
        key: 'messages',
        title: 'Broadcast communication drafts',
        meta: `${adminWorkflow.value.draftBulkMessages} draft messages available`,
        to: '/announcements'
      }
    ]
  }

  if (isTeacher.value) {
    return [
      {
        key: 'session',
        title: 'Confirm next mentoring session',
        meta: nextEvent.value ? `${nextEvent.value.title} · ${formatDateAU(nextEvent.value.date) || 'TBC'}` : 'No event scheduled',
        to: '/events'
      },
      {
        key: 'groups',
        title: 'Check recent group activity',
        meta: `${groupsCount.value} groups assigned to you`,
        to: '/groups'
      },
      {
        key: 'resources',
        title: 'Review support materials',
        meta: `${resourcesCount.value} mentor resources available`,
        to: '/resources'
      }
    ]
  }

  return [
    {
      key: 'event',
      title: 'Prepare for your next event',
      meta: nextEvent.value ? `${nextEvent.value.title} · ${formatEventDate(nextEvent.value.date)}` : 'No event scheduled',
      to: '/events'
    },
    {
      key: 'group',
      title: 'Check your group space',
      meta: `${groupsCount.value} active group spaces`,
      to: '/groups'
    },
    {
      key: 'resource',
      title: 'Continue your current milestone task',
      meta: `${progressSnapshot.value.nextMilestone} is the next milestone`,
      to: '/resources'
    }
  ]
}

// User action handlers
function handleActionClick(action) {
  if (!action) return

  if (action.type === 'route' && action.to) {
    router.push(action.to)
    return
  }

  if (action.type === 'link' && action.url) {
    window.open(action.url, '_blank', 'noopener')
  }
}

function openShowcaseLink(item) {
  if (!item) return

  if (typeof item.link === 'string' && item.link.startsWith('http')) {
    window.open(item.link, '_blank', 'noopener')
    return
  }

  if (typeof item.link === 'string' && item.link.startsWith('/')) {
    router.push(item.link)
  }
}

// Helpers
function filterResourcesByRole(items) {
  const role = normalizedRole.value

  return items.filter(item => {
    const resourceRole = String(item?.role || 'all').toLowerCase()

    if (resourceRole === 'all') return true
    if (role === 'teacher' && ['mentor', 'supervisor'].includes(resourceRole)) return true
    if (role === 'admin' && resourceRole === 'admin') return true
    if (role === 'student' && resourceRole === 'student') return true
    if (role === 'admin') return true

    return false
  })
}

function getAnnouncementTitle(item) {
  return item?.title || item?.name || item?.subject || 'Untitled announcement'
}

function getAnnouncementMeta(item) {
  return item?.updated || item?.date || item?.created_at || 'Recently posted'
}

function getAnnouncementSnippet(item) {
  return item?.summary || item?.description || item?.content || item?.excerpt || 'Open the announcement to read more details.'
}

function getResourceTitle(item) {
  return item?.title || item?.name || 'Untitled resource'
}

function getResourceMeta(item) {
  return item?.updated || item?.date || item?.created_at || 'Recently updated'
}

function getResourceCategory(item) {
  return item?.type || item?.category || item?.tag || 'General'
}

function getGroupName(group) {
  return group?.name || group?.title || 'Untitled group'
}

function getGroupMemberCount(group) {
  return Number(group?.members || group?.memberCount || 0)
}

function getGroupLead(group) {
  return group?.mentor || group?.lead || group?.supervisor || group?.owner || 'Mentor team'
}

function getGroupSecondaryLabel(group) {
  const source = group?.track || group?.category || group?.status || 'BF'
  return String(source).slice(0, 2).toUpperCase()
}

watch(
  () => biotechShowcaseItems.value.length,
  () => {
    if (activeShowcaseIndex.value >= biotechShowcaseItems.value.length) {
      activeShowcaseIndex.value = 0
    }
    restartShowcaseAutoplay()
  }
)

onMounted(async () => {
  await loadDashboardData()

  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleEscapeClose)

  await nextTick()
  startShowcaseAutoplay()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleEscapeClose)
  stopShowcaseAutoplay()
})

</script>

<style scoped>
.dashboard-page-shell {
  --dashboard-title: #ecf4ff;
  --dashboard-text: #d8e3f5;
  --dashboard-muted: #93a6c6;
  --dashboard-link: #a8c8ff;
  --dashboard-line: rgba(255, 255, 255, 0.08);
  --dashboard-border: rgba(255, 255, 255, 0.12);
  --dashboard-border-strong: rgba(255, 255, 255, 0.18);
  --dashboard-surface: rgba(11, 19, 36, 0.56);
  --dashboard-surface-strong: rgba(10, 18, 34, 0.78);
  --dashboard-surface-soft: rgba(255, 255, 255, 0.045);
  --dashboard-shadow: 0 24px 70px rgba(2, 8, 23, 0.36);
  --dashboard-shadow-soft: 0 14px 34px rgba(2, 8, 23, 0.2);
  --dashboard-bg-image: linear-gradient(135deg, rgba(9, 15, 30, 0.72), rgba(10, 18, 36, 0.72));

  position: relative;
  isolation: isolate;
  min-height: 100%;
  height: auto;
  overflow: visible;
  padding: 1.4rem 1rem 2.5rem;
  color: var(--dashboard-text);
}

.dashboard-page-inner {
  position: relative;
  max-width: 1520px;
  margin: 0 auto;
  overflow: visible;
}

.dashboard-page-shell::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -5;
  background:
    radial-gradient(circle at 18% 18%, rgba(56, 189, 248, 0.05), transparent 26%),
    radial-gradient(circle at 84% 18%, rgba(99, 102, 241, 0.05), transparent 24%),
    radial-gradient(circle at 78% 80%, rgba(16, 185, 129, 0.05), transparent 24%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.03)),
    var(--dashboard-bg-image);
  background-size: 100% 100%;
  background-position: center;
  background-repeat: no-repeat;
  transform: none;
}

.dashboard-page-shell::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -4;
  pointer-events: none;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.02), transparent 28%);
}

.dashboard-backdrop-orb {
  position: absolute;
  border-radius: 999px;
  filter: blur(72px);
  opacity: 0.68;
  pointer-events: none;
  z-index: -2;
}

.orb-one {
  width: 300px;
  height: 300px;
  top: 30px;
  right: 4%;
  background: rgba(59, 130, 246, 0.18);
}

.orb-two {
  width: 260px;
  height: 260px;
  left: 2%;
  bottom: 140px;
  background: rgba(45, 212, 191, 0.14);
}

.dashboard-backdrop-grid {
  position: absolute;
  inset: 0;
  z-index: -3;
  opacity: 0.06;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.16) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.16) 1px, transparent 1px);
  background-size: 36px 36px;
  mask-image: linear-gradient(180deg, rgba(255, 255, 255, 0.9), transparent 82%);
}

.dashboard-particle-layer {
  position: absolute;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background:
    radial-gradient(circle at 12% 30%, rgba(255, 255, 255, 0.12) 0 1px, transparent 2px),
    radial-gradient(circle at 28% 62%, rgba(255, 255, 255, 0.1) 0 1px, transparent 2px),
    radial-gradient(circle at 60% 18%, rgba(255, 255, 255, 0.1) 0 1px, transparent 2px),
    radial-gradient(circle at 82% 38%, rgba(255, 255, 255, 0.09) 0 1px, transparent 2px),
    radial-gradient(circle at 72% 76%, rgba(255, 255, 255, 0.08) 0 1px, transparent 2px);
  animation: particleDrift 18s linear infinite;
  opacity: 0.55;
}

@keyframes particleDrift {
  0% {
    transform: translateY(0) translateX(0);
  }
  50% {
    transform: translateY(-8px) translateX(4px);
  }
  100% {
    transform: translateY(0) translateX(0);
  }
}

.dashboard-section {
  margin-bottom: 1.5rem;
}

.dashboard-section-grid {
  display: grid;
  gap: 1.2rem;
}

.two-col-layout {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.dashboard-hero-shell {
  margin-bottom: 1.35rem;
}

.dashboard-hero-card {
  position: relative;
  overflow: hidden;
  border-radius: 32px;
  padding: 1.4rem;
  border: 1px solid var(--dashboard-border);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.065), rgba(255, 255, 255, 0.028)),
    linear-gradient(135deg, rgba(9, 17, 34, 0.82), rgba(10, 18, 34, 0.62));
  box-shadow: var(--dashboard-shadow);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
}

.dashboard-hero-card::before {
  content: '';
  position: absolute;
  inset: -20% auto auto -8%;
  width: 360px;
  height: 360px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(96, 165, 250, 0.18), transparent 68%);
  pointer-events: none;
}

.dashboard-hero-card::after {
  content: '';
  position: absolute;
  inset: auto -12% -28% auto;
  width: 340px;
  height: 340px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(45, 212, 191, 0.12), transparent 72%);
  pointer-events: none;
}

.dashboard-theme-rail {
  position: absolute;
  top: 1rem;
  right: 1rem;
  z-index: 5;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.7rem;
}

.theme-rail-trigger {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  min-height: 44px;
  padding: 0.58rem 1rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(8, 14, 28, 0.62);
  color: #f8fbff;
  cursor: pointer;
  box-shadow: 0 14px 30px rgba(2, 6, 23, 0.22);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  transition:
    transform 0.22s ease,
    border-color 0.22s ease,
    background 0.22s ease;
}

.theme-rail-trigger:hover {
  transform: translateY(-2px);
  border-color: rgba(168, 200, 255, 0.32);
  background: rgba(10, 18, 34, 0.76);
}

.theme-rail-panel {
  width: 180px;
  padding: 0.5rem;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(8, 14, 28, 0.9);
  box-shadow: 0 10px 24px rgba(2, 6, 23, 0.22);
}

.theme-rail-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.theme-rail-item {
  width: 100%;
  padding: 0.65rem 0.8rem;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #f8fbff;
  cursor: pointer;
  text-align: left;
  font-size: 0.9rem;
  font-weight: 600;
  transition: background 0.2s ease;
}

.theme-rail-item:hover {
  transform: none;
  background: rgba(255, 255, 255, 0.08);
  box-shadow: none;
  border-color: transparent;
}

.theme-rail-item.active {
  background: rgba(255, 255, 255, 0.14);
  box-shadow: none;
  border-color: transparent;
}

.theme-rail-panel-enter-active,
.theme-rail-panel-leave-active {
  transition: all 0.24s ease;
}

.theme-rail-panel-enter-from,
.theme-rail-panel-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.985);
}

.dashboard-hero-main {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
  gap: 1.2rem;
  align-items: start;
  padding-top: 2.9rem;
}

.dashboard-hero-copy {
  min-width: 0;
  padding: 0.25rem 0.15rem 0.15rem;
}

.hero-eyebrow-row {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  flex-wrap: wrap;
  margin-bottom: 0.9rem;
}

.hero-eyebrow,
.hero-org {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0.35rem 0.82rem;
  border-radius: 999px;
  font-size: 0.79rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.hero-eyebrow {
  color: #dbeafe;
  background: rgba(59, 130, 246, 0.14);
  border: 1px solid rgba(96, 165, 250, 0.2);
}

.hero-org {
  color: #d1fae5;
  background: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(52, 211, 153, 0.18);
}

.hero-title {
  margin: 0;
  font-size: clamp(2rem, 3vw, 3.1rem);
  line-height: 1.02;
  font-weight: 800;
  letter-spacing: -0.05em;
  color: #f8fbff;
}

.dashboard-subtext {
  margin-top: 0.6rem;
  font-size: 0.96rem;
  color: rgba(219, 234, 254, 0.8);
  letter-spacing: -0.01em;
}

.dashboard-hero-message {
  margin-top: 1rem;
  max-width: 760px;
  color: rgba(230, 238, 252, 0.9);
  line-height: 1.72;
  font-size: 1.01rem;
}

.hero-highlight-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
  margin-top: 1.15rem;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  padding: 0.45rem 0.9rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.07);
  color: #f8fbff;
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 0.83rem;
  font-weight: 700;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.dashboard-hero-aside {
  min-width: 0;
  align-self: start;
}

.showcase-card {
  height: auto;
  align-self: start;
  padding: 0.9rem;
  border-radius: 28px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.065), rgba(255, 255, 255, 0.028)),
    rgba(255, 255, 255, 0.035);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: var(--dashboard-shadow-soft);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  overflow: hidden;
}

.showcase-heading-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.8rem;
}

.showcase-kicker {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 800;
  color: #9dc3ff;
}

.showcase-mini-label {
  margin-top: 0.34rem;
  color: rgba(216, 227, 245, 0.72);
  font-size: 0.85rem;
}

.showcase-controls {
  display: flex;
  gap: 0.48rem;
}

.showcase-nav-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.08);
  color: #f8fbff;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    background 0.2s ease;
}

.showcase-nav-btn:hover {
  transform: translateY(-1px);
  background: rgba(255, 255, 255, 0.12);
}

.showcase-body {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}

.showcase-image {
  position: relative;
  aspect-ratio: 16 / 8.2;
  min-height: unset;
  width: 100%;
  border-radius: 22px;
  overflow: hidden;
  background-size: cover;
  background-position: center;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.showcase-image-overlay {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(2, 6, 23, 0.08), rgba(2, 6, 23, 0.28)),
    radial-gradient(circle at 24% 20%, rgba(255, 255, 255, 0.08), transparent 28%);
}

.showcase-copy {
  min-width: 0;
}

.showcase-title {
  margin: 0;
  color: #f8fbff;
  font-size: 1.08rem;
  font-weight: 800;
  line-height: 1.32;
}

.showcase-summary {
  margin: 0.45rem 0 0;
  color: rgba(226, 232, 240, 0.84);
  font-size: 0.9rem;
  line-height: 1.6;
}

.showcase-footer {
  margin-top: 0.7rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.showcase-dots {
  display: flex;
  align-items: center;
  gap: 0.46rem;
}

.showcase-dot {
  width: 10px;
  height: 10px;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.22);
  cursor: pointer;
  transition:
    transform 0.2s ease,
    background 0.2s ease,
    width 0.2s ease;
}

.showcase-dot.active {
  width: 22px;
  background: #93c5fd;
}

.showcase-link-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  min-height: 38px;
  padding: 0.52rem 0.9rem;
  border-radius: 999px;
  border: 1px solid rgba(147, 197, 253, 0.2);
  background: rgba(59, 130, 246, 0.14);
  color: #eff6ff;
  cursor: pointer;
  font-weight: 700;
}

.showcase-fade-enter-active,
.showcase-fade-leave-active {
  transition: opacity 0.32s ease, transform 0.32s ease;
}

.showcase-fade-enter-from,
.showcase-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.hero-bottom-metrics {
  position: relative;
  z-index: 1;
  margin-top: 1rem;
  padding-top: 1rem;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.9rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.hero-metric {
  padding: 0.92rem 1rem;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.hero-metric-label {
  display: block;
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: rgba(191, 219, 254, 0.72);
}

.hero-metric-value {
  display: block;
  margin-top: 0.36rem;
  color: #f8fbff;
  font-size: 1rem;
  font-weight: 800;
}

.dashboard-alert {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.95rem 1rem;
  margin-bottom: 1.25rem;
  border-radius: 18px;
  background: rgba(251, 191, 36, 0.1);
  border: 1px solid rgba(251, 191, 36, 0.16);
  color: #fde68a;
  box-shadow: var(--dashboard-shadow-soft);
}

.summary-card {
  position: relative;
  overflow: hidden;
  min-height: 182px;
  padding: 1.2rem 1.2rem 1.15rem;
  border-radius: 26px;
  border: 1px solid var(--dashboard-border);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.055), rgba(255, 255, 255, 0.022)),
    rgba(11, 19, 36, 0.5);
  box-shadow: var(--dashboard-shadow);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  transition:
    transform 0.24s ease,
    border-color 0.24s ease,
    box-shadow 0.24s ease;
}

.summary-card:hover {
  transform: translateY(-4px);
  border-color: var(--dashboard-border-strong);
  box-shadow: 0 28px 56px rgba(2, 6, 23, 0.38);
}

.summary-card::after {
  content: '';
  position: absolute;
  width: 170px;
  height: 170px;
  right: -42px;
  top: -34px;
  border-radius: 999px;
  opacity: 0.24;
  pointer-events: none;
}

.accent-blue::after {
  background: radial-gradient(circle, rgba(59, 130, 246, 0.85), transparent 70%);
}

.accent-violet::after {
  background: radial-gradient(circle, rgba(139, 92, 246, 0.8), transparent 70%);
}

.accent-teal::after {
  background: radial-gradient(circle, rgba(20, 184, 166, 0.82), transparent 70%);
}

.accent-amber::after {
  background: radial-gradient(circle, rgba(245, 158, 11, 0.78), transparent 70%);
}

.accent-rose::after {
  background: radial-gradient(circle, rgba(244, 63, 94, 0.76), transparent 70%);
}

.summary-card-top {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.summary-icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #f8fbff;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 1rem;
}

.summary-label {
  color: rgba(226, 232, 240, 0.86);
  font-size: 0.93rem;
  font-weight: 700;
}

.summary-card-value {
  margin-top: 1.04rem;
  font-size: clamp(2rem, 3vw, 2.65rem);
  line-height: 1;
  font-weight: 800;
  color: #f8fbff;
  letter-spacing: -0.05em;
}

.summary-card-subtext {
  margin-top: 0.72rem;
  max-width: 28ch;
  color: rgba(203, 213, 225, 0.78);
  font-size: 0.92rem;
  line-height: 1.6;
}

.surface-card {
  border-radius: 28px;
  padding: 1.18rem;
  border: 1px solid var(--dashboard-border);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.02)),
    var(--dashboard-surface);
  box-shadow: var(--dashboard-shadow);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.feature-card {
  min-height: 100%;
}

.surface-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.surface-kicker {
  margin: 0 0 0.25rem;
  font-size: 0.76rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: rgba(157, 195, 255, 0.9);
}

.surface-card-title {
  margin: 0;
  color: #f8fbff;
  font-size: 1.16rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.surface-link {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  padding: 0.42rem 0.82rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--dashboard-link);
  border: 1px solid rgba(143, 186, 255, 0.12);
  text-decoration: none;
  font-size: 0.84rem;
  font-weight: 700;
  transition:
    transform 0.22s ease,
    border-color 0.22s ease,
    background 0.22s ease;
}

.surface-link:hover {
  transform: translateY(-1px);
  border-color: rgba(168, 200, 255, 0.22);
  background: rgba(255, 255, 255, 0.07);
}

.action-center-list {
  display: flex;
  flex-direction: column;
  gap: 0.82rem;
}

.action-center-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  text-align: left;
  padding: 1rem;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.028)),
    rgba(255, 255, 255, 0.02);
  color: inherit;
  cursor: pointer;
  transition:
    transform 0.22s ease,
    border-color 0.22s ease,
    box-shadow 0.22s ease;
}

.action-center-item:hover {
  transform: translateY(-2px);
  border-color: rgba(143, 186, 255, 0.2);
  box-shadow: var(--dashboard-shadow-soft);
}

.action-center-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.action-center-main {
  color: #f8fbff;
  font-weight: 800;
  font-size: 0.98rem;
}

.action-center-helper {
  margin-top: 0.3rem;
  color: rgba(203, 213, 225, 0.74);
  font-size: 0.91rem;
  line-height: 1.5;
}

.action-center-arrow {
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: rgba(59, 130, 246, 0.14);
  color: #dbeafe;
}

.progress-layout {
  display: flex;
  gap: 1.1rem;
  align-items: center;
  flex-wrap: wrap;
}

.progress-ring-shell {
  flex: 0 0 156px;
  display: flex;
  justify-content: center;
}

.progress-ring {
  width: 136px;
  height: 136px;
  border-radius: 999px;
  padding: 11px;
}

.progress-ring-inner {
  width: 100%;
  height: 100%;
  border-radius: 999px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background:
    linear-gradient(180deg, rgba(8, 15, 30, 0.95), rgba(7, 12, 24, 0.95));
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.progress-value {
  font-size: 1.95rem;
  font-weight: 800;
  color: #f8fbff;
  letter-spacing: -0.04em;
}

.progress-label {
  margin-top: 0.18rem;
  color: rgba(203, 213, 225, 0.76);
  font-size: 0.82rem;
  font-weight: 700;
}

.progress-details {
  flex: 1;
  min-width: 230px;
}

.progress-detail-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.42rem 0;
  color: rgba(226, 232, 240, 0.82);
  border-bottom: 1px dashed rgba(255, 255, 255, 0.08);
}

.progress-detail-row:last-of-type {
  border-bottom: none;
}

.progress-detail-row strong {
  color: #f8fbff;
}

.progress-bar-shell {
  margin-top: 1rem;
  height: 10px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.14);
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #3b82f6, #67e8f9);
  box-shadow: 0 8px 18px rgba(59, 130, 246, 0.32);
}

.event-detail-card {
  display: flex;
  gap: 1rem;
  align-items: stretch;
}

.event-date-badge {
  flex: 0 0 92px;
  min-height: 112px;
  border-radius: 22px;
  padding: 0.95rem 0.85rem;
  background:
    linear-gradient(180deg, rgba(59, 130, 246, 0.22), rgba(59, 130, 246, 0.08)),
    rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(96, 165, 250, 0.14);
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: center;
}

.event-date-day {
  color: #f8fbff;
  font-size: 1.5rem;
  font-weight: 800;
  line-height: 1;
}

.event-date-rest {
  margin-top: 0.42rem;
  color: rgba(219, 234, 254, 0.78);
  font-size: 0.85rem;
  line-height: 1.3;
}

.event-content {
  flex: 1;
  min-width: 0;
}

.event-title {
  font-size: 1.16rem;
  font-weight: 800;
  color: #f8fbff;
}

.event-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 0.72rem;
  color: rgba(226, 232, 240, 0.8);
  font-size: 0.93rem;
}

.event-meta-row span {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}

.location-row {
  margin-top: 0.55rem;
}

.event-actions {
  margin-top: 1rem;
}

.primary-chip {
  display: inline-flex;
  align-items: center;
  min-height: 40px;
  padding: 0.56rem 0.95rem;
  border-radius: 999px;
  background: linear-gradient(135deg, #2563eb, #60a5fa);
  color: #f8fbff;
  text-decoration: none;
  font-size: 0.84rem;
  font-weight: 700;
  box-shadow: 0 14px 24px rgba(37, 99, 235, 0.24);
}

.list-stack {
  display: flex;
  flex-direction: column;
  gap: 0.84rem;
}

.list-row {
  display: flex;
  align-items: flex-start;
  gap: 0.9rem;
  text-decoration: none;
  color: inherit;
}

.premium-row {
  padding: 0.95rem 1rem;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.018)),
    rgba(255, 255, 255, 0.016);
  transition:
    transform 0.22s ease,
    border-color 0.22s ease,
    box-shadow 0.22s ease;
}

.premium-row:hover {
  transform: translateY(-2px);
  border-color: rgba(143, 186, 255, 0.18);
  box-shadow: var(--dashboard-shadow-soft);
}

.list-row-icon {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  font-size: 0.96rem;
}

.announcement-icon {
  background: rgba(244, 63, 94, 0.14);
  color: #fecdd3;
}

.checklist-icon {
  background: rgba(59, 130, 246, 0.14);
  color: #bfdbfe;
}

.list-row-content {
  min-width: 0;
  flex: 1;
}

.list-row-title {
  color: #f8fbff;
  font-weight: 800;
  line-height: 1.45;
}

.list-row-meta {
  margin-top: 0.18rem;
  color: rgba(191, 219, 254, 0.74);
  font-size: 0.88rem;
}

.list-row-description {
  margin-top: 0.3rem;
  color: rgba(203, 213, 225, 0.78);
  font-size: 0.9rem;
  line-height: 1.6;
}

.list-row-tail {
  color: rgba(203, 213, 225, 0.52);
  padding-top: 0.2rem;
}

.groups-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.group-card-link,
.resource-card-link {
  display: block;
  text-decoration: none;
  color: inherit;
}

.group-card-surface {
  height: 100%;
  padding: 1rem 1rem 1.02rem;
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.018)),
    rgba(255, 255, 255, 0.02);
  transition:
    transform 0.22s ease,
    border-color 0.22s ease,
    box-shadow 0.22s ease;
}

.group-card-surface:hover {
  transform: translateY(-3px);
  border-color: rgba(143, 186, 255, 0.18);
  box-shadow: var(--dashboard-shadow-soft);
}

.group-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
}

.group-avatars {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.group-avatar {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px solid rgba(7, 12, 24, 0.8);
  margin-left: -0.35rem;
  font-size: 0.78rem;
  font-weight: 800;
}

.group-avatar:first-child {
  margin-left: 0;
}

.primary-avatar {
  color: #dbeafe;
  background: linear-gradient(135deg, #2563eb, #60a5fa);
}

.secondary-avatar {
  color: #d1fae5;
  background: linear-gradient(135deg, #0f766e, #14b8a6);
}

.tertiary-avatar {
  color: #fef3c7;
  background: linear-gradient(135deg, #b45309, #f59e0b);
}

.group-open-indicator {
  width: 34px;
  height: 34px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #dbeafe;
  background: rgba(59, 130, 246, 0.12);
}

.group-name {
  margin-top: 0.95rem;
  color: #f8fbff;
  font-size: 1rem;
  font-weight: 800;
}

.group-meta {
  margin-top: 0.3rem;
  color: rgba(203, 213, 225, 0.78);
  font-size: 0.9rem;
  line-height: 1.55;
}

.resource-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
}

.resource-card-surface {
  height: 100%;
  display: flex;
  align-items: flex-start;
  gap: 0.9rem;
  padding: 1rem;
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.018)),
    rgba(255, 255, 255, 0.02);
  transition:
    transform 0.22s ease,
    border-color 0.22s ease,
    box-shadow 0.22s ease;
}

.resource-card-surface:hover {
  transform: translateY(-2px);
  border-color: rgba(143, 186, 255, 0.18);
  box-shadow: var(--dashboard-shadow-soft);
}

.resource-icon {
  width: 46px;
  height: 46px;
  flex-shrink: 0;
  border-radius: 15px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 130, 246, 0.12);
  color: #dbeafe;
  border: 1px solid rgba(96, 165, 250, 0.12);
}

.resource-content {
  min-width: 0;
}

.resource-title {
  color: #f8fbff;
  font-weight: 800;
  line-height: 1.45;
}

.resource-meta {
  margin-top: 0.28rem;
  color: rgba(203, 213, 225, 0.76);
  font-size: 0.88rem;
  line-height: 1.55;
}

.empty-state {
  min-height: 160px;
  border-radius: 22px;
  border: 1px dashed rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.02);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.7rem;
  flex-direction: column;
  color: rgba(203, 213, 225, 0.78);
  text-align: center;
}

.empty-state i {
  font-size: 1.3rem;
  color: rgba(191, 219, 254, 0.72);
}

.timeline-list {
  display: flex;
  flex-direction: column;
  gap: 0.88rem;
}

.timeline-item {
  position: relative;
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr);
  gap: 0.9rem;
  align-items: center;
  padding: 0.9rem 1rem;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.07);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.018)),
    rgba(255, 255, 255, 0.018);
}

.timeline-rail-line {
  position: absolute;
  left: 1.05rem;
  top: 0.8rem;
  bottom: 0.8rem;
  width: 3px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
}

.timeline-badge {
  position: relative;
  z-index: 1;
  margin-left: 0.8rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  padding: 0.4rem 0.8rem;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 800;
  background: rgba(255, 255, 255, 0.07);
  color: #f8fbff;
}

.timeline-content {
  min-width: 0;
}

.timeline-title {
  color: #f8fbff;
  font-weight: 800;
}

.timeline-status {
  margin-top: 0.24rem;
  color: rgba(203, 213, 225, 0.72);
  font-size: 0.88rem;
  text-transform: capitalize;
}

.timeline-item.is-completed .timeline-badge {
  background: rgba(16, 185, 129, 0.16);
  color: #d1fae5;
}

.timeline-item.is-current .timeline-badge {
  background: rgba(59, 130, 246, 0.18);
  color: #dbeafe;
}

.timeline-item.is-upcoming .timeline-badge {
  background: rgba(148, 163, 184, 0.14);
  color: #e5eefc;
}

.dashboard-loading {
  position: fixed;
  right: 1.35rem;
  bottom: 1.35rem;
  z-index: 20;
  display: inline-flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.78rem 1rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(8, 14, 28, 0.82);
  color: #f8fbff;
  box-shadow: var(--dashboard-shadow);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.loading-ring {
  width: 16px;
  height: 16px;
  border-radius: 999px;
  border: 2px solid rgba(255, 255, 255, 0.22);
  border-top-color: #60a5fa;
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1400px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .groups-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1180px) {
  .dashboard-hero-main {
    grid-template-columns: 1fr;
    padding-top: 3.1rem;
  }

  .two-col-layout {
    grid-template-columns: 1fr;
  }

  .theme-rail-panel {
    width: min(520px, calc(100vw - 2.4rem));
  }
}

@media (max-width: 880px) {
  .dashboard-page-shell {
    padding: 1rem 0.75rem 2rem;
  }

  .summary-grid,
  .groups-grid,
  .resource-grid {
    grid-template-columns: 1fr;
  }

  .hero-bottom-metrics {
    grid-template-columns: 1fr;
  }

  .timeline-item {
    grid-template-columns: 1fr;
    padding-left: 1rem;
  }

  .timeline-badge {
    margin-left: 0.5rem;
    width: fit-content;
  }

  .timeline-rail-line {
    display: none;
  }

  .event-detail-card {
    flex-direction: column;
  }

  .event-date-badge {
    width: 100%;
    min-height: 86px;
  }

  .dashboard-theme-rail {
    position: static;
    align-items: stretch;
    margin-bottom: 1rem;
  }

  .theme-rail-trigger {
    width: 100%;
    justify-content: center;
  }

  .theme-rail-panel {
    width: 100%;
    max-height: none;
  }

  .dashboard-hero-main {
    padding-top: 0;
  }

  .theme-rail-panel-header,
  .showcase-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .showcase-image {
    aspect-ratio: 16 / 9;
  }
}

@media (max-width: 560px) {
  .dashboard-hero-card,
  .surface-card,
  .summary-card {
    border-radius: 24px;
  }

  .hero-title {
    font-size: 1.8rem;
  }

  .dashboard-subtext,
  .dashboard-hero-message {
    font-size: 0.92rem;
  }

  .summary-card-value {
    font-size: 2rem;
  }

  .showcase-title {
    font-size: 1.02rem;
  }
}
</style>