<template>
  <section class="activity-analytics-page">
    <div class="page-heading">
      <div class="heading-copy">
        <div class="breadcrumb">
          <RouterLink to="/dashboard">Home</RouterLink>
          <span>›</span>
          <RouterLink to="/analytics">Analytics</RouterLink>
          <span>›</span>
          <span>Activity Analytics</span>
        </div>

        <div class="title-line">
          <h1>Activity Analytics</h1>
          
        </div>
        <p>Understand how participants are engaging across the platform.</p>
      </div>

      <div class="page-actions">
        <label v-if="availableYears.length > 1" class="year-control">
          <i class="fas fa-calendar" aria-hidden="true"></i>
          <select v-model.number="selectedYear" aria-label="Select analytics year">
            <option v-for="year in availableYears" :key="year" :value="year">
              {{ year }}
            </option>
          </select>
        </label>

        <div class="analytics-export-stack">
          <button type="button" class="export-button" :disabled="exportDisabled" @click="exportCsv">
            <i class="fas fa-download" aria-hidden="true"></i>
            Export CSV
          </button>
          <div class="analytics-update-status">
            <AnalyticsRefreshStatus :updated-at="lastUpdated" :refresh-failed="refreshFailed" />
          </div>
        </div>
      </div>
    </div>

    <AnalyticsPartialNotice :sources="unavailableSources" @retry="loadAnalytics(true)" />

    <AnalyticsDataState
      :loading="isLoading"
      :error="loadError"
      :empty="isEmpty"
      empty-message="No participant or group activity records are available in the current database. Generate or load a dataset, then refresh this page."
      @retry="refreshAnalytics"
    >
    <div class="kpi-grid">
      <article class="kpi-card">
        <div class="kpi-icon"><i class="fas fa-user-clock"></i></div>
        <div>
          <span>Daily Active Users</span>
          <div class="analytics-value-row">
            <strong><AnalyticsNumber :value="yearKpis.dailyActive ?? '—'" /></strong>
            <AnalyticsYearChange
              v-if="activityWindowComparison"
              :current="activityWindowComparison.daily.current"
              :previous="activityWindowComparison.daily.previous"
              label="vs previous day"
            />
          </div>
          <small>Selected day</small>
        </div>
      </article>

      <article class="kpi-card">
        <div class="kpi-icon"><i class="fas fa-users"></i></div>
        <div>
          <span>Weekly Active Users</span>
          <div class="analytics-value-row">
            <strong><AnalyticsNumber :value="yearKpis.weeklyActive ?? '—'" /></strong>
            <AnalyticsYearChange
              v-if="activityWindowComparison"
              :current="activityWindowComparison.weekly.current"
              :previous="activityWindowComparison.weekly.previous"
              label="vs previous 7 days"
            />
          </div>
          <small>7 days ending on selected date</small>
        </div>
      </article>

      <article class="kpi-card">
        <div class="kpi-icon"><i class="fas fa-calendar-days"></i></div>
        <div>
          <span>Monthly Active Users</span>
          <div class="analytics-value-row">
            <strong><AnalyticsNumber :value="yearKpis.monthlyActive ?? '—'" /></strong>
            <AnalyticsYearChange
              v-if="activityWindowComparison"
              :current="activityWindowComparison.monthly.current"
              :previous="activityWindowComparison.monthly.previous"
              label="vs previous 30 days"
            />
          </div>
          <small>30 days ending on selected date</small>
        </div>
      </article>

      <article class="kpi-card">
        <div class="kpi-icon"><i class="fas fa-arrow-right-to-bracket"></i></div>
        <div>
          <span>Logged In</span>
          <strong><AnalyticsNumber :value="sourceAvailable('users') ? `${selectedLoggedInRate}%` : '—'" /></strong>
          <small v-if="sourceAvailable('users')">{{ loggedInCount }} of {{ selectedUserYearData.totalUsers }} current users</small>
          <small v-else>Participant details are unavailable.</small>
        </div>
      </article>

      <article v-if="sourceAvailable('loginActivity')" class="kpi-card">
        <div class="kpi-icon"><i class="fas fa-chart-line"></i></div>
        <div>
          <span>Participants Logged In</span>
          <div class="analytics-value-row">
            <strong><AnalyticsNumber :value="yearlyLoginComparison.current" /></strong>
            <AnalyticsYearChange
              :current="yearlyLoginComparison.current"
              :previous="yearlyLoginComparison.previous"
              :label="`vs ${yearlyLoginComparison.previousYear}`"
            />
          </div>
          <small>Unique users this year</small>
        </div>
      </article>

      <article class="kpi-card">
        <div class="kpi-icon warning"><i class="fas fa-triangle-exclamation"></i></div>
        <div>
          <span>Never Logged In</span>
          <strong><AnalyticsNumber :value="sourceAvailable('users') ? selectedNeverLoggedIn : '—'" /></strong>
          <small>Needs attention</small>
        </div>
      </article>
    </div>

    <section class="filter-card sticky-filter-card">
      <label class="view-filter-control">
        <span>View</span>
        <select v-model="viewMode">
          <option value="users">Users</option>
          <option value="groups" :disabled="!sourceAvailable('groups') || !sourceAvailable('groupActivity')">Groups</option>
        </select>
      </label>

      <label class="date-filter-control">
        <span>Trend start date</span>
        <AnalyticsDatePicker
          :model-value="selectedStartDate"
          :min="trendDataStart"
          :max="selectedEndDate || trendDataEnd"
          :available-years="trendDataYears"
          label="Trend start date"
          @update:model-value="updateTrendStart"
        />
      </label>

      <label class="date-filter-control">
        <span>Trend end date</span>
        <AnalyticsDatePicker
          :model-value="selectedEndDate"
          :min="selectedStartDate || trendDataStart"
          :max="trendDataEnd"
          :available-years="trendDataYears"
          label="Trend end date"
          @update:model-value="updateTrendEnd"
        />
      </label>

      <label>
        <span>Trend interval</span>
        <select v-model="trendInterval" aria-label="Trend interval">
          <option value="day">Day</option>
          <option value="week">Week</option>
          <option value="month">Month</option>
        </select>
      </label>

      <label v-if="viewMode === 'users'">
        <span>User Role</span>
        <select v-model="selectedRole" aria-label="Filter by user role">
          <option value="all">All Roles</option>
          <option value="Student">Students</option>
          <option value="Mentor">Mentors</option>
          <option value="Supervisor">Supervisors</option>
        </select>
      </label>

      <label>
        <span>Activity Status</span>
        <select v-model="selectedStatus" aria-label="Filter by activity status">
          <option value="all">All Statuses</option>
          <option value="Active">Active</option>
          <option value="Inactive">Inactive</option>
          <option v-if="viewMode === 'users'" value="Never">Never Logged In</option>
          <option v-else value="Not started">Not Started</option>
        </select>
      </label>

      <button type="button" class="reset-button" @click="resetFilters">
        <i class="fas fa-rotate-left"></i>
        Reset filters
      </button>
    </section>

    <p v-if="viewMode === 'users' && sourceAvailable('users') && !loginHistoryAvailable" class="filter-scope-note" role="status">
      No recorded login history is available. Daily, weekly and monthly activity cannot be calculated.
      Last-login records below remain available; missing history does not mean zero activity.
    </p>
    <p v-if="viewMode === 'users' && !sourceAvailable('users')" class="filter-scope-note" role="status">
      Participant details are unavailable. Recorded login activity is shown when available.
    </p>
    <div v-if="viewMode === 'users' && loginHistoryAvailable" class="analytics-grid main-grid">
      <article class="analytics-card activity-chart-card">
        <div class="card-heading">
          <div>
            <h2>User Activity Trend</h2>
            <p>Unique active users grouped by {{ trendIntervalLabel.toLowerCase() }} in the selected date range.</p>
          </div>

          <div class="hide-role-controls">
            <strong>Hide roles</strong>
            <label><input v-model="hiddenRoles" type="checkbox" value="students" /> Student</label>
            <label><input v-model="hiddenRoles" type="checkbox" value="mentors" /> Mentor</label>
            <label><input v-model="hiddenRoles" type="checkbox" value="supervisors" /> Supervisor</label>
          </div>
        </div>

        <div class="line-chart-layout">
          <div class="y-axis activity-y-axis">
            <span
              v-for="tick in activityTicks"
              :key="tick"
              :style="{ top: `${activityYPercent(tick)}%` }"
            >{{ tick }}</span>
          </div>

          <div class="line-chart">
            <svg viewBox="0 0 720 250" role="img" aria-label="Daily user activity by role">
              <line
                v-for="tick in activityTicks"
                :key="`grid-${tick}`"
                x1="32"
                x2="688"
                :y1="activityY(tick)"
                :y2="activityY(tick)"
                class="grid-line"
              />

              <template v-for="series in visibleChartSeries" :key="series.key">
                <polyline :points="seriesPoints(series.values)" :class="['activity-line', series.key]" />
                <g v-for="point in seriesDots(series.values)" :key="`${series.key}-${point.index}`">
                  <circle
                    :cx="point.x"
                    :cy="point.y"
                    r="6"
                    :class="['activity-dot', series.key, 'interactive-point']"
                    @mouseenter="showTooltip($event, `${series.label} · ${chartDateLabels[point.index]}`, `${point.value}`, `${trendIntervalLabel} active`)"
                    @mousemove="moveTooltip"
                    @mouseleave="hideTooltip"
                  />
                  <text v-if="showPointValue(point.index, series.values.length)" :x="point.x" :y="Math.max(point.y - 12, 14)" text-anchor="middle" class="activity-value">
                    {{ point.value }}
                  </text>
                </g>
              </template>

              <text
                v-for="(label, index) in chartDateLabels"
                v-show="showXAxisLabel(index, chartDateLabels.length)"
                :key="`date-${label}-${index}`"
                :x="activityX(index, chartDateLabels.length)"
                y="238"
                text-anchor="middle"
                class="activity-date"
              >
                {{ label }}
              </text>
            </svg>

            <div class="legend">
              <span v-for="series in visibleChartSeries" :key="`legend-${series.key}`">
                <i :class="['dot', series.key]"></i>{{ series.label }}
              </span>
            </div>
          </div>
        </div>

      </article>

      <div v-if="sourceAvailable('users')" class="activity-side-stack">
        <article class="analytics-card login-role-card">
          <div class="card-heading">
            <div>
              <h2>Logged In by Role</h2>
              <p>Share of current users in each role who have logged in at least once.</p>
            </div>
          </div>

          <div class="role-rate-list">
            <div
              v-for="item in filteredRoleLoginRates"
              :key="item.role"
              class="role-rate-row interactive-chart-row"
              @mouseenter="showTooltip($event, pluralRole(item.role), `${item.value}%`, 'Logged in at least once')"
              @mousemove="moveTooltip"
              @mouseleave="hideTooltip"
            >
              <div class="role-label">
                <span class="role-icon"><i :class="roleIcon(item.role)"></i></span>
                <strong>{{ pluralRole(item.role) }}</strong>
              </div>
              <div class="rate-track"><i :style="{ width: `${item.value}%` }"></i></div>
              <strong>{{ item.value }}%</strong>
            </div>
          </div>
        </article>
      </div>
    </div>


    <template v-else-if="viewMode === 'groups' && sourceAvailable('groups') && sourceAvailable('groupActivity')">
      <div class="analytics-grid main-grid group-mode-grid">
        <article class="analytics-card activity-chart-card">
          <div class="card-heading">
            <div>
              <h2>Group Activity Trend</h2>
              <p>Current groups with or without a recorded message by {{ trendIntervalLabel.toLowerCase() }} in the selected date range.</p>
            </div>
          </div>

          <div class="line-chart-layout">
            <div class="y-axis">
              <span v-for="tick in groupActivityTicks" :key="`group-tick-${tick}`">{{ tick }}</span>
            </div>

            <div class="line-chart">
              <svg viewBox="0 0 720 250" role="img" aria-label="Group activity by month">
                <line
                  v-for="tick in groupActivityTicks"
                  :key="`group-grid-${tick}`"
                  x1="32"
                  x2="688"
                  :y1="groupActivityY(tick)"
                  :y2="groupActivityY(tick)"
                  class="grid-line"
                />

                <polyline :points="groupSeriesPoints(groupActiveValues)" class="activity-line group-active-line" />
                <polyline :points="groupSeriesPoints(groupInactiveValues)" class="activity-line group-inactive-line" />

                <g v-for="point in groupSeriesDots(groupActiveValues)" :key="`ga-${point.index}`">
                  <circle
                    :cx="point.x"
                    :cy="point.y"
                    r="6"
                    class="activity-dot group-active-dot interactive-point"
                    @mouseenter="showTooltip($event, `${groupMonthLabels[point.index]}`, `${point.value}`, 'Active groups')"
                    @mousemove="moveTooltip"
                    @mouseleave="hideTooltip"
                  />
                  <text :x="point.x" :y="Math.max(point.y - 11, 13)" text-anchor="middle" class="activity-value">
                    {{ point.value }}
                  </text>
                </g>

                <g v-for="point in groupSeriesDots(groupInactiveValues)" :key="`gi-${point.index}`">
                  <circle
                    :cx="point.x"
                    :cy="point.y"
                    r="6"
                    class="activity-dot group-inactive-dot interactive-point"
                    @mouseenter="showTooltip($event, `${groupMonthLabels[point.index]}`, `${point.value}`, 'Inactive groups')"
                    @mousemove="moveTooltip"
                    @mouseleave="hideTooltip"
                  />
                  <text :x="point.x" :y="Math.max(point.y - 11, 13)" text-anchor="middle" class="activity-value inactive-label">
                    {{ point.value }}
                  </text>
                </g>

                <text
                  v-for="(label, index) in groupMonthLabels"
                  :key="`group-month-${label}`"
                  :x="groupActivityX(index, groupMonthLabels.length)"
                  y="238"
                  text-anchor="middle"
                  class="activity-date"
                >
                  {{ label }}
                </text>
              </svg>

              <div class="legend">
                <span><i class="dot group-active-dot"></i>Active groups</span>
                <span><i class="dot group-inactive-dot"></i>Inactive groups</span>
              </div>
            </div>
          </div>
        </article>

        <article class="analytics-card group-status-summary-card">
          <h2>Group Activity Status</h2>

          <div class="group-status-summary-list">
            <button
              type="button"
              :class="[
                'group-status-summary-row',
                'interactive-chart-row',
                { 'is-selected': highlightedGroupStatus === 'Active' },
              ]"
              :aria-pressed="highlightedGroupStatus === 'Active'"
              aria-label="Filter groups by Active status"
              @click="applyGroupStatusFilter('Active')"
              @mouseenter="showTooltip($event, 'Active Groups', `${groupActiveCount}`, `${groupActivePercent}% of current groups`)"
              @mousemove="moveTooltip"
              @mouseleave="hideTooltip"
            >
              <span class="group-summary-icon active"><i class="fas fa-users"></i></span>
              <div>
                <strong>Active</strong>
                <small>
                  Last message within {{ groupActivityThreshold }}
                  day{{ groupActivityThreshold === 1 ? '' : 's' }}
                </small>
              </div>
              <b>{{ groupActiveCount }}</b>
            </button>

            <button
              type="button"
              :class="[
                'group-status-summary-row',
                'interactive-chart-row',
                { 'is-selected': highlightedGroupStatus === 'Inactive' },
              ]"
              :aria-pressed="highlightedGroupStatus === 'Inactive'"
              aria-label="Filter groups by Inactive status"
              @click="applyGroupStatusFilter('Inactive')"
              @mouseenter="showTooltip($event, 'Inactive Groups', `${groupInactiveCount}`, `${groupInactivePercent}% of current groups`)"
              @mousemove="moveTooltip"
              @mouseleave="hideTooltip"
            >
              <span class="group-summary-icon inactive"><i class="fas fa-user-clock"></i></span>
              <div>
                <strong>Inactive</strong>
                <small>
                  Last message more than {{ groupActivityThreshold }}
                  day{{ groupActivityThreshold === 1 ? '' : 's' }} ago
                </small>
              </div>
              <b>{{ groupInactiveCount }}</b>
            </button>

            <button
              type="button"
              :class="[
                'group-status-summary-row',
                'interactive-chart-row',
                { 'is-selected': highlightedGroupStatus === 'Not started' },
              ]"
              :aria-pressed="highlightedGroupStatus === 'Not started'"
              aria-label="Filter groups by Not Started status"
              @click="applyGroupStatusFilter('Not started')"
              @mouseenter="showTooltip($event, 'Not Started Groups', `${groupNotStartedCount}`, `${groupNotStartedPercent}% of current groups`)"
              @mousemove="moveTooltip"
              @mouseleave="hideTooltip"
            >
              <span class="group-summary-icon not-started"><i class="fas fa-hourglass-start"></i></span>
              <div>
                <strong>Not Started</strong>
                <small>No recorded messages</small>
              </div>
              <b>{{ groupNotStartedCount }}</b>
            </button>
          </div>
        </article>
      </div>

      <article class="analytics-card group-activity-details-card">
        <div class="table-heading group-table-heading">
          <div>
            <h2>Group Activity Details</h2>
            <p>
              Current groups and their latest recorded message day; status uses the saved
              {{ groupActivityThreshold }}-day threshold.
            </p>
          </div>
          <div class="table-heading-controls">
            <label class="show-all-control">
              <input
                v-model="showAllActivityDetails"
                type="checkbox"
                aria-label="Show all group activity details"
              />
              <span>Show all data</span>
            </label>
            <label class="threshold-control">
              <span>Active threshold</span>
              <input
                v-model.number="groupActivityThreshold"
                type="number"
                min="0"
                max="3650"
                step="1"
                aria-label="Group active threshold in days"
                @change="normaliseThreshold('groups')"
              />
              <small>days</small>
            </label>
            <input v-model.trim="groupSearch" type="search" placeholder="Search group or mentor" />
          </div>
        </div>

        <div class="group-directory-summary">
          Showing <strong>{{ filteredGroupRows.length }}</strong> of
          <strong>{{ groupRows.length }}</strong> current groups
        </div>

        <div class="table-wrap group-table-wrap">
          <table class="group-activity-table">
            <colgroup>
              <col class="group-col-name" />
              <col class="group-col-mentor" />
              <col class="group-col-status" />
              <col class="group-col-last-active" />
              <col class="group-col-days" />
            </colgroup>
            <thead>
              <tr>
                <th class="sortable" @click="toggleGroupSort('name')">Group <i :class="groupSortIcon('name')"></i></th>
                <th>Mentors</th>
                <th class="sortable" @click="toggleGroupSort('status')">Activity Status <i :class="groupSortIcon('status')"></i></th>
                <th class="sortable" @click="toggleGroupSort('lastActiveDate')">Last Message Date <i :class="groupSortIcon('lastActiveDate')"></i></th>
                <th class="sortable" @click="toggleGroupSort('daysSinceActive')">
                  Days Since Last Message <i :class="groupSortIcon('daysSinceActive')"></i>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="group in filteredGroupRows" :key="group.id">
                <td>
                  <strong>{{ group.name }}</strong>
                  <small class="group-id-label">ID {{ group.id }}</small>
                </td>
                <td>
                  <span v-if="group.mentors.length">{{ group.mentors.join(', ') }}</span>
                  <span v-else class="mentor-none-pill">None</span>
                </td>
                <td><span :class="['status-pill', groupStatusClass(group.status)]">{{ group.status }}</span></td>
                <td>{{ formatGroupLastActive(group.lastActiveDate) }}</td>
                <td>{{ group.daysSinceActive === null ? '—' : `${group.daysSinceActive} days` }}</td>
              </tr>
              <tr v-if="filteredGroupRows.length === 0">
                <td colspan="5" class="empty-state">No groups match the current filters.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </template>


    <div v-if="viewMode === 'users' && sourceAvailable('users')" class="analytics-grid lower-grid">
      <article id="user-activity-details" class="analytics-card table-card">
        <div class="table-heading">
          <div>
            <h2>User Activity Details</h2>
            <p>Search and review recent login activity for participants.</p>
          </div>
          <div class="table-heading-controls">
            <label class="show-all-control">
              <input
                v-model="showAllActivityDetails"
                type="checkbox"
                aria-label="Show all user activity details"
              />
              <span>Show all data</span>
            </label>
            <label class="threshold-control">
              <span>Active threshold</span>
              <input
                v-model.number="userActivityThreshold"
                type="number"
                min="0"
                max="3650"
                step="1"
                aria-label="User active threshold in days"
                @change="normaliseThreshold('users')"
              />
              <small>days</small>
            </label>
            <input v-model.trim="searchQuery" type="search" placeholder="Search user" />
          </div>
        </div>

        <div v-if="issueContext" class="activity-issue-context">
          <i class="fas fa-circle-info" aria-hidden="true"></i>
          <span v-if="issueContext === 'inactive-mentors'">Showing mentors with an inactive account.</span>
          <span v-else>Showing inactive user accounts.</span>
        </div>

        <div class="table-wrap">
          <table>
            <colgroup>
              <col class="col-user" />
              <col class="col-role" />
              <col class="col-login" />
              <col class="col-days" />
              <col class="col-status" />
            </colgroup>
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th class="sortable" @click="toggleSort('login')">Last Login <i class="fas fa-sort"></i></th>
                <th class="sortable" @click="toggleSort('days')">{{ activityMetricHeading }} <i class="fas fa-sort"></i></th>
                <th>{{ detailStatusHeading }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in filteredUsers" :key="user.id">
                <td><strong>{{ user.name }}</strong></td>
                <td><span :class="['role-pill', user.role.toLowerCase()]">{{ user.role }}</span></td>
                <td>{{ formatLogin(user.lastLogin) }}</td>
                <td>{{ activityMetricValue(user) }}</td>
                <td><span :class="['status-pill', userDetailStatusClass(user)]">{{ userDetailStatusLabel(user) }}</span></td>
              </tr>
              <tr v-if="filteredUsers.length === 0">
                <td colspan="5" class="empty-state">No users match the current filters.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <div class="right-stack">

        <article class="analytics-card recency-card">
          <h2>Login Recency</h2>
          <p class="card-subtitle">Users grouped by how recently they logged in.</p>

          <div class="recency-list">
            <div
              v-for="(item, index) in selectedLoginRecency"
              :key="item.label"
              class="recency-row interactive-chart-row"
              @mouseenter="showTooltip($event, item.label, `${item.value}`, 'Users')"
              @mousemove="moveTooltip"
              @mouseleave="hideTooltip"
            >
              <span class="rank">{{ index + 1 }}</span>
              <span>{{ item.label }}</span>
              <div class="recency-track">
                <i :style="{ width: `${(item.value / maxRecency) * 100}%` }"></i>
              </div>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </article>

        <article class="analytics-card insights-card">
          <AnalyticsKeyInsights
            :items="activityInsightItems"
            description="Summarises login coverage and identifies the participant role with the strongest login rate."
          />
        </article>
      </div>
    </div>

    <ChartTooltip
      :visible="tooltip.visible"
      :x="tooltip.x"
      :y="tooltip.y"
      :title="tooltip.title"
      :value="tooltip.value"
      :detail="tooltip.detail"
    />
    </AnalyticsDataState>
  </section>
</template>

<script setup lang="ts">
import AnalyticsPartialNotice from '@/components/analytics/AnalyticsPartialNotice.vue'
import AnalyticsYearChange from '@/components/analytics/AnalyticsYearChange.vue'
import AnalyticsNumber from '@/components/analytics/AnalyticsNumber.vue'
import type { AnalyticsSource } from '@/utils/liveAnalyticsData'
import AnalyticsRefreshStatus from '@/components/analytics/AnalyticsRefreshStatus.vue'
import { useAnalyticsRefresh } from '@/composables/useAnalyticsRefresh'
import { useAnalyticsRefreshState } from '@/composables/useAnalyticsRefreshState'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import AnalyticsKeyInsights from '@/components/analytics/AnalyticsKeyInsights.vue'
import AnalyticsDataState from '@/components/analytics/AnalyticsDataState.vue'
import AnalyticsDatePicker from '@/components/analytics/AnalyticsDatePicker.vue'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import type { LoginActivityResponse } from '@/utils/liveAnalyticsApi'
import { useRoute } from 'vue-router'
import type {
  ActivityAnalyticsData,
  ActivityRole,
  ActivityStatus,
  GroupsAnalyticsYear,
  UserAnalyticsYear,
} from '@/types/analytics'
import {
  buildGroupActivityDetailRows,
  type GroupActivityDetailRow,
  type GroupActivityDetailStatus,
} from '@/utils/activityGroupRows'
import {
  buildActivityAnalytics,
  buildGroupsAnalytics,
  buildUsersAnalytics,
  liveAnalyticsAsOf,
  liveAnalyticsYear,
  loadActivityAnalyticsBundle,
  loadLoginActivityRange,
  type CoreAnalyticsBundle,
} from '@/utils/liveAnalyticsData'

const data = reactive<ActivityAnalyticsData>({
  totalUsers: 0,
  dailyActive: 0,
  weeklyActive: 0,
  monthlyActive: 0,
  loggedInRate: 0,
  neverLoggedIn: 0,
  dailySeries: { students: [], mentors: [], supervisors: [] },
  roleLoginRates: [],
  loginRecency: [],
  users: [],
})
const liveUserData = ref<UserAnalyticsYear>({
  totalUsers: 0, students: 0, mentors: 0, supervisors: 0,
  totalGrowth: null, studentGrowth: null, mentorGrowth: null, supervisorGrowth: null,
  loginRates: { students: 0, mentors: 0, supervisors: 0 },
  dailyActivity: { labels: [], total: [] },
  lastLogin: [], userLastLogins: [],
  registration: { students: [], mentors: [], supervisors: [] },
  regions: [], interests: [],
})
const liveGroupData = ref<GroupsAnalyticsYear>({
  totalGroups: 0, groupGrowth: 0, averageGroupSize: 0,
  averageGroupSizePrevious: null, averageGroupSizePreviousYear: new Date().getFullYear() - 1, avgSizeChange: 0,
  groupsWithMentor: 0, groupsWithoutMentor: 0, mentorStudentRatio: 0,
  comparisonPreviousYear: new Date().getFullYear() - 1,
  groupsWithMentorPrevious: null, groupsWithoutMentorPrevious: null,
  mentorStudentRatioPrevious: null,
  smallGroups: 0, inactiveRecent: 0, nearCapacity: 0, overCapacity: 0,
  groupSizeDistribution: [], groupStatus: [], ratioDistribution: [], groupActivity: [],
})
const liveYear = ref(new Date().getFullYear())
const unavailableSources = ref<AnalyticsSource[]>([])
const sourceAvailable = (source: AnalyticsSource) => !unavailableSources.value.includes(source)
const loadError = ref('')
const isLoading = ref(true)
const isEmpty = ref(false)
const hasLoaded = ref(false)
const exportDisabled = computed(() => isLoading.value || !!loadError.value || isEmpty.value || !hasLoaded.value || (viewMode.value === 'groups'
  ? !sourceAvailable('groups') || !sourceAvailable('groupActivity')
  : !sourceAvailable('users')))
const route = useRoute()
const issueContext = ref<'inactive-mentors' | 'deactivated' | ''>('')

const viewMode = ref<'users' | 'groups'>('users')
const liveCoreBundle = ref<CoreAnalyticsBundle | null>(null)

const tooltip = ref({
  visible: false,
  x: 0,
  y: 0,
  title: '',
  value: '',
  detail: '',
})

function showTooltip(event: MouseEvent, title: string, value: string, detail = '') {
  tooltip.value = {
    visible: true,
    x: event.clientX,
    y: event.clientY,
    title,
    value,
    detail,
  }
}

function moveTooltip(event: MouseEvent) {
  tooltip.value.x = event.clientX
  tooltip.value.y = event.clientY
}

function hideTooltip() {
  tooltip.value.visible = false
}

const today = ref(new Date())
const currentYear = computed(() => liveYear.value)
const availableYears = computed(() => [liveYear.value])
const selectedYear = ref(liveYear.value)
const selectedUserYearData = computed(() => liveUserData.value)

type TrendInterval = 'day' | 'week' | 'month'
const trendInterval = ref<TrendInterval>('day')
const selectedRole = ref<'all' | ActivityRole>('all')
const selectedStatus = ref<'all' | ActivityStatus | GroupActivityDetailStatus>('all')
const hiddenRoles = ref<string[]>([])
const searchQuery = ref('')
const showAllActivityDetails = ref(false)
const highlightedGroupStatus = ref<GroupActivityDetailStatus | null>(null)
const sortKey = ref<'login' | 'days'>('days')
const sortDirection = ref<'asc' | 'desc'>('asc')

function applyGroupStatusFilter(status: GroupActivityDetailStatus) {
  showAllActivityDetails.value = false
  selectedStatus.value = status
  highlightedGroupStatus.value = status
}

const USER_ACTIVITY_THRESHOLD_KEY = 'btf.analytics.activity.userThresholdDays'
const GROUP_ACTIVITY_THRESHOLD_KEY = 'btf.analytics.activity.groupThresholdDays'
const DEFAULT_USER_ACTIVITY_THRESHOLD_DAYS = 7
const DEFAULT_GROUP_ACTIVITY_THRESHOLD_DAYS = 3

function savedThreshold(key: string, fallback: number) {
  if (typeof window === 'undefined') return fallback
  const saved = window.localStorage.getItem(key)
  if (saved === null || saved.trim() === '') return fallback
  const value = Number(saved)
  return Number.isFinite(value) && value >= 0
    ? Math.min(3650, Math.round(value))
    : fallback
}

const userActivityThreshold = ref(savedThreshold(USER_ACTIVITY_THRESHOLD_KEY, DEFAULT_USER_ACTIVITY_THRESHOLD_DAYS))
const groupActivityThreshold = ref(savedThreshold(GROUP_ACTIVITY_THRESHOLD_KEY, DEFAULT_GROUP_ACTIVITY_THRESHOLD_DAYS))

function normaliseThreshold(scope: 'users' | 'groups') {
  const target = scope === 'users' ? userActivityThreshold : groupActivityThreshold
  const parsed = Number(target.value)
  target.value = Number.isFinite(parsed)
    ? Math.min(3650, Math.max(0, Math.round(parsed)))
    : scope === 'users'
      ? DEFAULT_USER_ACTIVITY_THRESHOLD_DAYS
      : DEFAULT_GROUP_ACTIVITY_THRESHOLD_DAYS
}

watch(userActivityThreshold, (value) => {
  if (typeof window !== 'undefined' && Number.isFinite(Number(value))) {
    window.localStorage.setItem(USER_ACTIVITY_THRESHOLD_KEY, String(value))
  }
})

watch(groupActivityThreshold, (value) => {
  if (typeof window !== 'undefined' && Number.isFinite(Number(value))) {
    window.localStorage.setItem(GROUP_ACTIVITY_THRESHOLD_KEY, String(value))
  }
})


function toInputDate(date: Date) {
  const year = date.getUTCFullYear()
  const month = String(date.getUTCMonth() + 1).padStart(2, '0')
  const day = String(date.getUTCDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function startOfDay(date: Date) {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()))
}

const yearAnchorDate = computed(() => {
  const month = currentYear.value === selectedYear.value ? today.value.getUTCMonth() : 8
  const day = currentYear.value === selectedYear.value ? today.value.getUTCDate() : 15
  return new Date(Date.UTC(selectedYear.value, month, day))
})

function dateInSelectedYearDaysAgo(count: number) {
  const date = startOfDay(yearAnchorDate.value)
  date.setUTCDate(date.getUTCDate() - count)
  return date
}

const selectedStartDate = ref(toInputDate(dateInSelectedYearDaysAgo(29)))
const selectedEndDate = ref(toInputDate(yearAnchorDate.value))
const trendDataStart = ref(selectedStartDate.value)
const trendDataEnd = ref(selectedEndDate.value)
const trendDataYears = ref<number[]>([Number(selectedEndDate.value.slice(0, 4))])

function updateTrendStart(value: string) {
  selectedStartDate.value = value
  normaliseTrendDates('start')
}

function updateTrendEnd(value: string) {
  selectedEndDate.value = value
  normaliseTrendDates('end')
}

function normaliseTrendDates(changed: 'start' | 'end') {
  if (trendDataStart.value && selectedStartDate.value < trendDataStart.value) {
    selectedStartDate.value = trendDataStart.value
  }
  if (trendDataEnd.value && selectedStartDate.value > trendDataEnd.value) {
    selectedStartDate.value = trendDataEnd.value
  }
  if (trendDataStart.value && selectedEndDate.value < trendDataStart.value) {
    selectedEndDate.value = trendDataStart.value
  }
  if (trendDataEnd.value && selectedEndDate.value > trendDataEnd.value) {
    selectedEndDate.value = trendDataEnd.value
  }
  if (selectedStartDate.value > selectedEndDate.value) {
    if (changed === 'start') selectedEndDate.value = selectedStartDate.value
    else selectedStartDate.value = selectedEndDate.value
  }
}

watch(selectedYear, () => {
  selectedStartDate.value = toInputDate(dateInSelectedYearDaysAgo(29))
  selectedEndDate.value = toInputDate(yearAnchorDate.value)
  searchQuery.value = ''
})

watch(viewMode, (mode) => {
  highlightedGroupStatus.value = null
  if (!availableYears.value.includes(selectedYear.value)) {
    selectedYear.value = availableYears.value[0]
  }
  if (mode === 'groups') {
    selectedRole.value = 'all'
    if (selectedStatus.value === 'Never') selectedStatus.value = 'all'
  } else {
    if (selectedStatus.value === 'Not started') selectedStatus.value = 'all'
  }
  if (liveCoreBundle.value) applyObservedTrendRange()
})

watch(selectedStatus, (status) => {
  if (highlightedGroupStatus.value !== status) {
    highlightedGroupStatus.value = null
  }
})

watch(showAllActivityDetails, (showAll) => {
  if (showAll) highlightedGroupStatus.value = null
})

const selectedLoggedInRate = computed(() => {
  return data.users.length ? Math.round(loggedInCount.value / data.users.length * 100) : 0
})

const loggedInCount = computed(() =>
  data.users.filter((user) => !!user.lastLogin).length,
)
const selectedNeverLoggedIn = computed(() =>
  data.users.filter((user) => !user.lastLogin).length,
)
const loginHistoryAvailable = computed(() => data.loginHistoryAvailable
  ?? !!liveCoreBundle.value?.loginActivity?.by_day.length)

type ActivityWindowComparison = NonNullable<LoginActivityResponse['active_user_comparison']>
const activityWindowComparison = ref<ActivityWindowComparison | null>(null)
let activityWindowRequest = 0

async function loadActivityWindowComparison() {
  const request = ++activityWindowRequest
  const end = parseInputDate(selectedEndDate.value)
  if (!end || !sourceAvailable('loginActivity')) {
    activityWindowComparison.value = null
    return
  }
  // The unranged response already compares windows ending on the latest
  // login date, so the default end date needs no extra request.
  const loaded = liveCoreBundle.value?.loginActivity
  if (loaded?.active_user_comparison && loaded.latest_activity_date === selectedEndDate.value) {
    activityWindowComparison.value = loaded.active_user_comparison
    return
  }
  const start = new Date(end)
  start.setUTCDate(start.getUTCDate() - 59)
  try {
    const response = await loadLoginActivityRange(
      start.toISOString().slice(0, 10),
      selectedEndDate.value,
    )
    if (request === activityWindowRequest) {
      activityWindowComparison.value = response.active_user_comparison ?? null
    }
  } catch {
    if (request === activityWindowRequest) activityWindowComparison.value = null
  }
}

const yearKpis = computed(() => ({
  dailyActive: activityWindowComparison.value?.daily.current ?? data.dailyActive,
  weeklyActive: activityWindowComparison.value?.weekly.current ?? data.weeklyActive,
  monthlyActive: activityWindowComparison.value?.monthly.current ?? data.monthlyActive,
}))
watch(selectedEndDate, () => { void loadActivityWindowComparison() })
const yearlyLoginComparison = computed(() => {
  const rows = liveCoreBundle.value?.loginActivity?.by_year ?? []
  return {
    current: rows.find((row) => row.year === selectedYear.value)?.total ?? 0,
    previous: rows.find((row) => row.year === selectedYear.value - 1)?.total ?? 0,
    previousYear: selectedYear.value - 1,
  }
})



function parseInputDate(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const date = new Date(`${value}T00:00:00Z`)
  return Number.isNaN(date.getTime()) ? null : date
}

const validTrendRange = computed(() => {
  const start = parseInputDate(selectedStartDate.value)
  const end = parseInputDate(selectedEndDate.value)
  return start && end && start <= end ? { start, end } : null
})

function recommendedInterval(start: Date, end: Date): TrendInterval {
  const days = Math.floor((end.getTime() - start.getTime()) / 86_400_000) + 1
  if (days <= 45) return 'day'
  if (days <= 240) return 'week'
  return 'month'
}

watch([selectedStartDate, selectedEndDate], () => {
  const range = validTrendRange.value
  if (range) trendInterval.value = recommendedInterval(range.start, range.end)
})

function trendBucket(date: Date) {
  if (trendInterval.value === 'week') {
    const monday = new Date(date)
    const day = monday.getUTCDay() || 7
    monday.setUTCDate(monday.getUTCDate() - day + 1)
    return {
      key: monday.toISOString().slice(0, 10),
      label: `Week of ${monday.toLocaleDateString('en-AU', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' })}`,
      shortLabel: monday.toLocaleDateString('en-AU', { day: '2-digit', month: 'short', timeZone: 'UTC' }),
    }
  }
  if (trendInterval.value === 'month') {
    return {
      key: date.toISOString().slice(0, 7),
      label: date.toLocaleDateString('en-AU', { month: 'long', year: 'numeric', timeZone: 'UTC' }),
      shortLabel: date.toLocaleDateString('en-AU', { month: 'short', year: '2-digit', timeZone: 'UTC' }),
    }
  }
  return {
    key: date.toISOString().slice(0, 10),
    label: date.toLocaleDateString('en-AU', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }),
    shortLabel: date.toLocaleDateString('en-AU', { day: '2-digit', month: 'short', timeZone: 'UTC' }),
  }
}

const trendBuckets = computed(() => {
  const range = validTrendRange.value
  if (!range) return []
  const buckets = new Map<string, { key: string; label: string; shortLabel: string }>()
  for (const cursor = new Date(range.start); cursor <= range.end; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
    const bucket = trendBucket(cursor)
    if (!buckets.has(bucket.key)) buckets.set(bucket.key, bucket)
  }
  return [...buckets.values()]
})

const trendIntervalLabel = computed(() =>
  trendInterval.value === 'day' ? 'Daily' : trendInterval.value === 'week' ? 'Weekly' : 'Monthly',
)
const chartDateLabels = computed(() => trendBuckets.value.map((bucket) => bucket.shortLabel))

const filteredSeries = computed(() => {
  const indexes = new Map(trendBuckets.value.map((bucket, index) => [bucket.key, index]))
  const result = {
    students: Array(trendBuckets.value.length).fill(0) as number[],
    mentors: Array(trendBuckets.value.length).fill(0) as number[],
    supervisors: Array(trendBuckets.value.length).fill(0) as number[],
  }
  const recordedLogins = liveCoreBundle.value?.loginActivity?.by_day
  if (recordedLogins) {
    for (const row of recordedLogins) {
      if (!validTrendRange.value || row.date < selectedStartDate.value || row.date > selectedEndDate.value) continue
      const date = new Date(`${row.date}T00:00:00Z`)
      const index = indexes.get(trendBucket(date).key)
      if (index === undefined) continue
      result.students[index] += row.students
      result.mentors[index] += row.mentors
      result.supervisors[index] += row.supervisors
    }
    return result
  }
  for (const user of data.users) {
    if (!user.lastLogin) continue
    const date = new Date(user.lastLogin)
    if (Number.isNaN(date.getTime()) || !validTrendRange.value) continue
    const day = date.toISOString().slice(0, 10)
    if (day < selectedStartDate.value || day > selectedEndDate.value) continue
    const index = indexes.get(trendBucket(date).key)
    if (index === undefined) continue
    const series = user.role === 'Student' ? result.students : user.role === 'Mentor' ? result.mentors : result.supervisors
    series[index] += 1
  }
  return result
})


const chartSeries = computed(() => [
  {
    key: 'students',
    role: 'Student' as ActivityRole,
    label: 'Students',
    values: filteredSeries.value.students,
  },
  {
    key: 'mentors',
    role: 'Mentor' as ActivityRole,
    label: 'Mentors',
    values: filteredSeries.value.mentors,
  },
  {
    key: 'supervisors',
    role: 'Supervisor' as ActivityRole,
    label: 'Supervisors',
    values: filteredSeries.value.supervisors,
  },
])

const visibleChartSeries = computed(() =>
  chartSeries.value.filter((series) => {
    const matchesRole = selectedRole.value === 'all' || series.role === selectedRole.value
    return matchesRole && !hiddenRoles.value.includes(series.key)
  }),
)

const activityMax = computed(() =>
  Math.max(
    ...visibleChartSeries.value.flatMap((series) => series.values),
    1,
  ),
)

function showXAxisLabel(index: number, length: number) {
  if (length <= 10) return true
  const step = Math.ceil((length - 1) / 9)
  return index === 0 || index === length - 1 || index % step === 0
}

function showPointValue(index: number, length: number) {
  return length <= 14 || showXAxisLabel(index, length)
}


const groupMonthLabels = computed(() => trendBuckets.value.map((bucket) => bucket.shortLabel))
const groupActiveValues = computed(() => {
  const indexes = new Map(trendBuckets.value.map((bucket, index) => [bucket.key, index]))
  const activeIds = trendBuckets.value.map(() => new Set<number>())
  for (const row of liveCoreBundle.value?.groupActivity.messages_by_group_by_day ?? []) {
    const day = row.date.slice(0, 10)
    if (day < selectedStartDate.value || day > selectedEndDate.value || row.message_count <= 0) continue
    const date = parseInputDate(day)
    if (!date) continue
    const index = indexes.get(trendBucket(date).key)
    if (index !== undefined) activeIds[index]?.add(row.group_id)
  }
  return activeIds.map((ids) => ids.size)
})
const groupInactiveValues = computed(() =>
  groupActiveValues.value.map((active) => Math.max(0, (liveCoreBundle.value?.groups.length ?? 0) - active)),
)
const groupActivityMax = computed(() =>
  Math.max(...groupActiveValues.value, ...groupInactiveValues.value, 1),
)
const groupActivityAxisMax = computed(() => niceMax(groupActivityMax.value))
const groupActivityTicks = computed(() => {
  const max = groupActivityAxisMax.value
  return [max, Math.round(max * 0.75), Math.round(max * 0.5), Math.round(max * 0.25), 0]
})

function groupActivityX(index: number, count: number) {
  if (count <= 1) return 360
  return 40 + index * (640 / (count - 1))
}

function groupActivityY(value: number) {
  const top = 24
  const bottom = 210
  return bottom - (value / groupActivityAxisMax.value) * (bottom - top)
}

function groupSeriesDots(values: number[]) {
  return values.map((value, index) => ({
    index,
    value,
    x: groupActivityX(index, values.length),
    y: groupActivityY(value),
  }))
}

function groupSeriesPoints(values: number[]) {
  return groupSeriesDots(values).map((point) => `${point.x},${point.y}`).join(' ')
}

const groupActiveCount = computed(
  () => groupRows.value.filter((group) => group.status === 'Active').length,
)
const groupInactiveCount = computed(
  () => groupRows.value.filter((group) => group.status === 'Inactive').length,
)
const groupNotStartedCount = computed(
  () => groupRows.value.filter((group) => group.status === 'Not started').length,
)
const groupActivityTotal = computed(() => Math.max(
  groupActiveCount.value + groupInactiveCount.value + groupNotStartedCount.value,
  1,
))
const groupActivePercent = computed(() => Math.round((groupActiveCount.value / groupActivityTotal.value) * 100))
const groupInactivePercent = computed(() => Math.round((groupInactiveCount.value / groupActivityTotal.value) * 100))
const groupNotStartedPercent = computed(() => Math.round((groupNotStartedCount.value / groupActivityTotal.value) * 100))

type GroupSortKey = 'name' | 'status' | 'lastActiveDate' | 'daysSinceActive'

const groupSearch = ref('')
const groupSortKey = ref<GroupSortKey>('daysSinceActive')
const groupSortDirection = ref<'asc' | 'desc'>('asc')

useAnalyticsRefreshState('activity', {
  selectedYear,
  viewMode,
  selectedStartDate,
  selectedEndDate,
  trendInterval,
  selectedRole,
  selectedStatus,
  hiddenRoles,
  searchQuery,
  groupSearch,
  showAllActivityDetails,
  highlightedGroupStatus,
  userActivityThreshold,
  groupActivityThreshold,
  sortKey,
  sortDirection,
  groupSortKey,
  groupSortDirection,
}, () => !isLoading.value && hasLoaded.value)

const groupRows = computed<GroupActivityDetailRow[]>(() => {
  const rows = liveCoreBundle.value ? buildGroupActivityDetailRows(liveCoreBundle.value) : []
  return rows.map((group) => ({
    ...group,
    status: (
      group.daysSinceActive === null
        ? 'Not started'
        : group.daysSinceActive <= Number(groupActivityThreshold.value)
          ? 'Active'
          : 'Inactive'
    ) as GroupActivityDetailStatus,
  }))
})

function matchesGroupPeriod(group: GroupActivityDetailRow) {
  if (selectedStatus.value === 'all') return true
  if (selectedStatus.value === 'Not started') return group.lastActiveDate === null
  if (selectedStatus.value === 'Inactive') return true
  if (!group.lastActiveDate) return false
  return group.lastActiveDate >= selectedStartDate.value && group.lastActiveDate <= selectedEndDate.value
}

const filteredGroupRows = computed(() => {
  const query = groupSearch.value.trim().toLowerCase()
  return [...groupRows.value]
    .filter((group) => {
      const matchesSearch = !query || [group.name, ...group.mentors]
        .some((value) => value.toLowerCase().includes(query))
      const matchesStatus = selectedStatus.value === 'all' || group.status === selectedStatus.value
      return matchesSearch && (
        showAllActivityDetails.value || (matchesStatus && matchesGroupPeriod(group))
      )
    })
    .sort((a, b) => {
      const key = groupSortKey.value
      let comparison = 0
      if (key === 'name') comparison = a.name.localeCompare(b.name, undefined, { numeric: true })
      else if (key === 'status') comparison = a.status.localeCompare(b.status)
      else {
        const aValue = key === 'lastActiveDate'
          ? (a.lastActiveDate ? new Date(`${a.lastActiveDate}T00:00:00Z`).getTime() : null)
          : a.daysSinceActive
        const bValue = key === 'lastActiveDate'
          ? (b.lastActiveDate ? new Date(`${b.lastActiveDate}T00:00:00Z`).getTime() : null)
          : b.daysSinceActive
        if (aValue === null || bValue === null) {
          if (aValue === bValue) comparison = 0
          else return aValue === null ? 1 : -1
        } else comparison = aValue - bValue
      }
      const directed = groupSortDirection.value === 'asc' ? comparison : -comparison
      return directed || a.name.localeCompare(b.name, undefined, { numeric: true })
    })
})

function toggleGroupSort(key: GroupSortKey) {
  if (groupSortKey.value === key) {
    groupSortDirection.value = groupSortDirection.value === 'asc' ? 'desc' : 'asc'
    return
  }
  groupSortKey.value = key
  groupSortDirection.value = 'asc'
}

function groupSortIcon(key: GroupSortKey) {
  if (groupSortKey.value !== key) return 'fas fa-sort'
  return groupSortDirection.value === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'
}

function formatGroupLastActive(date: string | null) {
  if (!date) return 'No messages recorded'
  return new Date(`${date}T00:00:00Z`).toLocaleDateString('en-AU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

function groupStatusClass(status: GroupActivityDetailStatus) {
  return status.toLowerCase().replace(/\s+/g, '-')
}

function niceMax(value: number) {
  if (value <= 20) return Math.max(4, Math.ceil(value / 4) * 4)
  if (value <= 100) return Math.ceil(value / 20) * 20
  return Math.ceil(value / 50) * 50
}

const activityAxisMax = computed(() => niceMax(activityMax.value))
const activityTicks = computed(() => {
  const max = activityAxisMax.value
  return [max, max * 0.75, max * 0.5, max * 0.25, 0]
})

function activityX(index: number, count: number) {
  if (count <= 1) return 360
  return 40 + index * (640 / (count - 1))
}

function activityY(value: number) {
  const top = 24
  const bottom = 210
  return bottom - (value / activityAxisMax.value) * (bottom - top)
}

function activityYPercent(value: number) {
  return (activityY(value) / 250) * 100
}

function seriesDots(values: number[]) {
  return values.map((value, index) => ({
    index,
    value,
    x: activityX(index, values.length),
    y: activityY(value),
  }))
}

function seriesPoints(values: number[]) {
  return seriesDots(values).map((point) => `${point.x},${point.y}`).join(' ')
}

function roleIcon(role: ActivityRole) {
  if (role === 'Student') return 'fas fa-graduation-cap'
  if (role === 'Mentor') return 'fas fa-user-tie'
  return 'fas fa-user-shield'
}

function pluralRole(role: ActivityRole) {
  if (role === 'Student') return 'Students'
  if (role === 'Mentor') return 'Mentors'
  return 'Supervisors'
}

function statusLabel(status: ActivityStatus) {
  return status === 'Never' ? 'Never Logged In' : status
}

const activityMetricHeading = computed(() => {
  if (selectedStatus.value === 'Active') return 'Days Since Last Login'
  if (selectedStatus.value === 'Inactive') return 'Days Inactive'
  if (selectedStatus.value === 'Never') return 'Login Activity'
  return 'Activity Recency'
})

function activityMetricValue(user: (typeof yearUsers.value)[number]) {
  if (user.status === 'Never' || user.daysInactive === null) return 'Never logged in'
  if (selectedStatus.value === 'all') {
    return user.daysInactive === 0
      ? 'Today'
      : `${user.daysInactive} day${user.daysInactive === 1 ? '' : 's'} ago`
  }
  return user.daysInactive
}


function matchesSelectedPeriod(user: (typeof yearUsers.value)[number]) {
  if (selectedStatus.value === 'all') return true
  if (selectedStatus.value === 'Never') return user.lastLogin === null
  if (selectedStatus.value === 'Inactive') return true
  if (!user.lastLogin) return false
  const loginDay = new Date(user.lastLogin).toISOString().slice(0, 10)
  return loginDay >= selectedStartDate.value && loginDay <= selectedEndDate.value
}

const filteredRoleLoginRates = computed(() => {
  const rates = selectedUserYearData.value.loginRates
  const items = [
    { role: 'Student' as ActivityRole, value: rates.students },
    { role: 'Mentor' as ActivityRole, value: rates.mentors },
    { role: 'Supervisor' as ActivityRole, value: rates.supervisors },
  ]

  return selectedRole.value === 'all'
    ? items
    : items.filter((item) => item.role === selectedRole.value)
})


function formatLogin(value: string | null) {
  if (!value) return 'Never'
  const date = new Date(value)
  return date.toLocaleString('en-AU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

const yearUsers = computed(() =>
  data.users.map((user) => ({
    ...user,
    status: (
      accountIsInactive(user)
        ? 'Inactive'
        : user.lastLogin === null || user.daysInactive === null
        ? 'Never'
        : user.daysInactive <= Number(userActivityThreshold.value)
          ? 'Active'
          : 'Inactive'
    ) as ActivityStatus,
  })),
)

const detailStatusHeading = computed(() => issueContext.value ? 'Account Status' : 'Status')

function accountIsInactive(user: ActivityAnalyticsData['users'][number]) {
  const status = (user.accountStatus ?? '').toLowerCase()
  return user.isActive === false || status === 'deactivated' || status === 'suspended'
}

function matchesIssueContext(user: (typeof yearUsers.value)[number]) {
  if (issueContext.value === 'inactive-mentors') return user.role === 'Mentor' && user.isActive === false
  if (issueContext.value === 'deactivated') return accountIsInactive(user)
  return true
}

function userDetailStatusLabel(user: (typeof yearUsers.value)[number]) {
  if (!issueContext.value) return statusLabel(user.status)
  if (accountIsInactive(user)) return 'Inactive'
  const accountStatus = (user.accountStatus ?? '').trim()
  if (accountStatus) return accountStatus.charAt(0).toUpperCase() + accountStatus.slice(1).toLowerCase()
  return user.isActive === false ? 'Inactive' : 'Active'
}

function userDetailStatusClass(user: (typeof yearUsers.value)[number]) {
  if (!issueContext.value) return user.status.toLowerCase()
  return accountIsInactive(user) ? 'inactive' : 'active'
}

const filteredUsers = computed(() => {
  const query = searchQuery.value.toLowerCase()
  const rows = yearUsers.value.filter((user) => {
    const matchesSearch = !query || user.name.toLowerCase().includes(query)
    const matchesRole = selectedRole.value === 'all' || user.role === selectedRole.value
    const matchesStatus = selectedStatus.value === 'all' || user.status === selectedStatus.value
    if (!matchesSearch) return false
    if (showAllActivityDetails.value) return true
    if (issueContext.value) return matchesRole && matchesIssueContext(user)
    return matchesRole && matchesStatus && matchesSelectedPeriod(user)
  })

  return [...rows].sort((a, b) => {
    let result = 0

    if (sortKey.value === 'days') {
      const aValue = a.daysInactive ?? Number.POSITIVE_INFINITY
      const bValue = b.daysInactive ?? Number.POSITIVE_INFINITY
      result = aValue - bValue
    } else {
      const aValue = a.lastLogin ? new Date(a.lastLogin).getTime() : 0
      const bValue = b.lastLogin ? new Date(b.lastLogin).getTime() : 0
      result = aValue - bValue
    }

    return sortDirection.value === 'asc' ? result : -result
  })
})

function toggleSort(key: 'login' | 'days') {
  if (sortKey.value === key) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDirection.value = 'asc'
  }
}

const selectedLoginRecency = computed(() =>
  selectedUserYearData.value.lastLogin.map((item) => ({ label: item.label, value: item.value })),
)
const maxRecency = computed(() => Math.max(...selectedLoginRecency.value.map((item) => item.value), 1))
const mostActiveRole = computed(() =>
  [...filteredRoleLoginRates.value].sort((a, b) => b.value - a.value)[0] ?? {
    role: 'Student' as ActivityRole,
    value: 0,
  },
)
const activityInsightItems = computed(() => [
  { key: 'logged-in', value: `${selectedLoggedInRate.value}%`, text: 'of current participants have logged in at least once.' },
  { key: 'never', value: selectedNeverLoggedIn.value, text: 'participants have never logged in and may need follow-up.' },
  {
    key: 'role',
    value: mostActiveRole.value.role,
    text: `currently has the highest login rate at ${mostActiveRole.value.value}%.`,
  },
])

function applyObservedTrendRange() {
  const bundle = liveCoreBundle.value
  const fallbackEnd = toInputDate(today.value)
  if (!bundle) {
    selectedStartDate.value = fallbackEnd
    selectedEndDate.value = fallbackEnd
    trendInterval.value = 'day'
    return
  }

  // The chart uses recorded login events, so its controls must expose the same history.
  const userObserved = (bundle.loginActivity?.by_day ?? [])
    .map((row) => row.date)
    .filter((value) => /^\d{4}-\d{2}-\d{2}$/.test(value))
  const groupObserved = [
    ...bundle.groupActivity.messages_by_day.map((row) => row.date.slice(0, 10)),
    ...groupRows.value.map((group) => group.lastActiveDate),
  ].filter((value): value is string => !!value && /^\d{4}-\d{2}-\d{2}$/.test(value))
  const observed = (viewMode.value === 'users' ? userObserved : groupObserved).sort()
  const end = observed[observed.length - 1] ?? fallbackEnd

  trendDataStart.value = observed[0] ?? end
  trendDataEnd.value = end
  if (viewMode.value === 'users') {
    // Include silent years between events: dates in those years are valid zero-activity selections.
    const firstYear = Number(trendDataStart.value.slice(0, 4))
    const lastYear = Number(end.slice(0, 4))
    trendDataYears.value = Array.from({ length: lastYear - firstYear + 1 }, (_, index) => firstYear + index)
  } else {
    trendDataYears.value = [...new Set(observed.map((value) => Number(value.slice(0, 4))))].sort((a, b) => a - b)
  }
  if (!trendDataYears.value.length) trendDataYears.value = [Number(end.slice(0, 4))]
  const defaultStart = new Date(`${trendDataEnd.value}T00:00:00Z`)
  defaultStart.setUTCDate(defaultStart.getUTCDate() - 7)
  selectedStartDate.value = defaultStart.toISOString().slice(0, 10) < trendDataStart.value
    ? trendDataStart.value
    : defaultStart.toISOString().slice(0, 10)
  selectedEndDate.value = trendDataEnd.value
  const range = validTrendRange.value
  trendInterval.value = range ? recommendedInterval(range.start, range.end) : 'day'
}

function resetFilters() {
  applyObservedTrendRange()
  selectedRole.value = 'all'
  selectedStatus.value = 'all'
  searchQuery.value = ''
  groupSearch.value = ''
  showAllActivityDetails.value = false
}


const analyticsRefreshBusy = ref(false)
const { lastUpdated, refreshFailed, markUpdated, markRefreshFailed } = useAnalyticsRefresh(async () => { if (!analyticsRefreshBusy.value) await loadAnalytics(true, true) })

async function loadAnalytics(force = false, preserveFilters = false) {
  if (analyticsRefreshBusy.value) return
  analyticsRefreshBusy.value = true
  if (!preserveFilters || !lastUpdated.value) isLoading.value = true
  loadError.value = ''
  try {
    const bundle = await loadActivityAnalyticsBundle(force)
    unavailableSources.value = bundle.unavailableSources ?? []
    const year = liveAnalyticsYear(bundle)
    today.value = new Date(`${liveAnalyticsAsOf(bundle)}T00:00:00Z`)
    liveYear.value = year
    if (!preserveFilters) selectedYear.value = year
    Object.assign(data, buildActivityAnalytics(bundle))
    liveUserData.value = buildUsersAnalytics(bundle)
    liveGroupData.value = buildGroupsAnalytics(bundle)
    liveCoreBundle.value = bundle
    if (!preserveFilters) applyObservedTrendRange()
    // Show the page now; the window KPIs update when their comparison arrives.
    void loadActivityWindowComparison()
    const hasParticipants = bundle.users.some((user) =>
      ['student', 'mentor', 'supervisor'].includes((user.role ?? '').toLowerCase()),
    )
    isEmpty.value = unavailableSources.value.length === 0 && !hasParticipants && bundle.groups.length === 0
    if (!sourceAvailable('users') && sourceAvailable('groups') && sourceAvailable('groupActivity')) viewMode.value = 'groups'
    else if (!sourceAvailable('groups') || !sourceAvailable('groupActivity')) viewMode.value = 'users'
    hasLoaded.value = true
    markUpdated()
  } catch (error) {
    if (preserveFilters && lastUpdated.value) { markRefreshFailed(); return }
    console.error('Failed to load activity analytics from the backend.', error)
    loadError.value = 'Activity analytics could not be loaded from the backend. Check the API and try again.'
    hasLoaded.value = false
  } finally {
    analyticsRefreshBusy.value = false
    isLoading.value = false
  }
}

function refreshAnalytics() {
  return loadAnalytics(true)
}

onMounted(async () => {
  await loadAnalytics()

  const role = typeof route.query.role === 'string' ? route.query.role : ''
  const status = typeof route.query.status === 'string' ? route.query.status : ''
  const issue = typeof route.query.issue === 'string' ? route.query.issue : ''

  if (route.hash !== '#user-activity-details' && !issue) return

  viewMode.value = 'users'
  searchQuery.value = ''

  if (role === 'Mentor' || role === 'Student' || role === 'Supervisor') {
    selectedRole.value = role
  } else {
    selectedRole.value = 'all'
  }

  issueContext.value =
    issue === 'inactive-mentors' || issue === 'deactivated'
      ? issue
      : ''

  if (issueContext.value) {
    selectedStatus.value = 'all'
  } else if (status === 'Active' || status === 'Inactive' || status === 'Never') {
    selectedStatus.value = status
  } else {
    selectedStatus.value = 'all'
  }

  await nextTick()
  requestAnimationFrame(() => {
    document
      .getElementById('user-activity-details')
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
})

function exportCsv() {
  const rows = viewMode.value === 'groups'
    ? [
        ['Group ID', 'Group', 'Mentors', 'Activity Status', 'Last Message Date (UTC)', 'Days Since Last Message'],
        ...filteredGroupRows.value.map((group) => [
          group.id,
          group.name,
          group.mentors.join('; ') || 'None',
          group.status,
          group.lastActiveDate ?? 'No messages recorded',
          group.daysSinceActive ?? '',
        ]),
      ]
    : [
        ['User', 'Role', 'Last Login', activityMetricHeading.value, 'Status'],
        ...filteredUsers.value.map((user) => [
          user.name,
          user.role,
          formatLogin(user.lastLogin),
          activityMetricValue(user),
          statusLabel(user.status),
        ]),
      ]

  const csv = rows
    .map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(','))
    .join('\n')

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `activity-analytics-${viewMode.value}-${selectedYear.value}.csv`
  anchor.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.activity-analytics-page {
  min-width: 0;
  padding: 32px 40px 44px;
  background: #f7faf9;
  color: #174243;
  font-family: Arial, sans-serif;
}

.page-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  margin-bottom: 22px;
}

.breadcrumb {
  display: flex;
  gap: 8px;
  margin-bottom: 18px;
  color: #59706e;
  font-size: 14px;
}

.breadcrumb a {
  color: inherit;
  text-decoration: none;
}

.title-line {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

h1 {
  margin: 0;
  color: #174243;
  font-size: 36px;
  line-height: 1.15;
  font-weight: 800;
}

.heading-copy > p {
  margin: 8px 0 0;
  color: #617572;
  font-size: 16px;
}

.demo-badge {
  display: inline-flex;
  min-height: 30px;
  align-items: center;
  padding: 0 10px;
  border: 1px solid #BAD7B8;
  border-radius: 999px;
  background: #F1E5A6;
  font-size: 12px;
  font-weight: 700;
}

.page-actions {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.year-control,
.export-button,
.reset-button {
  height: 46px;
  border: 1px solid #9fd8c7;
  border-radius: 12px;
  background: #fff;
  color: #017151;
  font-weight: 700;
}

.year-control {
  display: inline-flex;
  width: 120px;
  align-items: center;
  gap: 9px;
  padding: 0 13px;
}

.year-control select {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: #017151;
  font: inherit;
}

.export-button {
  display: inline-flex;
  width: 142px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.kpi-card,
.analytics-card,
.filter-card {
  border: 1px solid #d7e3df;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 8px 20px rgba(23, 66, 67, .04);
}

.kpi-card {
  display: flex;
  min-height: 122px;
  align-items: flex-start;
  gap: 14px;
  padding: 18px;
}

.kpi-icon {
  display: grid;
  width: 50px;
  height: 50px;
  flex: 0 0 50px;
  place-items: center;
  border-radius: 14px;
  background: #e4f0e2;
  color: #017151;
  font-size: 19px;
}

.kpi-icon.warning {
  background: #fff7d6;
  color: #9d7100;
}

.kpi-card span {
  color: #465b57;
  font-size: 13px;
  font-weight: 700;
}

.kpi-card strong {
  display: block;
  margin-top: 5px;
  color: #123f3c;
  font-size: 30px;
  line-height: 1;
}

.kpi-card small {
  display: block;
  margin-top: 8px;
  color: #6c7c78;
  font-size: 12px;
}

.filter-card {
  display: grid;
  grid-template-columns: repeat(3, minmax(180px, 1fr)) auto;
  gap: 14px;
  align-items: end;
  margin-bottom: 18px;
  padding: 16px 18px;
}

.filter-card label {
  display: grid;
  gap: 7px;
}

.filter-card label > span {
  color: #425e59;
  font-size: 12px;
  font-weight: 700;
}

.filter-card select,
.table-heading input {
  height: 42px;
  padding: 0 12px;
  border: 1px solid #BAD7B8;
  border-radius: 10px;
  background: #fff;
  color: #174243;
  font-size: 13px;
}

.reset-button {
  display: inline-flex;
  min-width: 132px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 14px;
  cursor: pointer;
}

.analytics-grid {
  display: grid;
  gap: 18px;
  margin-bottom: 18px;
}

.main-grid {
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, .85fr);
}

.lower-grid {
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, .85fr);
}

.analytics-card {
  padding: 20px;
  min-width: 0;
}

.analytics-card h2 {
  margin: 0;
  color: #174243;
  font-size: 20px;
}

.card-heading,
.table-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.card-heading p,
.table-heading p,
.card-subtitle {
  margin: 5px 0 0;
  color: #6c7c78;
  font-size: 12px;
}

.hide-role-controls {
  display: flex;
  align-items: center;
  gap: 9px;
  flex-wrap: wrap;
  color: #425e59;
  font-size: 11px;
}

.activity-heading-actions {
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}

.compare-year-control {
  display: grid;
  gap: 5px;
}

.compare-year-control span {
  color: #425e59;
  font-size: 11px;
  font-weight: 700;
}

.compare-year-control select {
  height: 34px;
  min-width: 104px;
  padding: 0 30px 0 10px;
  border: 1px solid #BAD7B8;
  border-radius: 9px;
  background: #fff;
  color: #017151;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.hide-role-controls strong {
  color: #174243;
}

.hide-role-controls label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.hide-role-controls input {
  width: 15px;
  height: 15px;
  accent-color: #017151;
}

.line-chart-layout {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 8px;
}

.y-axis {
  display: flex;
  height: 250px;
  flex-direction: column;
  justify-content: space-between;
  padding: 20px 0 30px;
  box-sizing: border-box;
  color: #6c7c78;
  font-size: 11px;
  text-align: right;
}

.activity-y-axis {
  position: relative;
  padding: 0;
}

.activity-analytics-page .activity-y-axis {
  padding: 0 !important;
}

.activity-y-axis span {
  position: absolute;
  right: 0;
  transform: translateY(-50%);
}

.line-chart {
  min-width: 0;
}

.line-chart svg {
  display: block;
  width: 100%;
  height: 250px;
  overflow: visible;
}

.grid-line {
  stroke: #dde7e3;
  stroke-width: 1;
}

.activity-line {
  fill: none;
  stroke-width: 3;
}

.activity-line.students { stroke: #39687B; }
.activity-line.mentors { stroke: #017151; }
.activity-line.supervisors { stroke: #5EA99E; }

.activity-dot {
  stroke: #fff;
  stroke-width: 2;
}

.activity-dot.students { fill: #39687B; }
.activity-dot.mentors { fill: #017151; }
.activity-dot.supervisors { fill: #5EA99E; }

.activity-value {
  fill: #174243;
  font-size: 10px;
  font-weight: 700;
  paint-order: stroke;
  stroke: #fff;
  stroke-width: 3px;
}

.activity-date {
  fill: #667873;
  font-size: 10px;
}

.legend {
  display: flex;
  justify-content: center;
  gap: 18px;
  margin-top: 4px;
  color: #536762;
  font-size: 11px;
}

.legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.dot.students { background: #39687B; }
.dot.mentors { background: #017151; }
.dot.supervisors { background: #5EA99E; }

.text-button {
  border: 0;
  background: transparent;
  color: #017151;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}


.activity-side-stack {
  display: grid;
  gap: 18px;
  align-content: start;
}

.comparison-card-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
}

.comparison-card-heading p {
  margin: 5px 0 0;
  color: #6c7c78;
  font-size: 12px;
  line-height: 1.4;
}

.activity-compare-card .compare-year-control {
  flex: 0 0 150px;
}

.activity-comparison-strip {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 14px;
  margin-top: 0;
  padding: 14px;
  border: 1px solid #dce8e4;
  border-radius: 12px;
  background: #f8fbfa;
}

.activity-comparison-strip > div:not(.comparison-arrow):not(.comparison-change) {
  display: grid;
  gap: 3px;
}

.activity-comparison-strip span {
  color: #6c7c78;
  font-size: 11px;
}

.activity-comparison-strip strong {
  color: #174243;
  font-size: 18px;
}

.comparison-arrow {
  color: #7d918c;
  font-size: 18px;
}

.comparison-change {
  grid-column: 1 / -1;
  justify-self: end;
  min-width: 72px;
  padding: 7px 10px;
  border-radius: 999px;
  text-align: center;
  font-size: 12px;
  font-weight: 800;
}

.comparison-change.positive {
  background: #e5f3ed;
  color: #017151;
}

.comparison-change.negative {
  background: #fff3c4;
  color: #7a5b00;
}

.role-rate-list {
  display: grid;
  gap: 20px;
  margin-top: 24px;
}

.role-rate-row {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr) 48px;
  gap: 12px;
  align-items: center;
}

.role-label {
  display: flex;
  align-items: center;
  gap: 10px;
}

.role-icon {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border-radius: 11px;
  background: #e4f0e2;
  color: #017151;
}

.rate-track,
.recency-track {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: #e8efec;
}

.rate-track i,
.recency-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #5EA99E;
}

.table-heading input {
  width: 250px;
}

.table-heading-controls {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex: 0 0 auto;
}

.show-all-control {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  gap: 7px;
  padding: 0 11px;
  border: 1px solid #bad7b8;
  border-radius: 10px;
  background: #fff;
  color: #425e59;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
  cursor: pointer;
}

.show-all-control input {
  width: 15px !important;
  height: 15px !important;
  margin: 0;
  accent-color: #007f5f;
}

.threshold-control {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  border: 1px solid #bad7b8;
  border-radius: 10px;
  background: #fff;
  color: #425e59;
  white-space: nowrap;
}

.threshold-control span {
  font-size: 11px;
  font-weight: 700;
}

.threshold-control input {
  width: 58px !important;
  height: 30px !important;
  padding: 0 5px !important;
  border-radius: 7px !important;
  text-align: center;
}

.threshold-control small {
  color: #6c7c78;
  font-size: 10px;
}

.table-wrap {
  max-height: 430px;
  overflow: auto;
  border: 1px solid #e0e8e5;
  border-radius: 12px;
}

table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 12px;
}

.col-user { width: 22%; }
.col-role { width: 14%; }
.col-login { width: 26%; }
.col-days { width: 23%; }
.col-status { width: 15%; }

th {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 12px;
  background: #edf4ef;
  color: #174243;
  text-align: left;
}

td {
  padding: 12px;
  border-top: 1px solid #e4ebe8;
  color: #536762;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

tbody tr:hover td {
  background: rgba(186, 215, 184, .35);
}

.sortable {
  cursor: pointer;
  white-space: nowrap;
}

.role-pill,
.status-pill {
  display: inline-flex;
  min-height: 26px;
  align-items: center;
  padding: 0 10px;
  border-radius: 999px;
  font-weight: 700;
}

.role-pill.student { background: #e7eef1; color: #39687B; }
.role-pill.mentor { background: #e0f0eb; color: #017151; }
.role-pill.supervisor { background: #e0eeee; color: #347f76; }

.status-pill.active { background: #e0f0e5; color: #017151; }
.status-pill.inactive { background: #fff3c4; color: #7a5b00; }
.status-pill.never { background: #eef3f3; color: #52615c; }
.status-pill.not-started { background: #eef3f3; color: #52615c; }

.mentor-none-pill {
  display: inline-flex;
  min-height: 26px;
  align-items: center;
  padding: 0 10px;
  border-radius: 999px;
  background: #eef3f3;
  color: #52615c;
  font-weight: 700;
}

.empty-state {
  padding: 28px;
  text-align: center;
}

.right-stack {
  display: grid;
  gap: 18px;
}

.recency-list {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.recency-row {
  display: grid;
  grid-template-columns: 30px 92px minmax(0, 1fr) 42px;
  gap: 10px;
  align-items: center;
  font-size: 12px;
}

.rank {
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border-radius: 8px;
  background: #f0f4f2;
  font-weight: 700;
}

.insights-card h2 i {
  margin-right: 6px;
  color: #39687B;
}

.insight-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  padding: 12px 0;
  border-top: 1px solid #e7eeeb;
}

.insight-row:first-of-type {
  margin-top: 12px;
}

.insight-row strong {
  color: #017151;
  font-size: 18px;
}

.insight-row span {
  color: #536762;
  font-size: 12px;
  line-height: 1.4;
}

@media (max-width: 1200px) {
  .kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .main-grid,
  .lower-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .activity-analytics-page {
    padding: 24px 18px 36px;
  }

  .page-heading {
    grid-template-columns: 1fr;
  }

  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-card {
    grid-template-columns: 1fr;
  }

  .card-heading,
  .table-heading {
    flex-direction: column;
  }

  .activity-heading-actions {
    width: 100%;
    align-items: flex-start;
    justify-content: flex-start;
  }

  .activity-comparison-strip {
    grid-template-columns: 1fr 1fr;
  }

  .comparison-arrow {
    display: none;
  }

  .table-heading input {
    width: 100%;
  }

  .table-heading-controls {
    width: 100%;
    flex-wrap: wrap;
    justify-content: flex-start;
  }

  .table-heading-controls > input[type='search'] {
    flex: 1 1 220px;
  }
}

/* =========================================================
   Activity page density alignment
   Match the visual scale/spacing used by Messages Analytics
   at browser 100% + shared 90% analytics zoom.
   ========================================================= */

@media (min-width: 1280px) {
  .activity-analytics-page {
    padding: 28px 40px 40px;
  }

  .activity-analytics-page .page-heading {
    margin-bottom: 18px;
  }

  .activity-analytics-page h1 {
    font-size: 36px;
  }

  .activity-analytics-page .heading-copy > p {
    margin-top: 7px;
    font-size: 15px;
  }

  /* KPI cards should have the same compact visual weight as Messages KPI cards. */
  .activity-analytics-page .kpi-grid {
    gap: 10px;
    margin-bottom: 16px;
  }

  .activity-analytics-page .kpi-card {
    min-height: 108px;
    gap: 12px;
    padding: 14px 12px;
  }

  .activity-analytics-page .kpi-icon {
    width: 48px;
    height: 48px;
    flex-basis: 48px;
    border-radius: 13px;
    font-size: 18px;
  }

  .activity-analytics-page .kpi-card span {
    font-size: 11px;
    line-height: 1.35;
  }

  .activity-analytics-page .kpi-card strong {
    margin-top: 4px;
    font-size: 27px;
  }

  .activity-analytics-page .kpi-card small {
    margin-top: 7px;
    font-size: 11px;
    line-height: 1.35;
  }

  /* Match Messages filter-card height and spacing. */
  .activity-analytics-page .filter-card {
    gap: 14px;
    margin-bottom: 16px;
    padding: 13px 18px;
  }

  .activity-analytics-page .filter-card label {
    gap: 5px;
  }

  .activity-analytics-page .filter-card select {
    height: 42px;
    font-size: 13px;
  }

  .activity-analytics-page .reset-button {
    height: 42px;
  }

  /* Main cards should start at the same visual level/density as Messages. */
  .activity-analytics-page .analytics-grid {
    gap: 16px;
    margin-bottom: 16px;
  }

  .activity-analytics-page .analytics-card {
    padding: 18px;
  }

  .activity-analytics-page .analytics-card h2 {
    font-size: 20px;
  }

  .activity-analytics-page .card-heading,
  .activity-analytics-page .table-heading {
    margin-bottom: 12px;
  }

  /* Keep the top two content cards aligned with Messages' 1.55 / .95 split. */
  .activity-analytics-page .main-grid,
  .activity-analytics-page .lower-grid {
    grid-template-columns: minmax(0, 1.55fr) minmax(320px, .95fr);
  }
}


/* =========================================================
   Exact layout alignment with Messages Analytics
   Values below mirror MessagesAnalyticsPage.vue.
   ========================================================= */

@media (min-width: 1280px) {
  .activity-analytics-page {
    min-height: 100%;
    padding: 28px 32px 40px !important;
  }

  .activity-analytics-page .page-heading {
    display: grid !important;
    grid-template-columns: minmax(0, 1fr) auto !important;
    align-items: start !important;
    gap: 24px !important;
    margin-bottom: 22px !important;
  }

  .activity-analytics-page .breadcrumb {
    margin-bottom: 18px !important;
    font-size: 14px !important;
  }

  .activity-analytics-page .title-line {
    gap: 12px !important;
  }

  .activity-analytics-page .title-line h1,
  .activity-analytics-page h1 {
    font-size: 36px !important;
    line-height: 1.15 !important;
  }

  .activity-analytics-page .heading-copy > p {
    margin: 7px 0 0 !important;
    font-size: 16px !important;
  }

  .activity-analytics-page .page-actions {
    align-items: center !important;
    gap: 12px !important;
    margin-top: 0 !important;
  }

  .activity-analytics-page .year-control,
  .activity-analytics-page .export-button {
    height: 46px !important;
    border-radius: 12px !important;
    font-size: 14px !important;
  }

  .activity-analytics-page .year-control {
    width: 120px !important;
    padding: 0 13px !important;
  }

  .activity-analytics-page .export-button {
    width: 142px !important;
    padding: 0 16px !important;
  }

  /* Same card density as Messages KPI cards. */
  .activity-analytics-page .kpi-grid {
    display: grid !important;
    grid-template-columns: repeat(5, minmax(0, 1fr)) !important;
    gap: 14px !important;
    margin-bottom: 16px !important;
  }

  .activity-analytics-page .kpi-card,
  .activity-analytics-page .filter-card,
  .activity-analytics-page .analytics-card {
    border-radius: 12px !important;
    border-color: #e1e9e6 !important;
    box-shadow: 0 8px 22px rgba(16, 32, 27, 0.035) !important;
  }

  .activity-analytics-page .kpi-card {
    display: flex !important;
    min-height: 120px !important;
    align-items: flex-start !important;
    gap: 12px !important;
    padding: 16px !important;
  }

  .activity-analytics-page .kpi-icon {
    width: 42px !important;
    height: 42px !important;
    flex: 0 0 42px !important;
    border-radius: 10px !important;
    font-size: 17px !important;
  }

  .activity-analytics-page .kpi-card > div:not(.kpi-icon) {
    min-width: 0 !important;
    display: grid !important;
    grid-template-rows: 34px 38px 34px !important;
    align-content: start !important;
  }

  .activity-analytics-page .kpi-card > div:not(.kpi-icon) > span {
    display: flex !important;
    align-items: flex-start !important;
    color: #516966 !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    line-height: 17px !important;
  }

  .activity-analytics-page .kpi-card strong {
    display: flex !important;
    align-items: center !important;
    margin: 0 !important;
    font-size: 30px !important;
    line-height: 38px !important;
    white-space: nowrap !important;
  }

  .activity-analytics-page .kpi-card small {
    display: flex !important;
    align-items: flex-start !important;
    margin: 0 !important;
    padding-top: 5px !important;
    font-size: 11px !important;
    line-height: 15px !important;
  }

  /* Use the same filter geometry as Messages. */
  .activity-analytics-page .filter-card {
    display: flex !important;
    align-items: end !important;
    gap: 22px !important;
    margin-bottom: 16px !important;
    padding: 12px 16px !important;
  }

  .activity-analytics-page .filter-card label {
    display: grid !important;
    min-width: 210px !important;
    flex: 1 1 210px !important;
    gap: 6px !important;
  }

  .activity-analytics-page .filter-card label > span {
    font-size: 12px !important;
  }

  .activity-analytics-page .filter-card select {
    height: 38px !important;
    padding: 0 34px 0 11px !important;
    border-radius: 8px !important;
    font-size: 13px !important;
  }

  .activity-analytics-page .reset-button {
    height: 38px !important;
    min-width: 0 !important;
    margin-left: auto !important;
    padding: 0 13px !important;
    border-radius: 8px !important;
    font-size: 12px !important;
  }

  /* Same card grid / card padding / headings as Messages. */
  .activity-analytics-page .analytics-grid {
    display: grid !important;
    gap: 14px !important;
    margin-bottom: 14px !important;
  }

  .activity-analytics-page .main-grid,
  .activity-analytics-page .lower-grid {
    grid-template-columns: minmax(0, 1.9fr) minmax(285px, 0.7fr) !important;
    align-items: stretch !important;
  }

  .activity-analytics-page .analytics-card {
    min-width: 0 !important;
    padding: 16px !important;
  }

  .activity-analytics-page .card-heading,
  .activity-analytics-page .table-heading {
    gap: 12px !important;
    margin-bottom: 14px !important;
  }

  .activity-analytics-page .analytics-card h2,
  .activity-analytics-page .card-heading h2,
  .activity-analytics-page .table-heading h2 {
    font-size: 18px !important;
    font-weight: 800 !important;
  }

  .activity-analytics-page .card-heading p,
  .activity-analytics-page .table-heading p,
  .activity-analytics-page .card-subtitle {
    margin: 4px 0 0 !important;
    font-size: 12px !important;
  }

  /* Match Messages chart area dimensions. */
  .activity-analytics-page .line-chart {
    min-height: 300px !important;
  }

  .activity-analytics-page .line-chart svg {
    width: 100% !important;
    height: 260px !important;
  }

  .activity-analytics-page .line-chart-layout {
    grid-template-columns: 42px minmax(0, 1fr) !important;
    gap: 8px !important;
  }

  .activity-analytics-page .y-axis {
    height: 260px !important;
    padding: 24px 0 32px !important;
    font-size: 11px !important;
  }
}


/* Activity sticky filters and fixed table widths */
.activity-analytics-page .sticky-filter-card { position: sticky; top: 72px; z-index: 20; background: #fff; box-shadow: 0 8px 20px rgba(23,66,67,.08); }
.activity-analytics-page .date-filter-control input { width:100%; height:38px; box-sizing:border-box; padding:0 11px; border:1px solid #dbe5e2; border-radius:8px; outline:0; background:#fff; color:#234844; font:inherit; font-size:13px; }
.activity-analytics-page .date-filter-control input:focus { border-color:#017151; box-shadow:0 0 0 2px rgba(1,113,81,.12); }
.activity-analytics-page .table-wrap { overflow-x:hidden; }
.activity-analytics-page .table-wrap table { width:100%; min-width:0; table-layout:fixed; }
.activity-analytics-page #user-activity-details .col-user,
.activity-analytics-page #user-activity-details th:nth-child(1),
.activity-analytics-page #user-activity-details td:nth-child(1) { width:22%; }
.activity-analytics-page #user-activity-details .col-role,
.activity-analytics-page #user-activity-details th:nth-child(2),
.activity-analytics-page #user-activity-details td:nth-child(2) { width:14%; }
.activity-analytics-page #user-activity-details .col-login,
.activity-analytics-page #user-activity-details th:nth-child(3),
.activity-analytics-page #user-activity-details td:nth-child(3) { width:26%; }
.activity-analytics-page #user-activity-details .col-days,
.activity-analytics-page #user-activity-details th:nth-child(4),
.activity-analytics-page #user-activity-details td:nth-child(4) { width:23%; }
.activity-analytics-page #user-activity-details .col-status,
.activity-analytics-page #user-activity-details th:nth-child(5),
.activity-analytics-page #user-activity-details td:nth-child(5) { width:15%; }
@media (min-width:1280px) { .activity-analytics-page .sticky-filter-card { flex-wrap:nowrap !important; } .activity-analytics-page .sticky-filter-card label { min-width:0 !important; } .activity-analytics-page .sticky-filter-card .date-filter-control { flex:.85 1 175px !important; } }
@media (max-width:1279px) { .activity-analytics-page .sticky-filter-card { position:relative; top:0; } }


/* =========================================================
   Sticky Activity filters
   The main application content is the scrolling container,
   so the filter sticks to the top of that container.
   ========================================================= */

.activity-analytics-page {
  overflow: visible !important;
}

.activity-analytics-page .sticky-filter-card {
  position: -webkit-sticky !important;
  position: sticky !important;
  top: 84px !important;
  z-index: 100 !important;
  isolation: isolate;
  background: #ffffff !important;
  box-shadow: 0 8px 18px rgba(23, 66, 67, 0.10) !important;
}

/* Give the sticky bar a little separation once it is pinned. */
.activity-analytics-page .sticky-filter-card::before {
  content: "";
  position: absolute;
  inset: -2px 0 auto;
  height: 2px;
  background: #f7faf9;
  pointer-events: none;
}

/* Daily chart is always exactly seven recent days. */
.activity-analytics-page .activity-chart-card .line-chart svg {
  overflow: visible;
}


/* Logged In by Role follows the active filters. */
.activity-analytics-page .login-role-card .card-heading {
  align-items: flex-start;
}

.activity-analytics-page .login-role-card .role-rate-list {
  margin-top: 22px;
}


/* User / Group mode */
.activity-analytics-page .view-filter-control {
  flex: 0.72 1 150px !important;
}

.activity-analytics-page .interactive-point,
.activity-analytics-page .interactive-chart-row {
  cursor: default;
}

.activity-analytics-page .group-active-line {
  stroke: #017151;
}

.activity-analytics-page .group-inactive-line {
  stroke: #5EA99E;
}

.activity-analytics-page .group-active-dot {
  fill: #017151;
  background: #017151;
}

.activity-analytics-page .group-inactive-dot {
  fill: #5EA99E;
  background: #5EA99E;
}

.activity-analytics-page .inactive-label {
  fill: #347f76;
}

.activity-analytics-page .group-status-summary-list {
  display: grid;
  flex: 1;
  grid-template-rows: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.activity-analytics-page .group-status-summary-card {
  display: flex;
  flex-direction: column;
}

.activity-analytics-page .group-status-summary-row {
  display: grid;
  width: 100%;
  grid-template-columns: 44px minmax(0, 1fr) 54px;
  gap: 12px;
  align-items: center;
  padding: 12px;
  border: 1px solid #dfe9e5;
  border-radius: 12px;
  background: #fff;
  color: inherit;
  font: inherit;
  text-align: left;
  transition: background-color .18s ease, border-color .18s ease, box-shadow .18s ease;
}

.activity-analytics-page .group-status-summary-row:hover {
  border-color: #9ccbbb;
  background: #f5faf7;
}

.activity-analytics-page .group-status-summary-row.is-selected {
  border-color: #017151;
  background: #e8f5ee;
  box-shadow: 0 0 0 1px #017151;
}

.activity-analytics-page .group-status-summary-row:focus-visible {
  outline: 3px solid rgb(1 113 81 / 22%);
  outline-offset: 2px;
}

.activity-analytics-page .group-status-summary-row b {
  color: #174243;
  font-size: 24px;
  text-align: right;
}

.activity-analytics-page .group-status-summary-row small {
  display: block;
  margin-top: 4px;
  color: #6c7c78;
  font-size: 11px;
}

.activity-analytics-page .group-summary-icon {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 11px;
  background: #e4f0e2;
  color: #017151;
}

.activity-analytics-page .group-summary-icon.inactive {
  background: #e7f1ef;
  color: #5EA99E;
}

.activity-analytics-page .group-summary-icon.not-started {
  background: #eef3f3;
  color: #52615c;
}

.activity-analytics-page .group-activity-details-card {
  margin-bottom: 18px;
}

.activity-analytics-page .group-directory-summary {
  margin: -2px 0 12px;
  color: #60736f;
  font-size: 12px;
}

.activity-analytics-page .group-id-label {
  display: block;
  margin-top: 3px;
  color: #60736f;
  font-size: 11px;
}

.activity-analytics-page .group-col-name { width: 19%; }
.activity-analytics-page .group-col-mentor { width: 20%; }
.activity-analytics-page .group-col-status { width: 14%; }
.activity-analytics-page .group-col-last-active { width: 27%; }
.activity-analytics-page .group-col-days { width: 20%; }

.activity-analytics-page .group-activity-table {
  table-layout: fixed;
}

.activity-analytics-page .group-activity-table th,
.activity-analytics-page .group-activity-table td {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}


@media (max-width: 900px) {
  .comparison-card-heading {
    flex-direction: column;
  }

  .activity-compare-card .compare-year-control {
    width: 100%;
    flex-basis: auto;
  }
}

/* Keep the top activity row compact; comparison now starts in the lower right column. */
.activity-analytics-page .main-grid {
  align-items: start !important;
}

.activity-analytics-page .login-role-card {
  align-self: stretch;
}


/* === Year-controlled activity layout === */
.activity-analytics-page .kpi-comparison-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 245px;
  gap: 14px;
  align-items: stretch;
  margin-bottom: 16px;
}

.activity-analytics-page .kpi-comparison-row .kpi-grid {
  margin-bottom: 0 !important;
}

.activity-analytics-page .compact-compare-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 120px;
  padding: 14px 16px !important;
}

.activity-analytics-page .compact-compare-card h2 {
  margin: 0 !important;
  font-size: 15px !important;
}

.activity-analytics-page .compact-compare-card > p {
  margin: 4px 0 10px;
  color: #6c7c78;
  font-size: 10px;
  line-height: 1.3;
}

.activity-analytics-page .compact-comparison-values {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  grid-template-rows: auto auto;
  gap: 4px 8px;
  align-items: center;
}

.activity-analytics-page .compact-comparison-values > div {
  display: grid;
  gap: 2px;
}

.activity-analytics-page .compact-comparison-values span {
  color: #6c7c78;
  font-size: 9px;
}

.activity-analytics-page .compact-comparison-values strong {
  color: #174243;
  font-size: 20px;
  line-height: 1;
}

.activity-analytics-page .compact-comparison-values .comparison-arrow {
  color: #7d918c;
  font-size: 15px;
}

.activity-analytics-page .comparison-number-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.activity-analytics-page .compact-comparison-values .comparison-change {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 4px 9px;
  background: #e5f3ee;
  color: #017151;
  font-size: 11px;
  line-height: 1;
}

.activity-analytics-page .compact-comparison-values .comparison-change.negative {
  background: #fff1df;
  color: #9a5b00;
}

.activity-analytics-page .activity-side-stack {
  display: grid;
  align-self: stretch;
}

.activity-analytics-page .activity-side-stack .login-role-card {
  height: 100%;
}

@media (max-width: 1450px) {
  .activity-analytics-page .kpi-comparison-row {
    grid-template-columns: 1fr;
  }

  .activity-analytics-page .compact-compare-card {
    min-height: auto;
  }
}


/* Logged In by Role fills the complete side column beside the activity chart. */
.activity-analytics-page .kpi-comparison-row {
  display: block !important;
  margin-bottom: 0 !important;
}

.activity-analytics-page .kpi-grid {
  grid-template-columns: repeat(6, minmax(0, 1fr)) !important;
  gap: 12px !important;
  margin-bottom: 16px !important;
}

.activity-analytics-page .kpi-card {
  min-width: 0 !important;
  padding-inline: 13px !important;
  gap: 11px !important;
}

.activity-analytics-page .kpi-card > div:not(.kpi-icon) {
  flex: 1 1 auto;
  min-width: 0;
}

.activity-analytics-page .kpi-card > div:not(.kpi-icon) > strong {
  width: 100%;
  text-align: left;
}

.activity-analytics-page .kpi-card .analytics-value-row {
  width: 100%;
  justify-content: flex-start;
}

@media (max-width: 1279px) {
  .activity-analytics-page .kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
  }
}

@media (max-width: 720px) {
  .activity-analytics-page .kpi-grid {
    grid-template-columns: minmax(0, 1fr) !important;
  }
}

.activity-analytics-page .activity-side-stack {
  display: grid !important;
  grid-template-rows: minmax(0, 1fr);
  gap: 0;
  align-content: stretch;
  align-self: stretch;
}

.activity-analytics-page .activity-side-stack .login-role-card {
  display: flex;
  flex-direction: column;
  height: 100% !important;
}

.activity-analytics-page .login-role-card .role-rate-list {
  display: grid;
  grid-auto-rows: minmax(0, 1fr);
  flex: 1;
  min-height: 0;
  gap: 0;
  margin-top: 12px;
}


/* Final alignment: stretch Daily User Activity to match the full right-side stack height. */
.activity-analytics-page .main-grid {
  align-items: stretch !important;
}

.activity-analytics-page .activity-chart-card {
  height: 100% !important;
  box-sizing: border-box;
}

.activity-analytics-page .activity-side-stack {
  height: 100%;
}

#user-activity-details {
  scroll-margin-top: 170px;
}

.activity-issue-context {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 10px;
  padding: 8px 10px;
  border: 1px solid #bad7b8;
  border-radius: 8px;
  background: #f2f8f1;
  color: #174243;
  font-size: 11px;
  font-weight: 700;
}

.activity-issue-context i {
  color: #017151;
}

/* Keep every Activity filter usable when browser zoom narrows the content area. */
@media (max-width: 1279px) {
  .activity-analytics-page .sticky-filter-card {
    display: grid !important;
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    align-items: end !important;
    gap: 14px !important;
    position: relative !important;
    top: 0 !important;
  }

  .activity-analytics-page .sticky-filter-card label {
    width: auto !important;
    min-width: 0 !important;
    max-width: none !important;
    flex: none !important;
  }

  .activity-analytics-page .sticky-filter-card select,
  .activity-analytics-page .sticky-filter-card input,
  .activity-analytics-page .sticky-filter-card .reset-button {
    width: 100% !important;
    min-width: 0 !important;
    max-width: 100% !important;
    box-sizing: border-box;
    margin-left: 0 !important;
  }
}

@media (max-width: 720px) {
  .activity-analytics-page .sticky-filter-card {
    grid-template-columns: minmax(0, 1fr) !important;
  }
}

/* Shared analytics filter appearance (matches Registration and Messages). */
.activity-analytics-page .sticky-filter-card {
  display: grid !important;
  grid-template-columns:
    110px
    minmax(165px, 1.15fr)
    minmax(165px, 1.15fr)
    minmax(120px, .8fr)
    minmax(130px, .9fr)
    minmax(145px, 1fr)
    132px !important;
  gap: 10px !important;
  align-items: end !important;
  padding: 16px !important;
  border: 1px solid #d7e3df !important;
  border-radius: 14px !important;
  background: #fff !important;
}

.activity-analytics-page .sticky-filter-card label {
  width: auto !important;
  min-width: 0 !important;
  max-width: none !important;
  gap: 6px !important;
}

.activity-analytics-page .sticky-filter-card label > span {
  color: #425e59 !important;
  font-size: 12px !important;
  font-weight: 700 !important;
  line-height: 1.2;
}

.activity-analytics-page .sticky-filter-card select,
.activity-analytics-page .sticky-filter-card input[type='date'] {
  width: 100% !important;
  height: 42px !important;
  box-sizing: border-box;
  padding: 0 12px !important;
  border: 1px solid #79bdb4 !important;
  border-radius: 10px !important;
  background: #fff !important;
  color: #017151 !important;
  font: inherit;
  font-size: 13px !important;
}

.activity-analytics-page .sticky-filter-card .reset-button {
  width: auto !important;
  min-width: 132px !important;
  height: 42px !important;
  margin: 0 !important;
  border: 1px solid #79bdb4 !important;
  border-radius: 10px !important;
  background: #fff !important;
  color: #017151 !important;
  white-space: nowrap;
}

@media (max-width: 1350px) {
  .activity-analytics-page .sticky-filter-card {
    grid-template-columns: repeat(3, minmax(170px, 1fr)) !important;
  }

  .activity-analytics-page .sticky-filter-card .reset-button {
    width: 100% !important;
  }
}

@media (max-width: 720px) {
  .activity-analytics-page .sticky-filter-card {
    grid-template-columns: minmax(0, 1fr) !important;
  }
}

</style>
