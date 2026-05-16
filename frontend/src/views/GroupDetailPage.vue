<template>
  <div class="content-area group-detail" :data-active="activeTab" :aria-busy="isLoadingGroupDetail">
    <div v-if="isLoadingGroupDetail" class="group-detail-loading" role="status" aria-live="polite">
      <span class="sr-only">Loading group details...</span>
      <div class="group-hero-card group-loading-hero">
        <div class="gd-head group-loading-head">
          <div class="group-loading-avatar skeleton-block"></div>
          <div class="group-loading-title-stack">
            <div class="skeleton-block skeleton-title"></div>
            <div class="skeleton-block skeleton-subtitle"></div>
            <div class="group-loading-meta">
              <div class="skeleton-block skeleton-pill"></div>
              <div class="skeleton-block skeleton-pill skeleton-pill--short"></div>
            </div>
          </div>
          <div class="skeleton-block skeleton-select"></div>
        </div>
      </div>

      <div class="group-loading-grid">
        <section class="card group-loading-panel">
          <div class="group-loading-panel-header">
            <div class="skeleton-block skeleton-heading"></div>
            <div class="skeleton-block skeleton-button"></div>
          </div>
          <div class="group-loading-filter-row">
            <div
              v-for="item in 5"
              :key="`task-filter-${item}`"
              class="skeleton-block skeleton-filter"
            ></div>
          </div>
          <div class="group-loading-list">
            <div v-for="item in 5" :key="`task-row-${item}`" class="group-loading-row">
              <div class="skeleton-block skeleton-dot"></div>
              <div class="group-loading-row-copy">
                <div class="skeleton-block skeleton-line"></div>
                <div class="skeleton-block skeleton-line skeleton-line--short"></div>
              </div>
            </div>
          </div>
        </section>

        <section class="group-loading-panel group-loading-chat">
          <div class="group-loading-panel-header">
            <div class="skeleton-block skeleton-heading"></div>
            <div class="skeleton-block skeleton-status"></div>
          </div>
          <div class="group-loading-messages">
            <div
              v-for="item in 4"
              :key="`message-${item}`"
              class="group-loading-message"
              :class="{ 'group-loading-message--own': item % 2 === 0 }"
            >
              <div class="skeleton-block skeleton-message-avatar"></div>
              <div class="group-loading-bubble">
                <div class="skeleton-block skeleton-line"></div>
                <div class="skeleton-block skeleton-line skeleton-line--short"></div>
              </div>
            </div>
          </div>
          <div class="skeleton-block skeleton-composer"></div>
        </section>
      </div>
    </div>

    <template v-else>
      <!-- Header -->
      <div class="group-hero-card">
        <div class="gd-head">
          <div class="gd-head-left">
            <div class="group-avatars">
              <div class="group-avatar" style="width: 48px; height: 48px; font-size: 1.1rem">
                {{ groupInitials }}
              </div>
            </div>
            <div>
              <h2 class="gd-title">{{ group.name }}</h2>
              <p class="gd-subtitle">{{ groupSubtitle }}</p>
              <div v-if="groupMetaItems.length" class="gd-meta-row">
                <span v-for="item in groupMetaItems" :key="item">{{ item }}</span>
              </div>
            </div>
          </div>
          <div class="gd-head-actions">
            <button
              type="button"
              class="group-members-btn"
              :disabled="isLoadingMembers || !visibleGroupMembers.length"
              @click="showGroupMembersDialog = true"
            >
              <i class="fas fa-users"></i>
              Members
              <span>{{ visibleGroupMembers.length }}</span>
            </button>
          </div>
        </div>
      </div>

      <div
        v-if="showGroupMembersDialog"
        class="group-members-dialog-backdrop"
        role="dialog"
        aria-modal="true"
        aria-label="Group members"
      >
        <section class="group-members-dialog">
          <div class="group-members-dialog-header">
            <div>
              <h3>Group members</h3>
              <p>{{ visibleGroupMembers.length }} visible members</p>
            </div>
            <button
              type="button"
              class="group-members-dialog-close"
              title="Close"
              @click="showGroupMembersDialog = false"
            >
              <i class="fas fa-times"></i>
            </button>
          </div>

          <div class="group-members-list">
            <div v-for="member in visibleGroupMembers" :key="member.key" class="group-member-row">
              <div class="group-member-avatar">{{ getInitials(member.name).slice(0, 2) }}</div>
              <div class="group-member-copy">
                <strong>{{ member.name }}</strong>
                <span>{{ member.roleLabel }}</span>
              </div>
            </div>
            <div v-if="!visibleGroupMembers.length" class="group-members-empty">
              No members are available.
            </div>
          </div>
        </section>
      </div>

      <!-- Mobile tabs (hidden on desktop) -->
      <nav class="mobile-tabs">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'tasks' }"
          @click="activeTab = 'tasks'"
        >
          Tasks
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'discussion' }"
          @click="activeTab = 'discussion'"
        >
          Discussion
        </button>
      </nav>

      <!-- Desktop: two columns; mobile: single column via tabs -->
      <div class="split" :data-active="activeTab">
        <!-- Left column: Tasks -->
        <section class="pane pane--tasks card">
          <div class="card-header">
            <h3 class="card-title">Tasks</h3>
            <div class="task-header-actions">
              <button
                type="button"
                class="task-mode-toggle"
                :class="{ 'is-active': taskSelectionMode }"
                :title="taskSelectionMode ? 'Exit select mode' : 'Select tasks for bulk actions'"
                :aria-pressed="taskSelectionMode"
                @click="toggleTaskSelectionMode"
              >
                <i class="fas fa-check-square"></i>
                {{ taskSelectionMode ? 'Done selecting' : 'Select' }}
              </button>
              <button
                v-if="canCreateGroupTasks"
                type="button"
                class="btn btn-primary btn-sm"
                :disabled="!backendGroupId || isLoadingTasks"
                title="Create a shared group task"
                @click="openCreateTaskDialog('group')"
              >
                <i class="fas fa-plus"></i> Group Task
              </button>
              <button
                v-if="canCreateIndividualTasks"
                type="button"
                class="btn btn-outline btn-sm"
                :disabled="!backendGroupId || isLoadingTasks"
                title="Create an individual task"
                @click="openCreateTaskDialog('individual')"
              >
                <i class="fas fa-user-plus"></i> Individual Task
              </button>
            </div>
          </div>
          <div class="card-content tasks-content">
            <div class="task-toolbar">
              <div class="task-search">
                <i class="fas fa-search task-search-icon" aria-hidden="true"></i>
                <input
                  v-model.trim="taskFilters.search"
                  type="search"
                  class="task-search-input"
                  placeholder="Search tasks..."
                  aria-label="Search tasks"
                />
              </div>
              <div class="task-toolbar-controls">
                <div class="task-filter-popover">
                  <button
                    type="button"
                    class="task-toolbar-btn"
                    :class="{ 'has-active': activeTaskFilterCount }"
                    :aria-expanded="isTaskFiltersOpen"
                    aria-haspopup="true"
                    @click="isTaskFiltersOpen = !isTaskFiltersOpen"
                  >
                    <i class="fas fa-sliders-h" aria-hidden="true"></i>
                    Filters
                    <span v-if="activeTaskFilterCount" class="task-filter-badge">
                      {{ activeTaskFilterCount }}
                    </span>
                  </button>
                  <div v-if="isTaskFiltersOpen" class="task-filter-panel" role="dialog" aria-label="Filters">
                    <label class="task-filter-row">
                      <span>Type</span>
                      <select v-model="taskFilters.taskType">
                        <option value="">All</option>
                        <option value="group">Group</option>
                        <option value="individual">Individual</option>
                      </select>
                    </label>
                    <label class="task-filter-row">
                      <span>Status</span>
                      <select v-model="taskFilters.status">
                        <option value="">All</option>
                        <option
                          v-for="option in TASK_STATUS_OPTIONS"
                          :key="option.value"
                          :value="option.value"
                        >
                          {{ option.label }}
                        </option>
                      </select>
                    </label>
                    <label class="task-filter-row">
                      <span>State</span>
                      <select v-model="taskFilters.completed">
                        <option value="">All</option>
                        <option value="true">Done</option>
                        <option value="false">Open</option>
                      </select>
                    </label>
                    <label class="task-filter-row">
                      <span>Assignee</span>
                      <select v-model="taskFilters.assignedUser">
                        <option value="">All members</option>
                        <option
                          v-for="member in taskAssigneeOptions"
                          :key="member.userId"
                          :value="String(member.userId)"
                        >
                          {{ member.label }}
                        </option>
                      </select>
                    </label>
                    <label class="task-filter-row">
                      <span>Subtasks of</span>
                      <select v-model="taskFilters.parentId">
                        <option value="">Any task</option>
                        <option
                          v-for="option in parentTaskFilterOptions"
                          :key="option.id"
                          :value="String(option.id)"
                        >
                          {{ option.label }}
                        </option>
                      </select>
                    </label>
                    <div class="task-filter-row-pair">
                      <label class="task-filter-row">
                        <span>Due after</span>
                        <input v-model="taskFilters.dueDateAfter" type="datetime-local" />
                      </label>
                      <label class="task-filter-row">
                        <span>Due before</span>
                        <input v-model="taskFilters.dueDateBefore" type="datetime-local" />
                      </label>
                    </div>
                    <label class="task-filter-row task-filter-row--checkbox">
                      <input
                        v-model="taskFilters.showDeleted"
                        type="checkbox"
                        @change="toggleDeletedTaskVisibility"
                      />
                      <span>Show deleted</span>
                    </label>
                    <div class="task-filter-panel-footer">
                      <button
                        type="button"
                        class="task-filter-clear"
                        :disabled="!activeTaskFilterCount"
                        @click="resetTaskFilters"
                      >
                        Clear
                      </button>
                      <button
                        type="button"
                        class="task-filter-close"
                        @click="isTaskFiltersOpen = false"
                      >
                        Close
                      </button>
                    </div>
                  </div>
                </div>
                <label class="task-toolbar-sort">
                  <span class="visually-hidden">Sort by</span>
                  <select v-model="taskFilters.ordering">
                    <option
                      v-for="option in TASK_ORDERING_OPTIONS"
                      :key="option.value"
                      :value="option.value"
                    >
                      Sort: {{ option.label }}
                    </option>
                  </select>
                </label>
                <button
                  type="button"
                  class="task-toolbar-icon-btn"
                  :class="{ 'is-active': showTaskDepthColors }"
                  :aria-pressed="showTaskDepthColors"
                  :title="showTaskDepthColors ? 'Tint by nesting level: on' : 'Tint by nesting level: off'"
                  :aria-label="showTaskDepthColors ? 'Disable level tint' : 'Enable level tint'"
                  @click="showTaskDepthColors = !showTaskDepthColors"
                >
                  <i class="fas fa-layer-group" aria-hidden="true"></i>
                </button>
                <button
                  v-if="hiddenStaleCompletedCount || showCompletedOverdue"
                  type="button"
                  class="task-toolbar-icon-btn"
                  :class="{ 'is-active': showCompletedOverdue }"
                  :aria-pressed="showCompletedOverdue"
                  :title="showCompletedOverdue
                    ? 'Hide completed tasks past their due date'
                    : `Show ${hiddenStaleCompletedCount} completed task${hiddenStaleCompletedCount === 1 ? '' : 's'} past due`"
                  :aria-label="showCompletedOverdue ? 'Hide completed overdue' : 'Show completed overdue'"
                  @click="showCompletedOverdue = !showCompletedOverdue"
                >
                  <i :class="showCompletedOverdue ? 'fas fa-eye' : 'fas fa-eye-slash'" aria-hidden="true"></i>
                  <span v-if="!showCompletedOverdue && hiddenStaleCompletedCount" class="task-toolbar-badge">
                    {{ hiddenStaleCompletedCount }}
                  </span>
                </button>
              </div>
            </div>


            <div v-if="taskError" class="task-banner is-error" role="alert">
              <i class="fas fa-exclamation-circle" aria-hidden="true"></i>
              <span>{{ taskError }}</span>
            </div>

            <div v-if="isLoadingTasks && !tasks.length" class="task-skeleton-list" aria-busy="true">
              <div v-for="n in 4" :key="`task-skeleton-${n}`" class="task-skeleton-row">
                <div class="task-skeleton-circle"></div>
                <div class="task-skeleton-lines">
                  <div class="task-skeleton-line task-skeleton-line--lg"></div>
                  <div class="task-skeleton-line task-skeleton-line--sm"></div>
                </div>
              </div>
            </div>

            <div
              v-for="section in taskSections"
              v-else
              :key="section.key"
              class="task-section"
            >
              <div class="task-section-header">
                <div class="task-section-title">
                  <i :class="section.icon" aria-hidden="true"></i>
                  <span>{{ section.title }}</span>
                  <span v-if="section.total" class="task-section-count">{{ section.total }}</span>
                </div>
                <div
                  v-if="section.total"
                  class="task-section-progress"
                  :title="`${section.completed} of ${section.total} complete`"
                >
                  <div class="task-section-progress-bar">
                    <div
                      class="task-section-progress-fill"
                      :style="{ width: `${Math.round((section.completed / section.total) * 100)}%` }"
                    ></div>
                  </div>
                  <span class="task-section-progress-label">
                    {{ Math.round((section.completed / section.total) * 100) }}%
                  </span>
                </div>
              </div>
              <ul class="task-list" role="tree">
                <li
                  v-for="row in section.rows"
                  :key="row.task.id"
                  class="task-item"
                  :class="[
                    showTaskDepthColors ? `task-depth-${Math.min(row.depth, 4)}` : 'task-depth-flat',
                    {
                      'is-subtask': row.depth > 0,
                      'is-deleted': row.task.deletedAt,
                      'is-complete': row.task.completed,
                      'is-selected': isTaskSelected(row.task.id),
                    },
                  ]"
                  :style="{ '--task-depth': row.depth }"
                  role="treeitem"
                  :aria-level="row.depth + 1"
                  :aria-selected="isTaskSelected(row.task.id)"
                  :aria-expanded="row.hasChildren ? !row.isCollapsed : undefined"
                >
                  <button
                    v-if="row.hasChildren"
                    type="button"
                    class="task-collapse"
                    :class="{ 'is-collapsed': row.isCollapsed }"
                    :title="row.isCollapsed ? `Show ${row.childCount} sub-task${row.childCount === 1 ? '' : 's'}` : 'Hide sub-tasks'"
                    :aria-label="row.isCollapsed ? `Show sub-tasks of ${row.task.name}` : `Hide sub-tasks of ${row.task.name}`"
                    :aria-expanded="!row.isCollapsed"
                    @click="toggleTaskCollapsed(row.task.id)"
                  >
                    <i class="fas fa-chevron-down" aria-hidden="true"></i>
                  </button>
                  <span v-else class="task-collapse-spacer" aria-hidden="true"></span>

                  <button
                    v-if="taskSelectionMode"
                    type="button"
                    class="task-select-box"
                    :class="{ 'is-selected': isTaskSelected(row.task.id) }"
                    :disabled="
                      row.task.deletedAt ||
                      !canToggleTask(row.task)
                    "
                    :aria-label="
                      `${isTaskSelected(row.task.id) ? 'Deselect' : 'Select'} ${row.task.name}`
                    "
                    :aria-pressed="isTaskSelected(row.task.id)"
                    @click="setTaskSelected(row.task.id, !isTaskSelected(row.task.id))"
                  >
                    <i
                      v-if="isTaskSelected(row.task.id)"
                      class="fas fa-check"
                      aria-hidden="true"
                    ></i>
                  </button>

                  <div v-else class="task-state-wrap">
                    <button
                      type="button"
                      class="task-state"
                      :class="[
                        `task-state--${row.task.status || 'todo'}`,
                        { 'is-open': isStatusMenuOpen(row.task.id), 'is-disabled': !canToggleTask(row.task) },
                      ]"
                      :data-status="row.task.status || 'todo'"
                      :disabled="
                        isUpdatingTask(row.task.id) ||
                        row.task.deletedAt ||
                        !canToggleTask(row.task)
                      "
                      :aria-haspopup="canToggleTask(row.task) ? 'menu' : undefined"
                      :aria-expanded="isStatusMenuOpen(row.task.id)"
                      :aria-label="`Status: ${getTaskStatusMeta(row.task.status).label}. ${canToggleTask(row.task) ? 'Click to change.' : ''}`"
                      :title="canToggleTask(row.task) ? 'Change status' : `Status: ${getTaskStatusMeta(row.task.status).label}`"
                      @click="canToggleTask(row.task) && (isStatusMenuOpen(row.task.id) ? closeStatusMenu() : openStatusMenu(row.task.id))"
                    >
                      <i :class="`fas fa-${getTaskStatusMeta(row.task.status).icon}`" aria-hidden="true"></i>
                      <span class="task-state-label">{{ getTaskStatusMeta(row.task.status).short }}</span>
                      <i v-if="canToggleTask(row.task)" class="fas fa-caret-down task-state-caret" aria-hidden="true"></i>
                    </button>

                    <div
                      v-if="isStatusMenuOpen(row.task.id)"
                      class="task-state-menu"
                      role="menu"
                      :aria-label="`Set status for ${row.task.name}`"
                    >
                      <button
                        v-for="opt in TASK_STATUS_OPTIONS"
                        :key="opt.value"
                        type="button"
                        class="task-state-menu-item"
                        :class="[
                          `task-state--${opt.value}`,
                          { 'is-current': row.task.status === opt.value },
                        ]"
                        role="menuitem"
                        @click="changeTaskStatus(row.task, opt.value)"
                      >
                        <i :class="`fas fa-${getTaskStatusMeta(opt.value).icon}`" aria-hidden="true"></i>
                        <span>{{ opt.label }}</span>
                        <i v-if="row.task.status === opt.value" class="fas fa-check task-state-menu-check" aria-hidden="true"></i>
                      </button>
                    </div>
                  </div>

                  <div class="task-body">
                    <div class="task-headline">
                      <span class="task-label">{{ row.task.name }}</span>
                      <span
                        v-if="row.task.deletedAt"
                        class="task-chip task-chip--deleted"
                      >
                        <i class="fas fa-trash" aria-hidden="true"></i>
                        Deleted
                      </span>
                    </div>
                    <div v-if="row.task.description" class="task-description">
                      {{ row.task.description }}
                    </div>
                    <div v-if="row.task.dueDate || row.task.createdBy" class="task-meta">
                      <span
                        v-if="row.task.dueDate"
                        class="task-chip task-chip--date"
                        :class="{ 'is-overdue': isTaskOverdue(row.task) }"
                      >
                        <i class="fas fa-calendar" aria-hidden="true"></i>
                        {{ formatDate(row.task.dueDate) }}
                      </span>
                      <span
                        v-if="row.task.createdBy && row.task.createdBy.name"
                        class="task-assigned-by"
                        :title="row.task.creatorRole ? `Role: ${formatTaskStatus(row.task.creatorRole)}` : ''"
                      >
                        Assigned by
                        <strong>{{ row.task.createdBy.name }}</strong>
                      </span>
                    </div>
                  </div>

                  <button
                    v-if="row.task.taskType === 'individual' && getAssigneeDisplay(row.task)"
                    type="button"
                    class="task-assignee"
                    :class="{
                      'is-self': getAssigneeDisplay(row.task).isSelf,
                      'is-active': String(taskFilters.assignedUser) === String(row.task.assignedUser),
                    }"
                    :title="`Filter tasks by ${getAssigneeDisplay(row.task).isSelf ? 'you' : getAssigneeDisplay(row.task).label}`"
                    :aria-label="`Filter by ${getAssigneeDisplay(row.task).isSelf ? 'you' : getAssigneeDisplay(row.task).label}`"
                    @click="toggleAssigneeQuickFilter(row.task.assignedUser)"
                  >
                    <i :class="getAssigneeDisplay(row.task).isSelf ? 'fas fa-circle-user' : 'fas fa-user'" aria-hidden="true"></i>
                    <span>{{ getAssigneeDisplay(row.task).label }}</span>
                  </button>

                  <div class="task-row-actions">
                    <button
                      type="button"
                      class="task-icon-btn"
                      :disabled="
                        isLoadingTasks ||
                        row.task.deletedAt ||
                        !canCreateTaskType(row.task.taskType, row.task)
                      "
                      title="Add a sub-task"
                      :aria-label="`Add a sub-task to ${row.task.name}`"
                      @click="openCreateTaskDialog(row.task.taskType, row.task)"
                    >
                      <i class="fas fa-plus" aria-hidden="true"></i>
                    </button>
                    <button
                      v-if="canManageTask(row.task)"
                      type="button"
                      class="task-icon-btn"
                      :disabled="isLoadingTasks || row.task.deletedAt"
                      title="Edit task"
                      :aria-label="`Edit ${row.task.name}`"
                      @click="openEditTaskDialog(row.task)"
                    >
                      <i class="fas fa-pen" aria-hidden="true"></i>
                    </button>
                    <button
                      v-if="canManageTask(row.task)"
                      type="button"
                      class="task-icon-btn task-icon-btn--danger"
                      :disabled="isDeletingTask(row.task.id) || row.task.deletedAt"
                      title="Delete task"
                      :aria-label="`Delete ${row.task.name}`"
                      @click="removeTask(row.task)"
                    >
                      <i class="fas fa-trash" aria-hidden="true"></i>
                    </button>
                  </div>
                </li>

                <li v-if="!section.rows.length" class="task-empty-state">
                  <i :class="section.icon" aria-hidden="true"></i>
                  <span>No {{ section.title.toLowerCase() }} yet.</span>
                  <button
                    v-if="(section.key === 'group' && canCreateGroupTasks) || (section.key === 'individual' && canCreateIndividualTasks)"
                    type="button"
                    class="task-empty-cta"
                    @click="openCreateTaskDialog(section.key)"
                  >
                    <i class="fas fa-plus" aria-hidden="true"></i>
                    Add {{ section.key === 'group' ? 'group' : 'individual' }} task
                  </button>
                </li>
              </ul>
            </div>

            <div
              v-if="!isLoadingTasks && totalRelevantTaskCount"
              class="task-list-footer"
            >
              <span class="task-list-count">
                Showing {{ visibleSectionTaskCount }} of {{ totalRelevantTaskCount }}
              </span>
              <button
                v-if="hasMoreTasksToShow"
                type="button"
                class="task-list-more"
                @click="loadMoreTasks"
              >
                Show {{ Math.min(TASK_LOAD_BATCH, totalRelevantTaskCount - taskShownLimit) }} more
              </button>
            </div>

            <transition name="task-bulk-fade">
              <div
                v-if="selectedTaskIds.size"
                class="task-bulk-bar"
                role="region"
                aria-label="Bulk task actions"
              >
                <span class="task-bulk-count">
                  <i class="fas fa-check-square" aria-hidden="true"></i>
                  {{ selectedTaskIds.size }} selected
                </span>
                <div class="task-bulk-actions">
                  <button
                    type="button"
                    class="task-bulk-btn task-bulk-btn--primary"
                    :disabled="isBulkUpdatingTasks"
                    @click="bulkSetTaskCompletion(true)"
                  >
                    <i class="fas fa-check" aria-hidden="true"></i> Mark done
                  </button>
                  <button
                    type="button"
                    class="task-bulk-btn"
                    :disabled="isBulkUpdatingTasks"
                    @click="bulkSetTaskCompletion(false)"
                  >
                    <i class="fas fa-undo" aria-hidden="true"></i> Reopen
                  </button>
                  <button
                    type="button"
                    class="task-bulk-btn task-bulk-btn--ghost"
                    :disabled="isBulkUpdatingTasks"
                    @click="clearTaskSelection"
                  >
                    Clear
                  </button>
                </div>
              </div>
            </transition>
          </div>

          <Transition name="task-dialog">
            <div
              v-if="taskDialogOpen"
              class="task-dialog-backdrop"
              role="dialog"
              aria-modal="true"
              :aria-label="taskDialogTitle"
              @click.self="closeTaskDialog"
              @keydown.esc="closeTaskDialog"
            >
              <form class="task-dialog" @submit.prevent="saveTask" @keydown.meta.enter.prevent="saveTask" @keydown.ctrl.enter.prevent="saveTask">
                <header class="task-dialog-header">
                  <div class="task-dialog-title">
                    <i :class="taskDialogMode === 'edit' ? 'fas fa-pen' : 'fas fa-plus'" aria-hidden="true"></i>
                    <h4>{{ taskDialogTitle }}</h4>
                  </div>
                  <button
                    type="button"
                    class="task-dialog-close"
                    title="Close (Esc)"
                    aria-label="Close dialog"
                    @click="closeTaskDialog"
                  >
                    <i class="fas fa-times" aria-hidden="true"></i>
                  </button>
                </header>

                <div v-if="taskFormError" class="task-banner is-error" role="alert">
                  <i class="fas fa-exclamation-circle" aria-hidden="true"></i>
                  <span>{{ taskFormError }}</span>
                </div>

                <div class="task-dialog-body">
                  <input
                    ref="taskDialogNameInput"
                    v-model.trim="taskForm.name"
                    type="text"
                    class="task-dialog-title-input"
                    placeholder="Task name"
                    maxlength="255"
                    required
                  />

                  <textarea
                    v-model.trim="taskForm.description"
                    class="task-dialog-description-input"
                    placeholder="Add a description..."
                    rows="3"
                  ></textarea>

                  <!-- Type as segmented control -->
                  <div class="task-dialog-field">
                    <label class="task-dialog-label">
                      <i class="fas fa-layer-group" aria-hidden="true"></i>
                      <span>Type</span>
                    </label>
                    <div class="task-segmented" role="radiogroup" aria-label="Task type">
                      <button
                        v-for="option in allowedTaskTypeOptions"
                        :key="option.value"
                        type="button"
                        class="task-segmented-option"
                        :class="{ 'is-active': taskForm.taskType === option.value }"
                        :disabled="taskDialogMode === 'edit'"
                        role="radio"
                        :aria-checked="taskForm.taskType === option.value"
                        @click="taskForm.taskType = option.value; syncTaskAssigneeForType()"
                      >
                        <i :class="option.value === 'group' ? 'fas fa-users' : 'fas fa-user'" aria-hidden="true"></i>
                        {{ option.label }}
                      </button>
                    </div>
                  </div>

                  <!-- Status as colored pill segmented control -->
                  <div class="task-dialog-field">
                    <label class="task-dialog-label">
                      <i class="fas fa-flag" aria-hidden="true"></i>
                      <span>Status</span>
                    </label>
                    <div class="task-segmented task-segmented--status" role="radiogroup" aria-label="Task status">
                      <button
                        v-for="option in TASK_STATUS_OPTIONS"
                        :key="option.value"
                        type="button"
                        class="task-segmented-option task-segmented-option--status"
                        :class="[
                          `task-state--${option.value}`,
                          { 'is-active': taskForm.status === option.value },
                        ]"
                        role="radio"
                        :aria-checked="taskForm.status === option.value"
                        @click="taskForm.status = option.value"
                      >
                        <i :class="`fas fa-${getTaskStatusMeta(option.value).icon}`" aria-hidden="true"></i>
                        {{ option.label }}
                      </button>
                    </div>
                  </div>

                  <div class="task-dialog-row">
                    <div class="task-dialog-field task-dialog-field--half">
                      <label class="task-dialog-label" for="task-dialog-due">
                        <i class="fas fa-calendar" aria-hidden="true"></i>
                        <span>Due date</span>
                      </label>
                      <input id="task-dialog-due" v-model="taskForm.dueDate" type="datetime-local" class="task-dialog-input" />
                    </div>

                    <div v-if="taskForm.taskType === 'individual'" class="task-dialog-field task-dialog-field--half">
                      <label class="task-dialog-label" for="task-dialog-assignee">
                        <i class="fas fa-user-tag" aria-hidden="true"></i>
                        <span>Assignee</span>
                      </label>
                      <div
                        v-if="taskDialogMode === 'edit' || isStudentOnlyIndividualAssignee"
                        class="task-dialog-readonly"
                      >
                        {{ selectedTaskAssigneeLabel }}
                      </div>
                      <select v-else id="task-dialog-assignee" v-model="taskForm.assignedUser" class="task-dialog-input" required>
                        <option value="" disabled>Select assignee</option>
                        <option
                          v-for="option in individualTaskAssigneeOptions"
                          :key="option.userId"
                          :value="String(option.userId)"
                        >
                          {{ option.label }}
                        </option>
                      </select>
                    </div>
                  </div>
                </div>

                <footer class="task-dialog-footer">
                  <span class="task-dialog-hint">
                    <kbd>Esc</kbd> close &middot; <kbd>Ctrl</kbd>+<kbd>Enter</kbd> save
                  </span>
                  <div class="task-dialog-actions">
                    <button type="button" class="task-dialog-btn" @click="closeTaskDialog">Cancel</button>
                    <button type="submit" class="task-dialog-btn task-dialog-btn--primary" :disabled="isSavingTask">
                      <i v-if="!isSavingTask" :class="taskDialogMode === 'edit' ? 'fas fa-check' : 'fas fa-plus'" aria-hidden="true"></i>
                      <i v-else class="fas fa-spinner fa-spin" aria-hidden="true"></i>
                      {{ isSavingTask ? 'Saving...' : (taskDialogMode === 'edit' ? 'Save changes' : 'Create task') }}
                    </button>
                  </div>
                </footer>
              </form>
            </div>
          </Transition>
        </section>

        <!-- Right column: Discussion -->
        <section class="pane pane--discussion">
          <div class="chat-container">
            <!-- Discussion header -->
            <div class="chat-header">
              <h3 style="margin: 0">Discussion Board</h3>
              <div class="chat-header-actions">
                <button
                  type="button"
                  class="mentions-toggle chat-search-toggle"
                  :class="{ active: showMessageSearch }"
                  title="Search messages"
                  @click="toggleMessageSearch"
                >
                  <i class="fas fa-search"></i>
                </button>
                <button
                  type="button"
                  class="mentions-toggle"
                  :class="{ active: showMentionInbox }"
                  title="Mentions"
                  @click="toggleMentionInbox"
                >
                  <i class="fas fa-at"></i>
                  <span v-if="mentionUnreadCount" class="mention-badge">{{ mentionUnreadCount }}</span>
                </button>
                <span
                  class="chat-status"
                  :class="`chat-status--${isLoadingMessages ? 'loading' : (wsConnectionState === 'connected' ? 'connected' : 'offline')}`"
                  :title="
                    isLoadingMessages
                      ? 'Fetching latest messages'
                      : (wsConnectionState === 'connected'
                          ? 'Realtime updates active'
                          : 'Realtime updates unavailable — click Reconnect to retry')
                  "
                >
                  <i
                    class="chat-status-dot"
                    :class="{
                      'fas fa-circle-notch fa-spin': isLoadingMessages,
                      'fas fa-circle': !isLoadingMessages,
                    }"
                    aria-hidden="true"
                  ></i>
                  <template v-if="isLoadingMessages">Loading…</template>
                  <template v-else-if="wsConnectionState === 'connected'">Live</template>
                  <template v-else>Offline</template>
                  <button
                    v-if="!isLoadingMessages && wsConnectionState !== 'connected'"
                    type="button"
                    class="chat-reconnect-btn"
                    aria-label="Reconnect to live chat"
                    @click="connectChatSocket"
                  >
                    Reconnect
                  </button>
                </span>
              </div>
            </div>

            <div v-if="chatError" class="chat-alert">
              {{ chatError }}
            </div>
            <div v-if="chatNotice" class="chat-notice">
              {{ chatNotice }}
            </div>
            <div v-if="showMessageSearch" class="message-search-panel">
              <form class="message-search-form" @submit.prevent="searchMessages(true)">
                <input
                  ref="messageSearchInputRef"
                  v-model.trim="messageSearchQuery"
                  type="search"
                  class="message-search-input"
                  placeholder="Search messages"
                />
                <button
                  type="submit"
                  class="message-action-btn"
                  :disabled="isSearchingMessages"
                >
                  {{ isSearchingMessages ? 'Searching...' : 'Search' }}
                </button>
                <button
                  type="button"
                  class="message-action-btn"
                  :class="{ active: showSearchFilters }"
                  :aria-pressed="showSearchFilters"
                  @click="showSearchFilters = !showSearchFilters"
                >
                  <i class="fas fa-sliders-h"></i> Filters
                </button>
                <button
                  v-if="messageSearchQuery || messageSearchResults.length || hasActiveSearchFilters()"
                  type="button"
                  class="message-action-btn"
                  @click="clearMessageSearch"
                >
                  Clear
                </button>
              </form>
              <div v-if="showSearchFilters" class="message-search-filters">
                <label>
                  <span>Type</span>
                  <select v-model="messageSearchFilters.type">
                    <option value="">Any</option>
                    <option value="text">Text</option>
                    <option value="attachment">Attachments</option>
                    <option value="resource">Resources</option>
                    <option value="gif">GIFs</option>
                  </select>
                </label>
                <label>
                  <span>From</span>
                  <input type="date" v-model="messageSearchFilters.from" />
                </label>
                <label>
                  <span>To</span>
                  <input type="date" v-model="messageSearchFilters.to" />
                </label>
              </div>
              <div v-if="messageSearchError" class="gif-status">{{ messageSearchError }}</div>
              <div v-if="isSearchingMessages" class="gif-status">Searching messages...</div>
              <div v-else class="message-search-list">
                <button
                  v-for="result in messageSearchResults"
                  :key="`search-${result.id}`"
                  type="button"
                  class="message-search-row"
                  @click="openSearchResult(result)"
                >
                  <span class="message-search-row-head">
                    <strong>{{ result.author }}</strong>
                    <small>{{ formatDate(result.date) }} {{ result.time }}</small>
                  </span>
                  <span class="message-search-text">
                    <template v-if="result.text">
                      <template
                        v-for="(segment, segmentIndex) in getMessageTextSegments(result.text)"
                        :key="`${result.id}-search-segment-${segmentIndex}`"
                      >
                        <span v-if="segment.type === 'mention'" class="mention-token">{{
                          segment.text
                        }}</span>
                        <span v-else>{{ segment.text }}</span>
                      </template>
                    </template>
                    <template v-else>{{ getMessageSearchSummary(result) }}</template>
                  </span>
                  <span
                    v-if="result.attachments?.length || result.resources?.length || result.preview"
                    class="message-search-tags"
                  >
                    <span v-if="result.attachments?.length">
                      <i class="fas fa-paperclip"></i> Attachment
                    </span>
                    <span v-if="result.resources?.length">
                      <i class="fas fa-book-open"></i> Resource
                    </span>
                    <span v-if="result.preview">
                      <i class="fas fa-link"></i> Preview
                    </span>
                  </span>
                </button>
                <button
                  v-if="messageSearchNextBefore"
                  type="button"
                  class="load-older-messages"
                  :disabled="isLoadingMoreSearchResults"
                  @click="loadMoreSearchResults"
                >
                  {{ isLoadingMoreSearchResults ? 'Loading...' : 'Load more results' }}
                </button>
                <div
                  v-if="
                    messageSearchQuery &&
                    !messageSearchResults.length &&
                    !messageSearchError &&
                    hasSearchedMessages
                  "
                  class="gif-status"
                >
                  No matching messages.
                </div>
              </div>
            </div>
            <div v-if="showMentionInbox" class="mention-inbox">
              <div class="mention-inbox-header">
                <strong>Mentions</strong>
                <button
                  type="button"
                  class="message-action-btn"
                  :disabled="!mentionUnreadCount || isUpdatingMentions"
                  @click="markAllMentionsRead"
                >
                  Mark all read
                </button>
              </div>
              <div v-if="mentionInboxError" class="gif-status">{{ mentionInboxError }}</div>
              <div v-if="isLoadingMentions" class="gif-status">Loading mentions...</div>
              <div v-else class="mention-list">
                <button
                  v-for="mention in mentionItems"
                  :key="mention.id"
                  type="button"
                  class="mention-row"
                  :class="{ unread: !mention.read_at }"
                  @click="openMention(mention)"
                >
                  <span>{{ getMentionSenderLabel(mention) }}</span>
                  <strong>
                    <template
                      v-for="(segment, segmentIndex) in getMessageTextSegments(
                        mention.message_text,
                      )"
                      :key="`${mention.id}-mention-segment-${segmentIndex}`"
                    >
                      <span v-if="segment.type === 'mention'" class="mention-token">{{
                        segment.text
                      }}</span>
                      <span v-else>{{ segment.text }}</span>
                    </template>
                    <template v-if="!mention.message_text">Message was deleted.</template>
                  </strong>
                  <small>{{ formatDate(mention.sent_at) }} {{ formatTime(mention.sent_at) }}</small>
                </button>
                <div v-if="!mentionItems.length && !mentionInboxError" class="gif-status">
                  No mentions yet.
                </div>
              </div>
            </div>

            <div class="chat-messages" ref="msgList" @scroll="handleMessagesScroll">
              <div
                v-if="isLoadingMessages && !messages.length"
                class="chat-skeleton-list"
                aria-hidden="true"
              >
                <div v-for="i in 4" :key="`msg-sk-${i}`" class="chat-skeleton-row">
                  <div class="skeleton-message-avatar skeleton-block"></div>
                  <div class="chat-skeleton-body">
                    <div class="skeleton-line skeleton-block" style="width: 30%"></div>
                    <div class="skeleton-line skeleton-block" style="width: 80%"></div>
                    <div class="skeleton-line skeleton-block" style="width: 60%"></div>
                  </div>
                </div>
              </div>
              <div
                v-else-if="!isLoadingMessages && !messages.length"
                class="chat-empty-state"
              >
                <span class="chat-empty-emoji" aria-hidden="true">👋</span>
                <strong>It's quiet here</strong>
                <span>Be the first to say hi — start the conversation below.</span>
                <button type="button" class="btn btn-outline btn-sm" @click="composer?.focus()">
                  <i class="fas fa-pen"></i> Write a message
                </button>
              </div>
              <div
                v-if="isLoadingOlderMessages"
                class="load-older-status"
                role="status"
                aria-live="polite"
              >
                <span class="loading load-older-spinner" aria-hidden="true"></span>
                <span>Loading older messages...</span>
              </div>
              <button
                v-else-if="nextMessagesBefore"
                type="button"
                class="load-older-messages"
                @click="loadOlderMessages"
              >
                Load older messages
              </button>
              <div
                v-for="message in messages"
                :key="message.id"
                class="message-thread-item"
              >
                <div
                  v-if="isMissedMessageAnchor(message.id)"
                  class="missed-message-divider"
                  role="status"
                  aria-live="polite"
                >
                  <span>{{ missedMessageDividerText }}</span>
                  <button type="button" @click="scrollMessagesToBottom">Jump to latest</button>
                </div>
                <div
                  :data-message-id="message.id"
                  :class="[
                    'message',
                    {
                      own: message.isOwn,
                      pending: message.isLocalOnly,
                      'search-hit': String(highlightedSearchMessageId) === String(message.id),
                    },
                  ]"
                >
                <div class="message-avatar">{{ getInitials(message.author) }}</div>
                <div class="message-content">
                  <div class="message-header">
                    <span class="message-author">{{ message.author }}</span>
                    <span class="message-meta">
                      <span v-if="message.editedAt" class="message-edited">edited</span>
                      <span class="message-date">{{ formatDate(message.date) }}</span>
                      <span class="message-time">{{ message.time }}</span>
                      <!-- Inline action cluster: always-visible reply + smile,
                           and a kebab menu (Edit/Delete) shown only while the
                           10-min self-action window is open or the caller is
                           an admin (``canManageMessage``). -->
                      <span class="message-inline-actions">
                        <button
                          type="button"
                          class="inline-action-btn"
                          title="Reply"
                          aria-label="Reply"
                          @click="setReplyTarget(message)"
                        >
                          <i class="fas fa-reply"></i>
                        </button>
                        <button
                          v-if="supportsMessageReactions"
                          type="button"
                          class="inline-action-btn"
                          :class="{ active: activeReactionPickerMessageId === message.id }"
                          :title="hasMessageReactions(message) ? 'Add another reaction' : 'Add reaction'"
                          aria-label="Add reaction"
                          @click.stop="toggleReactionPicker(message.id)"
                        >
                          <i class="fas fa-smile"></i>
                        </button>
                        <span
                          v-if="canManageMessage(message)"
                          class="inline-kebab-wrap"
                        >
                          <button
                            type="button"
                            class="inline-action-btn"
                            :class="{ active: openMessageKebabId === message.id }"
                            :aria-expanded="openMessageKebabId === message.id"
                            aria-haspopup="menu"
                            title="More actions"
                            aria-label="More actions"
                            @click.stop="toggleMessageKebab(message.id)"
                          >
                            <i class="fas fa-ellipsis-v"></i>
                          </button>
                          <div
                            v-if="openMessageKebabId === message.id"
                            class="inline-kebab-menu"
                            role="menu"
                            @click.stop
                          >
                            <button
                              type="button"
                              class="inline-kebab-item"
                              role="menuitem"
                              @click="onKebabEdit(message)"
                            >
                              <i class="fas fa-pen"></i>
                              <span>Edit</span>
                            </button>
                            <button
                              type="button"
                              class="inline-kebab-item inline-kebab-item--danger"
                              role="menuitem"
                              :disabled="isDeletingMessageId === message.id"
                              @click="onKebabDelete(message)"
                            >
                              <i class="fas fa-trash"></i>
                              <span>Delete</span>
                            </button>
                          </div>
                        </span>
                        <!-- Inline picker popout — anchors to the smile button just above. -->
                        <div
                          v-if="supportsMessageReactions && activeReactionPickerMessageId === message.id"
                          class="reaction-picker reaction-picker--inline"
                          role="menu"
                          aria-label="Quick reactions"
                          @click.stop
                        >
                          <button
                            v-for="emoji in CHAT_REACTION_OPTIONS"
                            :key="`${message.id}-inline-${emoji}`"
                            type="button"
                            class="reaction-btn"
                            :title="`React with ${emoji}`"
                            @click="reactToMessage(message.id, emoji)"
                          >
                            <span>{{ emoji }}</span>
                          </button>
                        </div>
                      </span>
                    </span>
                  </div>
                  <div v-if="message.replyTo" class="message-reply">
                    <span>{{ getReplyLabel(message.replyTo) }}</span>
                    <strong>{{ getReplyText(message.replyTo) }}</strong>
                  </div>
                  <img
                    v-if="message.messageType === 'gif' && message.gifUrl"
                    :src="message.gifUrl"
                    :alt="message.text || 'GIF message'"
                    class="message-gif"
                    width="280"
                    height="210"
                    loading="lazy"
                    decoding="async"
                  />
                  <div v-else-if="editingMessageId !== message.id" class="message-text">
                    <template
                      v-for="(segment, segmentIndex) in getMessageTextSegments(message.text)"
                      :key="`${message.id}-segment-${segmentIndex}`"
                    >
                      <span v-if="segment.type === 'mention'" class="mention-token">{{
                        segment.text
                      }}</span>
                      <span v-else>{{ segment.text }}</span>
                    </template>
                  </div>
                  <form v-else class="message-edit-form" @submit.prevent="saveMessageEdit(message)">
                    <textarea
                      v-model="editingMessageText"
                      class="chat-input-field"
                      rows="2"
                    ></textarea>
                    <div class="message-edit-actions">
                      <button
                        type="button"
                        class="btn btn-outline btn-sm message-edit-cancel"
                        @click="cancelMessageEdit"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        class="btn btn-primary btn-sm message-edit-save"
                        :disabled="isUpdatingMessage"
                      >
                        {{ isUpdatingMessage ? 'Saving...' : 'Save' }}
                      </button>
                    </div>
                  </form>

                  <div v-if="message.attachments?.length" class="message-attachments">
                    <span
                      v-for="attachment in message.attachments"
                      :key="attachment.id || attachment.attachment_filename"
                      class="resource-chip-wrap"
                    >
                      <button
                        type="button"
                        class="attachment-chip"
                        :title="getAttachmentLabel(attachment)"
                        @click.stop="toggleAttachmentChoice(message.id, attachment)"
                      >
                        <i class="fas fa-paperclip"></i>
                        {{ getAttachmentLabel(attachment) }}
                      </button>
                      <div
                        v-if="
                          openAttachmentChoiceKey
                            === `${message.id}:${attachment.id || attachment.attachment_filename}`
                        "
                        class="resource-choice-popover"
                        role="menu"
                        @click.stop
                      >
                        <div
                          v-if="attachmentChoiceStatus"
                          class="resource-choice-status"
                        >
                          {{ attachmentChoiceStatus }}
                        </div>
                        <div class="resource-choice-actions">
                          <button
                            type="button"
                            class="resource-choice-btn"
                            title="Open in a new tab"
                            aria-label="Open"
                            :disabled="attachmentChoiceLoading"
                            @click="openAttachmentAction(attachment, 'open')"
                          >
                            <i class="fas fa-eye"></i>
                          </button>
                          <button
                            type="button"
                            class="resource-choice-btn"
                            title="Download"
                            aria-label="Download"
                            :disabled="attachmentChoiceLoading"
                            @click="openAttachmentAction(attachment, 'download')"
                          >
                            <i class="fas fa-arrow-down"></i>
                          </button>
                          <button
                            type="button"
                            class="resource-choice-btn resource-choice-btn--danger"
                            title="Cancel"
                            aria-label="Cancel"
                            @click="closeAttachmentChoice"
                          >
                            <i class="fas fa-times"></i>
                          </button>
                        </div>
                      </div>
                    </span>
                  </div>

                  <div v-if="message.resources?.length" class="message-attachments">
                    <span
                      v-for="resource in message.resources"
                      :key="resource.resource_id || resource.id"
                      class="resource-chip-wrap"
                    >
                      <button
                        type="button"
                        class="attachment-chip attachment-chip--resource"
                        :title="getResourceLabel(resource)"
                        @click.stop="toggleResourceChoice(message.id, resource)"
                      >
                        <i class="fas fa-book-open"></i>
                        {{ getResourceLabel(resource) }}
                      </button>
                      <div
                        v-if="
                          openResourceChoiceKey
                            === `${message.id}:${resource.resource_id || resource.id}`
                        "
                        class="resource-choice-popover"
                        role="menu"
                        @click.stop
                      >
                        <div
                          v-if="resourceChoiceStatus"
                          class="resource-choice-status"
                        >
                          {{ resourceChoiceStatus }}
                        </div>
                        <div class="resource-choice-actions">
                          <button
                            type="button"
                            class="resource-choice-btn"
                            title="Open in a new tab"
                            aria-label="Open"
                            :disabled="resourceChoiceLoading"
                            @click="openResourceAction(resource, 'open')"
                          >
                            <i class="fas fa-eye"></i>
                          </button>
                          <button
                            type="button"
                            class="resource-choice-btn"
                            title="Download"
                            aria-label="Download"
                            :disabled="resourceChoiceLoading"
                            @click="openResourceAction(resource, 'download')"
                          >
                            <i class="fas fa-arrow-down"></i>
                          </button>
                          <button
                            type="button"
                            class="resource-choice-btn resource-choice-btn--danger"
                            title="Cancel"
                            aria-label="Cancel"
                            @click="closeResourceChoice"
                          >
                            <i class="fas fa-times"></i>
                          </button>
                        </div>
                      </div>
                    </span>
                  </div>

                  <div v-if="message.preview" class="message-preview">
                    <img
                      v-if="message.preview.img"
                      :src="message.preview.img"
                      :alt="message.preview.title || 'Link preview'"
                      width="320"
                      height="180"
                      loading="lazy"
                      decoding="async"
                    />
                    <strong v-if="message.preview.title">{{ message.preview.title }}</strong>
                    <span v-if="message.preview.desc">{{ message.preview.desc }}</span>
                  </div>

                  <!-- Reaction chips strip — always at bottom-left of bubble.
                       The smile add-button now lives in the header (next to time)
                       so this block is read-only display of existing reactions. -->
                  <div
                    v-if="hasMessageReactions(message)"
                    class="reaction-pick-group has-reactions"
                  >
                    <div class="message-reactions" role="group" aria-label="Message reactions">
                      <button
                        v-for="[emoji, entry] in Object.entries(message.reactions)"
                        :key="`${message.id}-${emoji}-summary`"
                        type="button"
                        class="reaction-summary-btn"
                        :title="formatReactionUsers(entry)"
                        :disabled="!supportsMessageReactions"
                        @click="reactToMessage(message.id, emoji)"
                      >
                        <span>{{ emoji }}</span>
                        <span class="reaction-count">{{ entry.count || entry }}</span>
                      </button>
                    </div>
                  </div>

                  <div
                    v-if="message.isOwn"
                    class="message-receipt-wrap"
                  >
                    <button
                      type="button"
                      class="message-receipt message-receipt--ticks"
                      :class="[
                        `message-receipt--${getReceiptState(message)}`,
                        { 'is-open': openReceiptPopoverId === message.id },
                      ]"
                      :aria-expanded="openReceiptPopoverId === message.id"
                      :aria-label="getReceiptAriaLabel(message)"
                      :title="getReceiptAriaLabel(message)"
                      aria-haspopup="dialog"
                      @click.stop="openMessageReceipts(message.id, $event)"
                      @keydown.esc.stop="closeReceiptPopover"
                    >
                      <i
                        v-if="getReceiptState(message) === 'delivered'"
                        class="fas fa-check tick-icon"
                      ></i>
                      <i
                        v-else
                        class="fas fa-check-double tick-icon"
                      ></i>
                    </button>
                    <Teleport to="body">
                      <div
                        v-if="openReceiptPopoverId === message.id"
                        class="message-receipt-popover message-receipt-popover--floating"
                        role="dialog"
                        aria-label="Read receipts"
                        :style="receiptPopoverStyle"
                        @click.stop
                        @keydown.esc.stop="closeReceiptPopover"
                      >
                      <div v-if="isLoadingReceipts" class="message-receipt-popover-status">
                        Loading…
                      </div>
                      <div v-else-if="receiptError" class="message-receipt-popover-status error">
                        {{ receiptError }}
                      </div>
                      <template v-else>
                        <div
                          v-if="messageReceiptCache.get(message.id)?.readBy?.length"
                          class="message-receipt-popover-section"
                        >
                          <strong>Read by</strong>
                          <div
                            v-for="reader in messageReceiptCache.get(message.id).readBy"
                            :key="`r-${message.id}-${reader.id}`"
                            class="message-receipt-popover-row"
                          >
                            <i class="fas fa-check-double"></i>
                            <span class="receipt-name">{{ reader.name }}</span>
                            <span class="receipt-meta">{{ formatRelativeTime(reader.read_at) }}</span>
                          </div>
                        </div>
                        <div
                          v-if="messageReceiptCache.get(message.id)?.deliveredBy?.length"
                          class="message-receipt-popover-section"
                        >
                          <strong>Delivered to</strong>
                          <div
                            v-for="reader in messageReceiptCache.get(message.id).deliveredBy"
                            :key="`d-${message.id}-${reader.id}`"
                            class="message-receipt-popover-row"
                          >
                            <i class="fas fa-check"></i>
                            <span class="receipt-name">{{ reader.name }}</span>
                            <span class="receipt-meta">{{ formatRelativeTime(reader.delivered_at) }}</span>
                          </div>
                        </div>
                        <div
                          v-if="
                            !messageReceiptCache.get(message.id)?.readBy?.length
                            && !messageReceiptCache.get(message.id)?.deliveredBy?.length
                          "
                          class="message-receipt-popover-status"
                        >
                          Receipt details unavailable. {{ message.readCount }} read, {{ message.deliveredCount }} delivered.
                        </div>
                      </template>
                    </div>
                    </Teleport>
                  </div>
                  <!-- Hover toolbar removed — Reply / smile / kebab(Edit+Delete) live
                       inline in the message header (next to time). -->
                </div>
              </div>
            </div>
            </div>

            <button
              v-if="showScrollToBottomButton"
              type="button"
              class="scroll-bottom-btn"
              title="Jump to latest message"
              aria-label="Jump to latest message"
              @click="scrollMessagesToBottom"
            >
              <i class="fas fa-arrow-down"></i>
            </button>

            <button
              v-if="showMissedMessageJumpButton"
              type="button"
              class="missed-message-jump-btn"
              :class="{ 'has-scroll-bottom': showScrollToBottomButton }"
              :title="`Jump to ${missedMessageDividerText.toLowerCase()}`"
              :aria-label="`Jump to ${missedMessageDividerText.toLowerCase()}`"
              @click="jumpToMissedMessagesFromButton"
            >
              <i class="fas fa-location-arrow"></i>
              <span>{{ missedMessageJumpText }}</span>
            </button>

            <Transition name="typing">
              <div v-if="typingIndicatorText" class="typing-indicator" aria-live="polite">
                <span class="typing-dots" aria-hidden="true">
                  <span></span><span></span><span></span>
                </span>
                <span>{{ typingIndicatorText }}</span>
              </div>
            </Transition>

            <div class="chat-input">
              <div v-if="replyTarget" class="reply-composer">
                <div>
                  <span>Replying to {{ replyTarget.author }}</span>
                  <strong>{{ replyTarget.text || 'Attachment message' }}</strong>
                </div>
                <button type="button" class="message-action-btn" @click="clearReplyTarget">
                  Cancel
                </button>
              </div>
              <div v-if="selectedChatResources.length" class="selected-resource-strip">
                <span>Resources</span>
                <button
                  v-for="resource in selectedChatResources"
                  :key="resource.id"
                  type="button"
                  class="selected-resource-chip"
                  @click="toggleSelectedResource(resource)"
                >
                  <i class="fas fa-book-open"></i>
                  {{ resource.resource_name }}
                  <i class="fas fa-times"></i>
                </button>
              </div>
              <div v-if="showResourcePanel" class="resource-panel">
                <div class="resource-panel-header">
                  <input
                    v-model.trim="resourceQuery"
                    type="search"
                    class="gif-search-input"
                    placeholder="Search resources"
                    @keydown.enter.prevent="loadChatResources"
                  />
                  <button type="button" class="btn btn-outline btn-sm" @click="loadChatResources">
                    Search
                  </button>
                </div>
                <div v-if="resourcePickerError" class="gif-status">{{ resourcePickerError }}</div>
                <div v-if="isLoadingResources" class="gif-status">Loading resources...</div>
                <div v-else class="resource-picker-list">
                  <button
                    v-for="resource in chatResourceOptions"
                    :key="resource.id"
                    type="button"
                    class="resource-picker-row"
                    :class="{ selected: isResourceSelected(resource.id) }"
                    @click="toggleSelectedResource(resource)"
                  >
                    <i class="fas fa-book-open"></i>
                    <span>{{ resource.resource_name }}</span>
                    <i v-if="isResourceSelected(resource.id)" class="fas fa-check"></i>
                  </button>
                  <div v-if="!chatResourceOptions.length && !resourcePickerError" class="gif-status">
                    No resources found.
                  </div>
                </div>
              </div>
              <div v-if="supportsGifs && showGifPanel" class="gif-panel">
                <div class="gif-panel-header">
                  <input
                    v-model.trim="gifQuery"
                    type="text"
                    class="gif-search-input"
                    placeholder="Search Tenor GIFs"
                    aria-label="Search GIFs"
                    @input="scheduleGifSearch"
                    @keydown.enter.prevent="searchGifs"
                  />
                  <button type="button" class="btn btn-outline btn-sm" @click="searchGifs">
                    Search
                  </button>
                </div>
                <div v-if="gifError" class="gif-status gif-status--error">
                  {{ gifError }}
                  <button type="button" class="message-action-btn" @click="fetchGifResults(gifPanelMode)">Retry</button>
                </div>
                <div
                  v-if="isLoadingGifs && !gifResults.length"
                  class="gif-grid gif-grid--skeleton"
                  aria-hidden="true"
                >
                  <div v-for="i in 6" :key="`gif-sk-${i}`" class="gif-skeleton skeleton-block"></div>
                </div>
                <div
                  v-else-if="!isLoadingGifs && !gifResults.length && !gifError"
                  class="gif-status gif-status--empty"
                >
                  <i class="far fa-image"></i>
                  <span>{{ gifQuery.trim() ? `No GIFs found for "${gifQuery}"` : 'No trending GIFs right now.' }}</span>
                </div>
                <div
                  v-else
                  class="gif-grid"
                  @scroll="handleGifGridScroll"
                >
                  <button
                    v-for="gif in gifResults"
                    :key="gif.id"
                    type="button"
                    class="gif-card"
                    :title="gif.title"
                    @click="sendGifMessage(gif)"
                  >
                    <img
                      :src="gif.previewUrl || gif.url"
                      :alt="gif.title || 'GIF'"
                      width="170"
                      height="170"
                      loading="lazy"
                      decoding="async"
                    />
                  </button>
                </div>
                <div v-if="gifNextPos && gifResults.length" class="gif-load-more-row">
                  <button
                    type="button"
                    class="btn btn-outline btn-sm"
                    :disabled="isLoadingMoreGifs"
                    @click="loadMoreGifs"
                  >
                    <i v-if="isLoadingMoreGifs" class="fas fa-circle-notch fa-spin"></i>
                    {{ isLoadingMoreGifs ? 'Loading…' : 'Load more' }}
                  </button>
                </div>
                <div class="gif-attribution">Powered by Tenor</div>
              </div>

              <div class="chat-input-group">
                <textarea
                  ref="composer"
                  v-model="newMessage"
                  class="chat-input-field"
                  placeholder="Type your message..."
                  rows="2"
                  @keydown="handleComposerKeydown"
                  @input="handleComposerInput"
                  @focus="onComposerFocus"
                  @blur="onComposerBlur"
                ></textarea>
                <div v-if="showMentionSuggestions" class="mention-suggestions">
                  <button
                    v-for="(member, index) in mentionSuggestions"
                    :key="member.key || member.userId"
                    type="button"
                    class="mention-suggestion"
                    :class="{ active: index === activeMentionSuggestionIndex }"
                    @mousedown.prevent="insertMention(member)"
                  >
                    <i :class="member.icon || 'fas fa-at'"></i>
                    <span>{{ member.label }}</span>
                    <small>{{ member.role }}</small>
                  </button>
                </div>
                <div class="chat-actions">
                  <button
                    class="chat-btn chat-btn--toggle"
                    type="button"
                    :class="{ active: showGifPanel }"
                    :aria-pressed="showGifPanel"
                    :title="supportsGifs ? (showGifPanel ? 'Close GIF picker' : 'GIF picker') : 'GIF search is not available yet'"
                    :disabled="!supportsGifs"
                    @click="toggleGifPanel"
                  >
                    <span class="chat-btn-gif-glyph" aria-hidden="true">GIF</span>
                  </button>
                  <button
                    class="chat-btn"
                    type="button"
                    title="Attach file"
                    :disabled="isUploadingFile || !supportsAttachments"
                    @click="openFilePicker"
                  >
                    <i class="fas fa-paperclip"></i>
                  </button>
                  <button
                    class="chat-btn chat-btn--toggle"
                    type="button"
                    :class="{ active: showResourcePanel }"
                    :aria-pressed="showResourcePanel"
                    :title="showResourcePanel ? 'Close resources' : 'Attach resource'"
                    :disabled="isLoadingResources"
                    @click="toggleResourcePanel"
                  >
                    <i class="fas fa-book-open"></i>
                  </button>
                  <input
                    ref="fileInputRef"
                    type="file"
                    accept=".pdf,.txt,.csv,.png,.jpg,.jpeg,.gif,.webp,.doc,.docx,.xls,.xlsx,.ppt,.pptx"
                    class="hidden-file-input"
                    @change="uploadAttachment"
                  />
                  <button
                    class="chat-btn"
                    :disabled="isSendingMessage || !canSendChatMessage"
                    @click="sendMessage"
                    title="Send"
                  >
                    <i class="fas fa-paper-plane"></i>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useGroupsStore } from '@/stores/groups'
import { buildSessionHeaders, ensureCsrfCookie } from '@/utils/csrf'
import { apiErrorFromResponse } from '@/utils/apiError'
import { fetchResources } from '@/utils/resourcesAPI'
import {
  bulkToggleTasks,
  createTask as createTaskRequest,
  deleteTask as deleteTaskRequest,
  listTasks,
  retrieveTask,
  setTaskStatus as setTaskStatusRequest,
  updateTask as updateTaskRequest,
} from '@/utils/tasksAPI'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const groupsStore = useGroupsStore()
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const SIDEBAR_GROUP_READ_EVENT = 'biotech:group-chat-read'
const supportsGifs = true
const supportsAttachments = true
const supportsMessageReactions = true
const supportsChatClientSocketActions = true
const CHAT_REACTION_OPTIONS = ['\u{1F44D}', '\u2764\uFE0F', '\u{1F389}']
const routeGroupId = computed(() => (route.params.id ? String(route.params.id) : ''))
const group = ref({
  id: routeGroupId.value || null,
  name: routeGroupId.value ? `Group ${routeGroupId.value}` : 'Group',
  members: 0,
  createdAt: '',
})
const groupMemberships = ref([])
const isLoadingGroupDetail = ref(true)
const isLoadingMembers = ref(false)
const membersError = ref('')
const availableGroups = ref([])
const isLoadingGroupOptions = ref(false)
const groupOptionsError = ref('')
const showGroupMembersDialog = ref(false)

// Active mobile tab
const activeTab = ref('tasks')

// Live task state
const tasks = ref([])
const locallyDeletedTasks = ref(new Map())
const isLoadingTasks = ref(false)
const taskError = ref('')
const updatingTaskIds = ref(new Set())
const deletingTaskIds = ref(new Set())
const selectedTaskIds = ref(new Set())
const isBulkUpdatingTasks = ref(false)
const taskSelectionMode = ref(false)
const isTaskFiltersOpen = ref(false)
const showTaskDepthColors = ref(true)
const taskDialogNameInput = ref(null)
const taskPagination = ref({ page: 1, pageSize: 100 })
const TASK_LOAD_BATCH = 100
const taskShownLimit = ref(TASK_LOAD_BATCH)
const loadMoreTasks = () => { taskShownLimit.value += TASK_LOAD_BATCH }
const showCompletedOverdue = ref(false)
const isCompletedOverdueTask = (task) => {
  if (!task?.completed || !task?.dueDate) return false
  const due = new Date(task.dueDate)
  if (Number.isNaN(due.getTime())) return false
  return due.getTime() < Date.now()
}
const collapsedTaskIds = ref(new Set())
const toggleTaskCollapsed = (taskId) => {
  const id = Number(taskId)
  if (!Number.isFinite(id)) return
  const next = new Set(collapsedTaskIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  collapsedTaskIds.value = next
}
const taskFilters = ref({
  taskType: '',
  status: '',
  completed: '',
  assignedUser: '',
  parentId: '',
  dueDateAfter: '',
  dueDateBefore: '',
  search: '',
  ordering: 'due_date',
  showDeleted: false,
})
let taskFilterReloadTimer = null
const activeTaskFilterCount = computed(() => {
  const f = taskFilters.value
  let n = 0
  if (f.taskType) n += 1
  if (f.status) n += 1
  if (f.completed !== '') n += 1
  if (f.assignedUser) n += 1
  if (f.parentId) n += 1
  if (f.dueDateAfter) n += 1
  if (f.dueDateBefore) n += 1
  if (f.showDeleted) n += 1
  return n
})
const taskDialogOpen = ref(false)
const taskDialogMode = ref('create')
const taskDialogTitle = ref('New task')
const taskFormError = ref('')
const isSavingTask = ref(false)
const editingTaskId = ref(null)
const taskForm = ref({
  name: '',
  description: '',
  dueDate: '',
  status: 'todo',
  taskType: 'group',
  parent: '',
  group: '',
  assignedUser: '',
})

const TASK_STATUS_OPTIONS = [
  { value: 'todo', label: 'To do' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'done', label: 'Done' },
  { value: 'blocked', label: 'Blocked' },
]

// Visual definition for each status. icon = Font Awesome class (after `fas fa-`).
const TASK_STATUS_META = {
  todo:        { label: 'To do',       icon: 'circle',          short: 'To do' },
  in_progress: { label: 'In progress', icon: 'circle-half-stroke', short: 'In progress' },
  done:        { label: 'Done',        icon: 'circle-check',    short: 'Done' },
  blocked:     { label: 'Blocked',     icon: 'circle-exclamation', short: 'Blocked' },
}
const getTaskStatusMeta = (status) => TASK_STATUS_META[status] || TASK_STATUS_META.todo

// Which task's status menu is currently open (taskId or null)
const openStatusMenuTaskId = ref(null)
const closeStatusMenu = () => { openStatusMenuTaskId.value = null }
const openStatusMenu = (taskId) => { openStatusMenuTaskId.value = Number(taskId) }
const isStatusMenuOpen = (taskId) => openStatusMenuTaskId.value === Number(taskId)

const toggleAssigneeQuickFilter = (userId) => {
  const current = String(taskFilters.value.assignedUser || '')
  const next = current === String(userId) ? '' : String(userId)
  taskFilters.value = { ...taskFilters.value, assignedUser: next }
}

const TASK_ORDERING_OPTIONS = [
  { value: 'due_date', label: 'Due date' },
  { value: '-due_date', label: 'Due date desc' },
  { value: 'created_at', label: 'Created date' },
  { value: '-created_at', label: 'Created date desc' },
  { value: 'updated_at', label: 'Updated date' },
  { value: '-updated_at', label: 'Recently updated' },
  { value: 'status', label: 'Status' },
  { value: '-status', label: 'Status desc' },
]

const messages = ref([])

const newMessage = ref('')
const composer = ref(null)
const msgList = ref(null)
const fileInputRef = ref(null)
const messageSearchInputRef = ref(null)
const isLoadingMessages = ref(false)
const isLoadingOlderMessages = ref(false)
const isSendingMessage = ref(false)
const isUploadingFile = ref(false)
const isUpdatingMessage = ref(false)
const isDeletingMessageId = ref(null)
const isLoadingGifs = ref(false)
const isLoadingMoreGifs = ref(false)
const chatError = ref('')
const chatNotice = ref('')
const gifError = ref('')
const showGifPanel = ref(false)
const gifQuery = ref('')
const gifResults = ref([])
const gifNextPos = ref(null)
const gifPanelMode = ref('trending')
let gifSearchDebounceTimer = null
const GIF_SEARCH_DEBOUNCE_MS = 300
const showResourcePanel = ref(false)
const resourceQuery = ref('')
const chatResourceOptions = ref([])
const selectedChatResources = ref([])
const isLoadingResources = ref(false)
const resourcePickerError = ref('')
const mentionQuery = ref('')
const mentionStartIndex = ref(-1)
const activeMentionSuggestionIndex = ref(0)
const mentionItems = ref([])
const mentionUnreadCount = ref(0)
const mentionNextBefore = ref(null)
const showMentionInbox = ref(false)
const isLoadingMentions = ref(false)
const isUpdatingMentions = ref(false)
const mentionInboxError = ref('')
const showMessageSearch = ref(false)
const messageSearchQuery = ref('')
const messageSearchResults = ref([])
const messageSearchNextBefore = ref(null)
const showSearchFilters = ref(false)
const messageSearchFilters = ref({ type: '', from: '', to: '' })
const messageReceiptCache = ref(new Map())
const openReceiptPopoverId = ref(null)
const isLoadingReceipts = ref(false)
const receiptError = ref('')
// Anchor coordinates for the read-receipt popover. We render it via
// ``<Teleport to="body">`` so the scrollable chat container's ``overflow``
// can't clip it; in exchange we have to position it ourselves relative to
// the trigger button's bounding rect.
const receiptPopoverAnchor = ref(null)
const isSearchingMessages = ref(false)
const isLoadingMoreSearchResults = ref(false)
const hasSearchedMessages = ref(false)
const messageSearchError = ref('')
const typingUsers = ref([])
const wsConnectionState = ref('offline')
const nextMessagesBefore = ref(null)
const nextMessagesAfter = ref(null)
const replyTarget = ref(null)
const editingMessageId = ref(null)
const editingMessageText = ref('')
const manageWindowNow = ref(Date.now())
const activeReactionPickerMessageId = ref(null)
const openMessageKebabId = ref(null)
const isChatAwayFromBottom = ref(false)
const hasScrollableMessages = ref(false)
const highlightedSearchMessageId = ref(null)
const missedMessageAnchorId = ref(null)
const missedMessageCount = ref(0)
const isMissedMessageJumpDismissed = ref(false)

let chatSocket = null
// First successful WS open per page load is a no-op catch-up; subsequent
// reopens (reconnect after a drop) trigger a resync.
let hasConnectedChatSocket = false
let typingStopTimer = null
let manageWindowTimer = null
let searchHighlightTimer = null
let hasSentTypingStart = false
let lastTypingSentAt = 0
const typingUserTimers = new Map()
const SCROLL_BOTTOM_THRESHOLD = 96

const getInitials = (name) =>
  String(name || 'U')
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()

// Module-level cache: Intl.DateTimeFormat is expensive to construct;
// reuse per (locale, options) shape across renders.
const _dateFmt = new Intl.DateTimeFormat('en-AU', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
})
const _timeFmt = new Intl.DateTimeFormat([], { hour: '2-digit', minute: '2-digit' })

const formatDate = (d) => {
  const date = new Date(d)
  if (Number.isNaN(date.getTime())) return d
  return _dateFmt.format(date)
}

const formatTime = (value) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return _timeFmt.format(date)
}

const formatTaskStatus = (value) => {
  const label = String(value || '')
    .replace(/_/g, ' ')
    .trim()
  return label ? label.charAt(0).toUpperCase() + label.slice(1) : ''
}

const groupInitials = computed(() => {
  const initials = getInitials(group.value?.name)
  return initials.slice(0, 2) || 'G'
})

const groupSubtitle = computed(() => {
  const memberCount = Number(group.value?.members || 0)
  const memberLabel = memberCount === 1 ? '1 member' : `${memberCount} members`
  const createdLabel = group.value?.createdAt ? formatDate(group.value.createdAt) : 'unknown date'
  return `${memberLabel} - Group since ${createdLabel}`
})

const groupMetaItems = computed(() => {
  const mentorNames = groupMemberships.value
    .filter((item) =>
      String(item.role || '')
        .toLowerCase()
        .includes('mentor'),
    )
    .map((item) => item.userName || `User ${item.userId}`)
    .filter(Boolean)
  const items = []

  if (mentorNames.length) {
    items.push(`Mentor: ${mentorNames.join(', ')}`)
  }
  if (isLoadingMembers.value) {
    items.push('Loading members...')
  } else if (membersError.value) {
    items.push(membersError.value)
  }

  return items
})

const visibleGroupMembers = computed(() =>
  groupMemberships.value
    .filter((item) => {
      if (item.leftAt) return false
      return !String(item.role || '')
        .toLowerCase()
        .includes('supervisor')
    })
    .map((item) => ({
      key: `${item.id || item.userId}`,
      id: item.userId,
      name: item.userName || `User ${item.userId}`,
      roleLabel: formatTaskStatus(item.role || 'member') || 'Member',
      role: String(item.role || '').toLowerCase(),
    }))
    .sort((a, b) => {
      const roleRank = (role) => {
        if (role.includes('mentor')) return 0
        if (role.includes('student')) return 1
        return 2
      }
      return roleRank(a.role) - roleRank(b.role) || a.name.localeCompare(b.name)
    }),
)

const extractCollectionItems = (data) => {
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.results)) return data.results
  if (Array.isArray(data?.items)) return data.items
  return []
}

// Chat / GIF endpoints used to be wrapped in dual-URL helpers (``/api/v1/...``
// primary, ``/...`` fallback) because only the legacy mount existed. The
// backend now serves chat under both prefixes via ``config.urls._DUAL_MOUNTS``,
// so every helper returns a single canonical URL.
const buildChatMessageCollectionUrl = (groupId, suffix = '') =>
  `${API_BASE_URL}/api/v1/chat/groups/${groupId}/messages/${suffix}`

const buildChatMessageSearchUrl = (groupId, suffix = '') =>
  `${API_BASE_URL}/api/v1/chat/groups/${groupId}/messages/search/${suffix}`

const buildChatUploadUrl = (groupId) =>
  `${API_BASE_URL}/api/v1/chat/groups/${groupId}/messages/upload/`

const buildChatReactionUrl = (groupId, messageId) =>
  `${API_BASE_URL}/api/v1/chat/groups/${groupId}/messages/${messageId}/react/`

const buildChatMessageUrl = (groupId, messageId) =>
  `${API_BASE_URL}/api/v1/chat/groups/${groupId}/messages/${messageId}/`

const buildChatReadUrl = (groupId, messageId) =>
  `${API_BASE_URL}/api/v1/chat/groups/${groupId}/messages/${messageId}/read/`

const buildChatDeliveredUrl = (groupId, messageId) =>
  `${API_BASE_URL}/api/v1/chat/groups/${groupId}/messages/${messageId}/delivered/`

const buildMentionInboxUrl = (suffix = '') =>
  `${API_BASE_URL}/api/v1/chat/mentions/${suffix}`

const buildMentionReadUrl = (mentionId) =>
  `${API_BASE_URL}/api/v1/chat/mentions/${mentionId}/read/`

const buildMentionMarkAllReadUrl = () =>
  `${API_BASE_URL}/api/v1/chat/mentions/mark-all-read/`

const buildGifSearchUrl = (query, pos = '', limit = 30) => {
  const params = new URLSearchParams({ q: query })
  if (pos) params.set('pos', pos)
  if (limit) params.set('limit', String(limit))
  return `${API_BASE_URL}/api/v1/chat/gifs/search?${params.toString()}`
}

const buildGifTrendingUrl = (pos = '', limit = 30) => {
  const params = new URLSearchParams()
  if (pos) params.set('pos', pos)
  if (limit) params.set('limit', String(limit))
  const qs = params.toString()
  return `${API_BASE_URL}/api/v1/chat/gifs/trending${qs ? `?${qs}` : ''}`
}

const buildChatSendGifUrl = (gid) =>
  `${API_BASE_URL}/api/v1/chat/groups/${gid}/messages/send-gif/`

const buildChatMessageStatusUrl = (gid, messageId) =>
  `${API_BASE_URL}/api/v1/chat/groups/${gid}/messages/${messageId}/status/`

const buildChatWebSocketUrl = (groupId) => {
  try {
    const apiUrl = new URL(API_BASE_URL)
    const protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${apiUrl.host}/ws/chat/groups/${groupId}/`
  } catch {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}/ws/chat/groups/${groupId}/`
  }
}

const requestJson = async (url, options = {}) => {
  const isFormData = options.body instanceof FormData
  const method = String(options.method || 'GET').toUpperCase()
  const shouldIncludeCSRF = !['GET', 'HEAD', 'OPTIONS'].includes(method)

  if (shouldIncludeCSRF) {
    const csrfReady = await ensureCsrfCookie(API_BASE_URL)
    if (!csrfReady) {
      throw new Error('Could not initialize a secure session. Please refresh and try again.')
    }
  }

  const response = await fetch(url, {
    credentials: 'include',
    ...options,
    headers: buildSessionHeaders({
      includeCSRF: shouldIncludeCSRF,
      isFormData,
      headers: {
        Accept: 'application/json',
        ...(options.headers || {}),
      },
    }),
  })

  if (!response.ok) {
    throw await apiErrorFromResponse(response)
  }

  const text = await response.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = null
  }

  return data
}

const normalizeGroup = (item) => {
  return {
    ...group.value,
    ...item,
    id: item?.id,
    name: item?.group_name || item?.name || item?.title || group.value?.name || 'Untitled group',
    members: Number(
      item?.member_count ?? item?.memberCount ?? item?.members ?? group.value?.members ?? 0,
    ),
    createdAt: item?.created_at || item?.createdAt || '',
  }
}

const normalizeMembership = (item) => ({
  id: item?.id,
  groupId: item?.group,
  userId: item?.user,
  userName: item?.user_name || item?.userName || '',
  role: item?.membership_role || '',
  joinedAt: item?.joined_at || '',
  leftAt: item?.left_at || '',
})

const getCurrentUserMentionName = () => {
  if (!currentUserId.value) return ''
  return auth.displayName || auth.user?.email || `User ${currentUserId.value}`
}

const normalizeMentionMember = (item) => {
  const userId = Number(item?.userId || item?.user || item?.id || 0)
  const role = formatTaskStatus(item?.role || item?.membership_role || 'member') || 'Member'
  const userName = item?.userName || item?.user_name || ''
  const fallbackName = userId === currentUserId.value ? getCurrentUserMentionName() : `User ${userId}`
  return {
    userId,
    role,
    label: userName || fallbackName,
  }
}

const normalizeGroupOption = (item, memberCount = 0) => ({
  id: String(item?.id || ''),
  name:
    item?.group_name ||
    item?.name ||
    item?.title ||
    (item?.id ? `Group ${item.id}` : 'Untitled group'),
  memberCount: Number(memberCount || 0),
  createdAt: item?.created_at || item?.createdAt || '',
})

const ensureAuthUser = async () => {
  if (auth.user?.id) return

  try {
    await auth.fetchUserData?.()
  } catch {
    // Keep the current page usable; group option loading will show its own fallback.
  }
}

const loadGroupOptions = async () => {
  isLoadingGroupOptions.value = true
  groupOptionsError.value = ''

  // Single source of truth for "this user's groups" — shared with the
  // sidebar via the Pinia store, so this never refires its own bulk fetch.
  await groupsStore.ensureLoaded()

  if (groupsStore.error) {
    const currentGroupId = getBackendGroupId() || routeGroupId.value
    availableGroups.value = currentGroupId
      ? [
          normalizeGroupOption(
            { id: currentGroupId, group_name: group.value?.name || `Group ${currentGroupId}` },
            group.value?.members,
          ),
        ]
      : []
    groupOptionsError.value = 'Group list unavailable'
    isLoadingGroupOptions.value = false
    return
  }

  let options = groupsStore.sorted.map((g) =>
    normalizeGroupOption(
      { id: g.id, group_name: g.name, created_at: g.createdAt },
      g.memberCount,
    ),
  )

  // Keep the currently-viewed group visible even if it isn't in the store
  // (e.g. an admin viewing a group they're not a member of).
  const currentGroupId = getBackendGroupId() || routeGroupId.value
  if (currentGroupId && !options.some((option) => String(option.id) === String(currentGroupId))) {
    options = [
      normalizeGroupOption(
        {
          id: currentGroupId,
          group_name: group.value?.name || `Group ${currentGroupId}`,
          created_at: group.value?.createdAt,
        },
        group.value?.members,
      ),
      ...options,
    ]
  }

  availableGroups.value = options
  if (!options.length) {
    groupOptionsError.value = auth.isAdmin ? 'No groups available' : 'No groups assigned'
  }
  isLoadingGroupOptions.value = false
}

const loadGroupMembers = async () => {
  const currentGroupId = getBackendGroupId()
  if (!currentGroupId) {
    groupMemberships.value = []
    membersError.value = ''
    return
  }

  isLoadingMembers.value = true
  membersError.value = ''

  try {
    const data = await requestJson(
      `${API_BASE_URL}/groups/group-members/by-group/${currentGroupId}/`,
    )
    const activeMemberships = extractCollectionItems(data)
      .map(normalizeMembership)
      .filter((item) => !item.leftAt)

    groupMemberships.value = activeMemberships
    group.value = {
      ...group.value,
      members: activeMemberships.length,
    }
  } catch {
    groupMemberships.value = []
    membersError.value = 'Members unavailable'
  } finally {
    isLoadingMembers.value = false
  }
}

const normalizeReactionMap = (reactions) => {
  if (!reactions || typeof reactions !== 'object' || Array.isArray(reactions)) {
    return {}
  }

  return Object.fromEntries(
    Object.entries(reactions)
      .map(([emoji, value]) => {
        // Backend ships ``{count, users: [{id, name}, ...]}``; legacy callers
        // may still pass a bare number. Normalize to the rich shape so the
        // chip hover tooltip can render names without re-fetching.
        if (value && typeof value === 'object' && !Array.isArray(value)) {
          const count = Number(value.count) || 0
          const users = Array.isArray(value.users)
            ? value.users
                .filter((u) => u && (u.id != null || u.name))
                .map((u) => ({ id: Number(u.id) || 0, name: u.name || '' }))
            : []
          return [emoji, { count, users }]
        }
        const count = Number(value) || 0
        return [emoji, { count, users: [] }]
      })
      .filter(([, data]) => data.count > 0),
  )
}

const normalizeGifResults = (data) => {
  const items = extractCollectionItems(data)
  const normalized = items
    .map((item, index) => ({
      id: item?.id || item?.media_id || item?.url || `gif-${index}`,
      url:
        item?.gif_url ||
        item?.url ||
        item?.media?.gif?.url ||
        item?.media_formats?.gif?.url ||
        item?.itemurl ||
        '',
      previewUrl:
        item?.preview_url ||
        item?.preview ||
        item?.media_formats?.tinygif?.url ||
        item?.media_formats?.nanogif?.url ||
        item?.gif_url ||
        item?.url ||
        '',
      title: item?.title || item?.content_description || 'GIF',
    }))
    .filter((item) => item.url)

  return normalized
}

const loadGroup = async () => {
  try {
    const currentRouteGroupId = routeGroupId.value
    if (currentRouteGroupId) {
      const data = await requestJson(`${API_BASE_URL}/groups/groups/${currentRouteGroupId}/`)
      group.value = normalizeGroup(data)
      // Push the freshly-fetched detail (with authoritative member_count)
      // into the shared store so the sidebar can use the richer payload.
      groupsStore.upsert(data)
      return
    }

    // The /groups landing route is handled by the router guard now — it
    // resolves to the user's first group before this view mounts. If we
    // somehow arrive here without an id, fall back to the store rather
    // than fetching a stranger group.
    await groupsStore.ensureLoaded()
    const first = groupsStore.firstGroup
    if (first) {
      group.value = {
        id: first.id,
        name: first.name,
        members: first.memberCount,
        createdAt: first.createdAt,
      }
    } else {
      group.value = { id: null, name: 'No groups yet', members: 0, createdAt: '' }
    }
  } catch {
    group.value = {
      id: routeGroupId.value || null,
      name: routeGroupId.value ? `Group ${routeGroupId.value}` : 'Group unavailable',
      members: 0,
      createdAt: '',
    }
  }
}

const normalizeTask = (task) => ({
  id: task?.id,
  name: task?.name || task?.task_name || 'Untitled task',
  description: task?.description || task?.task_description || '',
  dueDate: task?.due_date || '',
  status: task?.status || '',
  completed: task?.completed === true || String(task?.status || '').toLowerCase() === 'done',
  parent: task?.parent ?? null,
  taskType: task?.task_type || 'group',
  group: task?.group ?? null,
  assignedUser: task?.assigned_user ?? null,
  assignedUserDetail: task?.assigned_user_detail || null,
  creatorRole: task?.creator_role || '',
  createdBy: task?.created_by || null,
  deletedAt: task?.deleted_at || null,
  createdAt: task?.created_at || '',
  updatedAt: task?.updated_at || '',
})

const groupMemberUserIds = computed(
  () =>
    new Set(
      groupMemberships.value
        .filter((item) => !item.leftAt)
        .map((item) => Number(item.userId))
        .filter(Number.isFinite),
    ),
)

const normalizeTaskAssigneeOption = (item) => {
  const userId = Number(item.userId)
  const role = formatTaskStatus(item.role || '')
  const baseLabel = item.userName || `User ${userId}`

  return {
    userId,
    label: role ? `${baseLabel} (${role})` : baseLabel,
    role: String(item.role || '').toLowerCase(),
  }
}

const activeGroupMemberOptions = computed(() =>
  groupMemberships.value
    .filter((item) => !item.leftAt)
    .map(normalizeTaskAssigneeOption)
    .filter((item) => Number.isFinite(item.userId) && item.userId > 0)
    .sort((a, b) => a.label.localeCompare(b.label)),
)

const taskAssigneeOptions = computed(() => activeGroupMemberOptions.value)

const studentMemberUserIds = computed(
  () =>
    new Set(
      groupMemberships.value
        .filter(
          (item) =>
            !item.leftAt &&
            String(item.role || '')
              .toLowerCase()
              .includes('student'),
        )
        .map((item) => Number(item.userId))
        .filter(Number.isFinite),
    ),
)

const supervisedStudentIds = computed(
  () =>
    new Set(
      (auth.user?.supervised_students || [])
        .map((student) => Number(student?.id))
        .filter(Number.isFinite),
    ),
)

const currentUserId = computed(() => Number(auth.user?.id || 0))

const currentUserTaskAssigneeOption = computed(() => {
  const userId = currentUserId.value
  if (!userId) return null
  const member = activeGroupMemberOptions.value.find((item) => item.userId === userId)
  if (member) return member
  return {
    userId,
    label: auth.displayName || auth.user?.email || `User ${userId}`,
    role: 'student',
  }
})

const individualTaskAssigneeOptions = computed(() => {
  if (auth.isStudent) {
    return currentUserTaskAssigneeOption.value ? [currentUserTaskAssigneeOption.value] : []
  }

  if (auth.isSupervisor) {
    return activeGroupMemberOptions.value.filter((item) =>
      supervisedStudentIds.value.has(Number(item.userId)),
    )
  }

  if (auth.isMentor) {
    return activeGroupMemberOptions.value.filter((item) =>
      groupMemberUserIds.value.has(Number(item.userId)),
    )
  }

  if (auth.isAdmin) {
    return activeGroupMemberOptions.value
  }

  return []
})

const isStudentOnlyIndividualAssignee = computed(
  () => auth.isStudent && taskDialogMode.value === 'create',
)

const selectedTaskAssigneeLabel = computed(() => {
  const assigneeId = Number(taskForm.value.assignedUser)
  const option =
    individualTaskAssigneeOptions.value.find((item) => item.userId === assigneeId) ||
    activeGroupMemberOptions.value.find((item) => item.userId === assigneeId)
  return option?.label || (assigneeId ? `User ${assigneeId}` : 'No assignee selected')
})

const isCurrentGroupMentor = computed(() =>
  groupMemberships.value.some(
    (item) =>
      !item.leftAt &&
      Number(item.userId) === currentUserId.value &&
      String(item.role || '')
        .toLowerCase()
        .includes('mentor'),
  ),
)

const supervisesAnyCurrentGroupStudent = computed(() => {
  if (!auth.isSupervisor) return false
  return Array.from(studentMemberUserIds.value).some((userId) =>
    supervisedStudentIds.value.has(userId),
  )
})

const isTaskRelevantToCurrentGroup = (task) => {
  const currentGroupId = getBackendGroupId()
  if (!currentGroupId) return false

  if (task.taskType === 'group') {
    return String(task.group) === String(currentGroupId)
  }

  return groupMemberUserIds.value.has(Number(task.assignedUser))
}

const buildTaskRows = (items) => {
  const byId = new Map()
  const childrenByParent = new Map()

  items.forEach((task) => {
    byId.set(Number(task.id), task)
  })

  items.forEach((task) => {
    const parentId = Number(task.parent)
    if (!parentId || !byId.has(parentId)) return
    if (!childrenByParent.has(parentId)) childrenByParent.set(parentId, [])
    childrenByParent.get(parentId).push(task)
  })

  const roots = items.filter((task) => {
    const parentId = Number(task.parent)
    return !parentId || !byId.has(parentId)
  })

  const collapsed = collapsedTaskIds.value
  const rows = []
  const appendRows = (task, depth = 0) => {
    const id = Number(task.id)
    const children = childrenByParent.get(id) || []
    const hasChildren = children.length > 0
    rows.push({
      task,
      depth,
      hasChildren,
      childCount: children.length,
      isCollapsed: hasChildren && collapsed.has(id),
    })
    if (hasChildren && !collapsed.has(id)) {
      children.forEach((child) => appendRows(child, depth + 1))
    }
  }

  roots.forEach((task) => appendRows(task))
  return rows
}

const createTaskSection = (key, title, icon, sectionTasks) => {
  const rows = buildTaskRows(sectionTasks)
  const total = sectionTasks.length
  const completed = sectionTasks.filter((task) => task.completed).length

  return {
    key,
    title,
    icon,
    rows,
    total,
    completed,
  }
}

const taskTotalPages = computed(() =>
  Math.max(1, Math.ceil(tasks.value.length / taskPagination.value.pageSize)),
)

const pagedTasks = computed(() => tasks.value.slice(0, taskShownLimit.value))

const parentTaskFilterOptions = computed(() =>
  tasks.value
    .filter((task) => !task.deletedAt)
    .map((task) => ({
      id: task.id,
      label: `${task.taskType === 'individual' ? 'Individual Task' : 'Group Task'} - ${task.name}`,
    }))
    .sort((a, b) => a.label.localeCompare(b.label)),
)

// Hide tasks that are completed AND past their due date by default. The
// toolbar toggle (showCompletedOverdue) un-hides them; the popover State=Done
// filter also bypasses the hide so the user always sees what they asked for.
const isStaleCompletedHidden = (task) => {
  if (showCompletedOverdue.value) return false
  if (taskFilters.value.completed === 'true') return false
  return isCompletedOverdueTask(task)
}

const taskSections = computed(() => {
  const relevantTasks = pagedTasks.value
    .filter(isTaskRelevantToCurrentGroup)
    .filter((task) => !isStaleCompletedHidden(task))
  const groupTasks = relevantTasks.filter((task) => task.taskType === 'group')
  const individualTasks = relevantTasks.filter((task) => task.taskType === 'individual')

  return [
    createTaskSection('group', 'Group Tasks', 'fas fa-users', groupTasks),
    createTaskSection('individual', 'Individual Tasks', 'fas fa-user-check', individualTasks),
  ]
})

// Shared base set — both counts below + taskSections downstream all
// repeatedly walked tasks.value for the same relevance test.
const groupRelevantTasks = computed(() =>
  tasks.value.filter(isTaskRelevantToCurrentGroup),
)
const totalRelevantTaskCount = computed(() => groupRelevantTasks.value.length)
const visibleSectionTaskCount = computed(
  () => taskSections.value.reduce((sum, section) => sum + section.total, 0),
)
const hasMoreTasksToShow = computed(
  () => taskShownLimit.value < totalRelevantTaskCount.value,
)
const hiddenStaleCompletedCount = computed(
  () => groupRelevantTasks.value.filter(isCompletedOverdueTask).length,
)

const selectedTaskIdList = computed(() =>
  Array.from(selectedTaskIds.value).map(Number).filter(Number.isFinite),
)
const canCreateGroupTasks = computed(
  () =>
    auth.isAdmin ||
    (auth.isMentor && isCurrentGroupMentor.value) ||
    supervisesAnyCurrentGroupStudent.value,
)
const canCreateIndividualTasks = computed(
  () =>
    auth.isAdmin ||
    auth.isStudent ||
    (auth.isMentor && isCurrentGroupMentor.value) ||
    supervisesAnyCurrentGroupStudent.value,
)
const allowedTaskTypeOptions = computed(() =>
  [
    canCreateGroupTasks.value ? { value: 'group', label: 'Group' } : null,
    canCreateIndividualTasks.value ? { value: 'individual', label: 'Individual' } : null,
  ].filter(Boolean),
)

const isUpdatingTask = (taskId) => updatingTaskIds.value.has(Number(taskId))
const isDeletingTask = (taskId) => deletingTaskIds.value.has(Number(taskId))

const setTaskUpdating = (taskId, value) => {
  const next = new Set(updatingTaskIds.value)
  const id = Number(taskId)
  if (value) next.add(id)
  else next.delete(id)
  updatingTaskIds.value = next
}

const setTaskDeleting = (taskId, value) => {
  const next = new Set(deletingTaskIds.value)
  const id = Number(taskId)
  if (value) next.add(id)
  else next.delete(id)
  deletingTaskIds.value = next
}

const isTaskSelected = (taskId) => selectedTaskIds.value.has(Number(taskId))

const setTaskSelected = (taskId, selected) => {
  const next = new Set(selectedTaskIds.value)
  const id = Number(taskId)
  if (!Number.isFinite(id)) return
  if (selected) next.add(id)
  else next.delete(id)
  selectedTaskIds.value = next
}

const clearTaskSelection = () => {
  selectedTaskIds.value = new Set()
}

const toggleTaskSelectionMode = () => {
  taskSelectionMode.value = !taskSelectionMode.value
  if (!taskSelectionMode.value) clearTaskSelection()
}

const resetTaskFilters = () => {
  taskFilters.value = {
    ...taskFilters.value,
    taskType: '',
    status: '',
    completed: '',
    assignedUser: '',
    parentId: '',
    dueDateAfter: '',
    dueDateBefore: '',
    showDeleted: false,
  }
}

const getAssigneeDisplay = (task) => {
  const assigneeId = Number(task?.assignedUser)
  if (!Number.isFinite(assigneeId) || assigneeId <= 0) return null
  const meId = currentUserId.value
  if (meId && assigneeId === Number(meId)) {
    return { label: 'You', isSelf: true }
  }
  const name = task?.assignedUserDetail?.name
  if (name) return { label: name, isSelf: false }
  return { label: `User ${assigneeId}`, isSelf: false }
}

const isTaskOverdue = (task) => {
  if (!task?.dueDate || task.completed || task.deletedAt) return false
  const due = new Date(task.dueDate)
  if (Number.isNaN(due.getTime())) return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return due < today
}

const syncSelectedTasks = () => {
  const visibleIds = new Set(
    pagedTasks.value
      .filter((task) => !task.deletedAt && canToggleTask(task))
      .map((task) => Number(task.id)),
  )
  selectedTaskIds.value = new Set(selectedTaskIdList.value.filter((id) => visibleIds.has(id)))
}

const isGroupTaskInCurrentGroup = (task) =>
  String(task?.group || '') === String(getBackendGroupId() || '')
const isCurrentGroupStudent = (userId) => studentMemberUserIds.value.has(Number(userId))
const isSupervisorOf = (userId) => supervisedStudentIds.value.has(Number(userId))
const isAssigneeSelf = (task) => Number(task?.assignedUser) === currentUserId.value

const isMentorOfTaskGroup = (task) => {
  if (!auth.isMentor || !isCurrentGroupMentor.value) return false
  if (task?.taskType === 'group') return isGroupTaskInCurrentGroup(task)
  return isCurrentGroupStudent(task?.assignedUser)
}

const isSupervisorInTaskGroup = (task) => {
  if (!auth.isSupervisor) return false
  if (task?.taskType === 'group')
    return isGroupTaskInCurrentGroup(task) && supervisesAnyCurrentGroupStudent.value
  return isSupervisorOf(task?.assignedUser)
}

const canManageTask = (task) => {
  if (!task || task.deletedAt) return false
  if (auth.isAdmin) return true
  const creatorId = Number(task.createdBy?.id)
  if (Number.isFinite(creatorId) && creatorId === currentUserId.value) return true

  if (task.creatorRole !== 'student') return false
  if (task.taskType === 'group') return isMentorOfTaskGroup(task)
  if (task.taskType === 'individual')
    return isMentorOfTaskGroup(task) || isSupervisorInTaskGroup(task)
  return false
}

// Visibility (`isTaskRelevantToCurrentGroup`) already scopes the task list
// to the current group. This gate only decides who can act on a visible task.
const canToggleTask = (task) => {
  if (!task || task.deletedAt) return false
  if (auth.isAdmin) return true

  if (task.taskType === 'group') {
    return isMentorOfTaskGroup(task) || isSupervisorInTaskGroup(task)
  }

  if (isAssigneeSelf(task)) return true

  if (['global_admin', 'track_admin', 'student'].includes(task.creatorRole)) {
    return isMentorOfTaskGroup(task) || isSupervisorInTaskGroup(task)
  }
  if (task.creatorRole === 'mentor') return isMentorOfTaskGroup(task)
  if (task.creatorRole === 'supervisor') return isSupervisorInTaskGroup(task)
  return false
}

const canCreateTaskType = (taskType, parentTask = null) => {
  if (taskType === 'group') return canCreateGroupTasks.value
  if (taskType !== 'individual') return false

  if (!parentTask?.assignedUser) return canCreateIndividualTasks.value
  const assigneeId = Number(parentTask.assignedUser)
  if (auth.isAdmin) return true
  if (auth.isStudent) return assigneeId === currentUserId.value
  if (auth.isMentor) return isCurrentGroupMentor.value && groupMemberUserIds.value.has(assigneeId)
  if (auth.isSupervisor) return isSupervisorOf(assigneeId)
  return false
}

const canCreateTaskFromForm = () => {
  const taskType = taskForm.value.taskType
  if (taskType === 'group') return canCreateGroupTasks.value

  const assigneeId = Number(taskForm.value.assignedUser)
  if (!Number.isFinite(assigneeId) || assigneeId <= 0) return false
  if (auth.isAdmin) return true
  if (auth.isStudent) return assigneeId === currentUserId.value
  if (auth.isMentor) return isCurrentGroupMentor.value && groupMemberUserIds.value.has(assigneeId)
  if (auth.isSupervisor) return isSupervisorOf(assigneeId)
  return false
}

const upsertTask = (task) => {
  const normalized = normalizeTask(task)
  const index = tasks.value.findIndex((item) => Number(item.id) === Number(normalized.id))
  if (index === -1) tasks.value.push(normalized)
  else tasks.value.splice(index, 1, normalized)
  tasks.value = sortTaskCollection(tasks.value)
}

const cacheDeletedTask = (task) => {
  const normalized = normalizeTask(task)
  if (!normalized.id || !normalized.deletedAt) return
  const next = new Map(locallyDeletedTasks.value)
  next.set(Number(normalized.id), normalized)
  locallyDeletedTasks.value = next
}

const mergeLocallyDeletedTasks = () => {
  const byId = new Map(tasks.value.map((task) => [Number(task.id), task]))
  locallyDeletedTasks.value.forEach((task) => {
    if (isTaskRelevantToCurrentGroup(task)) byId.set(Number(task.id), task)
  })
  tasks.value = sortTaskCollection(Array.from(byId.values()))
  ensureTaskPageInRange()
  syncSelectedTasks()
}

const hideLocallyDeletedTasks = () => {
  tasks.value = tasks.value.filter((task) => !task.deletedAt)
  ensureTaskPageInRange()
  syncSelectedTasks()
}

const toggleDeletedTaskVisibility = () => {
  if (taskFilters.value.showDeleted) {
    mergeLocallyDeletedTasks()
  } else {
    hideLocallyDeletedTasks()
  }
}

const removeTaskFromList = (taskId) => {
  const index = tasks.value.findIndex((item) => Number(item.id) === Number(taskId))
  if (index !== -1) tasks.value.splice(index, 1)
}

const getTaskListBaseParams = () => ({
  status: taskFilters.value.status,
  completed: taskFilters.value.completed === '' ? '' : taskFilters.value.completed === 'true',
  parent_id: taskFilters.value.parentId,
  due_date_after: fromDateTimeLocal(taskFilters.value.dueDateAfter) || '',
  due_date_before: fromDateTimeLocal(taskFilters.value.dueDateBefore) || '',
  search: taskFilters.value.search,
  ordering: taskFilters.value.ordering,
})

const fetchAllTaskPages = async (params) => {
  const items = []
  let page = 1
  let hasNext = true

  while (hasNext) {
    const data = await listTasks({
      ...params,
      page,
      page_size: 100,
    })
    items.push(...extractCollectionItems(data).map(normalizeTask))
    hasNext = Boolean(data?.next)
    page += 1
  }

  return items
}

const sortTaskCollection = (items) => {
  const ordering = taskFilters.value.ordering || 'due_date'
  const descending = ordering.startsWith('-')
  const field = descending ? ordering.slice(1) : ordering

  const valueFor = (task) => {
    if (field === 'due_date') return task.dueDate ? new Date(task.dueDate).getTime() : Infinity
    if (field === 'created_at') return task.createdAt ? new Date(task.createdAt).getTime() : 0
    if (field === 'updated_at') return task.updatedAt ? new Date(task.updatedAt).getTime() : 0
    if (field === 'status') return task.status || ''
    return task.id || 0
  }

  return [...items].sort((a, b) => {
    const first = valueFor(a)
    const second = valueFor(b)
    const result =
      typeof first === 'string'
        ? first.localeCompare(String(second))
        : Number(first) - Number(second)

    return descending ? -result : result
  })
}

const ensureTaskPageInRange = () => {
  if (taskPagination.value.page > taskTotalPages.value) {
    taskPagination.value.page = taskTotalPages.value
  }
  if (taskPagination.value.page < 1) {
    taskPagination.value.page = 1
  }
}

const loadTasks = async ({ resetPage = true } = {}) => {
  const currentGroupId = getBackendGroupId()
  if (!currentGroupId) {
    tasks.value = []
    taskError.value = 'Live task data needs a backend numeric group id.'
    return
  }

  isLoadingTasks.value = true
  taskError.value = ''

  try {
    if (resetPage) taskPagination.value.page = 1

    const baseParams = getTaskListBaseParams()
    const requestedType = taskFilters.value.taskType
    const requestedAssignee = Number(taskFilters.value.assignedUser)
    const taskRequests = []

    if ((!requestedType || requestedType === 'group') && !requestedAssignee) {
      taskRequests.push(
        fetchAllTaskPages({
          ...baseParams,
          task_type: 'group',
          group_id: currentGroupId,
        }),
      )
    }

    if (!requestedType || requestedType === 'individual') {
      const assigneeIds =
        Number.isFinite(requestedAssignee) && requestedAssignee > 0
          ? [requestedAssignee]
          : Array.from(groupMemberUserIds.value)

      if (assigneeIds.length === 1) {
        taskRequests.push(
          fetchAllTaskPages({
            ...baseParams,
            task_type: 'individual',
            assigned_user: assigneeIds[0],
          }),
        )
      } else if (assigneeIds.length > 1) {
        // One round-trip across every group member; backend
        // ``assigned_user__in`` accepts a comma-separated id list.
        taskRequests.push(
          fetchAllTaskPages({
            ...baseParams,
            task_type: 'individual',
            assigned_user__in: assigneeIds.join(','),
          }),
        )
      }
    }

    const taskBatches = await Promise.all(taskRequests)
    const byId = new Map()
    taskBatches.flat().forEach((task) => {
      if (task?.id) byId.set(Number(task.id), task)
    })
    if (taskFilters.value.showDeleted) {
      locallyDeletedTasks.value.forEach((task) => {
        if (isTaskRelevantToCurrentGroup(task)) byId.set(Number(task.id), task)
      })
    }

    tasks.value = sortTaskCollection(
      Array.from(byId.values()).filter((task) => {
        if (!taskFilters.value.showDeleted && task.deletedAt) return false
        return isTaskRelevantToCurrentGroup(task)
      }),
    )
    ensureTaskPageInRange()
    syncSelectedTasks()
    taskShownLimit.value = TASK_LOAD_BATCH
  } catch (error) {
    tasks.value = []
    taskError.value = error instanceof Error ? error.message : 'Task data could not be loaded.'
  } finally {
    isLoadingTasks.value = false
  }
}

const scheduleTaskReload = () => {
  if (!getBackendGroupId()) return
  if (taskFilterReloadTimer) clearTimeout(taskFilterReloadTimer)
  taskFilterReloadTimer = setTimeout(() => {
    taskFilterReloadTimer = null
    loadTasks()
  }, 300)
}

watch(
  () => ({ ...taskFilters.value }),
  () => scheduleTaskReload(),
  { deep: true },
)

const normalizeMessage = (item) => {
  const raw = item?.message ? item.message : item
  const sentAt = raw?.sent_at || raw?.sent_datetime || raw?.created_at || new Date().toISOString()
  const senderId = Number(raw?.sender_user || raw?.sender_id || raw?.sender_user_id || 0)
  const currentUserId = Number(auth.user?.id || 0)
  const displayName = auth.displayName || ''
  const senderName = raw?.sender_name || raw?.author || ''
  const isOwn =
    raw?.isOwn === true ||
    (currentUserId > 0 && senderId === currentUserId) ||
    (senderName && displayName && senderName === displayName)
  const messageText = raw?.message_text || raw?.text || ''
  const messageType = raw?.message_type || 'text'
  const attachments = Array.isArray(raw?.attachments) ? raw.attachments : []
  const resources = Array.isArray(raw?.resources) ? raw.resources : []
  // Backend ships GIFs as ``{message_type: 'gif', gif: {gif_url, preview_url, title, provider_id}}``.
  // Falling back to ``messageText`` covers any legacy pending-bubble path that stuffed the URL into ``text``.
  const gifPayload = raw?.gif && typeof raw.gif === 'object' ? raw.gif : null
  const gifUrl = messageType === 'gif'
    ? (gifPayload?.gif_url || gifPayload?.url || messageText)
    : ''
  const gifPreviewUrl = gifPayload?.preview_url || ''
  const gifTitle = gifPayload?.title || ''
  const author = isOwn
    ? 'You'
    : raw?.sender_name || raw?.author || getMentionLabel(senderId)

  return {
    id: raw?.id || `${senderId}-${sentAt}`,
    senderId,
    author,
    text: messageText,
    time: formatTime(sentAt),
    date: sentAt,
    isOwn,
    messageType,
    gifUrl,
    gifPreviewUrl,
    gifTitle,
    attachments,
    resources,
    reactions: normalizeReactionMap(raw?.reactions),
    preview: raw?.preview || null,
    replyTo: raw?.reply_to || null,
    editedAt: raw?.edited_at || null,
    deletedAt: raw?.deleted_at || null,
    isEdited: Boolean(raw?.is_edited || raw?.isEdited || raw?.edited_at),
    isDeleted: Boolean(raw?.is_deleted || raw?.isDeleted || raw?.deleted_at),
    readCount: Number(raw?.read_count || raw?.readCount || 0),
    deliveredCount: Number(raw?.delivered_count || raw?.deliveredCount || 0),
    isReadByMe: Boolean(raw?.is_read_by_me || raw?.isReadByMe),
    isDeliveredToMe: Boolean(raw?.is_delivered_to_me || raw?.isDeliveredToMe),
    readBy: Array.isArray(raw?.read_by) ? raw.read_by : [],
    deliveredTo: Array.isArray(raw?.delivered_to) ? raw.delivered_to : [],
    isLocalOnly: Boolean(raw?.isLocalOnly),
  }
}

const getAttachmentLabel = (attachment) => {
  return (
    attachment?.attachment_filename ||
    attachment?.name ||
    'Attachment'
  )
}

const getAttachmentHref = (attachment) => {
  const url = String(attachment?.download_url || attachment?.url || '#')
  if (url.startsWith('/')) return `${API_BASE_URL}${url}`
  return url
}

const getFilenameFromDisposition = (disposition) => {
  if (!disposition) return ''
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1].replace(/"/g, ''))

  const plainMatch = disposition.match(/filename="?([^";]+)"?/i)
  return plainMatch?.[1] ? plainMatch[1].trim() : ''
}

const triggerBrowserDownload = (blob, filename) => {
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename || 'attachment'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}

const downloadAttachment = async (attachment) => {
  const url = getAttachmentHref(attachment)
  if (!url || url === '#') return

  chatError.value = ''

  try {
    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
    })

    if (!response.ok) {
      throw await apiErrorFromResponse(response, 'Attachment could not be downloaded.')
    }

    const blob = await response.blob()
    const filename =
      getFilenameFromDisposition(response.headers.get('Content-Disposition')) ||
      getAttachmentLabel(attachment)
    triggerBrowserDownload(blob, filename)
  } catch (error) {
    chatError.value = error instanceof Error ? error.message : 'Attachment could not be downloaded.'
    window.open(url, '_blank', 'noopener')
  }
}

// Click a resource chip in a chat bubble → prompt the user to either
// Open (view in a new tab) or Download (force-save). The choice popover
// fetches the resolved URL lazily from the backend and triggers the right
// action. ``access`` returns ``external_url`` for link-resources and a
// signed SAS for managed files; ``download`` always returns a Content-
// Disposition: attachment stream for managed files.
const openResourceChoiceKey = ref(null)
const resourceChoiceLoading = ref(false)
const resourceChoiceStatus = ref('')
// Same Open/Download/Cancel popover but keyed by ``messageId:attachmentId``.
const openAttachmentChoiceKey = ref(null)
const attachmentChoiceLoading = ref(false)
const attachmentChoiceStatus = ref('')

const toggleResourceChoice = (messageId, resource) => {
  const rid = resource?.resource_id || resource?.id
  if (!rid) return
  const key = `${messageId}:${rid}`
  if (openResourceChoiceKey.value === key) {
    closeResourceChoice()
    return
  }
  openResourceChoiceKey.value = key
  resourceChoiceStatus.value = ''
}

const closeResourceChoice = () => {
  openResourceChoiceKey.value = null
  resourceChoiceLoading.value = false
  resourceChoiceStatus.value = ''
}

const toggleAttachmentChoice = (messageId, attachment) => {
  const key = `${messageId}:${attachment?.id || attachment?.attachment_filename}`
  if (openAttachmentChoiceKey.value === key) {
    closeAttachmentChoice()
    return
  }
  openAttachmentChoiceKey.value = key
  attachmentChoiceStatus.value = ''
}

const closeAttachmentChoice = () => {
  openAttachmentChoiceKey.value = null
  attachmentChoiceLoading.value = false
  attachmentChoiceStatus.value = ''
}

const openAttachmentAction = async (attachment, mode) => {
  const baseUrl = getAttachmentHref(attachment)
  if (!baseUrl || baseUrl === '#') return
  attachmentChoiceLoading.value = true
  attachmentChoiceStatus.value = mode === 'download'
    ? 'Preparing download…'
    : 'Opening…'
  try {
    if (mode === 'open') {
      // Append ``?inline=1`` so the backend serves Content-Disposition: inline
      // and the browser previews (PDF viewer, image, etc.) instead of saving.
      const sep = baseUrl.includes('?') ? '&' : '?'
      window.open(`${baseUrl}${sep}inline=1`, '_blank', 'noopener,noreferrer')
      closeAttachmentChoice()
      return
    }
    // Download path — fetch as blob so the filename comes from
    // Content-Disposition and the browser definitely saves regardless of the
    // file type (PDFs would otherwise open inline in some browsers even with
    // Content-Disposition: attachment when navigated to directly).
    const response = await fetch(baseUrl, { method: 'GET', credentials: 'include' })
    if (!response.ok) {
      throw await apiErrorFromResponse(response, 'Attachment could not be downloaded.')
    }
    const blob = await response.blob()
    const filename =
      getFilenameFromDisposition(response.headers.get('Content-Disposition')) ||
      getAttachmentLabel(attachment)
    triggerBrowserDownload(blob, filename)
    closeAttachmentChoice()
  } catch (error) {
    attachmentChoiceStatus.value = error instanceof Error
      ? error.message
      : 'Attachment could not be opened.'
    attachmentChoiceLoading.value = false
  }
}

const openResourceAction = async (resource, mode) => {
  const id = resource?.resource_id || resource?.id
  if (!id) return
  resourceChoiceLoading.value = true
  resourceChoiceStatus.value = mode === 'download'
    ? 'Preparing download…'
    : 'Opening…'
  try {
    const data = await requestJson(`${API_BASE_URL}/resources/resource-files/${id}/access/`)
    const externalUrl = data?.external_url
    const downloadUrl = data?.download_url
    const accessUrl = data?.access_url || downloadUrl
    if (mode === 'download') {
      // For managed files the download endpoint already streams the file
      // with ``Content-Disposition: attachment``. For external link
      // resources we tack on ``?force=1`` so the backend proxies the upstream
      // bytes through us with the same header — without it the browser's
      // ``<a download>`` hint is ignored cross-origin and the file opens
      // inline instead of saving.
      let target = downloadUrl || externalUrl || accessUrl
      if (!target) {
        resourceChoiceStatus.value = data?.detail || 'This resource has no downloadable file.'
        resourceChoiceLoading.value = false
        return
      }
      if (downloadUrl) {
        const sep = downloadUrl.includes('?') ? '&' : '?'
        target = `${downloadUrl}${sep}force=1`
      }
      const a = document.createElement('a')
      a.href = target
      a.rel = 'noopener noreferrer'
      a.download = data?.file_name || ''
      document.body.appendChild(a)
      a.click()
      a.remove()
    } else {
      const target = externalUrl || accessUrl || downloadUrl
      if (!target) {
        resourceChoiceStatus.value = data?.detail || 'This resource cannot be opened.'
        resourceChoiceLoading.value = false
        return
      }
      window.open(target, '_blank', 'noopener,noreferrer')
    }
    closeResourceChoice()
  } catch (error) {
    resourceChoiceStatus.value = error instanceof Error
      ? error.message
      : 'Resource could not be opened.'
    resourceChoiceLoading.value = false
  }
}

const getResourceLabel = (resource) =>
  resource?.resource_name || resource?.name || `Resource ${resource?.resource_id || resource?.id || ''}`

const getReplyLabel = (reply) => {
  if (!reply) return ''
  if (reply.deleted) return 'Deleted message'
  // Prefer the backend-supplied name (ReplyToSerializer.user_name). Fall back to
  // any name we already loaded — group memberships, mention members, or another
  // message in the list authored by the same user — before defaulting to the
  // generic "User N" label.
  const name = reply.user_name || resolveUserDisplayName(reply.user_id)
  return `Reply to ${name}`
}

const resolveUserDisplayName = (userId) => {
  const numericUserId = Number(userId)
  if (!Number.isFinite(numericUserId) || numericUserId <= 0) return 'Team member'
  // 1) Mention members (loaded with the group)
  const member = mentionLabelMembers.value.find((item) => Number(item.userId) === numericUserId)
  if (member?.label) return member.label
  // 2) Self
  if (numericUserId === currentUserId.value) return getCurrentUserMentionName()
  // 3) Any other message we've already loaded — uses the sender_name the
  //    backend ships on full message rows.
  const peerMessage = messages.value.find(
    (m) => Number(m?.senderId) === numericUserId && m?.author && m.author !== 'You',
  )
  if (peerMessage?.author) return peerMessage.author
  return `User ${numericUserId}`
}

const getReplyText = (reply) => {
  if (!reply) return ''
  if (reply.deleted) return 'Original message was deleted.'
  return reply.text || 'Attachment message'
}

const getMentionLabel = (userId) => {
  const numericUserId = Number(userId)
  if (!Number.isFinite(numericUserId) || numericUserId <= 0) return 'Team member'
  const member = mentionLabelMembers.value.find((item) => Number(item.userId) === numericUserId)
  if (member?.label) return member.label
  if (numericUserId === currentUserId.value) return getCurrentUserMentionName()
  return `User ${numericUserId}`
}

const getMentionSenderLabel = (mention) => {
  return mention?.sender_name || getMentionLabel(mention?.sender_user_id)
}

const getMessageTextSegments = (text) => {
  const source = String(text || '')
  const segments = []
  const pattern = /<@(\d+)>|(?<![\w@])@(here|channel)\b/gi
  let cursor = 0
  let isHidingBroadcastExpansion = false
  let match = pattern.exec(source)

  while (match) {
    const gap = source.slice(cursor, match.index)
    if (match[1] && isHidingBroadcastExpansion && /^\s*$/.test(gap)) {
      cursor = match.index + match[0].length
      match = pattern.exec(source)
      continue
    }

    if (match.index > cursor) {
      segments.push({ type: 'text', text: gap })
    }
    const label = match[1] ? getMentionLabel(match[1]) : String(match[2] || '').toLowerCase()
    segments.push({ type: 'mention', text: `@${label}` })
    isHidingBroadcastExpansion = Boolean(match[2])
    cursor = match.index + match[0].length
    match = pattern.exec(source)
  }

  if (cursor < source.length) {
    segments.push({ type: 'text', text: source.slice(cursor) })
  }

  return segments.length ? segments : [{ type: 'text', text: source }]
}

const getMessageSearchSummary = (message) => {
  if (message?.attachments?.length) return getAttachmentLabel(message.attachments[0])
  if (message?.resources?.length) return getResourceLabel(message.resources[0])
  if (message?.preview?.title) return message.preview.title
  return 'Message'
}

const normalizeChatResource = (resource) => ({
  id: Number(resource?.id || resource?.resource_id || 0),
  resource_name: resource?.resource_name || resource?.name || 'Untitled resource',
})

const isResourceSelected = (resourceId) =>
  selectedChatResources.value.some((resource) => Number(resource.id) === Number(resourceId))

const toggleSelectedResource = (resource) => {
  const normalized = normalizeChatResource(resource)
  if (!normalized.id) return

  if (isResourceSelected(normalized.id)) {
    selectedChatResources.value = selectedChatResources.value.filter(
      (item) => Number(item.id) !== Number(normalized.id),
    )
    return
  }

  selectedChatResources.value = [...selectedChatResources.value, normalized]
}

const clearSelectedResources = () => {
  selectedChatResources.value = []
}

const getBackendGroupId = () => {
  const id = routeGroupId.value || group.value?.id
  return /^\d+$/.test(String(id || '')) ? String(id) : ''
}

const isCurrentBackendGroupId = (groupId) => String(groupId || '') === String(getBackendGroupId())

const backendGroupId = computed(() => getBackendGroupId())

const notifySidebarGroupRead = (groupId) => {
  const targetGroupId = String(groupId || '')
  if (!targetGroupId) return

  window.dispatchEvent(
    new CustomEvent(SIDEBAR_GROUP_READ_EVENT, {
      detail: { groupId: targetGroupId },
    }),
  )
}

const resolveIndividualTaskAssignee = (parentTask = null) => {
  if (parentTask?.assignedUser) return Number(parentTask.assignedUser)
  if (auth.isStudent && auth.user?.id) return Number(auth.user.id)

  const assigneeId = Number(individualTaskAssigneeOptions.value[0]?.userId || '')
  return Number.isFinite(assigneeId) && assigneeId > 0 ? assigneeId : null
}

const syncTaskAssigneeForType = () => {
  if (taskForm.value.taskType !== 'individual') {
    taskForm.value.assignedUser = ''
    return
  }

  const currentAssignee = Number(taskForm.value.assignedUser)
  const currentAllowed = individualTaskAssigneeOptions.value.some(
    (item) => item.userId === currentAssignee,
  )

  if (!currentAllowed) {
    const fallbackAssignee = resolveIndividualTaskAssignee()
    taskForm.value.assignedUser = fallbackAssignee ? String(fallbackAssignee) : ''
  }
}

const toDateTimeLocal = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const offsetMs = date.getTimezoneOffset() * 60000
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16)
}

const fromDateTimeLocal = (value) => {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

const resetTaskForm = (taskType = 'group', parentTask = null) => {
  const currentGroupId = getBackendGroupId()
  const parentAssignee =
    parentTask?.taskType === 'individual'
      ? parentTask.assignedUser
      : resolveIndividualTaskAssignee(parentTask)

  taskForm.value = {
    name: '',
    description: '',
    dueDate: '',
    status: 'todo',
    taskType,
    parent: parentTask?.id ? String(parentTask.id) : '',
    group: taskType === 'group' ? String(currentGroupId || '') : '',
    assignedUser: taskType === 'individual' && parentAssignee ? String(parentAssignee) : '',
  }
}

const openCreateTaskDialog = (taskType, parentTask = null) => {
  const currentGroupId = getBackendGroupId()
  if (!currentGroupId) {
    taskError.value = 'A backend numeric group id is required before tasks can be added.'
    return
  }
  if (!canCreateTaskType(taskType, parentTask)) {
    taskError.value = 'You do not have permission to create this task type for this group.'
    return
  }

  taskDialogMode.value = 'create'
  taskDialogTitle.value = parentTask
    ? 'New sub-task'
    : taskType === 'group'
      ? 'New group task'
      : 'New individual task'
  editingTaskId.value = null
  taskFormError.value = ''
  resetTaskForm(taskType, parentTask)
  taskDialogOpen.value = true
}

const openEditTaskDialog = async (task) => {
  let editableTask = task
  taskError.value = ''

  try {
    const latestTask = await retrieveTask(task.id)
    editableTask = normalizeTask(latestTask)
    upsertTask(latestTask)
  } catch (error) {
    taskError.value =
      error instanceof Error ? error.message : 'Latest task details could not be loaded.'
  }

  taskDialogMode.value = 'edit'
  taskDialogTitle.value = 'Edit task'
  editingTaskId.value = Number(editableTask.id)
  taskFormError.value = ''
  taskForm.value = {
    name: editableTask.name || '',
    description: editableTask.description || '',
    dueDate: toDateTimeLocal(editableTask.dueDate),
    status: editableTask.status || 'todo',
    taskType: editableTask.taskType || 'group',
    parent: editableTask.parent ? String(editableTask.parent) : '',
    group: editableTask.group ? String(editableTask.group) : '',
    assignedUser: editableTask.assignedUser ? String(editableTask.assignedUser) : '',
  }
  taskDialogOpen.value = true
}

const closeTaskDialog = ({ force = false } = {}) => {
  if (isSavingTask.value && !force) return
  taskDialogOpen.value = false
  taskFormError.value = ''
}

watch(taskDialogOpen, (isOpen) => {
  if (typeof document === 'undefined') return
  document.body.style.overflow = isOpen ? 'hidden' : ''
  if (isOpen) {
    nextTick(() => {
      taskDialogNameInput.value?.focus?.()
      try { taskDialogNameInput.value?.select?.() } catch { /* ignore */ }
    })
  }
})

const buildCreateTaskPayload = () => {
  const taskType = taskForm.value.taskType
  const payload = {
    name: taskForm.value.name.trim(),
    description: taskForm.value.description.trim(),
    due_date: fromDateTimeLocal(taskForm.value.dueDate),
    status: taskForm.value.status,
    task_type: taskType,
    parent: taskForm.value.parent ? Number(taskForm.value.parent) : null,
  }

  if (taskType === 'group') {
    payload.group = Number(getBackendGroupId())
    payload.assigned_user = null
  } else {
    payload.group = null
    payload.assigned_user = Number(taskForm.value.assignedUser)
  }

  return payload
}

const buildUpdateTaskPayload = () => ({
  name: taskForm.value.name.trim(),
  description: taskForm.value.description.trim(),
  due_date: fromDateTimeLocal(taskForm.value.dueDate),
  status: taskForm.value.status,
  parent: taskForm.value.parent ? Number(taskForm.value.parent) : null,
})

const saveTask = async () => {
  if (!taskForm.value.name.trim()) {
    taskFormError.value = 'Task name is required.'
    return
  }
  if (
    taskDialogMode.value === 'create' &&
    taskForm.value.taskType === 'individual' &&
    !Number(taskForm.value.assignedUser)
  ) {
    taskFormError.value = 'Please choose an assignee for this individual task.'
    return
  }
  if (taskDialogMode.value === 'create' && !canCreateTaskFromForm()) {
    taskFormError.value = 'You do not have permission to create a task for this target.'
    return
  }

  isSavingTask.value = true
  taskFormError.value = ''

  try {
    if (taskDialogMode.value === 'edit' && editingTaskId.value) {
      const updatedTask = await updateTaskRequest(editingTaskId.value, buildUpdateTaskPayload())
      upsertTask(updatedTask)
    } else {
      const createdTask = await createTaskRequest(buildCreateTaskPayload())
      upsertTask(createdTask)
    }
    closeTaskDialog({ force: true })
  } catch (error) {
    taskFormError.value = error instanceof Error ? error.message : 'Task could not be saved.'
  } finally {
    isSavingTask.value = false
  }
}

const changeTaskStatus = async (task, newStatus) => {
  if (!task?.id || isUpdatingTask(task.id)) return
  if (newStatus === task.status) {
    closeStatusMenu()
    return
  }

  setTaskUpdating(task.id, true)
  taskError.value = ''
  closeStatusMenu()

  try {
    const updatedTask = await setTaskStatusRequest(task.id, newStatus)
    upsertTask(updatedTask)
  } catch (error) {
    taskError.value = error instanceof Error ? error.message : 'Task status could not be updated.'
  } finally {
    setTaskUpdating(task.id, false)
  }
}

const bulkSetTaskCompletion = async (completed) => {
  const taskIds = selectedTaskIdList.value
  if (!taskIds.length) return

  isBulkUpdatingTasks.value = true
  taskError.value = ''

  try {
    const result = await bulkToggleTasks(taskIds, completed)
    result.updated.forEach(upsertTask)
    clearTaskSelection()
    if (result.forbidden.length || result.not_found.length) {
      taskError.value = [
        result.forbidden.length ? `${result.forbidden.length} task(s) were not allowed.` : '',
        result.not_found.length ? `${result.not_found.length} task(s) were not found.` : '',
      ]
        .filter(Boolean)
        .join(' ')
    }
  } catch (error) {
    taskError.value =
      error instanceof Error ? error.message : 'Selected tasks could not be updated.'
  } finally {
    isBulkUpdatingTasks.value = false
  }
}

const removeTask = async (task) => {
  if (!task?.id || isDeletingTask(task.id)) return
  const confirmed = window.confirm(`Delete "${task.name}" and its sub-tasks?`)
  if (!confirmed) return

  setTaskDeleting(task.id, true)
  taskError.value = ''

  try {
    const deletedTask = await deleteTaskRequest(task.id)
    cacheDeletedTask(deletedTask)
    setTaskSelected(task.id, false)
    if (taskFilters.value.showDeleted) upsertTask(deletedTask)
    else removeTaskFromList(task.id)
  } catch (error) {
    taskError.value = error instanceof Error ? error.message : 'Task could not be deleted.'
  } finally {
    setTaskDeleting(task.id, false)
  }
}

const typingIndicatorText = computed(() => {
  const list = typingUsers.value
  if (!list.length) return ''
  if (list.length === 1) return `${list[0]} is typing…`
  if (list.length === 2) return `${list[0]} and ${list[1]} are typing…`
  const extra = list.length - 2
  return `${list[0]}, ${list[1]} and ${extra} ${extra === 1 ? 'other' : 'others'} are typing…`
})

const showScrollToBottomButton = computed(
  () => hasScrollableMessages.value && isChatAwayFromBottom.value,
)

const showMissedMessageJumpButton = computed(
  () => missedMessageAnchorId.value !== null && !isMissedMessageJumpDismissed.value,
)

const missedMessageDividerText = computed(() => {
  const count = Number(missedMessageCount.value || 0)
  if (count <= 1) return 'New message'
  return `${count} new messages`
})

const missedMessageJumpText = computed(() => {
  const count = Number(missedMessageCount.value || 0)
  if (count <= 1) return 'Unread'
  return `${count} unread`
})

const canSendChatMessage = computed(
  () => Boolean(newMessage.value.trim()) || selectedChatResources.value.length > 0,
)

const mentionLabelMembers = computed(() =>
  groupMemberships.value
    .filter((item) => !item.leftAt)
    .map(normalizeMentionMember)
    .filter((member) => member.userId),
)

const mentionMembers = computed(() =>
  mentionLabelMembers.value
    .filter((member) => member.userId && member.userId !== currentUserId.value),
)

const broadcastMentionOptions = computed(() => [
  {
    key: 'broadcast-here',
    token: 'here',
    label: 'here',
    role: 'Notify everyone in this group',
    icon: 'fas fa-bullhorn',
    isBroadcast: true,
  },
  {
    key: 'broadcast-channel',
    token: 'channel',
    label: 'channel',
    role: 'Notify everyone in this group',
    icon: 'fas fa-bullhorn',
    isBroadcast: true,
  },
])

const mentionSuggestions = computed(() => {
  const query = mentionQuery.value.toLowerCase()
  return [...broadcastMentionOptions.value, ...mentionMembers.value]
    .filter((member) => {
      if (!query) return true
      return (
        member.label.toLowerCase().includes(query) ||
        String(member.token || '').toLowerCase().includes(query) ||
        member.role.toLowerCase().includes(query) ||
        (member.userId && String(member.userId).includes(query))
      )
    })
    .slice(0, 6)
})

const showMentionSuggestions = computed(
  () => mentionStartIndex.value >= 0 && mentionSuggestions.value.length > 0,
)

const applyMessageUpdate = (messageId, updater) => {
  const index = messages.value.findIndex((message) => String(message.id) === String(messageId))
  if (index === -1) return

  const current = messages.value[index]
  const nextValue = typeof updater === 'function' ? updater(current) : updater
  messages.value.splice(index, 1, nextValue)
}

const isPendingMessage = (message) =>
  String(message?.id || '').startsWith('pending-') || Boolean(message?.isLocalOnly)

const findMatchingPendingMessageIndex = (message) => {
  if (!message?.isOwn) return -1

  return messages.value.findIndex(
    (item) =>
      isPendingMessage(item) &&
      item.isOwn &&
      item.text === message.text &&
      item.messageType === message.messageType,
  )
}

const upsertMessage = (message) => {
  const normalized = normalizeMessage(message)
  const normalizedId = Number(normalized.id)
  if (Number.isFinite(normalizedId)) {
    const currentAfter = Number(nextMessagesAfter.value || 0)
    nextMessagesAfter.value = Math.max(currentAfter, normalizedId)
  }
  const index = messages.value.findIndex((item) => String(item.id) === String(normalized.id))
  if (index === -1) {
    const pendingIndex = findMatchingPendingMessageIndex(normalized)
    if (pendingIndex !== -1) {
      messages.value.splice(pendingIndex, 1, normalized)
      return
    }

    messages.value.push(normalized)
    return
  }

  messages.value.splice(index, 1, {
    ...messages.value[index],
    ...normalized,
  })
}

const getMissedMessages = (messageList = messages.value) =>
  (messageList || []).filter(
    (message) => !message.isOwn && !message.isLocalOnly && message.isReadByMe === false,
  )

const shouldLoadOlderMissedMessages = (messageList, nextBefore) => {
  if (!nextBefore || !getMissedMessages(messageList).length) return false
  const firstPeerMessage = (messageList || []).find(
    (message) => !message.isOwn && !message.isLocalOnly,
  )
  return firstPeerMessage?.isReadByMe === false
}

const expandMissedMessageWindow = async (messageList, initialNextBefore) => {
  const backendGroupId = getBackendGroupId()
  if (!backendGroupId) return { messages: messageList, nextBefore: initialNextBefore }

  let combinedMessages = [...messageList]
  let nextBefore = initialNextBefore
  const MAX_MISSED_LOOKBACK_PAGES = 5

  for (
    let page = 0;
    page < MAX_MISSED_LOOKBACK_PAGES && shouldLoadOlderMissedMessages(combinedMessages, nextBefore);
    page += 1
  ) {
    const data = await requestJson(
      buildChatMessageCollectionUrl(
        backendGroupId,
        `?limit=100&before=${encodeURIComponent(nextBefore)}`,
      ),
    )
    const olderMessages = extractCollectionItems(data).map(normalizeMessage).reverse()
    if (!olderMessages.length) {
      nextBefore = null
      break
    }

    const existingIds = new Set(combinedMessages.map((message) => String(message.id)))
    combinedMessages = [
      ...olderMessages.filter((message) => !existingIds.has(String(message.id))),
      ...combinedMessages,
    ]
    nextBefore = data?.next_before || null
  }

  return { messages: combinedMessages, nextBefore }
}

const setMissedMessageAnchor = (messageList = messages.value) => {
  const missedMessages = getMissedMessages(messageList)
  missedMessageAnchorId.value = missedMessages[0]?.id || null
  missedMessageCount.value = missedMessages.length
  isMissedMessageJumpDismissed.value = false
}

const clearMissedMessageAnchor = () => {
  missedMessageAnchorId.value = null
  missedMessageCount.value = 0
  isMissedMessageJumpDismissed.value = false
}

const isMissedMessageAnchor = (messageId) =>
  missedMessageAnchorId.value !== null &&
  String(missedMessageAnchorId.value) === String(messageId)

const removeTypingUser = (name) => {
  const timer = typingUserTimers.get(name)
  if (timer) {
    clearTimeout(timer)
    typingUserTimers.delete(name)
  }
  typingUsers.value = typingUsers.value.filter((item) => item !== name)
}

const addTypingUser = (name) => {
  if (!typingUsers.value.includes(name)) {
    typingUsers.value = [...typingUsers.value, name]
  }

  const existingTimer = typingUserTimers.get(name)
  if (existingTimer) clearTimeout(existingTimer)
  typingUserTimers.set(
    name,
    setTimeout(() => {
      removeTypingUser(name)
    }, 4500),
  )
}

const hasMessageReactions = (message) =>
  Object.values(message?.reactions || {}).some((entry) => {
    if (entry && typeof entry === 'object') return Number(entry.count) > 0
    return Number(entry) > 0
  })

const formatReactionUsers = (entry) => {
  const users = Array.isArray(entry?.users) ? entry.users : []
  if (!users.length) {
    const count = Number(entry?.count ?? entry) || 0
    return count === 1 ? '1 person reacted' : `${count} people reacted`
  }
  const names = users.map((u) => u.name).filter(Boolean)
  if (!names.length) return `${users.length} reacted`
  if (names.length === 1) return names[0]
  if (names.length === 2) return `${names[0]} and ${names[1]}`
  if (names.length === 3) return `${names[0]}, ${names[1]} and ${names[2]}`
  return `${names[0]}, ${names[1]} and ${names.length - 2} others`
}

const toggleReactionPicker = (messageId) => {
  if (!supportsMessageReactions) return
  activeReactionPickerMessageId.value =
    activeReactionPickerMessageId.value === messageId ? null : messageId
  if (activeReactionPickerMessageId.value !== null) openMessageKebabId.value = null
}

const toggleMessageKebab = (messageId) => {
  openMessageKebabId.value = openMessageKebabId.value === messageId ? null : messageId
  if (openMessageKebabId.value !== null) activeReactionPickerMessageId.value = null
}

const onKebabEdit = (message) => {
  openMessageKebabId.value = null
  startMessageEdit(message)
}

const onKebabDelete = (message) => {
  openMessageKebabId.value = null
  deleteMessage(message)
}

const sendSocketAction = (payload) => {
  if (!supportsChatClientSocketActions || !chatSocket || chatSocket.readyState !== WebSocket.OPEN)
    return false
  chatSocket.send(JSON.stringify(payload))
  return true
}

const sendTypingState = (typing) => {
  const sent = sendSocketAction({ type: 'typing', typing })
  if (sent) {
    lastTypingSentAt = Date.now()
  }
  return sent
}

const stopTypingIndicator = () => {
  clearTimeout(typingStopTimer)
  if (!supportsChatClientSocketActions) {
    hasSentTypingStart = false
    return
  }
  if (hasSentTypingStart) {
    sendTypingState(false)
    hasSentTypingStart = false
  }
}

const scheduleTypingStop = () => {
  clearTimeout(typingStopTimer)
  typingStopTimer = setTimeout(() => {
    stopTypingIndicator()
  }, 2600)
}

const handleComposerInput = () => {
  updateMentionQuery()

  if (!supportsChatClientSocketActions) return

  if (!newMessage.value.trim()) {
    stopTypingIndicator()
    return
  }

  if (!hasSentTypingStart) {
    sendTypingState(true)
    hasSentTypingStart = true
  } else if (Date.now() - lastTypingSentAt > 2200) {
    sendTypingState(true)
  }

  scheduleTypingStop()
}

const updateMentionQuery = () => {
  const cursor = composer.value?.selectionStart ?? newMessage.value.length
  const beforeCursor = newMessage.value.slice(0, cursor)
  const match = beforeCursor.match(/(^|\s)@([A-Za-z0-9_]*)$/)

  if (!match) {
    mentionStartIndex.value = -1
    mentionQuery.value = ''
    activeMentionSuggestionIndex.value = 0
    return
  }

  mentionStartIndex.value = beforeCursor.length - match[2].length - 1
  mentionQuery.value = match[2]
  activeMentionSuggestionIndex.value = 0
}

// Tracks the @-token text we wrote into the composer for each mention so we
// can rewrite it back to the backend's ``<@id>`` form on send. Cleared after
// a successful send / cancel.
const pendingComposerMentions = ref(new Map())

const insertMention = (member) => {
  if (mentionStartIndex.value < 0 || !member) return

  const displayName = member.isBroadcast
    ? String(member.token || member.label || '').toLowerCase()
    : member.label || `User ${member.userId}`
  if (!displayName || (!member.isBroadcast && !member.userId)) return
  // Visible token: ``@Name`` — readable to the user. We keep a map so we can
  // resolve it back to ``<@id>`` before posting. Multiple mentions with the
  // same display name collapse to the same id (acceptable; the map keeps the
  // last-wins entry).
  const visible = `@${displayName}`
  if (!member.isBroadcast) {
    pendingComposerMentions.value.set(visible, member.userId)
  }

  const cursor = composer.value?.selectionStart ?? newMessage.value.length
  const prefix = newMessage.value.slice(0, mentionStartIndex.value)
  const suffix = newMessage.value.slice(cursor)
  const spacer = suffix.startsWith(' ') || !suffix ? '' : ' '
  newMessage.value = `${prefix}${visible} ${spacer}${suffix}`.replace(/\s{2,}/g, ' ')
  mentionStartIndex.value = -1
  mentionQuery.value = ''
  activeMentionSuggestionIndex.value = 0

  nextTick(() => {
    composer.value?.focus()
    const position = `${prefix}${visible} `.length
    composer.value?.setSelectionRange(position, position)
  })
}

// Convert visible mention tokens to backend ``<@id>`` tokens just before
// sending. ``@here`` / ``@channel`` remain in the stored text; we append
// machine-readable user tokens after them so the unchanged backend can still
// create normal mention rows.
const resolveComposerMentions = (text) => {
  if (!text) return text
  const entries = [...pendingComposerMentions.value.entries()].sort(
    ([a], [b]) => b.length - a.length,
  )
  let out = text
  for (const [visible, userId] of entries) {
    const safe = visible.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    out = out.replace(new RegExp(safe, 'g'), `<@${userId}>`)
  }

  if (/@(here|channel)\b/i.test(out)) {
    let didExpandBroadcast = false
    out = out.replace(/(?<![\w@])@(here|channel)\b/gi, (token) => {
      if (didExpandBroadcast) return token

      const alreadyMentioned = new Set(
        [...out.matchAll(/<@(\d+)>/g)].map((match) => Number(match[1])),
      )
      const broadcastMentions = mentionMembers.value
        .map((member) => Number(member.userId))
        .filter((userId) => Number.isFinite(userId) && !alreadyMentioned.has(userId))
        .map((userId) => `<@${userId}>`)

      if (!broadcastMentions.length) return token
      didExpandBroadcast = true
      return `${token} ${broadcastMentions.join(' ')}`
    })
  }

  return out
}

// Close the @-autocomplete dropdown when the composer loses focus, unless
// the new focus target is the suggestion list itself (mousedown.prevent on
// each item keeps focus on the composer, so this only fires on truly
// outside clicks).
const onComposerBlur = (event) => {
  const next = event?.relatedTarget
  if (next instanceof Element && next.closest('.mention-suggestions')) return
  if (mentionStartIndex.value >= 0) {
    mentionStartIndex.value = -1
    mentionQuery.value = ''
  }
}

// Tapping into the composer always returns focus to "I'm typing a message",
// so any open side panels (GIF / Resources / Search / Mentions / kebab /
// reaction picker) should yield. Without this, panels stayed visible after
// the user tapped the textarea, which is unexpected.
const onComposerFocus = () => {
  closeAllComposerPanels({ except: null })
}

const handleComposerKeydown = (event) => {
  if (showMentionSuggestions.value) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      activeMentionSuggestionIndex.value =
        (activeMentionSuggestionIndex.value + 1) % mentionSuggestions.value.length
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      activeMentionSuggestionIndex.value =
        (activeMentionSuggestionIndex.value - 1 + mentionSuggestions.value.length) %
        mentionSuggestions.value.length
      return
    }
    if (event.key === 'Enter' || event.key === 'Tab') {
      event.preventDefault()
      insertMention(mentionSuggestions.value[activeMentionSuggestionIndex.value])
      return
    }
    if (event.key === 'Escape') {
      mentionStartIndex.value = -1
      mentionQuery.value = ''
      return
    }
  }

  // Respect IME composition — never intercept while a CJK candidate is selecting.
  if (event.isComposing || event.keyCode === 229) return

  if (event.key === 'Escape') {
    if (editingMessageId.value) {
      event.preventDefault()
      cancelMessageEdit()
      return
    }
    if (replyTarget.value) {
      event.preventDefault()
      clearReplyTarget()
      return
    }
    composer.value?.blur()
    return
  }

  if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
    event.preventDefault()
    void sendMessage()
    return
  }

  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    void sendMessage()
    return
  }

  // ArrowUp on an empty composer with no active reply/edit opens your most
  // recent in-window own message for editing — Slack-style quick-edit.
  if (
    event.key === 'ArrowUp'
    && !newMessage.value.trim()
    && !editingMessageId.value
    && !replyTarget.value
  ) {
    for (let i = messages.value.length - 1; i >= 0; i -= 1) {
      const candidate = messages.value[i]
      if (candidate?.isOwn && canManageMessage(candidate)) {
        event.preventDefault()
        startMessageEdit(candidate)
        return
      }
    }
  }
}

const applyReadCursor = (readerId, upToId) => {
  const numericReaderId = Number(readerId)
  const numericUpToId = Number(upToId)
  if (!Number.isFinite(numericReaderId) || !Number.isFinite(numericUpToId)) return

  const currentUserId = Number(auth.user?.id || 0)
  messages.value = messages.value.map((message) => {
    const messageId = Number(message.id)
    if (
      !Number.isFinite(messageId) ||
      messageId > numericUpToId ||
      Number(message.senderId || 0) === numericReaderId
    ) {
      return message
    }

    const readBy = Array.from(new Set([...(message.readBy || []), numericReaderId]))
    const readCount =
      readBy.length > (message.readBy || []).length
        ? Number(message.readCount || 0) + 1
        : Number(message.readCount || 0)

    return {
      ...message,
      readBy,
      readCount,
      deliveredCount: Math.max(Number(message.deliveredCount || 0), readCount),
      isReadByMe: numericReaderId === currentUserId ? true : message.isReadByMe,
      isDeliveredToMe: numericReaderId === currentUserId ? true : message.isDeliveredToMe,
    }
  })
}

const applyDeliveredCursor = (userId, upToId) => {
  const numericUserId = Number(userId)
  const numericUpToId = Number(upToId)
  if (!Number.isFinite(numericUserId) || !Number.isFinite(numericUpToId)) return

  const currentUserId = Number(auth.user?.id || 0)
  messages.value = messages.value.map((message) => {
    const messageId = Number(message.id)
    if (
      !Number.isFinite(messageId) ||
      messageId > numericUpToId ||
      Number(message.senderId || 0) === numericUserId
    ) {
      return message
    }

    const deliveredTo = Array.from(new Set([...(message.deliveredTo || []), numericUserId]))
    const deliveredCount =
      deliveredTo.length > (message.deliveredTo || []).length
        ? Number(message.deliveredCount || 0) + 1
        : Number(message.deliveredCount || 0)

    return {
      ...message,
      deliveredTo,
      deliveredCount: Math.max(deliveredCount, Number(message.readCount || 0)),
      isDeliveredToMe:
        numericUserId === currentUserId ? true : message.isDeliveredToMe,
    }
  })
}

const markMessagesAsRead = async (messageIds, groupId = getBackendGroupId()) => {
  const ids = (messageIds || []).map((id) => Number(id)).filter((id) => Number.isFinite(id))
  if (!ids.length) return

  const backendGroupId = String(groupId || '')
  if (!backendGroupId) return
  if (!isCurrentBackendGroupId(backendGroupId)) return

  const upToId = Math.max(...ids)
  try {
    const data = await requestJson(buildChatReadUrl(backendGroupId, upToId), {
      method: 'POST',
    })
    if (!isCurrentBackendGroupId(backendGroupId)) return
    applyReadCursor(auth.user?.id, data?.up_to_id || upToId)
    notifySidebarGroupRead(backendGroupId)
  } catch (error) {
    if (!isCurrentBackendGroupId(backendGroupId)) return
    console.error('Failed to mark messages as read:', error)
  }
}

const markMessagesAsDelivered = async (messageIds, groupId = getBackendGroupId()) => {
  const ids = (messageIds || []).map((id) => Number(id)).filter((id) => Number.isFinite(id))
  if (!ids.length) return

  const backendGroupId = String(groupId || '')
  if (!backendGroupId) return
  if (!isCurrentBackendGroupId(backendGroupId)) return

  const upToId = Math.max(...ids)
  try {
    const data = await requestJson(buildChatDeliveredUrl(backendGroupId, upToId), {
      method: 'POST',
    })
    if (!isCurrentBackendGroupId(backendGroupId)) return
    applyDeliveredCursor(auth.user?.id, data?.up_to_id || upToId)
  } catch (error) {
    if (!isCurrentBackendGroupId(backendGroupId)) return
    console.error('Failed to mark messages as delivered:', error)
  }
}

const updateScrollToBottomState = () => {
  const element = msgList.value
  if (!element) {
    hasScrollableMessages.value = false
    isChatAwayFromBottom.value = false
    return
  }

  const scrollableDistance = element.scrollHeight - element.clientHeight
  const distanceFromBottom = scrollableDistance - element.scrollTop
  hasScrollableMessages.value = scrollableDistance > SCROLL_BOTTOM_THRESHOLD
  isChatAwayFromBottom.value =
    hasScrollableMessages.value && distanceFromBottom > SCROLL_BOTTOM_THRESHOLD
}

const CHAT_TOP_TRIGGER_PX = 80

const handleMessagesScroll = () => {
  updateScrollToBottomState()
  const el = msgList.value
  if (!el) return
  if (
    el.scrollTop <= CHAT_TOP_TRIGGER_PX &&
    nextMessagesBefore.value &&
    !isLoadingOlderMessages.value
  ) {
    void loadOlderMessages()
  }
}

const scrollMessagesToBottom = async () => {
  await nextTick()
  if (msgList.value) {
    msgList.value.scrollTop = msgList.value.scrollHeight
    updateScrollToBottomState()
  }
}

const scrollMessagesToBottomAfterRender = async () => {
  await scrollMessagesToBottom()
  await new Promise((resolve) => window.requestAnimationFrame(resolve))
  await scrollMessagesToBottom()
  window.setTimeout(() => {
    void scrollMessagesToBottom()
  }, 120)
}

const setReplyTarget = (message) => {
  if (!message || isPendingMessage(message)) return
  replyTarget.value = message
  composer.value?.focus()
}

const clearReplyTarget = () => {
  replyTarget.value = null
}

const canManageMessage = (message) => {
  if (!message || isPendingMessage(message) || message.isDeleted) return false
  if (auth.isAdmin) return true
  if (!message.isOwn) return false

  const sentAt = new Date(message.date).getTime()
  if (!Number.isFinite(sentAt)) return false
  return manageWindowNow.value - sentAt <= 10 * 60 * 1000
}

const startMessageEdit = (message) => {
  if (!canManageMessage(message)) return
  editingMessageId.value = message.id
  editingMessageText.value = message.text || ''
  nextTick(() => composer.value?.blur())
}

const cancelMessageEdit = () => {
  editingMessageId.value = null
  editingMessageText.value = ''
}

const saveMessageEdit = async (message) => {
  const backendGroupId = getBackendGroupId()
  const text = editingMessageText.value.trim()
  if (!backendGroupId || !message?.id || !text || isUpdatingMessage.value) return

  isUpdatingMessage.value = true
  chatError.value = ''

  try {
    const updated = await requestJson(buildChatMessageUrl(backendGroupId, message.id), {
      method: 'PATCH',
      body: JSON.stringify({ message_text: resolveComposerMentions(text) }),
    })
    pendingComposerMentions.value.clear()
    upsertMessage(updated)
    cancelMessageEdit()
  } catch (error) {
    chatError.value = error instanceof Error ? error.message : 'Message could not be edited.'
  } finally {
    isUpdatingMessage.value = false
  }
}

const deleteMessage = async (message) => {
  const backendGroupId = getBackendGroupId()
  if (!backendGroupId || !message?.id || isDeletingMessageId.value) return
  const confirmed = window.confirm('Delete this message?')
  if (!confirmed) return

  isDeletingMessageId.value = message.id
  chatError.value = ''

  try {
    await requestJson(buildChatMessageUrl(backendGroupId, message.id), {
      method: 'DELETE',
    })
    messages.value = messages.value.filter((item) => String(item.id) !== String(message.id))
  } catch (error) {
    chatError.value = error instanceof Error ? error.message : 'Message could not be deleted.'
  } finally {
    isDeletingMessageId.value = null
  }
}

const disconnectChatSocket = () => {
  stopTypingIndicator()
  if (chatSocket) {
    chatSocket.close()
    chatSocket = null
  }
  wsConnectionState.value = 'offline'
  typingUserTimers.forEach((timer) => clearTimeout(timer))
  typingUserTimers.clear()
  typingUsers.value = []
}

const handleSocketPayload = async (payload) => {
  if (!payload || typeof payload !== 'object') return
  const eventName = payload.event || payload.type
  const payloadGroupId = payload.group_id || payload.message?.group || payload.message?.group_id
  if (
    eventName &&
    String(eventName).startsWith('message.') &&
    payloadGroupId &&
    !isCurrentBackendGroupId(payloadGroupId)
  ) {
    return
  }

  if (eventName === 'user.typing') {
    const currentUserId = Number(auth.user?.id || 0)
    if (Number(payload.user_id) === currentUserId) return

    const displayName = payload.user_name || `User ${payload.user_id}`
    if (payload.typing) {
      addTypingUser(displayName)
    } else {
      removeTypingUser(displayName)
    }
    return
  }

  if (eventName === 'message.reaction_updated') {
    applyMessageUpdate(payload.message_id, (message) => ({
      ...message,
      reactions: normalizeReactionMap(payload.reactions),
    }))
    return
  }

  if (eventName === 'message.read_updated') {
    applyReadCursor(payload.reader_id, payload.up_to_id)
    return
  }

  if (eventName === 'message.delivered_updated') {
    applyDeliveredCursor(payload.user_id, payload.up_to_id)
    return
  }

  if (eventName === 'message.preview_ready') {
    applyMessageUpdate(payload.message_id, (message) => ({
      ...message,
      preview: payload.preview || null,
    }))
    return
  }

  if (eventName === 'mention.created') {
    const currentGroupId = Number(getBackendGroupId() || 0)
    const mentionedGroupId = Number(payload.group_id || 0)
    mentionUnreadCount.value += 1
    mentionItems.value = [
      {
        id: payload.id || `live-${Date.now()}`,
        group_id: payload.group_id,
        message_id: payload.message_id,
        message_text: payload.preview || '',
        sender_user_id: payload.sender_user_id,
        sender_name: payload.sender_name || getMentionLabel(payload.sender_user_id),
        sent_at: payload.sent_at || new Date().toISOString(),
        created_at: new Date().toISOString(),
        read_at: null,
      },
      ...mentionItems.value,
    ].slice(0, 20)
    if (mentionedGroupId && mentionedGroupId !== currentGroupId) {
      chatNotice.value = `You were mentioned in group ${mentionedGroupId}.`
    } else {
      chatNotice.value = 'You were mentioned in this discussion.'
    }
    return
  }

  const socketMessage =
    payload.message && typeof payload.message === 'object' ? payload.message : null
  const socketMessageId = socketMessage?.id ?? payload.message_id

  if (eventName === 'message.created' && socketMessage) {
    upsertMessage(socketMessage)
    removeTypingUser(payload.user_name || socketMessage.sender_name || '')
    await scrollMessagesToBottom()
    if (
      Number(socketMessage.sender_user || socketMessage.sender_id || 0) !==
      Number(auth.user?.id || 0)
    ) {
      await markMessagesAsRead([socketMessage.id])
    }
    return
  }

  if (eventName === 'message.edited') {
    if (socketMessage) {
      upsertMessage(socketMessage)
    } else if (socketMessageId) {
      applyMessageUpdate(socketMessageId, (message) => ({
        ...message,
        text: payload.message_text || message.text,
        editedAt: payload.edited_at || message.editedAt,
      }))
    }
    return
  }

  if (eventName === 'message.deleted') {
    if (!socketMessageId) return
    messages.value = messages.value.map((message) => {
      if (String(message.replyTo?.id) !== String(socketMessageId)) return message
      return {
        ...message,
        replyTo: {
          ...message.replyTo,
          text: null,
          deleted: true,
        },
      }
    })
    messages.value = messages.value.filter(
      (message) => String(message.id) !== String(socketMessageId),
    )
  }
}

const connectChatSocket = () => {
  const backendGroupId = getBackendGroupId()
  if (!backendGroupId || typeof WebSocket === 'undefined') return

  disconnectChatSocket()

  try {
    chatSocket = new WebSocket(buildChatWebSocketUrl(backendGroupId))
  } catch {
    wsConnectionState.value = 'offline'
    return
  }

  wsConnectionState.value = 'connecting'

  chatSocket.addEventListener('open', () => {
    wsConnectionState.value = 'connected'
    // No catch-up fetch on first open — loadMessages already pulled the
    // freshest batch. Only resync on reconnect, where messages may have
    // arrived while the socket was down.
    if (hasConnectedChatSocket) {
      void loadNewerMessages()
      void markMessagesAsRead(
        messages.value.filter((message) => !message.isOwn).map((message) => message.id),
        backendGroupId,
      )
    }
    hasConnectedChatSocket = true
  })

  chatSocket.addEventListener('message', async (event) => {
    try {
      const payload = JSON.parse(event.data)
      await handleSocketPayload(payload)
    } catch (error) {
      console.error('Failed to parse chat socket payload:', error)
    }
  })

  chatSocket.addEventListener('close', () => {
    wsConnectionState.value = 'offline'
    typingUserTimers.forEach((timer) => clearTimeout(timer))
    typingUserTimers.clear()
    typingUsers.value = []
  })

  chatSocket.addEventListener('error', () => {
    wsConnectionState.value = 'offline'
  })
}

// Initial page size for the chat. Older pages are auto-fetched on
// scroll-up; the visible button is a fallback for no-JS or screen readers.
const CHAT_INITIAL_LIMIT = 11
const CHAT_PAGE_LIMIT = 11

const loadMessages = async () => {
  const backendGroupId = getBackendGroupId()
  if (!backendGroupId) {
    chatError.value = 'Live discussion needs a backend numeric group id.'
    messages.value = []
    clearMissedMessageAnchor()
    await scrollMessagesToBottom()
    return
  }

  isLoadingMessages.value = true
  chatError.value = ''

  try {
    const data = await requestJson(
      buildChatMessageCollectionUrl(backendGroupId, `?limit=${CHAT_INITIAL_LIMIT}`),
    )
    let liveMessages = extractCollectionItems(data).map(normalizeMessage).reverse()
    let nextBefore = data?.next_before || null

    if (shouldLoadOlderMissedMessages(liveMessages, nextBefore)) {
      const expanded = await expandMissedMessageWindow(liveMessages, nextBefore)
      liveMessages = expanded.messages
      nextBefore = expanded.nextBefore
    }

    if (!isCurrentBackendGroupId(backendGroupId)) return

    messages.value = liveMessages.length ? liveMessages : []
    setMissedMessageAnchor(messages.value)
    nextMessagesAfter.value = data?.next_after || null
    nextMessagesBefore.value = nextBefore
  } catch (error) {
    if (!isCurrentBackendGroupId(backendGroupId)) return
    chatError.value =
      error instanceof Error ? error.message : 'Live discussion is unavailable right now.'
    messages.value = []
    clearMissedMessageAnchor()
    nextMessagesAfter.value = null
    nextMessagesBefore.value = null
  } finally {
    if (!isCurrentBackendGroupId(backendGroupId)) return
    isLoadingMessages.value = false
    // Fire-and-forget — scroll + delivery/read receipts must not gate the UI.
    const incomingIds = messages.value
      .filter((message) => !message.isOwn)
      .map((message) => message.id)
    if (missedMessageAnchorId.value) {
      void scrollToMissedMessages()
    } else {
      void scrollMessagesToBottomAfterRender()
    }
    void markMessagesAsDelivered(incomingIds, backendGroupId)
    void markMessagesAsRead(incomingIds, backendGroupId)
  }
}

const loadOlderMessages = async () => {
  const backendGroupId = getBackendGroupId()
  if (!backendGroupId || !nextMessagesBefore.value || isLoadingOlderMessages.value) return

  isLoadingOlderMessages.value = true
  chatError.value = ''

  // Anchor scroll so prepending older messages doesn't yank the user up.
  const scroller = msgList.value
  const prevScrollHeight = scroller?.scrollHeight ?? 0
  const prevScrollTop = scroller?.scrollTop ?? 0

  try {
    const data = await requestJson(
      buildChatMessageCollectionUrl(
        backendGroupId,
        `?limit=${CHAT_PAGE_LIMIT}&before=${encodeURIComponent(nextMessagesBefore.value)}`,
      ),
    )
    const olderMessages = extractCollectionItems(data).map(normalizeMessage).reverse()
    const existingIds = new Set(messages.value.map((message) => String(message.id)))
    messages.value = [
      ...olderMessages.filter((message) => !existingIds.has(String(message.id))),
      ...messages.value,
    ]
    nextMessagesBefore.value = data?.next_before || null

    await nextTick()
    if (scroller) {
      scroller.scrollTop = scroller.scrollHeight - prevScrollHeight + prevScrollTop
    }
  } catch (error) {
    chatError.value = error instanceof Error ? error.message : 'Older messages could not be loaded.'
  } finally {
    isLoadingOlderMessages.value = false
  }
}

const loadNewerMessages = async () => {
  const backendGroupId = getBackendGroupId()
  if (!backendGroupId || !nextMessagesAfter.value) return

  try {
    const data = await requestJson(
      buildChatMessageCollectionUrl(
        backendGroupId,
        `?limit=100&after=${encodeURIComponent(nextMessagesAfter.value)}`,
      ),
    )
    const newerMessages = extractCollectionItems(data).map(normalizeMessage).reverse()
    if (newerMessages.length) {
      const existingIds = new Set(messages.value.map((message) => String(message.id)))
      messages.value = [
        ...messages.value,
        ...newerMessages.filter((message) => !existingIds.has(String(message.id))),
      ]
      await scrollMessagesToBottom()
      await markMessagesAsRead(
        newerMessages.filter((message) => !message.isOwn).map((message) => message.id),
      )
    }
    nextMessagesAfter.value = data?.next_after || nextMessagesAfter.value
  } catch (error) {
    console.error('Failed to backfill newer chat messages:', error)
  }
}

const toggleMessageSearch = async () => {
  const next = !showMessageSearch.value
  closeAllComposerPanels({ except: next ? 'search' : null })
  showMessageSearch.value = next
  if (showMessageSearch.value) {
    await nextTick()
    messageSearchInputRef.value?.focus()
  }
}

const clearMessageSearch = () => {
  messageSearchQuery.value = ''
  messageSearchResults.value = []
  messageSearchNextBefore.value = null
  messageSearchError.value = ''
  hasSearchedMessages.value = false
  messageSearchFilters.value = { type: '', from: '', to: '' }
}

const mergeSearchResults = (current, incoming) => {
  const seen = new Set(current.map((message) => String(message.id)))
  return [...current, ...incoming.filter((message) => !seen.has(String(message.id)))]
}

const hasActiveSearchFilters = () => {
  const f = messageSearchFilters.value
  return Boolean(f.type || f.from || f.to)
}

const searchMessages = async (reset = true) => {
  const backendGroupId = getBackendGroupId()
  const query = messageSearchQuery.value.trim()

  if (!backendGroupId) {
    messageSearchError.value = 'Live discussion needs a backend numeric group id.'
    return
  }
  // Allow filter-only searches (e.g. "all GIFs from last week"). Bail only if
  // there is neither a query nor any active filter.
  if (!query && !hasActiveSearchFilters()) {
    clearMessageSearch()
    return
  }
  if (!reset && !messageSearchNextBefore.value) return

  if (reset) {
    isSearchingMessages.value = true
    messageSearchResults.value = []
    messageSearchNextBefore.value = null
  } else {
    isLoadingMoreSearchResults.value = true
  }
  messageSearchError.value = ''

  const params = new URLSearchParams({ limit: '20' })
  if (query) params.set('q', query)
  const filters = messageSearchFilters.value
  if (filters.type) params.set('type', filters.type)
  if (filters.from) params.set('from', filters.from)
  if (filters.to) params.set('to', filters.to)
  if (!reset && messageSearchNextBefore.value) {
    params.set('before', String(messageSearchNextBefore.value))
  }

  try {
    const data = await requestJson(buildChatMessageSearchUrl(backendGroupId, `?${params}`))
    const results = extractCollectionItems(data).map(normalizeMessage)
    messageSearchResults.value = reset
      ? results
      : mergeSearchResults(messageSearchResults.value, results)
    messageSearchNextBefore.value = data?.next_before || null
    hasSearchedMessages.value = true
  } catch (error) {
    messageSearchError.value =
      error instanceof Error ? error.message : 'Messages could not be searched.'
  } finally {
    isSearchingMessages.value = false
    isLoadingMoreSearchResults.value = false
  }
}

const loadMoreSearchResults = async () => {
  await searchMessages(false)
}

const insertMessageFromSearch = (message) => {
  const normalized = normalizeMessage(message)
  const existingIndex = messages.value.findIndex((item) => String(item.id) === String(normalized.id))
  if (existingIndex !== -1) {
    messages.value.splice(existingIndex, 1, {
      ...messages.value[existingIndex],
      ...normalized,
    })
    return normalized
  }

  const normalizedId = Number(normalized.id)
  if (Number.isFinite(normalizedId)) {
    const insertIndex = messages.value.findIndex((item) => Number(item.id) > normalizedId)
    if (insertIndex === -1) messages.value.push(normalized)
    else messages.value.splice(insertIndex, 0, normalized)
    return normalized
  }

  const normalizedTime = new Date(normalized.date).getTime()
  const insertIndex = messages.value.findIndex(
    (item) => new Date(item.date).getTime() > normalizedTime,
  )
  if (insertIndex === -1) messages.value.push(normalized)
  else messages.value.splice(insertIndex, 0, normalized)
  return normalized
}

const scrollToMessageId = async (messageId) => {
  await nextTick()
  const target = Array.from(msgList.value?.querySelectorAll('[data-message-id]') || []).find(
    (element) => element.dataset.messageId === String(messageId),
  )
  if (!target) return false

  target.scrollIntoView({ block: 'center', behavior: 'smooth' })
  highlightedSearchMessageId.value = messageId
  clearTimeout(searchHighlightTimer)
  searchHighlightTimer = setTimeout(() => {
    highlightedSearchMessageId.value = null
  }, 2200)
  return true
}

const scrollToMissedMessages = async () => {
  if (!missedMessageAnchorId.value) return false
  return scrollToMessageId(missedMessageAnchorId.value)
}

const jumpToMissedMessagesFromButton = async () => {
  const didScroll = await scrollToMissedMessages()
  if (didScroll) {
    isMissedMessageJumpDismissed.value = true
  }
}

const openSearchResult = async (result) => {
  const backendGroupId = getBackendGroupId()
  if (!backendGroupId || !result?.id) return

  messageSearchError.value = ''
  showMessageSearch.value = false

  if (!messages.value.some((message) => String(message.id) === String(result.id))) {
    try {
      const detail = await requestJson(buildChatMessageUrl(backendGroupId, result.id))
      insertMessageFromSearch(detail)
    } catch {
      insertMessageFromSearch(result)
    }
  }

  const didScroll = await scrollToMessageId(result.id)
  if (!didScroll) {
    messageSearchError.value = 'Message was found, but could not be shown in the current view.'
  }
}

const sendMessagePayload = async ({
  body,
  requestOptions,
  pendingId,
  keepLocalOnFailure = false,
}) => {
  const backendGroupId = getBackendGroupId()
  if (!backendGroupId) {
    chatError.value = 'Live discussion needs a backend numeric group id.'
    throw new Error(chatError.value)
  }

  chatError.value = ''

  try {
    const savedMessage = await requestJson(
      body === 'upload'
        ? buildChatUploadUrl(backendGroupId)
        : buildChatMessageCollectionUrl(backendGroupId),
      requestOptions,
    )

    if (!savedMessage) {
      return null
    }

    if (pendingId) {
      const index = messages.value.findIndex((message) => message.id === pendingId)
      const normalizedSavedMessage = normalizeMessage(savedMessage)
      const existingIndex = messages.value.findIndex(
        (message) => String(message.id) === String(normalizedSavedMessage.id),
      )

      if (index !== -1 && existingIndex !== -1 && index !== existingIndex) {
        messages.value.splice(index, 1)
        messages.value.splice(existingIndex > index ? existingIndex - 1 : existingIndex, 1, {
          ...messages.value[existingIndex > index ? existingIndex - 1 : existingIndex],
          ...normalizedSavedMessage,
        })
      } else if (index !== -1) {
        messages.value.splice(index, 1, normalizedSavedMessage)
      } else if (existingIndex !== -1) {
        messages.value.splice(existingIndex, 1, {
          ...messages.value[existingIndex],
          ...normalizedSavedMessage,
        })
      } else {
        upsertMessage(savedMessage)
      }
    } else if (savedMessage) {
      upsertMessage(savedMessage)
    }
    return savedMessage
  } catch (error) {
    chatError.value = error instanceof Error ? error.message : 'Message could not be sent.'
    if (pendingId && !keepLocalOnFailure) {
      messages.value = messages.value.filter((message) => message.id !== pendingId)
    }
    throw error
  } finally {
    await scrollMessagesToBottom()
  }
}

const sendMessage = async () => {
  const text = newMessage.value.trim()
  if (!canSendChatMessage.value || isSendingMessage.value) return
  if (!getBackendGroupId()) {
    chatError.value = 'Live discussion needs a backend numeric group id.'
    return
  }

  const now = new Date()
  const pendingId = `pending-${Date.now()}`
  const selectedResources = selectedChatResources.value.map((resource) => ({ ...resource }))
  const draftMessage = {
    id: pendingId,
    author: 'You',
    text,
    time: now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    date: now.toISOString(),
    isOwn: true,
    message_type: 'text',
    resources: selectedResources.map((resource) => ({
      resource_id: resource.id,
      resource_name: resource.resource_name,
    })),
    reply_to: replyTarget.value
      ? {
          id: replyTarget.value.id,
          text: replyTarget.value.text,
          user_id: replyTarget.value.senderId,
          deleted: false,
        }
      : null,
  }

  messages.value.push(normalizeMessage(draftMessage))
  const currentReplyTarget = replyTarget.value
  newMessage.value = ''
  clearReplyTarget()
  clearSelectedResources()
  showResourcePanel.value = false
  stopTypingIndicator()
  await scrollMessagesToBottom()

  // Visible ``@Name`` tokens in the textarea -> backend ``<@id>`` form.
  // We snapshot the resolved string here so the optimistic bubble keeps the
  // friendly display while the wire payload carries the canonical token.
  const wireText = resolveComposerMentions(text)
  pendingComposerMentions.value.clear()

  isSendingMessage.value = true
  try {
    await sendMessagePayload({
      body: 'message',
      pendingId,
      requestOptions: {
        method: 'POST',
        body: JSON.stringify({
          message_text: wireText,
          ...(selectedResources.length
            ? { resources: selectedResources.map((resource) => ({ resource_id: resource.id })) }
            : {}),
          ...(currentReplyTarget?.id ? { reply_to_id: currentReplyTarget.id } : {}),
        }),
      },
    })
  } catch {
    newMessage.value = text
    replyTarget.value = currentReplyTarget
    selectedChatResources.value = selectedResources
  } finally {
    isSendingMessage.value = false
    composer.value?.focus()
  }
}

const sendGifMessage = async (gif) => {
  if (!supportsGifs) {
    gifError.value = 'GIF search is not available in the backend yet.'
    return
  }
  if (!gif?.url || isSendingMessage.value) return
  const backendGroupId = getBackendGroupId()
  if (!backendGroupId) {
    chatError.value = 'Live discussion needs a backend numeric group id.'
    return
  }
  const caption = newMessage.value.trim()
  const wireCaption = resolveComposerMentions(caption)
  isSendingMessage.value = true
  chatError.value = ''
  gifError.value = ''
  try {
    await requestJson(buildChatSendGifUrl(backendGroupId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: 'tenor',
        provider_id: String(gif.id ?? ''),
        gif_url: gif.url,
        preview_url: gif.previewUrl || '',
        title: gif.title || '',
        ...(wireCaption ? { message_text: wireCaption } : {}),
      }),
    })
    pendingComposerMentions.value.clear()
    newMessage.value = ''
    showGifPanel.value = false
    // The WS ``message.created`` broadcast delivers the rendered bubble into
    // the list — no local upsert needed.
  } catch (error) {
    gifError.value = error instanceof Error ? error.message : 'GIF could not be sent.'
  } finally {
    isSendingMessage.value = false
    composer.value?.focus()
  }
}

const openFilePicker = () => {
  if (!supportsAttachments) {
    chatError.value = 'File upload is not available in the backend yet.'
    return
  }
  fileInputRef.value?.click()
}

const closeReceiptPopover = () => {
  openReceiptPopoverId.value = null
  receiptError.value = ''
  receiptPopoverAnchor.value = null
}

const getOtherRecipientCount = () => {
  // Recipients = active group members minus the sender (current user).
  const memberships = Array.isArray(groupMemberships.value) ? groupMemberships.value : []
  const me = Number(auth.user?.id || 0)
  const total = memberships.filter((m) => {
    const uid = Number(m?.user_id ?? m?.user ?? m?.userId ?? 0)
    return uid && uid !== me
  }).length
  return total
}

const getReceiptState = (message) => {
  // Tick semantics requested by the team:
  //   single grey  — delivered (no one has read yet)
  //   double grey  — SOME but not ALL recipients have read
  //   double blue  — ALL recipients have read
  if (!message) return 'delivered'
  const reads = Number(message.readCount) || 0
  const recipients = getOtherRecipientCount()
  if (recipients > 0 && reads >= recipients) return 'read'   // all-seen
  if (reads > 0) return 'partial'                              // some-seen
  return 'delivered'                                           // none-read yet
}

const getReceiptAriaLabel = (message) => {
  const state = getReceiptState(message)
  const r = Number(message.readCount) || 0
  const recipients = getOtherRecipientCount()
  if (state === 'read') return `Read by everyone (${r})`
  if (state === 'partial') return `Read by ${r} of ${recipients || r}`
  const d = Number(message.deliveredCount) || 0
  return d > 0 ? `Delivered to ${d}` : 'Delivered'
}

const formatRelativeTime = (iso) => {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  if (!Number.isFinite(then)) return ''
  const diffMs = Date.now() - then
  if (diffMs < 60_000) return 'just now'
  const mins = Math.round(diffMs / 60_000)
  if (mins < 60) return `${mins}m ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}

const openMessageReceipts = async (messageId, event) => {
  if (!messageId) return
  if (openReceiptPopoverId.value === messageId) {
    closeReceiptPopover()
    return
  }
  openReceiptPopoverId.value = messageId
  receiptError.value = ''
  // Capture the trigger's bounding rect so the teleported popover knows
  // where to anchor. Flip above/below depending on available viewport space.
  const triggerEl = event?.currentTarget instanceof Element
    ? event.currentTarget
    : null
  if (triggerEl) {
    const rect = triggerEl.getBoundingClientRect()
    const viewportH = window.innerHeight || document.documentElement.clientHeight
    const spaceAbove = rect.top
    const spaceBelow = viewportH - rect.bottom
    const placeAbove = spaceAbove > 220 || spaceAbove > spaceBelow
    receiptPopoverAnchor.value = {
      top: placeAbove ? rect.top : rect.bottom,
      left: rect.left,
      right: window.innerWidth - rect.right,
      placement: placeAbove ? 'top' : 'bottom',
    }
  } else {
    receiptPopoverAnchor.value = null
  }
  if (messageReceiptCache.value.has(messageId)) return
  const backendGroupId = getBackendGroupId()
  if (!backendGroupId) {
    receiptError.value = 'Live discussion needs a backend numeric group id.'
    return
  }
  isLoadingReceipts.value = true
  try {
    const data = await requestJson(buildChatMessageStatusUrl(backendGroupId, messageId))
    messageReceiptCache.value.set(messageId, {
      readBy: Array.isArray(data?.read_by) ? data.read_by : [],
      deliveredBy: Array.isArray(data?.delivered_by) ? data.delivered_by : [],
    })
  } catch (error) {
    receiptError.value = error instanceof Error
      ? error.message
      : 'Read receipts are unavailable right now.'
  } finally {
    isLoadingReceipts.value = false
  }
}

const receiptPopoverStyle = computed(() => {
  const a = receiptPopoverAnchor.value
  if (!a) return null
  const offset = 6
  return a.placement === 'top'
    ? { position: 'fixed', top: `${a.top - offset}px`, right: `${a.right}px`, transform: 'translateY(-100%)' }
    : { position: 'fixed', top: `${a.top + offset}px`, right: `${a.right}px` }
})

const uploadAttachment = async (event) => {
  if (!supportsAttachments) {
    chatError.value = 'File upload is not available in the backend yet.'
    return
  }
  const input = event?.target
  const file = input?.files?.[0]
  if (!file || isUploadingFile.value) return
  if (selectedChatResources.value.length) {
    chatError.value = 'Send selected resources as a chat message before uploading a local file.'
    if (input) input.value = ''
    return
  }
  const caption = newMessage.value.trim()
  const wireCaption = resolveComposerMentions(caption)
  const formData = new FormData()
  formData.append('uploaded_file', file)
  if (wireCaption) formData.append('message_text', wireCaption)
  // Upload endpoint now accepts reply_to_id (mirror of the JSON create path)
  // so replies can carry attachments.
  if (replyTarget.value?.id) {
    formData.append('reply_to_id', String(replyTarget.value.id))
  }

  isUploadingFile.value = true
  chatError.value = ''

  try {
    const savedMessage = await sendMessagePayload({
      body: 'upload',
      requestOptions: {
        method: 'POST',
        body: formData,
      },
    })
    if (savedMessage) {
      pendingComposerMentions.value.clear()
      newMessage.value = ''
      clearReplyTarget()
    }
  } catch (error) {
    chatError.value = error instanceof Error ? error.message : `Upload for ${file.name} failed.`
  } finally {
    isUploadingFile.value = false
    if (input) input.value = ''
    composer.value?.focus()
  }
}

const fetchGifResults = async (mode = 'trending', { append = false } = {}) => {
  if (!supportsGifs) {
    gifResults.value = []
    gifError.value = 'GIF search is not available in the backend yet.'
    return
  }
  gifPanelMode.value = mode
  if (append) {
    if (isLoadingMoreGifs.value || !gifNextPos.value) return
    isLoadingMoreGifs.value = true
  } else {
    isLoadingGifs.value = true
  }
  gifError.value = ''

  try {
    const url = mode === 'search'
      ? buildGifSearchUrl(gifQuery.value.trim(), append ? gifNextPos.value : '')
      : buildGifTrendingUrl(append ? gifNextPos.value : '')
    const data = await requestJson(url, { method: 'GET' })
    const items = normalizeGifResults({ results: data?.items ?? data?.results ?? [] })
    gifResults.value = append ? [...gifResults.value, ...items] : items
    gifNextPos.value = data?.next_pos ?? data?.next ?? null
  } catch {
    if (!append) gifResults.value = []
    gifError.value = 'Live GIF search is unavailable right now.'
  } finally {
    if (append) isLoadingMoreGifs.value = false
    else isLoadingGifs.value = false
  }
}

const loadMoreGifs = async () => {
  if (!gifNextPos.value || isLoadingMoreGifs.value) return
  await fetchGifResults(gifPanelMode.value, { append: true })
}

const handleGifGridScroll = (event) => {
  const target = event?.currentTarget
  if (!target || !gifNextPos.value || isLoadingMoreGifs.value) return
  const remaining = target.scrollHeight - (target.scrollTop + target.clientHeight)
  if (remaining < 120) {
    void loadMoreGifs()
  }
}

// Generic helper: only one composer-adjacent panel may be open at a time.
// Closes the other panels + the message-search / mention-inbox / kebab /
// reaction picker so they don't all stack on top of each other.
const closeAllComposerPanels = ({ except } = {}) => {
  if (except !== 'gif') showGifPanel.value = false
  if (except !== 'resource') showResourcePanel.value = false
  if (except !== 'search') showMessageSearch.value = false
  if (except !== 'mentions') showMentionInbox.value = false
  if (except !== 'kebab') openMessageKebabId.value = null
  if (except !== 'picker') activeReactionPickerMessageId.value = null
}

const toggleGifPanel = async () => {
  if (!supportsGifs) {
    gifError.value = 'GIF search is not available in the backend yet.'
    return
  }
  const next = !showGifPanel.value
  closeAllComposerPanels({ except: next ? 'gif' : null })
  showGifPanel.value = next
  if (showGifPanel.value) {
    gifNextPos.value = null
    await fetchGifResults('trending')
  }
}

const searchGifs = async () => {
  gifNextPos.value = null
  if (!gifQuery.value.trim()) {
    await fetchGifResults('trending')
    return
  }
  await fetchGifResults('search')
}

const scheduleGifSearch = () => {
  if (gifSearchDebounceTimer) clearTimeout(gifSearchDebounceTimer)
  gifSearchDebounceTimer = setTimeout(() => {
    void searchGifs()
  }, GIF_SEARCH_DEBOUNCE_MS)
}

const loadChatResources = async () => {
  isLoadingResources.value = true
  resourcePickerError.value = ''

  try {
    const data = await fetchResources({
      search: resourceQuery.value.trim(),
      page_size: 20,
      order: 'newest',
    })
    chatResourceOptions.value = extractCollectionItems(data)
      .map(normalizeChatResource)
      .filter((resource) => resource.id)
  } catch (error) {
    chatResourceOptions.value = []
    resourcePickerError.value =
      error instanceof Error ? error.message : 'Resources could not be loaded.'
  } finally {
    isLoadingResources.value = false
  }
}

const toggleResourcePanel = async () => {
  const next = !showResourcePanel.value
  closeAllComposerPanels({ except: next ? 'resource' : null })
  showResourcePanel.value = next
  if (showResourcePanel.value && !chatResourceOptions.value.length) {
    await loadChatResources()
  }
}

const loadMentions = async (unreadOnly = false) => {
  isLoadingMentions.value = true
  mentionInboxError.value = ''

  const params = new URLSearchParams({ limit: '20' })
  if (unreadOnly) params.set('unread', 'true')

  try {
    const data = await requestJson(buildMentionInboxUrl(`?${params.toString()}`))
    mentionItems.value = extractCollectionItems(data)
    mentionNextBefore.value = data?.next_before || null
    mentionUnreadCount.value = Number(data?.unread_count || 0)
  } catch (error) {
    mentionInboxError.value = error instanceof Error ? error.message : 'Mentions could not be loaded.'
  } finally {
    isLoadingMentions.value = false
  }
}

const toggleMentionInbox = async () => {
  showMentionInbox.value = !showMentionInbox.value
  if (showMentionInbox.value) {
    await loadMentions()
  }
}

const markMentionRead = async (mentionId) => {
  if (!mentionId) return null
  const updated = await requestJson(buildMentionReadUrl(mentionId), {
    method: 'POST',
  })
  mentionItems.value = mentionItems.value.map((mention) =>
    Number(mention.id) === Number(mentionId) ? updated : mention,
  )
  mentionUnreadCount.value = Math.max(0, mentionUnreadCount.value - 1)
  return updated
}

const markAllMentionsRead = async () => {
  if (isUpdatingMentions.value) return
  isUpdatingMentions.value = true
  mentionInboxError.value = ''

  try {
    const data = await requestJson(buildMentionMarkAllReadUrl(), {
      method: 'POST',
    })
    mentionUnreadCount.value = Number(data?.unread_count || 0)
    mentionItems.value = mentionItems.value.map((mention) => ({
      ...mention,
      read_at: mention.read_at || new Date().toISOString(),
    }))
  } catch (error) {
    mentionInboxError.value =
      error instanceof Error ? error.message : 'Mentions could not be marked read.'
  } finally {
    isUpdatingMentions.value = false
  }
}

const openMention = async (mention) => {
  if (!mention?.id) return
  mentionInboxError.value = ''

  try {
    const numericMentionId = Number(mention.id)
    if (!mention.read_at && Number.isFinite(numericMentionId)) {
      await markMentionRead(mention.id)
    }
    showMentionInbox.value = false
    if (mention.group_id && String(mention.group_id) !== String(getBackendGroupId())) {
      await router.push(`/groups/${mention.group_id}`)
      return
    }
    await scrollMessagesToBottomAfterRender()
  } catch (error) {
    mentionInboxError.value = error instanceof Error ? error.message : 'Mention could not be opened.'
  }
}

const reactToMessage = async (messageId, emoji) => {
  if (!supportsMessageReactions) {
    chatError.value = 'Message reactions are not available in the backend yet.'
    return
  }

  const backendGroupId = getBackendGroupId()
  if (!backendGroupId) return

  try {
    const data = await requestJson(buildChatReactionUrl(backendGroupId, messageId), {
      method: 'POST',
      body: JSON.stringify({
        emoji,
      }),
    })
    applyMessageUpdate(messageId, (message) => ({
      ...message,
      reactions: normalizeReactionMap(data?.reactions),
    }))
    activeReactionPickerMessageId.value = null
  } catch (error) {
    chatError.value = error instanceof Error ? error.message : 'Reaction could not be updated.'
  }
}

let loadSequence = 0

const reloadGroupDetail = async () => {
  const sequence = ++loadSequence

  isLoadingGroupDetail.value = true
  disconnectChatSocket()
  hasConnectedChatSocket = false
  tasks.value = []
  messages.value = []
  taskError.value = ''
  chatError.value = ''
  chatNotice.value = ''
  activeReactionPickerMessageId.value = null
  showGroupMembersDialog.value = false
  showMessageSearch.value = false
  clearMessageSearch()
  highlightedSearchMessageId.value = null
  clearMissedMessageAnchor()

  try {
    // First wave: everything that only needs routeGroupId (getBackendGroupId
    // already falls back to the route param). Drops 3 sequential RTTs to 1.
    // WS doesn't depend on any HTTP fetch — connect immediately so the
    // socket is ready by the time messages render.
    connectChatSocket()

    // Critical path: only the header data the user actually waits on.
    // Tasks + chat have their own loading states and run in the
    // background.
    await Promise.all([loadGroup(), loadGroupMembers()])
    if (sequence !== loadSequence) return
    isLoadingGroupDetail.value = false

    // Fire-and-forget: chat and tasks resolve in parallel; their own
    // panel skeletons handle the wait. Sequence check on completion
    // guards against navigating between groups mid-flight.
    void loadMessages().then(() => {
      if (sequence === loadSequence) void scrollMessagesToBottomAfterRender()
    })
    void loadTasks()
  } catch (error) {
    console.error('reloadGroupDetail failed:', error)
  } finally {
    // Always clear the page skeleton on the latest reload's completion.
    // If a newer reload is in flight, it will set true again at its start.
    if (sequence === loadSequence) {
      isLoadingGroupDetail.value = false
    } else if (loadSequence > 0) {
      // Stale reload finishing while a newer one is mid-flight — leave the
      // newer one to manage the flag (it already set it true at its start).
    }
  }
}

watch(routeGroupId, async () => {
  await reloadGroupDetail()
  await loadMentions()
})

watch(
  () => auth.user?.id,
  async (userId, previousUserId) => {
    if (userId && userId !== previousUserId) {
      await loadGroupOptions()
    }
  },
)

const onDocumentClickForStatusMenu = (event) => {
  if (openStatusMenuTaskId.value === null) return
  const target = event.target
  if (!(target instanceof Element)) return
  if (target.closest('.task-state, .task-state-menu')) return
  closeStatusMenu()
}
const onDocumentKeydownForStatusMenu = (event) => {
  if (openStatusMenuTaskId.value !== null && event.key === 'Escape') {
    closeStatusMenu()
  }
}

const onDocumentClickForReceiptPopover = (event) => {
  if (openReceiptPopoverId.value === null) return
  const target = event.target
  if (!(target instanceof Element)) return
  if (target.closest('.message-receipt, .message-receipt-popover')) return
  closeReceiptPopover()
}
const onDocumentKeydownForReceiptPopover = (event) => {
  if (openReceiptPopoverId.value !== null && event.key === 'Escape') {
    closeReceiptPopover()
  }
}

const onDocumentClickForReactionPicker = (event) => {
  if (activeReactionPickerMessageId.value === null) return
  const target = event.target
  if (!(target instanceof Element)) return
  if (target.closest(
    '.reaction-pick-group, .reaction-picker, .reaction-picker-toggle, .inline-action-btn'
  )) return
  activeReactionPickerMessageId.value = null
}
const onDocumentKeydownForReactionPicker = (event) => {
  if (activeReactionPickerMessageId.value !== null && event.key === 'Escape') {
    activeReactionPickerMessageId.value = null
  }
}

const onDocumentClickForMessageKebab = (event) => {
  if (openMessageKebabId.value === null) return
  const target = event.target
  if (!(target instanceof Element)) return
  if (target.closest('.inline-kebab-wrap, .inline-kebab-menu')) return
  openMessageKebabId.value = null
}
const onDocumentKeydownForMessageKebab = (event) => {
  if (openMessageKebabId.value !== null && event.key === 'Escape') {
    openMessageKebabId.value = null
  }
}

const onDocumentClickForResourceChoice = (event) => {
  if (openResourceChoiceKey.value === null && openAttachmentChoiceKey.value === null) return
  const target = event.target
  if (!(target instanceof Element)) return
  if (target.closest('.resource-chip-wrap')) return
  closeResourceChoice()
  closeAttachmentChoice()
}
const onDocumentKeydownForResourceChoice = (event) => {
  if (event.key !== 'Escape') return
  if (openResourceChoiceKey.value !== null) closeResourceChoice()
  if (openAttachmentChoiceKey.value !== null) closeAttachmentChoice()
}

onMounted(async () => {
  manageWindowTimer = window.setInterval(() => {
    manageWindowNow.value = Date.now()
  }, 30000)
  document.addEventListener('mousedown', onDocumentClickForStatusMenu)
  document.addEventListener('keydown', onDocumentKeydownForStatusMenu)
  document.addEventListener('mousedown', onDocumentClickForReceiptPopover)
  document.addEventListener('keydown', onDocumentKeydownForReceiptPopover)
  document.addEventListener('mousedown', onDocumentClickForReactionPicker)
  document.addEventListener('keydown', onDocumentKeydownForReactionPicker)
  document.addEventListener('mousedown', onDocumentClickForMessageKebab)
  document.addEventListener('keydown', onDocumentKeydownForMessageKebab)
  document.addEventListener('mousedown', onDocumentClickForResourceChoice)
  document.addEventListener('keydown', onDocumentKeydownForResourceChoice)

  await ensureAuthUser()

  if (routeGroupId.value) {
    // App.vue's sidebar already pulls /groups/ + /group-members/ for the
    // switcher rail — re-fetching the same data here is pure waste.
    await reloadGroupDetail()
  } else {
    // No route id: only path that needs the group list, to pick a
    // fallback to redirect into.
    await loadGroupOptions()
    if (availableGroups.value.length) {
      await loadMentions()
      await router.replace(`/groups/${availableGroups.value[0].id}`)
      return
    }
    await reloadGroupDetail()
  }
})

onBeforeUnmount(() => {
  disconnectChatSocket()
  clearTimeout(typingStopTimer)
  clearTimeout(taskFilterReloadTimer)
  clearTimeout(searchHighlightTimer)
  clearTimeout(gifSearchDebounceTimer)
  typingUserTimers.forEach((timer) => clearTimeout(timer))
  typingUserTimers.clear()
  if (manageWindowTimer) {
    clearInterval(manageWindowTimer)
    manageWindowTimer = null
  }
  document.removeEventListener('mousedown', onDocumentClickForStatusMenu)
  document.removeEventListener('keydown', onDocumentKeydownForStatusMenu)
  document.removeEventListener('mousedown', onDocumentClickForReceiptPopover)
  document.removeEventListener('keydown', onDocumentKeydownForReceiptPopover)
  document.removeEventListener('mousedown', onDocumentClickForReactionPicker)
  document.removeEventListener('keydown', onDocumentKeydownForReactionPicker)
  document.removeEventListener('mousedown', onDocumentClickForMessageKebab)
  document.removeEventListener('keydown', onDocumentKeydownForMessageKebab)
  document.removeEventListener('mousedown', onDocumentClickForResourceChoice)
  document.removeEventListener('keydown', onDocumentKeydownForResourceChoice)
})
</script>

<style scoped>
/* Header */
.gd-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0;
}
.gd-head-left {
  display: flex;
  align-items: center;
  gap: 0.9rem;
}
.gd-title {
  margin: 0;
  color: var(--charcoal);
}
.gd-subtitle {
  color: #6c757d;
  margin-top: 0.1rem;
}
.gd-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.25rem;
  color: #6c757d;
  font-size: 0.78rem;
  font-weight: 600;
}
.gd-meta-row span {
  padding: 0.12rem 0.45rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.65);
}
.gd-head-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.35rem;
  min-width: 180px;
}
.group-members-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  min-height: 34px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 0.42rem 0.68rem;
  background: var(--white);
  color: var(--air-force-blue);
  font-size: 0.84rem;
  font-weight: 700;
  cursor: pointer;
}
.group-members-btn:hover:not(:disabled) {
  border-color: var(--air-force-blue);
  background: #f1f5f7;
}
.group-members-btn:disabled {
  cursor: not-allowed;
  color: #98a2ad;
  background: #f8f9fa;
}
.group-members-btn span {
  min-width: 1.4rem;
  border-radius: 999px;
  padding: 0.05rem 0.38rem;
  background: #eef7f9;
  color: var(--air-force-blue);
  text-align: center;
}
.group-members-dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(21, 32, 43, 0.42);
}

.group-members-dialog {
  width: min(460px, 100%);
  max-height: min(620px, 82vh);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: var(--white);
  box-shadow: 0 18px 48px rgba(24, 38, 50, 0.2);
}

.group-members-dialog-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem;
  border-bottom: 1px solid var(--border-light);
}

.group-members-dialog-header h3 {
  margin: 0;
  color: var(--charcoal);
  font-size: 1.05rem;
}

.group-members-dialog-header p {
  margin: 0.16rem 0 0;
  color: #6c757d;
  font-size: 0.84rem;
  font-weight: 600;
}

.group-members-dialog-close {
  width: 2rem;
  height: 2rem;
  border: 1px solid var(--border-light);
  border-radius: 50%;
  background: var(--white);
  color: #5b6770;
  cursor: pointer;
}

.group-members-dialog-close:hover {
  border-color: var(--air-force-blue);
  color: var(--air-force-blue);
  background: #f1f5f7;
}

.group-members-list {
  overflow-y: auto;
  padding: 0.45rem;
}

.group-member-row {
  display: flex;
  align-items: center;
  gap: 0.78rem;
  padding: 0.7rem;
  border-radius: 8px;
}

.group-member-row + .group-member-row {
  border-top: 1px solid #eef1f3;
}

.group-member-avatar {
  width: 2.25rem;
  height: 2.25rem;
  flex: 0 0 2.25rem;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--air-force-blue);
  color: var(--white);
  font-size: 0.82rem;
  font-weight: 800;
}

.group-member-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.12rem;
}

.group-member-copy strong {
  color: var(--charcoal);
  font-size: 0.92rem;
}

.group-member-copy span,
.group-members-empty {
  color: #6c757d;
  font-size: 0.82rem;
  font-weight: 600;
}

.group-members-empty {
  padding: 1rem;
  text-align: center;
}

/* Mobile tabs */
.mobile-tabs {
  display: none;
  gap: 0.75rem;
  margin-bottom: 1rem;
  border-bottom: 1px solid var(--border-light);
  padding-bottom: 0.5rem;
}
.tab-btn {
  background: transparent;
  border: none;
  padding: 0.5rem 0.25rem;
  color: var(--charcoal);
  font-weight: 500;
  border-bottom: 3px solid transparent;
  cursor: pointer;
}
.tab-btn.active {
  color: var(--dark-green);
  border-bottom-color: var(--dark-green);
}

/* Split layout */
.split {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: 1.5rem;
  align-items: stretch;
  max-height: 70vh;
  height: 70vh;
}

/* Tasks pane */
.pane--tasks {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 320px;
  position: relative;
  container-type: inline-size;
}

/* Discussion pane */
.pane--discussion {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 320px;
}

/* Card layout */
.card {
  height: 100%;
  min-height: 320px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.card-content {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}
.tasks-content {
  position: relative;
  padding-right: 2px;
  overflow-x: hidden;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.tasks-content.has-bulk-actions {
  padding-bottom: 5rem;
}

.task-header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.task-mode-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  height: 32px;
  padding: 0 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background: #fff;
  color: #50616c;
  font: inherit;
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 120ms ease, border-color 120ms ease, color 120ms ease;
}
.task-mode-toggle:hover {
  background: #f4f7f9;
  border-color: var(--air-force-blue);
  color: var(--charcoal);
}
.task-mode-toggle.is-active {
  background: var(--air-force-blue, #39687b);
  border-color: var(--air-force-blue, #39687b);
  color: #fff;
}

/* ---------- Toolbar (search + filter popover + sort) ---------- */

.task-toolbar {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.85rem;
  flex-wrap: wrap;
  position: sticky;
  top: 0;
  z-index: 5;
  padding: 0.5rem 0;
  background: var(--surface-elevated, #fff);
  box-shadow: 0 1px 0 var(--border-light, rgba(0, 0, 0, 0.08));
}

.task-search {
  position: relative;
  flex: 1 1 220px;
  min-width: 180px;
}
.task-search-icon {
  position: absolute;
  left: 0.7rem;
  top: 50%;
  transform: translateY(-50%);
  color: #94a3a8;
  font-size: 0.82rem;
  pointer-events: none;
}
.task-search-input {
  width: 100%;
  height: 36px;
  padding: 0 0.7rem 0 2rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: #fff;
  color: var(--charcoal);
  font: inherit;
}
.task-search-input:focus {
  outline: none;
  border-color: var(--air-force-blue);
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.12);
}

.task-toolbar-controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.task-toolbar-btn,
.task-toolbar-sort select {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  height: 36px;
  padding: 0 0.85rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: #fff;
  color: #50616c;
  font: inherit;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 120ms ease, background-color 120ms ease, color 120ms ease;
}
.task-toolbar-btn:hover,
.task-toolbar-sort select:hover {
  border-color: var(--air-force-blue);
  background: #f4f7f9;
  color: var(--charcoal);
}
.task-toolbar-btn.has-active {
  border-color: var(--air-force-blue);
  background: rgba(57, 104, 123, 0.08);
  color: var(--charcoal);
}

.task-filter-popover { position: relative; }
.task-filter-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 0.35rem;
  border-radius: 999px;
  background: var(--air-force-blue, #39687b);
  color: #fff;
  font-size: 0.7rem;
  font-weight: 700;
}
.task-filter-panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: 320px;
  max-height: calc(100vh - 220px);
  overflow-y: auto;
  padding: 0.85rem;
  background: #fff;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.12);
  z-index: 6;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.task-filter-row-pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
}
.task-filter-row input[type='datetime-local'] {
  width: 100%;
  height: 34px;
  padding: 0 0.55rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: #fff;
  color: var(--charcoal);
  font: inherit;
}
.task-filter-row {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.78rem;
  font-weight: 700;
  color: #5b6770;
}
.task-filter-row select {
  width: 100%;
  height: 34px;
  padding: 0 0.55rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: #fff;
  color: var(--charcoal);
  font: inherit;
}
.task-filter-row--checkbox {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--charcoal);
}
.task-filter-panel-footer {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  margin-top: 0.2rem;
}
.task-filter-clear,
.task-filter-close {
  flex: 1;
  height: 32px;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: #fff;
  color: #50616c;
  font: inherit;
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 120ms ease, color 120ms ease, border-color 120ms ease;
}
.task-filter-clear:hover:not(:disabled),
.task-filter-close:hover {
  border-color: var(--air-force-blue);
  background: #f4f7f9;
  color: var(--charcoal);
}
.task-filter-clear:disabled {
  cursor: not-allowed;
  opacity: 0.45;
  background: #f7f8f9;
  color: #a3adb3;
}

/* ---------- Banners ---------- */

.task-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  font-size: 0.85rem;
  margin-bottom: 0.85rem;
}
.task-banner.is-error {
  background: #fdecec;
  color: #8c1f1f;
  border: 1px solid #f3c2c2;
}

/* ---------- Sections ---------- */

.task-pagination-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.65rem;
  flex-wrap: wrap;
  padding-top: 0.85rem;
  color: #5b6770;
  font-size: 0.84rem;
  font-weight: 700;
}

.task-page-size {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.task-page-size select {
  min-width: 74px;
  padding: 0.45rem 0.55rem;
}

.task-section {
  margin-bottom: 1.4rem;
}
.task-section:last-child { margin-bottom: 0; }

.task-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  margin-bottom: 0.55rem;
  padding: 0 0.1rem;
}

.task-section-title {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--charcoal);
  font-size: 0.74rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.task-section-title i {
  color: var(--air-force-blue);
  font-size: 0.85rem;
}
.task-section-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 20px;
  padding: 0 0.4rem;
  border-radius: 999px;
  background: #eef2f4;
  color: #50616c;
  font-size: 0.7rem;
  letter-spacing: 0;
  text-transform: none;
}

.task-section-progress {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  font-size: 0.74rem;
  color: #6c757d;
}
.task-section-progress-bar {
  width: 88px;
  height: 6px;
  background: #eef2f4;
  border-radius: 999px;
  overflow: hidden;
}
.task-section-progress-fill {
  height: 100%;
  background: var(--dark-green, #4d745e);
  transition: width 200ms ease;
}
.task-section-progress-label { font-weight: 700; }

/* ---------- Task list & item ---------- */

.task-list {
  list-style: none;
  margin: 0;
  padding: 0;
  background: #fff;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  /* overflow stays visible so the status-menu popup can extend below the
     last (or only) task without being clipped. Rounded corners are kept
     by rounding the first/last task-item directly. */
}

.task-item {
  display: flex;
  align-items: flex-start;
  gap: 0.7rem;
  padding: 0.6rem 0.85rem 0.6rem calc(0.85rem + var(--task-depth, 0) * 1.1rem);
  border-bottom: 1px solid var(--task-depth-border, var(--border-light));
  background: var(--task-depth-bg, #fff);
  box-shadow: inset 3px 0 0 var(--task-depth-accent, transparent);
  transition: background-color 120ms ease, box-shadow 120ms ease;
  position: relative;
}
.task-item:first-child { border-top-left-radius: 11px; border-top-right-radius: 11px; }
.task-item:last-child { border-bottom: 0; border-bottom-left-radius: 11px; border-bottom-right-radius: 11px; }
.task-item:hover { background: rgba(0, 0, 0, 0.02); background: color-mix(in srgb, var(--task-depth-bg, #fff) 92%, #000); }
.task-item.is-selected {
  background: rgba(57, 104, 123, 0.08);
  box-shadow: inset 3px 0 0 var(--air-force-blue, #39687b);
}
.task-item.is-complete .task-label {
  color: #94a3a8;
  text-decoration: line-through;
  text-decoration-color: rgba(148, 163, 168, 0.6);
}
.task-item.is-deleted { opacity: 0.55; }

/* Depth-tinted palette: parents have a soft green hue, sub-tasks fade toward white */
.task-depth-0 {
  --task-depth-bg: #eaf6ee;
  --task-depth-border: #d0e6d8;
  --task-depth-accent: #79a988;
}
.task-depth-1 {
  --task-depth-bg: #f3faf5;
  --task-depth-border: #dceee2;
  --task-depth-accent: #9abc9f;
}
.task-depth-2 {
  --task-depth-bg: #fbfdfb;
  --task-depth-border: #edf5ef;
  --task-depth-accent: #c2d8c8;
}
.task-depth-3,
.task-depth-4 {
  --task-depth-bg: #fff;
  --task-depth-border: var(--border-light);
  --task-depth-accent: transparent;
}

/* Collapse/expand chevron for tasks with sub-tasks. Reserved-width spacer
   so rows align consistently whether or not they have children. */
.task-collapse,
.task-collapse-spacer {
  flex-shrink: 0;
  width: 18px;
  height: 22px;
  margin-top: 0.05rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  background: transparent;
}
.task-collapse {
  cursor: pointer;
  color: #6c757d;
  border-radius: 4px;
  transition: background-color 120ms ease, color 120ms ease, transform 160ms ease;
}
.task-collapse i { font-size: 0.78rem; transition: transform 160ms ease; }
.task-collapse:hover { background: rgba(0, 0, 0, 0.05); color: var(--charcoal); }
.task-collapse:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.25);
}
.task-collapse.is-collapsed i { transform: rotate(-90deg); }

/* ---------- State pill (leading control) -- shows status, opens menu to change ---------- */

.task-state-wrap {
  position: relative;
  flex-shrink: 0;
  margin-top: 0.05rem;
}

.task-state {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  height: 26px;
  padding: 0 0.6rem 0 0.55rem;
  border: 1px solid transparent;
  border-radius: 999px;
  background: #eef2f4;
  color: #50616c;
  font: inherit;
  font-size: 0.74rem;
  font-weight: 700;
  cursor: pointer;
  transition: filter 120ms ease, box-shadow 120ms ease, background-color 120ms ease;
  white-space: nowrap;
}
.task-state i { font-size: 0.78rem; }
.task-state-label { line-height: 1; }
.task-state-caret { font-size: 0.7rem; opacity: 0.7; margin-left: -0.1rem; }

.task-state:hover:not(:disabled) { filter: brightness(0.96); }
.task-state:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.25);
}
.task-state.is-open { box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.18); }

.task-state.is-disabled,
.task-state:disabled {
  cursor: default;
  filter: none;
  opacity: 0.85;
}

/* Status color variants -- used by both .task-state and .task-state-menu-item */
.task-state--todo        { background: #eef2f4; color: #50616c; }
.task-state--in_progress { background: #e0eef9; color: #1f5b89; }
.task-state--done        { background: rgba(77, 116, 94, 0.18); color: var(--dark-green, #4d745e); }
.task-state--blocked     { background: #fdecec; color: #8c1f1f; }

/* Status menu */
.task-state-menu {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  min-width: 180px;
  padding: 0.35rem;
  background: #fff;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.14);
  z-index: 6;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.task-state-menu-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.55rem;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #50616c;
  font: inherit;
  font-size: 0.82rem;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  transition: background-color 100ms ease;
}
.task-state-menu-item i:first-child {
  width: 1rem;
  text-align: center;
}
.task-state-menu-item:hover { background: #f4f7f9; }
.task-state-menu-item.is-current { background: rgba(57, 104, 123, 0.08); }
.task-state-menu-check { margin-left: auto; color: var(--air-force-blue, #39687b); }

/* Selection box (only shown in select mode) */
.task-select-box {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  margin-top: 0.15rem;
  padding: 0;
  border: 2px solid #c5cdd3;
  border-radius: 6px;
  background: #fff;
  color: #fff;
  cursor: pointer;
  transition: border-color 120ms ease, background-color 120ms ease;
}
.task-select-box i { font-size: 0.7rem; }
.task-select-box:hover:not(:disabled) {
  border-color: var(--air-force-blue, #39687b);
  background: rgba(57, 104, 123, 0.08);
}
.task-select-box.is-selected {
  border-color: var(--air-force-blue, #39687b);
  background: var(--air-force-blue, #39687b);
}
.task-select-box:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.25);
}
.task-select-box:disabled {
  cursor: not-allowed;
  background: #f1f3f5;
  border-color: #d8dee2;
}

/* Body */

.task-body {
  flex: 1 1 auto;
  min-width: 0;
}
.task-headline {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.task-label {
  color: var(--charcoal);
  font-size: 0.92rem;
  font-weight: 600;
  line-height: 1.3;
  word-break: break-word;
}
.task-description {
  margin-top: 0.25rem;
  color: #6c757d;
  font-size: 0.82rem;
  line-height: 1.5;
}
.task-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.45rem;
}

.task-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.18rem 0.5rem;
  border-radius: 999px;
  background: #eef2f4;
  color: #50616c;
  font-size: 0.72rem;
  font-weight: 600;
  line-height: 1.4;
}
.task-chip i { font-size: 0.7rem; }
.task-chip--date.is-overdue {
  background: #fdecec;
  color: #8c1f1f;
}
.task-chip--assignee {
  background: rgba(57, 104, 123, 0.1);
  color: var(--air-force-blue, #39687b);
}
.task-chip--assignee.is-self {
  background: rgba(77, 116, 94, 0.18);
  color: var(--dark-green, #4d745e);
}

/* Dedicated assignee slot on the right of the row, top-aligned with the state pill.
   Rendered as a button now -- click to filter by that person. */
.task-assignee {
  flex-shrink: 0;
  align-self: flex-start;
  margin-top: 0.05rem;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  max-width: 11rem;
  padding: 0.2rem 0.6rem;
  border: 1px solid transparent;
  border-radius: 999px;
  background: rgba(57, 104, 123, 0.1);
  color: var(--air-force-blue, #39687b);
  font: inherit;
  font-size: 0.74rem;
  font-weight: 700;
  line-height: 1.4;
  white-space: nowrap;
  cursor: pointer;
  transition: background-color 120ms ease, color 120ms ease, border-color 120ms ease, transform 120ms ease;
}
.task-assignee i { font-size: 0.72rem; flex-shrink: 0; }
.task-assignee span {
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
.task-assignee:hover {
  background: rgba(57, 104, 123, 0.18);
  transform: translateY(-1px);
}
.task-assignee:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.25);
}
.task-assignee.is-self {
  background: rgba(77, 116, 94, 0.18);
  color: var(--dark-green, #4d745e);
}
.task-assignee.is-self:hover {
  background: rgba(77, 116, 94, 0.3);
}
.task-assignee.is-active {
  border-color: var(--air-force-blue, #39687b);
  background: rgba(57, 104, 123, 0.22);
}
.task-assignee.is-self.is-active {
  border-color: var(--dark-green, #4d745e);
  background: rgba(77, 116, 94, 0.3);
}

.task-chip--deleted {
  background: #f7e7e7;
  color: #8c1f1f;
}
.task-chip--status[data-status='todo'] { background: #fff3d6; color: #8a6d1f; }
.task-chip--status[data-status='in_progress'] { background: #e0eef9; color: #1f5b89; }
.task-chip--status[data-status='in_review'] { background: #ebe2f7; color: #5b3b8c; }
.task-chip--status[data-status='done'] { background: rgba(77, 116, 94, 0.15); color: var(--dark-green, #4d745e); }
.task-chip--status[data-status='blocked'] { background: #fdecec; color: #8c1f1f; }
.task-chip--role {
  background: #f1f3f5;
  color: #50616c;
}

/* "Assigned by Name" -- subtle text inline with the date chip */
.task-assigned-by {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.74rem;
  color: #6c757d;
  font-weight: 500;
}
.task-assigned-by strong {
  color: #50616c;
  font-weight: 700;
}

/* Row actions -- hidden until hover/focus */

.task-row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.25rem;
  flex-shrink: 0;
  /* 3 icon buttons (30px) + 2 gaps (4px) -- reserved even when only the
     always-rendered + button is present, so the assignee column lines up
     across all rows regardless of edit/delete permission. */
  min-width: 98px;
  opacity: 0;
  transition: opacity 120ms ease;
}
.task-item:hover .task-row-actions,
.task-row-actions:focus-within { opacity: 1; }

.task-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: #6c757d;
  cursor: pointer;
  transition: background-color 120ms ease, color 120ms ease, border-color 120ms ease;
}
.task-icon-btn:hover:not(:disabled) {
  background: #f1f3f5;
  border-color: var(--border-light);
  color: var(--charcoal);
}
.task-icon-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.25);
}
.task-icon-btn--danger:hover:not(:disabled) {
  background: #fdecec;
  border-color: #f3c2c2;
  color: #8c1f1f;
}
.task-icon-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
  background: transparent;
  color: #c5cdd3;
}

/* Empty + skeleton states */

.task-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.45rem;
  padding: 1.6rem 1rem;
  color: #6c757d;
  font-size: 0.85rem;
}
.task-empty-state i { font-size: 1.4rem; color: #c5cdd3; }
.task-empty-cta {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.4rem;
  padding: 0.45rem 0.85rem;
  border: 1px dashed var(--air-force-blue, #39687b);
  border-radius: 999px;
  background: transparent;
  color: var(--air-force-blue, #39687b);
  font: inherit;
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 120ms ease, color 120ms ease;
}
.task-empty-cta:hover {
  background: var(--air-force-blue, #39687b);
  color: #fff;
}

.task-skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  background: #fff;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 0.5rem;
}
.task-skeleton-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.55rem 0.65rem;
}
.task-skeleton-circle {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: #eef2f4;
  flex-shrink: 0;
}
.task-skeleton-lines { flex: 1; display: flex; flex-direction: column; gap: 0.4rem; }
.task-skeleton-line {
  height: 10px;
  border-radius: 4px;
  background: #eef2f4;
}
.task-skeleton-line--lg { width: 70%; }
.task-skeleton-line--sm { width: 40%; }

/* Sticky bulk action bar */

.task-bulk-bar {
  position: sticky;
  bottom: 0.75rem;
  margin: 0.85rem auto 0;
  width: max-content;
  max-width: 100%;
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 0.55rem 0.7rem 0.55rem 1rem;
  background: #1f2530;
  color: #fff;
  border-radius: 999px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.18);
  z-index: 5;
  font-size: 0.84rem;
  font-weight: 600;
}
.task-bulk-count {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  white-space: nowrap;
}
.task-bulk-actions {
  display: flex;
  gap: 0.35rem;
  align-items: center;
}
.task-bulk-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  height: 30px;
  padding: 0 0.75rem;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  font: inherit;
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 120ms ease, border-color 120ms ease, color 120ms ease;
}
.task-bulk-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.16);
}
.task-bulk-btn--primary {
  background: var(--dark-green, #4d745e);
  border-color: var(--dark-green, #4d745e);
}
.task-bulk-btn--primary:hover:not(:disabled) {
  background: #5d8a72;
  border-color: #5d8a72;
}
.task-bulk-btn--ghost {
  background: transparent;
  border-color: transparent;
  color: rgba(255, 255, 255, 0.7);
}
.task-bulk-btn--ghost:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}
.task-bulk-btn:disabled { cursor: not-allowed; opacity: 0.55; }

.task-bulk-fade-enter-from,
.task-bulk-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
.task-bulk-fade-enter-active,
.task-bulk-fade-leave-active {
  transition: opacity 160ms ease, transform 160ms ease;
}

/* ---------- Refined task popup ---------- */

.task-dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(2px);
}

.task-dialog {
  width: min(100%, 560px);
  max-height: calc(100vh - 2rem);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.28);
  border: 1px solid rgba(15, 23, 42, 0.06);
}

.task-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.7rem;
  padding: 1rem 1.1rem 0.75rem;
  border-bottom: 1px solid var(--border-light);
}
.task-dialog-title {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  color: var(--charcoal);
}
.task-dialog-title i {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(57, 104, 123, 0.1);
  color: var(--air-force-blue, #39687b);
  border-radius: 8px;
  font-size: 0.82rem;
}
.task-dialog-title h4 {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
}
.task-dialog-close {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: #6c757d;
  cursor: pointer;
  transition: background-color 120ms ease, color 120ms ease;
}
.task-dialog-close:hover {
  background: #f4f7f9;
  color: var(--charcoal);
}
.task-dialog-close:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.25);
}

.task-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 0.95rem;
  padding: 1rem 1.1rem;
  overflow-y: auto;
}

.task-dialog-title-input {
  width: 100%;
  padding: 0.35rem 0;
  border: 0;
  border-bottom: 1px solid transparent;
  background: transparent;
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--charcoal);
  outline: none;
  transition: border-color 120ms ease;
}
.task-dialog-title-input::placeholder { color: #a3adb3; font-weight: 600; }
.task-dialog-title-input:focus { border-bottom-color: var(--air-force-blue, #39687b); }

.task-dialog-description-input {
  width: 100%;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: #fafbfc;
  color: var(--charcoal);
  font: inherit;
  font-size: 0.88rem;
  resize: vertical;
  min-height: 60px;
  transition: border-color 120ms ease, background-color 120ms ease;
}
.task-dialog-description-input::placeholder { color: #a3adb3; }
.task-dialog-description-input:focus {
  outline: none;
  border-color: var(--air-force-blue, #39687b);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.12);
}

.task-dialog-field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.task-dialog-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.85rem;
}
.task-dialog-field--half { min-width: 0; }
.task-dialog-label {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  color: #6c757d;
  font-size: 0.74rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.task-dialog-label i { font-size: 0.78rem; color: #94a3a8; }
.task-dialog-input {
  width: 100%;
  height: 36px;
  padding: 0 0.65rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: #fff;
  color: var(--charcoal);
  font: inherit;
  font-size: 0.88rem;
  transition: border-color 120ms ease, box-shadow 120ms ease;
}
.task-dialog-input:focus {
  outline: none;
  border-color: var(--air-force-blue, #39687b);
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.12);
}
.task-dialog-readonly {
  padding: 0.4rem 0.65rem;
  background: #f4f7f9;
  border-radius: 8px;
  color: #50616c;
  font-size: 0.85rem;
  min-height: 36px;
  display: flex;
  align-items: center;
}

/* Segmented control */
.task-segmented {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  padding: 0.25rem;
  background: #f4f7f9;
  border-radius: 10px;
}
.task-segmented-option {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.8rem;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #50616c;
  font: inherit;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 120ms ease, color 120ms ease, box-shadow 120ms ease;
}
.task-segmented-option i { font-size: 0.78rem; opacity: 0.7; }
.task-segmented-option:hover:not(:disabled):not(.is-active) {
  background: rgba(255, 255, 255, 0.6);
  color: var(--charcoal);
}
.task-segmented-option:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.25);
}
.task-segmented-option.is-active {
  background: #fff;
  color: var(--charcoal);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}
.task-segmented-option.is-active i { opacity: 1; }
.task-segmented-option:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

/* Status segmented uses the row pill colors when active */
.task-segmented-option--status.is-active.task-state--todo        { background: #eef2f4; color: #50616c; }
.task-segmented-option--status.is-active.task-state--in_progress { background: #e0eef9; color: #1f5b89; }
.task-segmented-option--status.is-active.task-state--done        { background: rgba(77, 116, 94, 0.18); color: var(--dark-green, #4d745e); }
.task-segmented-option--status.is-active.task-state--blocked     { background: #fdecec; color: #8c1f1f; }

.task-dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.7rem;
  padding: 0.75rem 1.1rem;
  border-top: 1px solid var(--border-light);
  background: #fafbfc;
}
.task-dialog-hint {
  color: #94a3a8;
  font-size: 0.74rem;
}
.task-dialog-hint kbd {
  display: inline-block;
  padding: 0 0.3rem;
  min-width: 18px;
  height: 18px;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  background: #fff;
  font-size: 0.7rem;
  font-family: inherit;
  color: #50616c;
  text-align: center;
}
.task-dialog-actions { display: flex; gap: 0.45rem; }
.task-dialog-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  height: 34px;
  padding: 0 0.95rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: #fff;
  color: #50616c;
  font: inherit;
  font-size: 0.85rem;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 120ms ease, color 120ms ease, border-color 120ms ease;
}
.task-dialog-btn:hover:not(:disabled) {
  background: #f4f7f9;
  border-color: var(--air-force-blue, #39687b);
  color: var(--charcoal);
}
.task-dialog-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.25);
}
.task-dialog-btn--primary {
  background: var(--air-force-blue, #39687b);
  border-color: var(--air-force-blue, #39687b);
  color: #fff;
}
.task-dialog-btn--primary:hover:not(:disabled) {
  background: #2d5365;
  border-color: #2d5365;
  color: #fff;
}
.task-dialog-btn:disabled { cursor: not-allowed; opacity: 0.55; }

/* Entrance/exit transition */
.task-dialog-enter-from .task-dialog,
.task-dialog-leave-to .task-dialog {
  opacity: 0;
  transform: translateY(10px) scale(0.97);
}
.task-dialog-enter-from,
.task-dialog-leave-to { opacity: 0; }
.task-dialog-enter-active,
.task-dialog-leave-active { transition: opacity 160ms ease; }
.task-dialog-enter-active .task-dialog,
.task-dialog-leave-active .task-dialog {
  transition: opacity 200ms ease, transform 200ms cubic-bezier(0.4, 0, 0.2, 1);
}

/* Tint level toggle in toolbar */
.task-toolbar-icon-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: #fff;
  color: #6c757d;
  cursor: pointer;
  transition: background-color 120ms ease, border-color 120ms ease, color 120ms ease;
}
.task-toolbar-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 0.25rem;
  border-radius: 999px;
  background: var(--air-force-blue, #39687b);
  color: #fff;
  font-size: 0.65rem;
  font-weight: 700;
  line-height: 1;
}
.task-toolbar-icon-btn:hover {
  background: #f4f7f9;
  border-color: var(--air-force-blue, #39687b);
  color: var(--charcoal);
}
.task-toolbar-icon-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.25);
}
.task-toolbar-icon-btn.is-active {
  background: rgba(77, 116, 94, 0.15);
  border-color: var(--dark-green, #4d745e);
  color: var(--dark-green, #4d745e);
}

/* List footer: Show more / count info */
.task-list-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-top: 0.65rem;
  padding: 0.4rem 0.4rem;
  font-size: 0.8rem;
  color: #6c757d;
}
.task-list-count { font-weight: 600; }
.task-list-more {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  height: 30px;
  padding: 0 0.85rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background: #fff;
  color: var(--air-force-blue, #39687b);
  font: inherit;
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 120ms ease, border-color 120ms ease, color 120ms ease;
}
.task-list-more:hover {
  background: var(--air-force-blue, #39687b);
  border-color: var(--air-force-blue, #39687b);
  color: #fff;
}
.task-list-more:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.25);
}

/* Flat (tint off) depth-class fallback */
.task-depth-flat {
  --task-depth-bg: #fff;
  --task-depth-border: var(--border-light);
  --task-depth-accent: transparent;
}

/* Discussion board: chat-container fills card, chat-messages scrolls */
.chat-status {
  color: #6c757d;
  font-size: 0.85rem;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.25rem 0.6rem;
  border-radius: 999px;
  background: rgba(108, 117, 125, 0.08);
  border: 1px solid rgba(108, 117, 125, 0.18);
}

.chat-status-dot {
  font-size: 0.55rem;
  line-height: 1;
}

.chat-status--connected {
  color: #1f7a3f;
  background: rgba(31, 122, 63, 0.08);
  border-color: rgba(31, 122, 63, 0.22);
}

.chat-status--connected .chat-status-dot {
  color: #2ea44f;
}

.chat-status--offline {
  color: #b54708;
  background: rgba(181, 71, 8, 0.08);
  border-color: rgba(181, 71, 8, 0.22);
}

.chat-status--offline .chat-status-dot {
  color: #d97706;
}

.chat-status--loading {
  color: var(--air-force-blue, #5b8c93);
}

.chat-reconnect-btn {
  margin-left: 0.35rem;
  border: 1px solid currentColor;
  background: transparent;
  color: inherit;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.1rem 0.55rem;
  border-radius: 999px;
  cursor: pointer;
}

.chat-reconnect-btn:hover {
  background: rgba(0, 0, 0, 0.05);
}

.chat-alert {
  padding: 0.65rem 0.9rem;
  color: #6c4b00;
  background: #fff7d6;
  border-bottom: 1px solid #f1dd97;
  font-size: 0.9rem;
}

.chat-notice {
  padding: 0.65rem 0.9rem;
  color: var(--air-force-blue);
  background: #eef7f9;
  border-bottom: 1px solid var(--border-light);
  font-size: 0.9rem;
  font-weight: 600;
}

.typing-indicator,
.gif-status {
  padding: 0.55rem 0.9rem;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.chat-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.55rem;
  padding: 2.4rem 1.4rem;
  text-align: center;
  color: var(--text-muted);
  min-height: 220px;
}

.chat-empty-emoji {
  font-size: 2.4rem;
  line-height: 1;
  margin-bottom: 0.2rem;
}

.chat-empty-state strong {
  font-size: 1.05rem;
  color: var(--text-primary);
}

.chat-empty-state span {
  font-size: 0.88rem;
  max-width: 320px;
}

.chat-empty-state .btn {
  margin-top: 0.5rem;
}

.chat-skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem 1.2rem;
}

.chat-skeleton-row {
  display: flex;
  gap: 0.7rem;
  align-items: flex-start;
}

.chat-skeleton-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.message-search-filters {
  display: flex;
  gap: 0.8rem;
  flex-wrap: wrap;
  padding: 0.6rem 0.9rem;
  margin: 0 0.9rem 0.6rem;
  background: rgba(0, 0, 0, 0.03);
  border: 1px solid var(--border-light, rgba(0, 0, 0, 0.08));
  border-radius: 10px;
}

.message-search-filters label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-muted);
}

.message-search-filters select,
.message-search-filters input[type="date"] {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 0.36rem 0.55rem;
  background: var(--surface, #fff);
  font: inherit;
  color: var(--text-primary);
}

.message-action-btn.active {
  background: rgba(31, 122, 63, 0.12);
  color: #1f7a3f;
  border-color: rgba(31, 122, 63, 0.32);
}

.scroll-bottom-btn {
  position: absolute;
  right: 1rem;
  bottom: 5.9rem;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.35rem;
  height: 2.35rem;
  border: 1px solid var(--border-light);
  border-radius: 50%;
  background: var(--dark-green);
  color: var(--white);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.18);
  cursor: pointer;
  transition:
    transform 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease;
}

.scroll-bottom-btn:hover {
  background: #015f45;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.22);
  transform: translateY(-1px);
}

.missed-message-jump-btn {
  position: absolute;
  right: 1rem;
  bottom: 8.75rem;
  z-index: 4;
  display: inline-flex;
  align-items: center;
  gap: 0.42rem;
  max-width: calc(100% - 2rem);
  min-height: 2.2rem;
  border: 1px solid rgba(57, 104, 123, 0.28);
  border-radius: 999px;
  background: #eef7f9;
  color: var(--air-force-blue);
  box-shadow: 0 4px 12px rgba(24, 38, 50, 0.12);
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 800;
  padding: 0.42rem 0.72rem;
  transition:
    transform 0.16s ease,
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease;
}

.missed-message-jump-btn.has-scroll-bottom {
  bottom: 8.75rem;
}

.missed-message-jump-btn:not(.has-scroll-bottom) {
  bottom: 5.9rem;
}

.missed-message-jump-btn:hover {
  border-color: var(--air-force-blue);
  background: #f6fbfc;
  box-shadow: 0 6px 16px rgba(24, 38, 50, 0.16);
  transform: translateY(-1px);
}

.missed-message-jump-btn span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.load-older-messages {
  align-self: center;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background: var(--white);
  color: var(--air-force-blue);
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 700;
  padding: 0.45rem 0.8rem;
}

.load-older-messages:disabled {
  cursor: wait;
  opacity: 0.6;
}

.message-thread-item {
  display: contents;
}

.missed-message-divider {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin: 0.7rem 0;
  color: var(--air-force-blue);
  font-size: 0.78rem;
  font-weight: 800;
}

.missed-message-divider::before,
.missed-message-divider::after {
  content: '';
  flex: 1 1 auto;
  height: 1px;
  background: rgba(57, 104, 123, 0.28);
}

.missed-message-divider span {
  flex: 0 0 auto;
  border: 1px solid rgba(57, 104, 123, 0.24);
  border-radius: 999px;
  background: #eef7f9;
  padding: 0.22rem 0.6rem;
}

.missed-message-divider button {
  flex: 0 0 auto;
  border: 1px solid rgba(57, 104, 123, 0.28);
  border-radius: 999px;
  background: var(--white);
  color: var(--air-force-blue);
  cursor: pointer;
  font-size: 0.74rem;
  font-weight: 800;
  padding: 0.22rem 0.58rem;
}

.missed-message-divider button:hover {
  border-color: var(--air-force-blue);
  background: #f3f8f7;
}

.load-older-status {
  align-self: center;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.85rem;
  font-size: 0.82rem;
  color: var(--air-force-blue);
}

.load-older-spinner {
  width: 14px;
  height: 14px;
  border-width: 2px;
}

.message.pending {
  opacity: 0.72;
}

.message-reply,
.reply-composer {
  border-left: 3px solid var(--air-force-blue);
  background: rgba(57, 104, 123, 0.08);
}

.message-reply {
  display: grid;
  gap: 0.2rem;
  margin: 0.4rem 0 0.55rem;
  padding: 0.45rem 0.65rem;
  border-radius: 6px;
}

.message-reply span,
.reply-composer span {
  color: #6c757d;
  font-size: 0.76rem;
  font-weight: 700;
}

.message-reply strong,
.reply-composer strong {
  color: inherit;
  font-size: 0.85rem;
  font-weight: 600;
}

.message.own .message-reply {
  border-left-color: var(--white);
  background: rgba(255, 255, 255, 0.18);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.18);
}

.message.own .message-reply span {
  color: rgba(255, 255, 255, 0.82);
}

.message.own .message-reply strong {
  color: var(--white);
}

.message-edit-form {
  display: grid;
  gap: 0.55rem;
  margin-top: 0.45rem;
}

.message-edit-actions,
.message-actions,
.reply-composer {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.message-edit-actions {
  justify-content: flex-end;
}

.message-edit-actions .message-edit-cancel {
  background: var(--white);
  border-color: #b9c4ca;
  color: var(--charcoal);
}

.message-edit-actions .message-edit-cancel:hover {
  background: #eef3f5;
  border-color: var(--dark-green);
  color: var(--dark-green);
}

.message-edit-actions .message-edit-save {
  background: var(--dark-green);
  border: 1px solid var(--dark-green);
  color: var(--white);
}

.message-edit-actions .message-edit-save:hover {
  background: #015f45;
  border-color: #015f45;
}

.message.own .message-edit-actions .message-edit-cancel {
  background: transparent;
  border-color: rgba(255, 255, 255, 0.72);
  color: var(--white);
}

.message.own .message-edit-actions .message-edit-cancel:hover {
  background: rgba(255, 255, 255, 0.12);
  border-color: var(--white);
  color: var(--white);
}

.message.own .message-edit-actions .message-edit-save {
  background: var(--white);
  border-color: var(--white);
  color: var(--dark-green);
}

.message.own .message-edit-actions .message-edit-save:hover {
  background: #eef7f3;
  border-color: #eef7f3;
  color: var(--dark-green);
}

.message-actions {
  flex-wrap: wrap;
  margin-top: 0.6rem;
}

.message-action-btn {
  border: 0;
  background: transparent;
  color: var(--air-force-blue);
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 700;
  padding: 0.1rem 0;
}

.message-action-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.reply-composer {
  justify-content: space-between;
  padding: 0.6rem 0.8rem;
}

.reply-composer > div {
  display: grid;
  min-width: 0;
}

.reply-composer strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-header-actions {
  display: inline-flex;
  align-items: center;
  gap: 0.65rem;
}

.mentions-toggle {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border: 1px solid var(--border-light);
  border-radius: 50%;
  background: var(--white);
  color: var(--dark-green);
  cursor: pointer;
}

.mentions-toggle.active,
.mentions-toggle:hover {
  border-color: var(--dark-green);
  background: #eef7f3;
}

.mention-badge {
  position: absolute;
  top: -0.35rem;
  right: -0.35rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.15rem;
  height: 1.15rem;
  border-radius: 999px;
  background: var(--danger);
  color: var(--white);
  font-size: 0.68rem;
  font-weight: 800;
  padding: 0 0.25rem;
}

.mention-inbox {
  border-bottom: 1px solid var(--border-light);
  background: var(--white);
  padding: 0.85rem;
}

.mention-inbox-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.65rem;
}

.mention-list {
  display: grid;
  gap: 0.45rem;
  max-height: 240px;
  overflow-y: auto;
}

.mention-row {
  display: grid;
  gap: 0.15rem;
  width: 100%;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
  cursor: pointer;
  padding: 0.55rem 0.7rem;
  text-align: left;
}

.mention-row.unread {
  border-color: var(--dark-green);
  background: #eef7f3;
}

.mention-row span,
.mention-row small {
  color: #6c757d;
  font-size: 0.76rem;
  font-weight: 700;
}

.mention-row strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.86rem;
}

.message-search-panel {
  display: grid;
  gap: 0.65rem;
  border-bottom: 1px solid var(--border-light);
  background: var(--white);
  padding: 0.85rem;
}

.message-search-form {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.message-search-input {
  flex: 1 1 auto;
  min-width: 0;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background: var(--white);
  color: var(--charcoal);
  font: inherit;
  padding: 0.55rem 1rem;
  transition: border-color 0.16s ease, box-shadow 0.16s ease;
}

.message-search-input:focus {
  outline: none;
  border-color: var(--air-force-blue);
  box-shadow: 0 0 0 4px rgba(57, 104, 123, 0.10);
}

.message-search-list {
  display: grid;
  gap: 0.45rem;
  max-height: 280px;
  overflow-y: auto;
}

.message-search-row {
  display: grid;
  gap: 0.35rem;
  width: 100%;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
  cursor: pointer;
  padding: 0.62rem 0.75rem;
  text-align: left;
}

.message-search-row:hover {
  border-color: var(--air-force-blue);
  background: #f3f8f7;
}

.message-search-row-head,
.message-search-tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.message-search-row-head {
  justify-content: space-between;
}

.message-search-row-head small,
.message-search-tags {
  color: #6c757d;
  font-size: 0.76rem;
  font-weight: 700;
}

.message-search-text {
  overflow: hidden;
  color: var(--charcoal);
  font-size: 0.86rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.message.search-hit .message-content {
  animation: message-search-pulse 2.2s ease;
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.22);
}

@keyframes message-search-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(57, 104, 123, 0);
  }
  20%,
  70% {
    box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.24);
  }
}

.selected-resource-strip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.45rem;
  padding: 0.55rem 0.8rem;
  border-top: 1px solid var(--border-light);
  background: #f8f9fa;
}

.selected-resource-strip > span {
  color: #6c757d;
  font-size: 0.78rem;
  font-weight: 700;
}

.selected-resource-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  max-width: min(100%, 260px);
  border: 1px solid var(--dark-green);
  border-radius: 999px;
  background: #eef7f3;
  color: var(--dark-green);
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 700;
  padding: 0.35rem 0.6rem;
}

.selected-resource-chip i:first-child,
.resource-picker-row i:first-child {
  flex: 0 0 auto;
}

.selected-resource-chip {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.resource-panel {
  border-top: 1px solid var(--border-light);
  border-bottom: 1px solid var(--border-light);
  background: var(--white);
  padding: 0.85rem;
}

.resource-panel-header {
  display: flex;
  gap: 0.6rem;
  margin-bottom: 0.75rem;
}

.resource-picker-list {
  display: grid;
  gap: 0.45rem;
  max-height: 220px;
  overflow-y: auto;
}

.resource-picker-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.55rem;
  width: 100%;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
  cursor: pointer;
  padding: 0.55rem 0.7rem;
  text-align: left;
}

.resource-picker-row span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.resource-picker-row:hover,
.resource-picker-row.selected {
  border-color: var(--dark-green);
  background: #eef7f3;
  color: var(--dark-green);
}

.chat-input-group {
  position: relative;
}

.mention-suggestions {
  position: absolute;
  left: 0;
  right: 3.5rem;
  bottom: calc(100% + 0.45rem);
  z-index: 5;
  display: grid;
  gap: 0.25rem;
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.16);
  padding: 0.35rem;
}

.mention-suggestion {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--charcoal);
  cursor: pointer;
  padding: 0.45rem 0.55rem;
  text-align: left;
}

.mention-suggestion.active,
.mention-suggestion:hover {
  background: #eef7f3;
  color: var(--dark-green);
}

.mention-suggestion span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 700;
}

.mention-suggestion small {
  color: #6c757d;
  font-size: 0.75rem;
  font-weight: 700;
}

.mention-token {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  border-radius: 999px;
  background: rgba(33, 150, 243, 0.12); /* soft blue */
  color: #1565c0;
  font-weight: 700;
  padding: 0.05rem 0.4rem;
  text-decoration: none;
}

.message.own .mention-token {
  background: rgba(255, 255, 255, 0.22);
  color: #cfe8ff;
}

.gif-panel {
  border-top: 1px solid var(--border-default);
  border-bottom: 1px solid var(--border-default);
  background: rgba(255, 255, 255, 0.04);
  padding: 0.85rem;
}

.gif-panel-header {
  display: flex;
  gap: 0.6rem;
  margin-bottom: 0.8rem;
}

.gif-search-input {
  flex: 1;
  border: 1px solid var(--border-default);
  border-radius: 12px;
  padding: 0.65rem 0.8rem;
  background: rgba(255, 255, 255, 0.9);
}

.gif-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.65rem;
  max-height: 320px;
  overflow-y: auto;
  padding-right: 0.25rem;
}

.gif-grid--skeleton {
  pointer-events: none;
}

.gif-card {
  border: 1px solid var(--border-default);
  border-radius: 16px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
  cursor: pointer;
  padding: 0;
  transition: transform 0.12s ease, box-shadow 0.12s ease;
  /* Pause off-screen GIFs in the picker grid. */
  content-visibility: auto;
  contain-intrinsic-size: 170px 170px;
}

.gif-card:hover,
.gif-card:focus-visible {
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
  outline: none;
}

.gif-card img {
  width: 100%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  display: block;
}

.gif-skeleton {
  aspect-ratio: 1 / 1;
  border-radius: 16px;
}

.gif-status--empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  padding: 1.2rem;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.gif-status--empty i {
  font-size: 1.5rem;
  opacity: 0.6;
}

.gif-status--error {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.gif-load-more-row {
  display: flex;
  justify-content: center;
  margin-top: 0.6rem;
}

.gif-attribution {
  margin-top: 0.6rem;
  text-align: right;
  font-size: 0.7rem;
  color: var(--text-muted);
  opacity: 0.75;
}

.chat-btn:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

.pane--discussion .chat-container {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  height: 100%;
  min-height: 0;
}

.pane--discussion .chat-messages {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
  /* Never horizontally scroll. The hover toolbars / reactions that poke into
     the gutter are constrained via the message row below. */
  overflow-x: hidden;
}

/* Tasks pane styles defined above; the legacy .add-subtask-btn /
   .task-empty-state overrides previously here have been replaced by
   the .task-icon-btn and .task-empty-state rules in the modernized block. */

/* Discussion header */
.pane--discussion .chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: var(--white) !important;
  color: var(--charcoal) !important;
  border-bottom: 1px solid var(--border-light);
}

/* Fill available chat space */
.pane--discussion .chat-container {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  height: 100%;
  min-height: 0;
}

/* Message scroller */
.chat-messages {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
  /* Never horizontally scroll. The hover toolbars / reactions that poke into
     the gutter are constrained via the message row below. */
  overflow-x: hidden;
}

/* Stop animating off-screen GIFs (and skip paint for off-screen text) by
   letting the browser skip rendering work for messages outside the viewport.
   contain-intrinsic-size keeps the scrollbar honest while the browser
   learns each message's real height. */
.chat-messages .message {
  content-visibility: auto;
  contain-intrinsic-size: auto 80px;
}

/* Message date and time layout */
.message-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.message-date {
  color: #6c757d;
  font-weight: 500;
}

/* Own-message date contrast */
.pane--discussion .message.own .message-date {
  color: #fff !important;
  opacity: 0.95;
}

/* Message text color for own messages */
.pane--discussion .message.own .message-text {
  color: #fff !important;
}

.message-edited {
  display: inline-flex;
  align-items: center;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent-blue) 18%, transparent);
  color: var(--text-primary);
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.message-gif {
  width: min(100%, 280px);
  border-radius: 18px;
  display: block;
  margin-top: 0.4rem;
  box-shadow: var(--shadow-sm);
}

.message-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.7rem;
}

.attachment-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.7rem;
  border-radius: 999px;
  border: 1px solid var(--border-default);
  background: color-mix(in srgb, var(--surface-elevated) 92%, transparent);
  color: var(--text-primary);
  text-decoration: none;
  font-size: 0.84rem;
}

/* Compact link-preview card — horizontal thumb + text layout, capped height
   so a single image card can't dominate the chat scroll like before. */
.message-preview {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 0.65rem;
  margin-top: 0.55rem;
  padding: 0.5rem 0.65rem;
  border-radius: 12px;
  border: 1px solid var(--border-default);
  background: color-mix(in srgb, var(--surface-base) 86%, transparent);
  color: var(--text-primary);
  max-width: 360px;
}

.message-preview img {
  width: 56px;
  height: 56px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
}

.message-preview strong {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 0.88rem;
}

.message-preview span {
  color: var(--text-secondary);
  font-size: 0.78rem;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Allow the strong/span pair to share the grid's second column. */
.message-preview > :not(img) {
  grid-column: 2;
}

.message-preview img {
  grid-row: span 2;
}

.message-reactions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.75rem;
}

/* Reaction chips — Telegram/Instagram style: compact, overlap the bubble */
.reaction-btn,
.reaction-summary-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  border-radius: 999px;
  border: 1px solid var(--border-default);
  background: color-mix(in srgb, var(--surface-elevated) 94%, transparent);
  color: var(--text-primary);
  padding: 0.2rem 0.5rem;
  font-size: 0.82rem;
  line-height: 1;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background 0.18s ease,
    transform 0.12s ease;
}

.reaction-btn:hover,
.reaction-summary-btn:hover {
  border-color: var(--air-force-blue);
  transform: translateY(-1px);
}

.reaction-count {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--text-muted);
}

.message-reactions {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  margin: 0;
  padding: 0;
}

.message-reactions .reaction-summary-btn {
  background: var(--white);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

/* Receipt button — reset default <button> chrome since we converted it. */
.message-receipt-wrap {
  position: relative;
  display: inline-flex;
  margin-top: 0.55rem;
}

/* Receipt wrap — anchor for the popover + slot for ticks. Pulled out of the
   bubble's vertical flow on own messages so it sits inline at the bottom-right
   corner (WhatsApp position) and adds zero extra height. */
.message.own .message-receipt-wrap {
  position: absolute;
  bottom: 0.35rem;
  right: 0.55rem;
}

.message-receipt {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  color: var(--text-muted);
  font-size: 0.72rem;
  font-weight: 600;
  background: transparent;
  border: none;
  padding: 0.05rem 0.3rem;
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.14s ease, color 0.14s ease;
}

.message-receipt:hover,
.message-receipt.is-open {
  color: var(--air-force-blue);
  background: rgba(57, 104, 123, 0.10);
}

.message.own .message-receipt {
  color: rgba(255, 255, 255, 0.78);
}

.message.own .message-receipt:hover,
.message.own .message-receipt.is-open {
  color: var(--white);
  background: rgba(255, 255, 255, 0.16);
}

/* Tick colours.
   - delivered:  single grey tick      (no reads yet)
   - partial:    double grey ticks     (some but not all members read)
   - read:       double blue ticks     (every other group member has read it) */
.message-receipt--ticks .tick-icon {
  font-size: 0.82rem;
}

.message-receipt--delivered .tick-icon,
.message-receipt--partial .tick-icon {
  color: rgba(0, 0, 0, 0.42);
}

.message.own .message-receipt--delivered .tick-icon,
.message.own .message-receipt--partial .tick-icon {
  color: rgba(255, 255, 255, 0.7);
}

.message-receipt--read .tick-icon {
  color: #2196f3;
}

.message.own .message-receipt--read .tick-icon {
  color: #6ad1ff;
}

.receipt-count {
  font-variant-numeric: tabular-nums;
  font-size: 0.72rem;
  opacity: 0.85;
}

.message-receipt-popover {
  position: absolute;
  bottom: calc(100% + 0.5rem);
  right: 0;
  min-width: 240px;
  max-width: 320px;
  z-index: 20;
  background: var(--white);
  border: 1px solid var(--border-default);
  border-radius: 12px;
  box-shadow: 0 14px 36px rgba(0, 0, 0, 0.16);
  padding: 0.7rem 0.8rem;
  font-size: 0.82rem;
  color: var(--text-primary);
  text-align: left;
}

/* Teleported variant: rendered at <body> root with fixed coordinates so
   the scrollable chat container's ``overflow: auto`` can't clip it. */
.message-receipt-popover--floating {
  /* Override the inline component-scoped absolute positioning baseline.
     ``position`` is set via inline style by the component. */
  bottom: auto;
  right: auto;
}

.message:not(.own) .message-receipt-popover {
  right: auto;
  left: 0;
}

.message-receipt-popover-section + .message-receipt-popover-section {
  margin-top: 0.55rem;
  padding-top: 0.55rem;
  border-top: 1px dashed var(--border-light);
}

.message-receipt-popover-section strong {
  display: block;
  font-size: 0.74rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  margin-bottom: 0.35rem;
}

.message-receipt-popover-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.2rem 0;
}

.message-receipt-popover-row .receipt-name {
  flex: 1;
  font-weight: 600;
}

.message-receipt-popover-row .receipt-meta {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.message-receipt-popover-status {
  color: var(--text-muted);
  font-size: 0.82rem;
}

.message-receipt-popover-status.error {
  color: #b54708;
}

.hidden-file-input {
  display: none;
}

/* Mobile layout */
@media (max-width: 1180px) {
  .split {
    grid-template-columns: 1fr;
    max-height: none;
    height: auto;
  }
  .mobile-tabs {
    display: none;
  }
  .split .pane {
    display: flex;
    height: auto;
  }
  .pane--discussion .chat-container {
    height: min(72vh, 620px);
    min-height: 420px;
  }
  .card {
    height: auto;
    min-height: 220px;
  }
  .pane--tasks.card {
    min-height: 520px;
  }
  .pane--discussion {
    min-height: 520px;
  }

  .gif-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
.group-detail {
  position: relative;
  isolation: isolate;
  min-height: 100%;
  overflow: visible;
  padding: 1.5rem 1.2rem 3rem;
  color: var(--text-primary);
  background:
    radial-gradient(circle at 10% 8%, var(--page-glow-one), transparent 26%),
    radial-gradient(circle at 86% 12%, var(--page-glow-two), transparent 24%),
    radial-gradient(circle at 68% 84%, var(--page-glow-three), transparent 26%);
}

.group-detail::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  background: var(--group-shell-backdrop);
}

.group-hero-card {
  position: relative;
  overflow: hidden;
  margin-bottom: 1.5rem;
  border-radius: 28px;
  padding: 1.6rem;
  border: 1px solid rgba(255, 255, 255, 0.13);
  box-shadow:
    var(--shadow-lg),
    inset 0 1px 0 rgba(255, 255, 255, 0.07);
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
}

.gd-head {
  position: relative;
  z-index: 1;
  padding: 1.35rem 1.45rem 1.4rem;
  border-radius: 28px;
  margin-bottom: 0;
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  transition:
    background 0.28s ease,
    border-color 0.28s ease,
    box-shadow 0.28s ease;
}

.gd-title {
  font-size: clamp(2rem, 3vw, 2.9rem);
  font-weight: 700;
  letter-spacing: 0;
  color: var(--text-primary);
}

.gd-subtitle {
  margin-top: 0.28rem;
  font-size: 0.98rem;
  color: var(--text-secondary);
}

.card {
  position: relative;
  border-radius: 28px;
  border: 1px solid var(--border-default);
  background: linear-gradient(
    165deg,
    color-mix(in srgb, var(--surface-elevated) 92%, transparent),
    color-mix(in srgb, var(--surface-base) 96%, transparent)
  );
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  transition:
    border-color 0.28s ease,
    box-shadow 0.28s ease;
}

.card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-lg);
}

.card::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: inherit;
  background:
    radial-gradient(
      circle at top left,
      color-mix(in srgb, var(--accent-teal) 14%, transparent),
      transparent 32%
    ),
    radial-gradient(
      circle at bottom right,
      color-mix(in srgb, var(--accent-blue) 10%, transparent),
      transparent 30%
    );
  opacity: 0.9;
}

.card > * {
  position: relative;
  z-index: 1;
}

.card-header {
  background: transparent;
  border-bottom: 1px solid var(--border-default);
}

.card-title {
  color: var(--text-primary);
}

.chat-status {
  color: var(--text-secondary);
}

.chat-alert {
  color: var(--text-primary);
  background: color-mix(in srgb, var(--accent-amber) 16%, transparent);
  border-bottom: 1px solid var(--border-default);
}

.pane--discussion .chat-container {
  position: relative;
  border-radius: 28px;
  border: 1px solid var(--border-default);
  background: linear-gradient(
    165deg,
    color-mix(in srgb, var(--surface-elevated) 92%, transparent),
    color-mix(in srgb, var(--surface-base) 96%, transparent)
  );
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  overflow: hidden;
}

.pane--discussion .chat-header {
  background: transparent !important;
  background-color: transparent !important;
  color: var(--text-primary) !important;
  border-bottom: 1px solid var(--border-default);
}

.pane--discussion .chat-header h3 {
  color: var(--text-primary);
}

.pane--discussion .chat-messages {
  background: transparent;
}

.pane--discussion .chat-input {
  background: transparent;
  border-top: 1px solid var(--border-default);
}

.chat-input-field {
  background: color-mix(in srgb, var(--surface-base) 82%, transparent);
  color: var(--text-primary);
  border: 1px solid var(--border-default);
}

.chat-input-field::placeholder {
  color: var(--text-muted);
}

.chat-input-field:focus {
  border-color: var(--border-strong);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent-teal) 12%, transparent);
}

.chat-btn {
  border: 1px solid var(--border-default);
  background: color-mix(in srgb, var(--surface-elevated) 94%, transparent);
  color: var(--text-primary);
}

.chat-btn:hover {
  border-color: var(--border-strong);
  background: color-mix(in srgb, var(--surface-elevated) 100%, transparent);
}

.chat-btn:disabled,
.chat-btn:disabled:hover {
  cursor: not-allowed;
  opacity: 0.48;
  border-color: var(--border-default);
  background: color-mix(in srgb, var(--surface-elevated) 94%, transparent);
}

@media (max-width: 1180px) {
  .split {
    grid-template-columns: 1fr;
    max-height: none;
    height: auto;
  }

  .mobile-tabs {
    display: none;
  }

  .split .pane {
    display: flex;
    height: auto;
  }

  .pane--discussion .chat-container {
    height: min(72vh, 620px);
    min-height: 420px;
  }

  .card {
    height: auto;
    min-height: 220px;
  }
  .pane--tasks.card {
    min-height: 520px;
  }
  .pane--discussion {
    min-height: 520px;
  }
}

/* Clean page treatment to match Events and Resources. */
.group-detail {
  isolation: auto;
  min-height: calc(100vh - 60px);
  overflow: auto;
  padding: 1rem 1.5rem 1.5rem;
  display: flex;
  flex-direction: column;
  color: var(--charcoal);
  background: var(--bg-light);
  --text-primary: var(--charcoal);
  --text-secondary: #6c757d;
  --text-muted: #8a949e;
  --surface-base: var(--white);
  --surface-elevated: var(--white);
  --border-default: var(--border-light);
  --border-strong: #cfd6dd;
  --accent-blue: var(--air-force-blue);
  --accent-teal: var(--mint-green);
  --accent-amber: var(--warning);
  --shadow-sm: 0 1px 2px var(--shadow);
  --shadow-md: 0 2px 4px var(--shadow);
  --shadow-lg: 0 4px 12px var(--shadow);
}

.group-detail::before,
.group-hero-card::before,
.group-hero-card::after,
.card::before {
  display: none;
}

.group-hero-card {
  margin-bottom: 0.8rem;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  box-shadow: none;
  overflow: visible;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.gd-head {
  padding: 0.85rem 1rem;
  margin-bottom: 0;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  box-shadow: 0 2px 4px var(--shadow);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.gd-head-left {
  padding-left: 0.35rem;
}

.gd-title {
  margin: 0;
  color: var(--charcoal);
  font-size: 1.45rem;
  font-weight: 600;
}

.gd-subtitle {
  margin-top: 0.1rem;
  color: #6c757d;
  font-size: 0.9rem;
}

.group-avatar {
  background: var(--air-force-blue);
  color: var(--white);
  border-color: var(--white);
}

@media (min-width: 1181px) {
  .group-detail {
    height: calc(100vh - 64px - 2rem);
    min-height: 0;
    overflow: hidden;
  }

  .group-hero-card {
    flex: 0 0 auto;
  }

  .split {
    flex: 1 1 auto;
    min-height: 0;
    height: auto;
    max-height: none;
  }

  .split .pane,
  .card,
  .pane--discussion {
    min-height: 0;
  }
}

.mobile-tabs {
  border-bottom-color: var(--border-light);
}

.tab-btn {
  color: var(--charcoal);
}

.tab-btn.active {
  color: var(--air-force-blue);
  border-bottom-color: var(--air-force-blue);
}

.card,
.pane--discussion .chat-container {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  box-shadow: 0 2px 4px var(--shadow);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  transition: box-shadow 0.2s ease;
}

.card:hover,
.pane--discussion .chat-container:hover {
  border-color: var(--border-light);
  box-shadow: 0 4px 12px var(--shadow);
}

.card-header,
.pane--discussion .chat-header {
  background: var(--white) !important;
  color: var(--charcoal) !important;
  border-bottom: 1px solid var(--border-light);
}

.card-title,
.pane--discussion .chat-header h3,
.task-section-title,
.task-label {
  color: var(--charcoal) !important;
}

.chat-status,
.message-date,
.message-time,
.typing-indicator,
.gif-status {
  color: #6c757d !important;
}

.chat-alert {
  color: #6c4b00;
  background: #fff7d6;
  border-bottom: 1px solid #f1dd97;
}

.chat-notice {
  color: var(--air-force-blue);
  background: #eef7f9;
  border-bottom: 1px solid var(--border-light);
}

.pane--discussion .chat-messages {
  background: #f8f9fa;
}

.pane--discussion .chat-input,
.gif-panel {
  background: var(--white);
  border-color: var(--border-light);
}

.chat-input-field,
.gif-search-input {
  background: var(--white);
  color: var(--charcoal);
  border: 1px solid var(--border-light);
  border-radius: 22px;
  padding: 0.7rem 1rem;
  font: inherit;
  line-height: 1.4;
  transition: border-color 0.16s ease, box-shadow 0.16s ease, background 0.16s ease;
}

.chat-input-field::placeholder,
.gif-search-input::placeholder {
  color: #8a949e;
}

.chat-input-field:focus,
.gif-search-input:focus {
  outline: none;
  border-color: var(--air-force-blue);
  background: var(--white);
  box-shadow: 0 0 0 4px rgba(57, 104, 123, 0.10);
}

.chat-input-field {
  /* textarea-specific tweaks for a rounder, friendlier composer */
  min-height: 2.65rem;
  resize: none;
}

.chat-btn {
  border: 1px solid var(--border-light);
  background: var(--white);
  color: var(--air-force-blue);
  border-radius: 999px;
  padding: 0.55rem 0.95rem;
  font-weight: 600;
  transition: border-color 0.16s ease, background 0.16s ease, transform 0.12s ease;
}

.chat-btn:hover {
  border-color: var(--air-force-blue);
  background: #f1f5f7;
  transform: translateY(-1px);
}

.chat-btn:active {
  transform: translateY(0);
}

.chat-btn:disabled,
.chat-btn:disabled:hover {
  color: #98a2ad;
  border-color: var(--border-light);
  background: var(--white);
  transform: none;
}

/* Icon-only chat-actions buttons (paperclip / image / resource panel) */
.chat-actions-strip .chat-btn,
.chat-input-actions .chat-btn {
  width: 2.6rem;
  height: 2.6rem;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* "GIF" glyph mark — small caps label inside a circular button. Matches the
   Tenor / iMessage convention better than a generic image icon. */
.chat-btn-gif-glyph {
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  line-height: 1;
  padding: 0.15rem 0.32rem;
  border: 1.5px solid currentColor;
  border-radius: 4px;
  font-family: var(--font-mono, "SFMono-Regular", "Menlo", monospace);
}

/* Panel-toggle buttons (GIF / Resources) keep an active state while their
   panel is open so the user sees what's currently expanded. */
.chat-btn--toggle.active {
  background: rgba(31, 122, 63, 0.12);
  border-color: var(--dark-green, #1f7a3f);
  color: var(--dark-green, #1f7a3f);
  box-shadow: inset 0 0 0 1px var(--dark-green, #1f7a3f);
}

.chat-btn--toggle.active:hover {
  background: rgba(31, 122, 63, 0.18);
}

.message-avatar {
  background: #8a949e;
}

.message-content,
.message-preview,
.attachment-chip,
.reaction-btn,
.reaction-summary-btn,
.gif-card {
  border: 1px solid var(--border-light);
  background: var(--white);
  color: var(--charcoal);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
}

.message-content {
  position: relative;
  border-radius: 18px;
  padding: 0.55rem 0.9rem 0.45rem;
  transition: box-shadow 0.18s ease, transform 0.18s ease;
  /* Never grow a scrollbar inside a bubble. If content is unusually wide
     (e.g. a giant URL), let it wrap rather than scroll. */
  overflow: visible;
  word-break: break-word;
  overflow-wrap: anywhere;
}

/* Ticks live in the bubble's bottom-right corner via absolute positioning.
   No reserved right-padding on the bubble — that produced a visible empty
   gap on short messages (e.g. "SSS"). On long messages where the last line
   approaches the right edge, the ticks overlay the trailing characters — a
   small inline spacer at the END of the text reserves just enough room on
   the LAST line so the bubble width stays snug. */
.message.own .message-text::after {
  content: "\00a0\00a0\00a0\00a0\00a0\00a0";
  display: inline-block;
  vertical-align: baseline;
}

.message:hover .message-content {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.message-header {
  padding-right: 2.2rem;
}

/* Telegram-style tail rounding — flatten the corner pointing at the avatar. */
.message:not(.own) .message-content {
  border-bottom-left-radius: 6px;
}

.message.own .message-content {
  background: var(--dark-green);
  color: var(--white);
  border-color: var(--dark-green);
  border-bottom-right-radius: 6px;
  box-shadow: 0 2px 8px rgba(31, 122, 63, 0.18);
}

.message.own:hover .message-content {
  box-shadow: 0 4px 14px rgba(31, 122, 63, 0.26);
}

/* Resource chip + open/download popover */
.resource-chip-wrap {
  position: relative;
  display: inline-flex;
}

.resource-choice-popover {
  position: absolute;
  bottom: calc(100% + 0.4rem);
  left: 0;
  z-index: 25;
  display: inline-flex;
  flex-direction: column;
  gap: 0.35rem;
  background: var(--white);
  border: 1px solid var(--border-default);
  border-radius: 999px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.16);
  padding: 0.35rem 0.45rem;
  color: var(--text-primary);
  font-size: 0.78rem;
  animation: kebab-pop 0.14s ease-out;
  white-space: nowrap;
}

.resource-choice-status {
  font-size: 0.72rem;
  color: var(--text-muted);
  padding: 0 0.4rem;
}

.resource-choice-actions {
  display: flex;
  gap: 0.4rem;
  align-items: center;
}

.resource-choice-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  padding: 0;
  border: 1px solid var(--border-default);
  border-radius: 50%;
  background: var(--white);
  color: var(--air-force-blue);
  cursor: pointer;
  font-size: 0.82rem;
  transition: background 0.14s ease, color 0.14s ease, border-color 0.14s ease, transform 0.12s ease;
}

.resource-choice-btn:hover:not(:disabled) {
  background: rgba(57, 104, 123, 0.10);
  border-color: var(--air-force-blue);
  transform: translateY(-1px);
}

.resource-choice-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.resource-choice-btn--danger {
  color: #c0392b;
  border-color: rgba(192, 57, 43, 0.4);
}

.resource-choice-btn--danger:hover:not(:disabled) {
  background: rgba(192, 57, 43, 0.10);
  border-color: #c0392b;
  color: #c0392b;
}

/* Attachment chips — softer, rounder */
.attachment-chip {
  border-radius: 14px;
  padding: 0.5rem 0.7rem;
  transition: border-color 0.16s ease, transform 0.12s ease;
}

.attachment-chip:hover {
  border-color: var(--air-force-blue);
  transform: translateY(-1px);
}

/* Message action buttons (Reply / Edit / Delete) — pill chips on hover */
.message-action-btn {
  border-radius: 999px;
  padding: 0.18rem 0.6rem !important;
  transition: background 0.14s ease, color 0.14s ease;
}

.message-action-btn:hover:not(:disabled) {
  background: rgba(57, 104, 123, 0.10);
}

.message.own .message-action-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.18);
}

/* Inline action cluster inside the message header (sits after the time).
   Reply + Smile are always visible; the kebab (Edit/Delete dropdown) only
   shows up while ``canManageMessage`` is true. */
.message-inline-actions {
  display: inline-flex;
  align-items: center;
  gap: 0.1rem;
  margin-left: 0.35rem;
  position: relative;
}

.inline-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  border-radius: 50%;
  cursor: pointer;
  font-size: 0.72rem;
  transition: background 0.14s ease, color 0.14s ease;
}

.inline-action-btn:hover:not(:disabled),
.inline-action-btn.active {
  background: rgba(57, 104, 123, 0.10);
  color: var(--air-force-blue);
}

.message.own .inline-action-btn {
  color: rgba(255, 255, 255, 0.78);
}

.message.own .inline-action-btn:hover:not(:disabled),
.message.own .inline-action-btn.active {
  background: rgba(255, 255, 255, 0.20);
  color: var(--white);
}

.inline-kebab-wrap {
  position: relative;
  display: inline-flex;
}

.inline-kebab-menu {
  position: absolute;
  top: calc(100% + 0.35rem);
  right: 0;
  min-width: 140px;
  z-index: 20;
  display: flex;
  flex-direction: column;
  background: var(--white);
  border: 1px solid var(--border-default);
  border-radius: 10px;
  box-shadow: 0 10px 26px rgba(0, 0, 0, 0.16);
  padding: 0.25rem;
  animation: kebab-pop 0.14s ease-out;
}

.inline-kebab-item {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.45rem 0.7rem;
  border: none;
  background: transparent;
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 0.85rem;
  text-align: left;
  cursor: pointer;
  transition: background 0.12s ease;
}

.inline-kebab-item i {
  width: 0.95rem;
  text-align: center;
  color: var(--text-secondary);
}

.inline-kebab-item:hover:not(:disabled) {
  background: rgba(57, 104, 123, 0.10);
}

.inline-kebab-item--danger {
  color: #c0392b;
}

.inline-kebab-item--danger i {
  color: #c0392b;
}

.inline-kebab-item--danger:hover:not(:disabled) {
  background: rgba(192, 57, 43, 0.10);
}

.inline-kebab-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@keyframes kebab-pop {
  from { opacity: 0; transform: translateY(-4px) scale(0.96); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

/* Inline picker popout — pops UPWARD above the message header so it never
   covers the message body. Anchored to the right edge of the inline action
   cluster (where the smile button sits). */
.reaction-picker--inline {
  position: absolute;
  bottom: calc(100% + 0.35rem);
  top: auto;
  right: 0;
  left: auto;
  z-index: 30;
  padding: 0.3rem 0.4rem;
  border: 1px solid var(--border-default);
  border-radius: 999px;
  background: var(--white);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.18);
  display: inline-flex;
  gap: 0.2rem;
  white-space: nowrap;
  animation: kebab-pop 0.14s ease-out;
}

.reaction-picker--inline .reaction-btn {
  width: 2rem;
  height: 2rem;
  padding: 0;
  border: none;
  background: transparent;
  border-radius: 50%;
  font-size: 1.05rem;
  cursor: pointer;
  transition: transform 0.12s ease, background 0.12s ease;
}

.reaction-picker--inline .reaction-btn:hover {
  transform: scale(1.18);
  background: #f1f5f7;
}

/* Floating hover toolbar — DEPRECATED: replaced by inline header actions.
   The .message-hover-toolbar block is preserved below as ``display: none``
   in case other places still wire it up. */
.message-hover-toolbar {
  display: none !important;
}

._unused_message_hover_toolbar_legacy {
  position: absolute;
  top: 0.35rem;
  right: 0.45rem;
  display: inline-flex;
  align-items: center;
  gap: 0.1rem;
  padding: 0.15rem;
  border: 1px solid var(--border-default);
  border-radius: 999px;
  background: var(--white);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  opacity: 0;
  pointer-events: none;
  transform: translateY(-2px);
  transition: opacity 0.14s ease, transform 0.14s ease;
  z-index: 3;
}

.message.own .message-hover-toolbar {
  top: 0.4rem;
  right: 0.4rem;
  left: auto;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.18rem;
  border-radius: 16px;
  transform: translateX(4px);
}

.message:hover .message-hover-toolbar,
.message-hover-toolbar:focus-within {
  opacity: 1;
  pointer-events: auto;
  transform: translateY(0);
}

.message.own:hover .message-hover-toolbar,
.message.own .message-hover-toolbar:focus-within {
  transform: translateX(0);
}

.hover-tool-btn {
  width: 1.7rem;
  height: 1.7rem;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.78rem;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  border-radius: 50%;
  cursor: pointer;
  transition: background 0.12s ease, color 0.12s ease, transform 0.12s ease;
}

.hover-tool-btn:hover:not(:disabled) {
  background: #f1f5f7;
  color: var(--air-force-blue);
  transform: scale(1.06);
}

.hover-tool-btn--danger:hover:not(:disabled) {
  color: #c0392b;
  background: rgba(192, 57, 43, 0.10);
}

.hover-tool-btn--reaction.active {
  background: rgba(31, 122, 63, 0.12);
  color: var(--dark-green, #1f7a3f);
}

.hover-tool-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Picker popout for own-messages — anchors next to the vertical toolbar
   and pops out to the LEFT (into the bubble) so it never escapes the
   container's right edge. */
.reaction-picker--own {
  bottom: auto;
  top: 50%;
  right: calc(100% + 0.45rem);
  left: auto;
  transform: translateY(-50%);
  animation: reaction-picker-own-pop 0.14s ease-out;
}

@keyframes reaction-picker-own-pop {
  from { opacity: 0; transform: translate(6px, -50%) scale(0.94); }
  to { opacity: 1; transform: translate(0, -50%) scale(1); }
}

/* Animated typing indicator — three bouncing dots inside a soft pill. */
.typing-indicator {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.45rem 0.85rem;
  margin: 0.25rem 0.9rem 0.4rem;
  width: fit-content;
  border-radius: 999px;
  background: rgba(57, 104, 123, 0.08);
  color: var(--air-force-blue);
  font-size: 0.78rem;
  font-weight: 600;
  animation: typing-pill-pop 0.18s ease-out;
}

.typing-dots {
  display: inline-flex;
  gap: 0.18rem;
  align-items: flex-end;
  height: 0.7rem;
}

.typing-dots span {
  width: 0.3rem;
  height: 0.3rem;
  border-radius: 50%;
  background: currentColor;
  display: inline-block;
  animation: typing-dot-bounce 1.2s infinite ease-in-out both;
}

.typing-dots span:nth-child(1) { animation-delay: -0.32s; }
.typing-dots span:nth-child(2) { animation-delay: -0.16s; }
.typing-dots span:nth-child(3) { animation-delay: 0s; }

@keyframes typing-dot-bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
  40% { transform: translateY(-3px); opacity: 1; }
}

@keyframes typing-pill-pop {
  from { opacity: 0; transform: translateY(4px) scale(0.94); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

/* Vue <Transition name="typing"> classes — slide+fade as the pill enters/leaves */
.typing-enter-active,
.typing-leave-active {
  transition: opacity 0.16s ease, transform 0.16s ease;
}
.typing-enter-from,
.typing-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

.message.own .message-author,
.message.own .message-time,
.message.own .message-date,
.pane--discussion .message.own .message-text,
.message.own .message-action-btn {
  color: var(--white) !important;
}

.message-edited {
  background: #eef3f5;
  color: var(--air-force-blue);
}

.reaction-pick-group {
  position: absolute;
  bottom: 0.3rem;
  left: 0.6rem;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  z-index: 4;
  min-height: 1.4rem;
}

/* Reaction chips stay at bottom-left for own and received alike — the smile
   button for own messages lives separately in the right-side toolbar. */

/* When reactions exist, the chip strip permanently occupies the slot;
   it's always visible (not gated by hover) so the count stays readable. */
.reaction-pick-group.has-reactions .message-reactions {
  opacity: 1;
  pointer-events: auto;
}

/* Reserve room at the bottom of the bubble so the chip strip (positioned
   ``bottom: -0.85rem``) doesn't crash into the next message. */
.message-content:has(.reaction-pick-group.has-reactions) {
  padding-bottom: 1.5rem;
}

.reaction-picker-toggle {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.85rem;
  height: 1.85rem;
  border: 1px solid var(--border-default);
  border-radius: 50%;
  background: var(--white);
  color: var(--air-force-blue);
  cursor: pointer;
  opacity: 0;
  pointer-events: none;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.14);
  transition:
    opacity 0.16s ease,
    border-color 0.16s ease,
    background 0.16s ease,
    transform 0.16s ease;
}

.message:hover .reaction-picker-toggle,
.message-content:hover .reaction-picker-toggle,
.reaction-pick-group:hover .reaction-picker-toggle,
.reaction-pick-group:focus-within .reaction-picker-toggle,
.reaction-pick-group.active .reaction-picker-toggle,
.reaction-picker-toggle.active {
  opacity: 1;
  pointer-events: auto;
}

.reaction-picker-toggle:hover,
.reaction-picker-toggle.active {
  border-color: var(--air-force-blue);
  background: #f1f5f7;
  transform: scale(1.04);
}

/* Smaller "+" smiley when sitting next to existing chips */
.reaction-pick-group.has-reactions .reaction-picker-toggle {
  width: 1.6rem;
  height: 1.6rem;
  font-size: 0.85rem;
}

.reaction-picker-toggle:hover,
.reaction-picker-toggle.active {
  border-color: var(--air-force-blue);
  background: #f1f5f7;
}

.message.own .reaction-picker-toggle {
  border-color: rgba(255, 255, 255, 0.56);
  background: rgba(255, 255, 255, 0.16);
  color: var(--white);
}

.message.own .reaction-picker-toggle:hover,
.message.own .reaction-picker-toggle.active {
  border-color: var(--white);
  background: rgba(255, 255, 255, 0.24);
}

/* Click-only picker. Renders only when ``activeReactionPickerMessageId``
   matches this message — no hover gating in CSS. Anchored above the smile
   button (WhatsApp-style) so it never collides with the bubble below. */
.reaction-picker {
  position: absolute;
  bottom: calc(100% + 0.35rem);
  right: 0;
  z-index: 6;
  display: inline-flex;
  gap: 0.2rem;
  padding: 0.3rem 0.4rem;
  border: 1px solid var(--border-default);
  border-radius: 999px;
  background: var(--white);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.18);
  white-space: nowrap;
  animation: reaction-picker-pop 0.14s ease-out;
}

.message.own .reaction-picker {
  right: auto;
  left: 0;
}

.reaction-picker .reaction-btn {
  width: 2rem;
  height: 2rem;
  padding: 0;
  border-radius: 50%;
  border-color: transparent;
  background: transparent;
  box-shadow: none;
  font-size: 1.05rem;
  transition: transform 0.12s ease, background 0.12s ease;
}

.reaction-picker .reaction-btn:hover {
  transform: scale(1.18);
  background: #f1f5f7;
  border-color: transparent;
}

@keyframes reaction-picker-pop {
  from {
    opacity: 0;
    transform: translateY(4px) scale(0.92);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.reaction-btn:hover,
.reaction-summary-btn:hover {
  border-color: var(--air-force-blue);
  background: #f8f9fa;
}

/* Task pane theming overrides (legacy `.add-subtask-btn` and the
   `.task-item:hover` reset removed -- handled by the modernized rules above). */

.add-subtask-btn:disabled,
.add-subtask-btn:disabled:hover {
  cursor: not-allowed;
  color: #98a2ad;
  border-color: var(--border-light);
  background: #f3f5f6;
  opacity: 0.62;
  box-shadow: none;
}

.group-detail-loading {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.group-loading-head {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.group-loading-avatar {
  width: 48px;
  height: 48px;
  flex: 0 0 48px;
  border-radius: 50%;
}

.group-loading-title-stack {
  flex: 1;
  min-width: 160px;
}

.group-loading-meta,
.group-loading-panel-header,
.group-loading-filter-row,
.group-loading-row,
.group-loading-message {
  display: flex;
  align-items: center;
}

.group-loading-meta {
  gap: 0.45rem;
  margin-top: 0.55rem;
}

.group-loading-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(320px, 0.92fr);
  gap: 1.5rem;
  align-items: stretch;
}

.group-loading-panel {
  min-height: 520px;
  padding: 1.5rem;
}

.group-loading-chat {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  box-shadow: 0 2px 4px var(--shadow);
}

.group-loading-panel-header {
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-light);
}

.group-loading-filter-row {
  flex-wrap: wrap;
  gap: 0.65rem;
  padding: 1rem 0;
}

.group-loading-list,
.group-loading-messages {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.group-loading-row {
  gap: 0.85rem;
  padding: 0.6rem 0;
}

.group-loading-row-copy,
.group-loading-bubble {
  flex: 1;
  min-width: 0;
}

.group-loading-message {
  gap: 0.8rem;
}

.group-loading-message--own {
  flex-direction: row-reverse;
}

.group-loading-message--own .group-loading-bubble {
  flex: 0 1 72%;
}

.group-loading-bubble {
  padding: 0.85rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: #f8f9fa;
}

.skeleton-block {
  position: relative;
  overflow: hidden;
  border-radius: 6px;
  background: #e8edf1;
}

.skeleton-title {
  width: min(360px, 78%);
  height: 2rem;
}

.skeleton-subtitle {
  width: min(300px, 64%);
  height: 1rem;
  margin-top: 0.65rem;
}

.skeleton-pill {
  width: 130px;
  height: 1.55rem;
  border-radius: 999px;
}

.skeleton-pill--short {
  width: 92px;
}

.skeleton-select {
  width: 180px;
  height: 2.35rem;
}

.skeleton-heading {
  width: 120px;
  height: 1.35rem;
}

.skeleton-button {
  width: 116px;
  height: 2rem;
}

.skeleton-filter {
  width: 116px;
  height: 2.35rem;
}

.skeleton-dot {
  width: 24px;
  height: 24px;
  flex: 0 0 24px;
  border-radius: 50%;
}

.skeleton-line {
  width: 100%;
  height: 0.95rem;
}

.skeleton-line--short {
  width: 58%;
  margin-top: 0.55rem;
}

.skeleton-status {
  width: 68px;
  height: 1.25rem;
}

.skeleton-message-avatar {
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  border-radius: 50%;
}

.skeleton-composer {
  height: 74px;
  margin-top: 1rem;
}

@media (max-width: 1180px) {
  .group-loading-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .gd-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .gd-head-actions {
    align-items: stretch;
    width: 100%;
  }

  .group-members-btn {
    justify-content: center;
    width: 100%;
  }

  .task-toolbar { gap: 0.5rem; }
  .task-search { flex: 1 1 100%; }
  .task-toolbar-controls { width: 100%; justify-content: flex-end; }
  .task-filter-panel { left: 0; right: auto; width: calc(100vw - 2rem); max-width: 320px; }

  .task-row-actions {
    opacity: 1; /* hover doesn't exist on touch -- always show actions */
  }
  .task-icon-btn { width: 34px; height: 34px; }

  .task-bulk-bar {
    bottom: 1rem;
    width: calc(100% - 1.5rem);
    justify-content: space-between;
  }

  .task-form-grid {
    grid-template-columns: 1fr;
  }

  .group-loading-head,
  .group-loading-panel-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .skeleton-select,
  .skeleton-button,
  .skeleton-filter {
    width: 100%;
  }
}
</style>
