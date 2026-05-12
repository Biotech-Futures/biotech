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
            <label class="group-switcher" for="group-switcher">
              <span>Group</span>
              <select
                id="group-switcher"
                :value="backendGroupId"
                :disabled="isLoadingGroupOptions || availableGroups.length <= 1"
                @change="switchGroup"
              >
                <option v-if="isLoadingGroupOptions" value="">Loading groups...</option>
                <option v-for="option in availableGroups" :key="option.id" :value="option.id">
                  {{ option.memberCount ? `${option.name} (${option.memberCount})` : option.name }}
                </option>
              </select>
            </label>
            <span v-if="groupOptionsError" class="group-switcher-error">{{
              groupOptionsError
            }}</span>
          </div>
        </div>
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
            <div class="task-filter-bar">
              <label class="task-filter-field">
                <span>Search</span>
                <input
                  v-model.trim="taskFilters.search"
                  type="search"
                  placeholder="Task name"
                  @keyup.enter="loadTasks"
                />
              </label>
              <label class="task-filter-field">
                <span>Type</span>
                <select v-model="taskFilters.taskType">
                  <option value="">All</option>
                  <option value="group">Group</option>
                  <option value="individual">Individual</option>
                </select>
              </label>
              <label class="task-filter-field">
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
              <label class="task-filter-field">
                <span>Done</span>
                <select v-model="taskFilters.completed">
                  <option value="">All</option>
                  <option value="true">Done</option>
                  <option value="false">Open</option>
                </select>
              </label>
              <label class="task-filter-field">
                <span>Sort</span>
                <select v-model="taskFilters.ordering">
                  <option
                    v-for="option in TASK_ORDERING_OPTIONS"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select>
              </label>
              <label class="task-deleted-toggle">
                <input v-model="taskFilters.showDeleted" type="checkbox" />
                Deleted
              </label>
              <button
                type="button"
                class="btn btn-outline btn-sm"
                :disabled="isLoadingTasks"
                @click="loadTasks"
              >
                Apply
              </button>
            </div>

            <div v-if="selectedTaskIds.size" class="task-bulk-bar">
              <span>{{ selectedTaskIds.size }} selected</span>
              <button
                type="button"
                class="btn btn-primary btn-sm"
                :disabled="isBulkUpdatingTasks"
                @click="bulkSetTaskCompletion(true)"
              >
                Mark done
              </button>
              <button
                type="button"
                class="btn btn-outline btn-sm"
                :disabled="isBulkUpdatingTasks"
                @click="bulkSetTaskCompletion(false)"
              >
                Mark open
              </button>
              <button
                type="button"
                class="btn btn-outline btn-sm"
                :disabled="isBulkUpdatingTasks"
                @click="clearTaskSelection"
              >
                Clear
              </button>
            </div>

            <div v-if="taskError" class="chat-alert" style="margin-bottom: 1rem">
              {{ taskError }}
            </div>
            <div v-if="isLoadingTasks" class="chat-alert" style="margin-bottom: 1rem">
              Loading tasks...
            </div>

            <div v-for="section in taskSections" :key="section.key" class="task-section">
              <div class="task-section-header">
                <div class="task-section-title">
                  <i :class="section.icon"></i>
                  {{ section.title }}
                </div>
                <div class="task-section-status">
                  {{ section.completed }}/{{ section.total }} Completed
                </div>
              </div>
              <div class="task-list">
                <div
                  v-for="row in section.rows"
                  :key="row.task.id"
                  class="task-item"
                  :class="{ 'is-subtask': row.depth > 0, 'is-deleted': row.task.deletedAt }"
                  :style="{ paddingLeft: `${0.85 + row.depth * 1.35}rem` }"
                >
                  <label class="task-select-control" title="Select task">
                    <input
                      type="checkbox"
                      :checked="isTaskSelected(row.task.id)"
                      :disabled="row.task.deletedAt || !canToggleTask(row.task)"
                      @change="setTaskSelectedFromEvent(row.task.id, $event)"
                    />
                  </label>
                  <div class="task-body">
                    <div :class="['task-label', { completed: row.task.completed }]">
                      {{ row.task.name }}
                    </div>
                    <div v-if="row.task.description" class="task-description">
                      {{ row.task.description }}
                    </div>
                    <div class="task-meta">
                      <span v-if="row.task.dueDate"
                        ><i class="fas fa-calendar"></i> {{ formatDate(row.task.dueDate) }}</span
                      >
                      <span v-if="row.task.status"
                        ><i class="fas fa-circle"></i> {{ formatTaskStatus(row.task.status) }}</span
                      >
                      <span v-if="row.task.assignedUser"
                        ><i class="fas fa-user"></i> User {{ row.task.assignedUser }}</span
                      >
                      <span v-if="row.task.creatorRole"
                        ><i class="fas fa-id-badge"></i>
                        {{ formatTaskStatus(row.task.creatorRole) }}</span
                      >
                      <span v-if="row.task.deletedAt"><i class="fas fa-trash"></i> Deleted</span>
                    </div>
                  </div>
                  <div class="task-row-actions">
                    <button
                      type="button"
                      :class="['task-status-toggle', { 'is-complete': row.task.completed }]"
                      :disabled="
                        isUpdatingTask(row.task.id) ||
                        row.task.deletedAt ||
                        !canToggleTask(row.task)
                      "
                      :title="
                        canToggleTask(row.task)
                          ? 'Toggle task status'
                          : 'You can view this task status only'
                      "
                      :aria-pressed="row.task.completed"
                      :aria-label="
                        row.task.completed
                          ? `Mark ${row.task.name} open`
                          : `Mark ${row.task.name} done`
                      "
                      @click="toggleTask(row.task)"
                    >
                      <i :class="row.task.completed ? 'fas fa-check-circle' : 'fas fa-circle'"></i>
                      <span>{{ row.task.completed ? 'Done' : 'Open' }}</span>
                    </button>
                    <button
                      type="button"
                      class="btn btn-outline btn-sm add-subtask-btn"
                      :disabled="
                        isLoadingTasks ||
                        row.task.deletedAt ||
                        !canCreateTaskType(row.task.taskType, row.task)
                      "
                      title="Add a sub-task"
                      @click="openCreateTaskDialog(row.task.taskType, row.task)"
                    >
                      <i class="fas fa-plus"></i>
                      Sub-task
                    </button>
                    <button
                      v-if="canManageTask(row.task)"
                      type="button"
                      class="btn btn-outline btn-sm"
                      :disabled="isLoadingTasks || row.task.deletedAt"
                      title="Edit task"
                      @click="openEditTaskDialog(row.task)"
                    >
                      <i class="fas fa-pen"></i>
                      Edit
                    </button>
                    <button
                      v-if="canManageTask(row.task)"
                      type="button"
                      class="btn btn-outline btn-sm"
                      :disabled="isDeletingTask(row.task.id) || row.task.deletedAt"
                      title="Delete task"
                      @click="removeTask(row.task)"
                    >
                      <i class="fas fa-trash"></i>
                      Delete
                    </button>
                  </div>
                </div>

                <div v-if="!section.rows.length" class="task-empty-state">
                  No {{ section.title.toLowerCase() }} are available yet.
                </div>
              </div>
            </div>
          </div>

          <div
            v-if="taskDialogOpen"
            class="task-dialog-backdrop"
            role="dialog"
            aria-modal="true"
            :aria-label="taskDialogTitle"
          >
            <form class="task-dialog" @submit.prevent="saveTask">
              <div class="task-dialog-header">
                <h4>{{ taskDialogTitle }}</h4>
                <button
                  type="button"
                  class="task-dialog-close"
                  title="Close"
                  @click="closeTaskDialog"
                >
                  <i class="fas fa-times"></i>
                </button>
              </div>

              <div v-if="taskFormError" class="chat-alert">
                {{ taskFormError }}
              </div>

              <label class="task-form-field task-form-field--wide">
                <span>Name</span>
                <input v-model.trim="taskForm.name" type="text" maxlength="255" required />
              </label>

              <label class="task-form-field task-form-field--wide">
                <span>Description</span>
                <textarea v-model.trim="taskForm.description" rows="3"></textarea>
              </label>

              <div class="task-form-grid">
                <label class="task-form-field">
                  <span>Status</span>
                  <select v-model="taskForm.status">
                    <option
                      v-for="option in TASK_STATUS_OPTIONS"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                </label>

                <label class="task-form-field">
                  <span>Due date</span>
                  <input v-model="taskForm.dueDate" type="datetime-local" />
                </label>

                <label class="task-form-field">
                  <span>Type</span>
                  <select v-model="taskForm.taskType" :disabled="taskDialogMode === 'edit'">
                    <option
                      v-for="option in allowedTaskTypeOptions"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                </label>

                <label v-if="taskForm.taskType === 'individual'" class="task-form-field">
                  <span>Assignee user id</span>
                  <input
                    v-model.trim="taskForm.assignedUser"
                    type="number"
                    min="1"
                    :disabled="taskDialogMode === 'edit'"
                    required
                  />
                </label>
              </div>

              <div class="task-dialog-actions">
                <button type="button" class="btn btn-outline btn-sm" @click="closeTaskDialog">
                  Cancel
                </button>
                <button type="submit" class="btn btn-primary btn-sm" :disabled="isSavingTask">
                  {{ isSavingTask ? 'Saving...' : 'Save task' }}
                </button>
              </div>
            </form>
          </div>
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
                  class="mentions-toggle"
                  :class="{ active: showMentionInbox }"
                  title="Mentions"
                  @click="toggleMentionInbox"
                >
                  <i class="fas fa-at"></i>
                  <span v-if="mentionUnreadCount" class="mention-badge">{{ mentionUnreadCount }}</span>
                </button>
                <span class="chat-status">
                  <template v-if="isLoadingMessages">Loading...</template>
                  <template v-else-if="wsConnectionState === 'connected'">Live</template>
                  <template v-else>Offline</template>
                </span>
              </div>
            </div>

            <div v-if="chatError" class="chat-alert">
              {{ chatError }}
            </div>
            <div v-if="chatNotice" class="chat-notice">
              {{ chatNotice }}
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
                  <span>{{ mention.sender_name || `User ${mention.sender_user_id}` }}</span>
                  <strong>{{ mention.message_text || 'Message was deleted.' }}</strong>
                  <small>{{ formatDate(mention.sent_at) }} {{ formatTime(mention.sent_at) }}</small>
                </button>
                <div v-if="!mentionItems.length && !mentionInboxError" class="gif-status">
                  No mentions yet.
                </div>
              </div>
            </div>

            <div class="chat-messages" ref="msgList" @scroll="handleMessagesScroll">
              <button
                v-if="nextMessagesBefore"
                type="button"
                class="load-older-messages"
                :disabled="isLoadingOlderMessages"
                @click="loadOlderMessages"
              >
                {{ isLoadingOlderMessages ? 'Loading...' : 'Load older messages' }}
              </button>
              <div
                v-for="message in messages"
                :key="message.id"
                :class="['message', { own: message.isOwn, pending: message.isLocalOnly }]"
              >
                <div class="message-avatar">{{ getInitials(message.author) }}</div>
                <div class="message-content">
                  <div class="message-header">
                    <span class="message-author">{{ message.author }}</span>
                    <span class="message-meta">
                      <span v-if="message.editedAt" class="message-edited">edited</span>
                      <span class="message-date">{{ formatDate(message.date) }}</span>
                      <span class="message-time">{{ message.time }}</span>
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
                    <a
                      v-for="attachment in message.attachments"
                      :key="attachment.id || attachment.attachment_filename"
                      :href="getAttachmentHref(attachment)"
                      class="attachment-chip"
                      @click.prevent="downloadAttachment(attachment)"
                    >
                      <i class="fas fa-paperclip"></i>
                      {{ getAttachmentLabel(attachment) }}
                    </a>
                  </div>

                  <div v-if="message.resources?.length" class="message-attachments">
                    <RouterLink
                      v-for="resource in message.resources"
                      :key="resource.resource_id || resource.id"
                      :to="`/resources/${resource.resource_id || resource.id}`"
                      class="attachment-chip"
                    >
                      <i class="fas fa-book-open"></i>
                      {{ getResourceLabel(resource) }}
                    </RouterLink>
                  </div>

                  <div v-if="message.preview" class="message-preview">
                    <img v-if="message.preview.img" :src="message.preview.img" alt="" />
                    <strong v-if="message.preview.title">{{ message.preview.title }}</strong>
                    <span v-if="message.preview.desc">{{ message.preview.desc }}</span>
                  </div>

                  <button
                    type="button"
                    class="reaction-picker-toggle"
                    :class="{ active: activeReactionPickerMessageId === message.id }"
                    :disabled="!supportsMessageReactions"
                    title="Add reaction"
                    aria-label="Add reaction"
                    @click="toggleReactionPicker(message.id)"
                  >
                    <i class="fas fa-smile"></i>
                  </button>

                  <div
                    v-if="activeReactionPickerMessageId === message.id"
                    class="reaction-picker"
                    role="menu"
                  >
                    <button
                      v-for="emoji in CHAT_REACTION_OPTIONS"
                      :key="`${message.id}-${emoji}`"
                      type="button"
                      class="reaction-btn"
                      :disabled="!supportsMessageReactions"
                      :title="
                        supportsMessageReactions
                          ? 'Add reaction'
                          : 'Reactions are not available yet'
                      "
                      @click="reactToMessage(message.id, emoji)"
                    >
                      <span>{{ emoji }}</span>
                    </button>
                  </div>

                  <div v-if="hasMessageReactions(message)" class="message-reactions">
                    <button
                      v-for="[emoji, count] in Object.entries(message.reactions)"
                      :key="`${message.id}-${emoji}-summary`"
                      type="button"
                      class="reaction-summary-btn"
                      :title="supportsMessageReactions ? 'Toggle reaction' : 'Reactions unavailable'"
                      :disabled="!supportsMessageReactions"
                      @click="reactToMessage(message.id, emoji)"
                    >
                      <span>{{ emoji }}</span>
                      <span class="reaction-count">{{ count }}</span>
                    </button>
                  </div>

                  <div
                    v-if="message.isOwn && (message.readCount || message.deliveredCount)"
                    class="message-receipt"
                  >
                    <i class="fas fa-check-double"></i>
                    <span v-if="message.readCount">Read by {{ message.readCount }}</span>
                    <span v-else>Delivered to {{ message.deliveredCount }}</span>
                  </div>
                  <div class="message-actions">
                    <button type="button" class="message-action-btn" @click="setReplyTarget(message)">
                      Reply
                    </button>
                    <button
                      v-if="canManageMessage(message)"
                      type="button"
                      class="message-action-btn"
                      @click="startMessageEdit(message)"
                    >
                      Edit
                    </button>
                    <button
                      v-if="canManageMessage(message)"
                      type="button"
                      class="message-action-btn"
                      :disabled="isDeletingMessageId === message.id"
                      @click="deleteMessage(message)"
                    >
                      Delete
                    </button>
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

            <div v-if="typingIndicatorText" class="typing-indicator">
              {{ typingIndicatorText }}
            </div>

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
                    placeholder="Search GIFs"
                    @keydown.enter.prevent="searchGifs"
                  />
                  <button type="button" class="btn btn-outline btn-sm" @click="searchGifs">
                    Search
                  </button>
                </div>
                <div v-if="gifError" class="gif-status">{{ gifError }}</div>
                <div class="gif-grid">
                  <button
                    v-for="gif in gifResults"
                    :key="gif.id"
                    type="button"
                    class="gif-card"
                    @click="sendGifMessage(gif)"
                  >
                    <img :src="gif.previewUrl || gif.url" :alt="gif.title" />
                    <span>{{ gif.title }}</span>
                  </button>
                </div>
                <div v-if="isLoadingGifs" class="gif-status">Loading GIFs...</div>
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
                ></textarea>
                <div v-if="showMentionSuggestions" class="mention-suggestions">
                  <button
                    v-for="(member, index) in mentionSuggestions"
                    :key="member.userId"
                    type="button"
                    class="mention-suggestion"
                    :class="{ active: index === activeMentionSuggestionIndex }"
                    @mousedown.prevent="insertMention(member)"
                  >
                    <i class="fas fa-at"></i>
                    <span>{{ member.label }}</span>
                    <small>{{ member.role }}</small>
                  </button>
                </div>
                <div class="chat-actions">
                  <button
                    class="chat-btn"
                    type="button"
                    :title="supportsGifs ? 'GIF picker' : 'GIF search is not available yet'"
                    :disabled="!supportsGifs"
                    @click="toggleGifPanel"
                  >
                    <i class="fas fa-image"></i>
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
                    class="chat-btn"
                    type="button"
                    title="Attach resource"
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
import { buildSessionHeaders, ensureCsrfCookie } from '@/utils/csrf'
import { apiErrorFromResponse } from '@/utils/apiError'
import { fetchResources } from '@/utils/resourcesAPI'
import {
  bulkToggleTasks,
  createTask as createTaskRequest,
  deleteTask as deleteTaskRequest,
  listTasks,
  toggleTaskCompletion,
  updateTask as updateTaskRequest,
} from '@/utils/tasksAPI'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const supportsGifs = false
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

// Active mobile tab
const activeTab = ref('tasks')

// Live task state
const tasks = ref([])
const isLoadingTasks = ref(false)
const taskError = ref('')
const updatingTaskIds = ref(new Set())
const deletingTaskIds = ref(new Set())
const selectedTaskIds = ref(new Set())
const isBulkUpdatingTasks = ref(false)
const taskFilters = ref({
  taskType: '',
  status: '',
  completed: '',
  search: '',
  ordering: 'due_date',
  showDeleted: false,
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

const TASK_ORDERING_OPTIONS = [
  { value: 'due_date', label: 'Due date' },
  { value: '-due_date', label: 'Due date desc' },
  { value: '-updated_at', label: 'Recently updated' },
  { value: 'status', label: 'Status' },
]

const messages = ref([])

const newMessage = ref('')
const composer = ref(null)
const msgList = ref(null)
const fileInputRef = ref(null)
const isLoadingMessages = ref(false)
const isLoadingOlderMessages = ref(false)
const isSendingMessage = ref(false)
const isUploadingFile = ref(false)
const isUpdatingMessage = ref(false)
const isDeletingMessageId = ref(null)
const isLoadingGifs = ref(false)
const chatError = ref('')
const chatNotice = ref('')
const gifError = ref('')
const showGifPanel = ref(false)
const gifQuery = ref('')
const gifResults = ref([])
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
const typingUsers = ref([])
const wsConnectionState = ref('offline')
const nextMessagesBefore = ref(null)
const nextMessagesAfter = ref(null)
const replyTarget = ref(null)
const editingMessageId = ref(null)
const editingMessageText = ref('')
const manageWindowNow = ref(Date.now())
const activeReactionPickerMessageId = ref(null)
const isChatAwayFromBottom = ref(false)
const hasScrollableMessages = ref(false)

let chatSocket = null
let typingStopTimer = null
let manageWindowTimer = null
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

const formatDate = (d) => {
  const date = new Date(d)
  if (Number.isNaN(date.getTime())) return d
  return date.toLocaleDateString('en-AU', { year: 'numeric', month: 'short', day: 'numeric' })
}

const formatTime = (value) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
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
  const mentorIds = groupMemberships.value
    .filter((item) =>
      String(item.role || '')
        .toLowerCase()
        .includes('mentor'),
    )
    .map((item) => item.userId)
    .filter(Boolean)
  const items = []

  if (mentorIds.length) {
    items.push(`Mentor: ${mentorIds.map((id) => `User ${id}`).join(', ')}`)
  }
  if (isLoadingMembers.value) {
    items.push('Loading members...')
  } else if (membersError.value) {
    items.push(membersError.value)
  }

  return items
})

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

const buildGifSearchUrl = (query) =>
  `${API_BASE_URL}/api/v1/chat/gifs/search?q=${encodeURIComponent(query)}`

const buildGifTrendingUrl = () =>
  `${API_BASE_URL}/api/v1/chat/gifs/trending`

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
  role: item?.membership_role || '',
  joinedAt: item?.joined_at || '',
  leftAt: item?.left_at || '',
})

const normalizeMentionMember = (item) => {
  const userId = Number(item?.userId || item?.user || item?.id || 0)
  const role = formatTaskStatus(item?.role || item?.membership_role || 'member') || 'Member'
  return {
    userId,
    role,
    label: userId === currentUserId.value ? 'You' : `User ${userId}`,
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

  try {
    const [groupsData, membershipsData] = await Promise.all([
      requestJson(`${API_BASE_URL}/groups/groups/?page_size=100`),
      requestJson(`${API_BASE_URL}/groups/group-members/?page_size=100`),
    ])
    const groupItems = extractCollectionItems(groupsData)
    const memberships = extractCollectionItems(membershipsData)
      .map(normalizeMembership)
      .filter((item) => !item.leftAt)
    const currentUserId = Number(auth.user?.id || 0)
    const visibleGroupIds = auth.isAdmin
      ? null
      : new Set(
          memberships
            .filter((item) => currentUserId > 0 && String(item.userId) === String(currentUserId))
            .map((item) => String(item.groupId)),
        )
    const memberCounts = new Map()

    memberships.forEach((item) => {
      const groupId = String(item.groupId || '')
      if (!groupId) return
      memberCounts.set(groupId, Number(memberCounts.get(groupId) || 0) + 1)
    })

    let options = groupItems
      .filter((item) => {
        const groupId = String(item?.id || '')
        return groupId && (visibleGroupIds === null || visibleGroupIds.has(groupId))
      })
      .map((item) => normalizeGroupOption(item, memberCounts.get(String(item?.id || ''))))
      .sort((a, b) => a.name.localeCompare(b.name))

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
  } catch {
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
  } finally {
    isLoadingGroupOptions.value = false
  }
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
        const count =
          value && typeof value === 'object' && !Array.isArray(value)
            ? Number(value.count)
            : Number(value)
        return [emoji, count || 0]
      })
      .filter(([, count]) => count > 0),
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
      return
    }

    const data = await requestJson(`${API_BASE_URL}/groups/groups/?page_size=1`)
    const firstGroup = extractCollectionItems(data)[0]
    if (firstGroup) {
      group.value = normalizeGroup(firstGroup)
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

  const rows = []
  const appendRows = (task, depth = 0) => {
    rows.push({ task, depth })
    ;(childrenByParent.get(Number(task.id)) || []).forEach((child) => appendRows(child, depth + 1))
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

const taskSections = computed(() => {
  const relevantTasks = tasks.value.filter(isTaskRelevantToCurrentGroup)
  const groupTasks = relevantTasks.filter((task) => task.taskType === 'group')
  const individualTasks = relevantTasks.filter((task) => task.taskType === 'individual')

  return [
    createTaskSection('group', 'Group Tasks', 'fas fa-users', groupTasks),
    createTaskSection('individual', 'Individual Tasks', 'fas fa-user-check', individualTasks),
  ]
})

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

const setTaskSelectedFromEvent = (taskId, event) => {
  setTaskSelected(taskId, Boolean(event?.target?.checked))
}

const clearTaskSelection = () => {
  selectedTaskIds.value = new Set()
}

const syncSelectedTasks = () => {
  const visibleIds = new Set(
    tasks.value
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

const canToggleTask = (task) => {
  if (!task || task.deletedAt) return false
  if (auth.isAdmin) return true

  if (task.taskType === 'group') {
    return isMentorOfTaskGroup(task) || isSupervisorInTaskGroup(task)
  }

  if (isAssigneeSelf(task)) return true
  if (!isCurrentGroupStudent(task.assignedUser)) return false

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
  if (auth.isMentor) return isCurrentGroupMentor.value && isCurrentGroupStudent(assigneeId)
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
  if (auth.isMentor) return isCurrentGroupMentor.value && isCurrentGroupStudent(assigneeId)
  if (auth.isSupervisor) return isSupervisorOf(assigneeId)
  return false
}

const upsertTask = (task) => {
  const normalized = normalizeTask(task)
  const index = tasks.value.findIndex((item) => Number(item.id) === Number(normalized.id))
  if (index === -1) tasks.value.push(normalized)
  else tasks.value.splice(index, 1, normalized)
}

const removeTaskFromList = (taskId) => {
  const index = tasks.value.findIndex((item) => Number(item.id) === Number(taskId))
  if (index !== -1) tasks.value.splice(index, 1)
}

const getTaskListParams = () => ({
  page_size: 100,
  deleted: taskFilters.value.showDeleted,
  task_type: taskFilters.value.taskType,
  status: taskFilters.value.status,
  completed: taskFilters.value.completed === '' ? '' : taskFilters.value.completed === 'true',
  search: taskFilters.value.search,
  ordering: taskFilters.value.ordering,
})

const loadTasks = async () => {
  const currentGroupId = getBackendGroupId()
  if (!currentGroupId) {
    tasks.value = []
    taskError.value = 'Live task data needs a backend numeric group id.'
    return
  }

  isLoadingTasks.value = true
  taskError.value = ''

  try {
    const data = await listTasks(getTaskListParams())
    tasks.value = extractCollectionItems(data).map(normalizeTask)
    syncSelectedTasks()
  } catch (error) {
    tasks.value = []
    taskError.value = error instanceof Error ? error.message : 'Task data could not be loaded.'
  } finally {
    isLoadingTasks.value = false
  }
}

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
  const author = isOwn
    ? 'You'
    : raw?.sender_name || raw?.author || (senderId ? `User ${senderId}` : 'Team member')

  return {
    id: raw?.id || `${senderId}-${sentAt}`,
    senderId,
    author,
    text: messageText,
    time: formatTime(sentAt),
    date: sentAt,
    isOwn,
    messageType,
    gifUrl: messageType === 'gif' ? messageText : '',
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

const getResourceLabel = (resource) =>
  resource?.resource_name || resource?.name || `Resource ${resource?.resource_id || resource?.id || ''}`

const getReplyLabel = (reply) => {
  if (!reply) return ''
  return reply.deleted ? 'Deleted message' : `Reply to User ${reply.user_id || ''}`.trim()
}

const getReplyText = (reply) => {
  if (!reply) return ''
  if (reply.deleted) return 'Original message was deleted.'
  return reply.text || 'Attachment message'
}

const getMentionLabel = (userId) => {
  const member = mentionMembers.value.find((item) => Number(item.userId) === Number(userId))
  return member?.label || `User ${userId}`
}

const getMessageTextSegments = (text) => {
  const source = String(text || '')
  const segments = []
  const pattern = /<@(\d+)>/g
  let cursor = 0
  let match = pattern.exec(source)

  while (match) {
    if (match.index > cursor) {
      segments.push({ type: 'text', text: source.slice(cursor, match.index) })
    }
    segments.push({ type: 'mention', text: `@${getMentionLabel(match[1])}` })
    cursor = match.index + match[0].length
    match = pattern.exec(source)
  }

  if (cursor < source.length) {
    segments.push({ type: 'text', text: source.slice(cursor) })
  }

  return segments.length ? segments : [{ type: 'text', text: source }]
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
  const id = group.value?.id || routeGroupId.value
  return /^\d+$/.test(String(id || '')) ? String(id) : ''
}

const backendGroupId = computed(() => getBackendGroupId())

const resolveIndividualTaskAssignee = (parentTask = null) => {
  if (parentTask?.assignedUser) return Number(parentTask.assignedUser)
  if (auth.isStudent && auth.user?.id) return Number(auth.user.id)

  const studentMemberships = groupMemberships.value.filter((item) => {
    const role = String(item.role || '').toLowerCase()
    return !item.leftAt && role.includes('student')
  })
  const assigneeId = Number(studentMemberships[0]?.userId || '')
  return Number.isFinite(assigneeId) && assigneeId > 0 ? assigneeId : null
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

const openEditTaskDialog = (task) => {
  taskDialogMode.value = 'edit'
  taskDialogTitle.value = 'Edit task'
  editingTaskId.value = Number(task.id)
  taskFormError.value = ''
  taskForm.value = {
    name: task.name || '',
    description: task.description || '',
    dueDate: toDateTimeLocal(task.dueDate),
    status: task.status || 'todo',
    taskType: task.taskType || 'group',
    parent: task.parent ? String(task.parent) : '',
    group: task.group ? String(task.group) : '',
    assignedUser: task.assignedUser ? String(task.assignedUser) : '',
  }
  taskDialogOpen.value = true
}

const closeTaskDialog = () => {
  if (isSavingTask.value) return
  taskDialogOpen.value = false
  taskFormError.value = ''
}

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
    taskFormError.value = 'Assignee user id is required for individual tasks.'
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
    closeTaskDialog()
  } catch (error) {
    taskFormError.value = error instanceof Error ? error.message : 'Task could not be saved.'
  } finally {
    isSavingTask.value = false
  }
}

const toggleTask = async (task) => {
  if (!task?.id || isUpdatingTask(task.id)) return

  setTaskUpdating(task.id, true)
  taskError.value = ''

  try {
    const updatedTask = await toggleTaskCompletion(task.id, !task.completed)
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
  if (!typingUsers.value.length) return ''
  if (typingUsers.value.length === 1) return `${typingUsers.value[0]} is typing...`
  return `${typingUsers.value[0]} and others are typing...`
})

const showScrollToBottomButton = computed(
  () => hasScrollableMessages.value && isChatAwayFromBottom.value,
)

const canSendChatMessage = computed(
  () => Boolean(newMessage.value.trim()) || selectedChatResources.value.length > 0,
)

const mentionMembers = computed(() =>
  groupMemberships.value
    .filter((item) => !item.leftAt)
    .map(normalizeMentionMember)
    .filter((member) => member.userId && member.userId !== currentUserId.value),
)

const mentionSuggestions = computed(() => {
  const query = mentionQuery.value.toLowerCase()
  return mentionMembers.value
    .filter((member) => {
      if (!query) return true
      return (
        member.label.toLowerCase().includes(query) ||
        member.role.toLowerCase().includes(query) ||
        String(member.userId).includes(query)
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
  Object.values(message?.reactions || {}).some((count) => Number(count) > 0)

const toggleReactionPicker = (messageId) => {
  if (!supportsMessageReactions) return
  activeReactionPickerMessageId.value =
    activeReactionPickerMessageId.value === messageId ? null : messageId
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

const insertMention = (member) => {
  if (mentionStartIndex.value < 0 || !member?.userId) return

  const cursor = composer.value?.selectionStart ?? newMessage.value.length
  const prefix = newMessage.value.slice(0, mentionStartIndex.value)
  const suffix = newMessage.value.slice(cursor)
  const spacer = suffix.startsWith(' ') || !suffix ? '' : ' '
  newMessage.value = `${prefix}<@${member.userId}> ${spacer}${suffix}`.replace(/\s{2,}/g, ' ')
  mentionStartIndex.value = -1
  mentionQuery.value = ''
  activeMentionSuggestionIndex.value = 0

  nextTick(() => {
    composer.value?.focus()
    const position = `${prefix}<@${member.userId}> `.length
    composer.value?.setSelectionRange(position, position)
  })
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

  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    void sendMessage()
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

const markMessagesAsRead = async (messageIds) => {
  const ids = (messageIds || []).map((id) => Number(id)).filter((id) => Number.isFinite(id))
  if (!ids.length) return

  const backendGroupId = getBackendGroupId()
  if (!backendGroupId) return

  const upToId = Math.max(...ids)
  try {
    const data = await requestJson(buildChatReadUrl(backendGroupId, upToId), {
      method: 'POST',
    })
    applyReadCursor(auth.user?.id, data?.up_to_id || upToId)
  } catch (error) {
    console.error('Failed to mark messages as read:', error)
  }
}

const markMessagesAsDelivered = async (messageIds) => {
  const ids = (messageIds || []).map((id) => Number(id)).filter((id) => Number.isFinite(id))
  if (!ids.length) return

  const backendGroupId = getBackendGroupId()
  if (!backendGroupId) return

  const upToId = Math.max(...ids)
  try {
    const data = await requestJson(buildChatDeliveredUrl(backendGroupId, upToId), {
      method: 'POST',
    })
    applyDeliveredCursor(auth.user?.id, data?.up_to_id || upToId)
  } catch (error) {
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

const handleMessagesScroll = () => {
  updateScrollToBottomState()
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
      body: JSON.stringify({ message_text: text }),
    })
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
        sender_name: payload.sender_name || `User ${payload.sender_user_id || ''}`,
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
    void loadNewerMessages()
    void markMessagesAsRead(
      messages.value.filter((message) => !message.isOwn).map((message) => message.id),
    )
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

const loadMessages = async () => {
  const backendGroupId = getBackendGroupId()
  if (!backendGroupId) {
    chatError.value = 'Live discussion needs a backend numeric group id.'
    messages.value = []
    await scrollMessagesToBottom()
    return
  }

  isLoadingMessages.value = true
  chatError.value = ''

  try {
    const data = await requestJson(buildChatMessageCollectionUrl(backendGroupId, '?limit=50'))
    const liveMessages = extractCollectionItems(data).map(normalizeMessage).reverse()

    messages.value = liveMessages.length ? liveMessages : []
    nextMessagesAfter.value = data?.next_after || null
    nextMessagesBefore.value = data?.next_before || null
  } catch (error) {
    chatError.value =
      error instanceof Error ? error.message : 'Live discussion is unavailable right now.'
    messages.value = []
    nextMessagesAfter.value = null
    nextMessagesBefore.value = null
  } finally {
    isLoadingMessages.value = false
    await scrollMessagesToBottomAfterRender()
    await markMessagesAsDelivered(
      messages.value.filter((message) => !message.isOwn).map((message) => message.id),
    )
    await markMessagesAsRead(
      messages.value.filter((message) => !message.isOwn).map((message) => message.id),
    )
  }
}

const loadOlderMessages = async () => {
  const backendGroupId = getBackendGroupId()
  if (!backendGroupId || !nextMessagesBefore.value || isLoadingOlderMessages.value) return

  isLoadingOlderMessages.value = true
  chatError.value = ''

  try {
    const data = await requestJson(
      buildChatMessageCollectionUrl(
        backendGroupId,
        `?limit=50&before=${encodeURIComponent(nextMessagesBefore.value)}`,
      ),
    )
    const olderMessages = extractCollectionItems(data).map(normalizeMessage).reverse()
    const existingIds = new Set(messages.value.map((message) => String(message.id)))
    messages.value = [
      ...olderMessages.filter((message) => !existingIds.has(String(message.id))),
      ...messages.value,
    ]
    nextMessagesBefore.value = data?.next_before || null
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

  isSendingMessage.value = true
  try {
    await sendMessagePayload({
      body: 'message',
      pendingId,
      requestOptions: {
        method: 'POST',
        body: JSON.stringify({
          message_text: text,
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
}

const openFilePicker = () => {
  if (!supportsAttachments) {
    chatError.value = 'File upload is not available in the backend yet.'
    return
  }
  fileInputRef.value?.click()
}

const uploadAttachment = async (event) => {
  if (!supportsAttachments) {
    chatError.value = 'File upload is not available in the backend yet.'
    return
  }
  const input = event?.target
  const file = input?.files?.[0]
  if (!file || isUploadingFile.value) return
  if (replyTarget.value) {
    chatError.value = 'Attachment replies are not supported by the upload endpoint yet.'
    if (input) input.value = ''
    return
  }
  if (selectedChatResources.value.length) {
    chatError.value = 'Send selected resources as a chat message before uploading a local file.'
    if (input) input.value = ''
    return
  }
  const caption = newMessage.value.trim()
  const formData = new FormData()
  formData.append('uploaded_file', file)
  if (caption) formData.append('message_text', caption)

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

const fetchGifResults = async (mode = 'trending') => {
  if (!supportsGifs) {
    gifResults.value = []
    gifError.value = 'GIF search is not available in the backend yet.'
    return
  }

  isLoadingGifs.value = true
  gifError.value = ''

  try {
    const data = await requestJson(
      mode === 'search' ? buildGifSearchUrl(gifQuery.value.trim()) : buildGifTrendingUrl(),
      {
        method: 'GET',
      },
    )
    gifResults.value = normalizeGifResults(data)
  } catch {
    gifResults.value = []
    gifError.value = 'Live GIF search is unavailable right now.'
  } finally {
    isLoadingGifs.value = false
  }
}

const toggleGifPanel = async () => {
  if (!supportsGifs) {
    gifError.value = 'GIF search is not available in the backend yet.'
    return
  }
  showGifPanel.value = !showGifPanel.value
  if (showGifPanel.value) showResourcePanel.value = false
  if (showGifPanel.value) {
    await fetchGifResults('trending')
  }
}

const searchGifs = async () => {
  if (!gifQuery.value.trim()) {
    await fetchGifResults('trending')
    return
  }

  await fetchGifResults('search')
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
  showResourcePanel.value = !showResourcePanel.value
  if (showResourcePanel.value) showGifPanel.value = false
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

const switchGroup = async (event) => {
  const selectedGroupId = event?.target?.value
  if (!selectedGroupId || String(selectedGroupId) === String(backendGroupId.value)) return
  await router.push(`/groups/${selectedGroupId}`)
}

const reloadGroupDetail = async () => {
  const sequence = ++loadSequence

  isLoadingGroupDetail.value = true
  disconnectChatSocket()
  tasks.value = []
  messages.value = []
  taskError.value = ''
  chatError.value = ''
  chatNotice.value = ''
  activeReactionPickerMessageId.value = null

  try {
    await loadGroup()
    if (sequence !== loadSequence) return

    await loadGroupMembers()
    if (sequence !== loadSequence) return

    await Promise.all([loadTasks(), loadMessages()])
    if (sequence !== loadSequence) return

    await scrollMessagesToBottomAfterRender()
    if (sequence !== loadSequence) return

    connectChatSocket()
  } finally {
    if (sequence === loadSequence) {
      isLoadingGroupDetail.value = false
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

onMounted(async () => {
  manageWindowTimer = window.setInterval(() => {
    manageWindowNow.value = Date.now()
  }, 30000)

  await ensureAuthUser()
  await loadGroupOptions()
  if (!routeGroupId.value && availableGroups.value.length) {
    await loadMentions()
    await router.replace(`/groups/${availableGroups.value[0].id}`)
    return
  }

  await reloadGroupDetail()
})

onBeforeUnmount(() => {
  disconnectChatSocket()
  clearTimeout(typingStopTimer)
  if (manageWindowTimer) {
    clearInterval(manageWindowTimer)
    manageWindowTimer = null
  }
})
</script>

<style scoped>
/* Header */
.gd-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.25rem;
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
  margin-top: 0.15rem;
}
.gd-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.35rem;
  color: #6c757d;
  font-size: 0.85rem;
  font-weight: 600;
}
.gd-meta-row span {
  padding: 0.2rem 0.5rem;
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
.group-switcher {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #6c757d;
  font-size: 0.85rem;
  font-weight: 700;
}
.group-switcher select {
  min-width: 150px;
  max-width: 240px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 0.45rem 0.65rem;
  background: rgba(255, 255, 255, 0.9);
  color: var(--charcoal);
  font-weight: 600;
}
.group-switcher select:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
.group-switcher-error {
  color: #8a5a00;
  font-size: 0.78rem;
  font-weight: 600;
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
}
.tasks-content {
  padding-right: 2px; /* for visible scrollbar */
}

.task-header-actions {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
}

.task-filter-bar,
.task-bulk-bar {
  display: flex;
  align-items: end;
  gap: 0.65rem;
  flex-wrap: wrap;
  margin-bottom: 0.85rem;
}

.task-filter-field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  min-width: 118px;
  color: #5b6770;
  font-size: 0.78rem;
  font-weight: 700;
}

.task-filter-field input,
.task-filter-field select,
.task-form-field input,
.task-form-field select,
.task-form-field textarea {
  width: 100%;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.52rem 0.62rem;
  background: var(--white);
  color: var(--charcoal);
  font: inherit;
}

.task-filter-field input:focus,
.task-filter-field select:focus,
.task-form-field input:focus,
.task-form-field select:focus,
.task-form-field textarea:focus {
  outline: none;
  border-color: var(--air-force-blue);
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.12);
}

.task-deleted-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.38rem;
  min-height: 38px;
  color: #5b6770;
  font-size: 0.82rem;
  font-weight: 700;
}

.task-bulk-bar {
  align-items: center;
  padding: 0.62rem 0.7rem;
  background: #f1f5f7;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  color: var(--charcoal);
  font-size: 0.84rem;
  font-weight: 700;
}

.task-section {
  border-bottom: 1px solid var(--border-light);
  padding: 0.9rem 0;
}

.task-section:last-child {
  border-bottom: 0;
}

.task-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  margin-bottom: 0.7rem;
}

.task-section-title {
  color: var(--charcoal);
  font-weight: 700;
}

.task-section-title i {
  margin-right: 0.45rem;
  color: var(--air-force-blue);
}

.task-section-status {
  color: #6c757d;
  font-size: 0.84rem;
  font-weight: 700;
}

.task-body {
  flex: 1;
  min-width: 0;
}

.task-select-control {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  flex-shrink: 0;
}

.task-select-control input {
  width: 15px;
  height: 15px;
  accent-color: var(--air-force-blue);
}

.task-description {
  margin-top: 0.18rem;
  color: #6c757d;
  font-size: 0.82rem;
  line-height: 1.45;
}

.task-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-top: 0.2rem;
  color: #6c757d;
  font-size: 0.78rem;
}

.task-meta i {
  margin-right: 0.25rem;
}

.task-row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.45rem;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.task-status-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  min-height: 32px;
  padding: 0.35rem 0.65rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: #fff;
  color: #50616c;
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease;
}

.task-status-toggle i {
  color: var(--air-force-blue);
  font-size: 0.82rem;
}

.task-status-toggle:hover:not(:disabled) {
  border-color: var(--air-force-blue);
  background: #f1f5f7;
  color: var(--charcoal);
}

.task-status-toggle.is-complete {
  border-color: rgba(77, 116, 94, 0.35);
  background: rgba(77, 116, 94, 0.1);
  color: var(--dark-green);
}

.task-status-toggle.is-complete i {
  color: var(--dark-green);
}

.task-status-toggle:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.task-item.is-deleted {
  opacity: 0.6;
}

.task-dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(15, 23, 42, 0.45);
}

.task-dialog {
  width: min(100%, 560px);
  max-height: min(720px, calc(100vh - 2rem));
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding: 1rem;
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  box-shadow: 0 20px 48px rgba(15, 23, 42, 0.22);
}

.task-dialog-header,
.task-dialog-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.7rem;
}

.task-dialog-header h4 {
  margin: 0;
  color: var(--charcoal);
  font-size: 1rem;
}

.task-dialog-close {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--white);
  color: var(--charcoal);
  cursor: pointer;
}

.task-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.8rem;
}

.task-form-field {
  display: flex;
  flex-direction: column;
  gap: 0.32rem;
  color: #5b6770;
  font-size: 0.82rem;
  font-weight: 700;
}

.task-form-field--wide {
  width: 100%;
}

.task-form-field textarea {
  resize: vertical;
}

/* Discussion board: chat-container fills card, chat-messages scrolls */
.chat-status {
  color: #6c757d;
  font-size: 0.85rem;
  font-weight: 600;
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
  cursor: wait;
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
  background: #eef7f3;
  color: var(--dark-green);
  font-weight: 700;
  padding: 0.05rem 0.35rem;
}

.message.own .mention-token {
  background: rgba(255, 255, 255, 0.18);
  color: var(--white);
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
}

.gif-card {
  border: 1px solid var(--border-default);
  border-radius: 16px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
  cursor: pointer;
  padding: 0;
}

.gif-card img {
  width: 100%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  display: block;
}

.gif-card span {
  display: block;
  padding: 0.45rem 0.55rem 0.6rem;
  font-size: 0.78rem;
  text-align: left;
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
}

.add-subtask-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border-color: var(--border-light);
  flex-shrink: 0;
}

.task-empty-state {
  padding: 0.8rem;
  color: #6c757d;
  background: #f8f9fa;
  border: 1px dashed var(--border-light);
  border-radius: 8px;
  font-size: 0.88rem;
}

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

.message-preview {
  display: grid;
  gap: 0.35rem;
  margin-top: 0.7rem;
  padding: 0.75rem 0.85rem;
  border-radius: 16px;
  border: 1px solid var(--border-default);
  background: color-mix(in srgb, var(--surface-base) 86%, transparent);
  color: var(--text-primary);
}

.message-preview img {
  width: 100%;
  max-height: 160px;
  border-radius: 8px;
  object-fit: cover;
}

.message-preview span {
  color: var(--text-secondary);
  font-size: 0.84rem;
}

.message-reactions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.75rem;
}

.reaction-btn,
.reaction-summary-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border-radius: 999px;
  border: 1px solid var(--border-default);
  background: color-mix(in srgb, var(--surface-elevated) 94%, transparent);
  color: var(--text-primary);
  padding: 0.35rem 0.6rem;
  font-size: 0.9rem;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background 0.18s ease;
}

.reaction-btn:hover,
.reaction-summary-btn:hover {
  border-color: var(--border-strong);
}

.reaction-count {
  font-size: 0.78rem;
  font-weight: 700;
}

.message-receipt {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.55rem;
  color: var(--text-muted);
  font-size: 0.76rem;
  font-weight: 700;
}

.message.own .message-receipt {
  color: rgba(255, 255, 255, 0.86);
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
  padding: 2rem;
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
  margin-bottom: 1.5rem;
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
  padding: 1.5rem;
  margin-bottom: 0;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  box-shadow: 0 2px 4px var(--shadow);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.gd-title {
  margin: 0;
  color: var(--charcoal);
  font-size: 2rem;
  font-weight: 600;
}

.gd-subtitle {
  margin-top: 0.15rem;
  color: #6c757d;
  font-size: 1rem;
}

.group-avatar {
  background: var(--air-force-blue);
  color: var(--white);
  border-color: var(--white);
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
.task-section-status,
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
  border-radius: 4px;
}

.chat-input-field::placeholder {
  color: #8a949e;
}

.chat-input-field:focus,
.gif-search-input:focus {
  outline: none;
  border-color: var(--air-force-blue);
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.12);
}

.chat-btn {
  border: 1px solid var(--border-light);
  background: var(--white);
  color: var(--air-force-blue);
}

.chat-btn:hover {
  border-color: var(--air-force-blue);
  background: #f1f5f7;
}

.chat-btn:disabled,
.chat-btn:disabled:hover {
  color: #98a2ad;
  border-color: var(--border-light);
  background: var(--white);
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
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.message-content {
  position: relative;
}

.message-header {
  padding-right: 2.2rem;
}

.message.own .message-content {
  background: var(--dark-green);
  color: var(--white);
  border-color: var(--dark-green);
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

.reaction-picker-toggle {
  position: absolute;
  top: 0.55rem;
  right: 0.55rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.8rem;
  height: 1.8rem;
  border: 1px solid var(--border-light);
  border-radius: 50%;
  background: var(--white);
  color: var(--air-force-blue);
  cursor: pointer;
  opacity: 0;
  pointer-events: none;
  transition:
    opacity 0.16s ease,
    border-color 0.16s ease,
    background 0.16s ease;
}

.message-content:hover .reaction-picker-toggle,
.message-content:focus-within .reaction-picker-toggle,
.reaction-picker-toggle.active {
  opacity: 1;
  pointer-events: auto;
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

.reaction-picker {
  position: absolute;
  top: 2.55rem;
  right: 0.55rem;
  z-index: 2;
  display: inline-flex;
  gap: 0.35rem;
  padding: 0.35rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background: var(--white);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.14);
}

.reaction-picker .reaction-btn {
  width: 2rem;
  height: 2rem;
  justify-content: center;
  padding: 0;
  border-radius: 50%;
  box-shadow: none;
}

.reaction-btn:hover,
.reaction-summary-btn:hover {
  border-color: var(--air-force-blue);
  background: #f8f9fa;
}

.task-section {
  border-bottom-color: var(--border-light);
}

.task-item:hover {
  margin: 0;
  padding-top: 0.5rem;
  padding-right: 0;
  padding-bottom: 0.5rem;
  background-color: transparent;
}

.add-subtask-btn {
  color: var(--air-force-blue);
  border-color: var(--border-light);
}

.add-subtask-btn:hover {
  background: #f1f5f7;
  border-color: var(--air-force-blue);
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

.skeleton-block::after {
  content: '';
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.72), transparent);
  animation: group-loading-shimmer 1.35s ease-in-out infinite;
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

@keyframes group-loading-shimmer {
  100% {
    transform: translateX(100%);
  }
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

  .group-switcher {
    justify-content: space-between;
    width: 100%;
  }

  .group-switcher select {
    flex: 1;
    max-width: none;
  }

  .task-filter-field {
    min-width: min(100%, 148px);
    flex: 1 1 140px;
  }

  .task-row-actions {
    width: 100%;
    justify-content: flex-start;
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
