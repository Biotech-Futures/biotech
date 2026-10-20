<template>
  <section class="users-analytics-page">
    <div class="page-heading">
      <div class="heading-copy">
        <div class="breadcrumb">
          <RouterLink to="/dashboard">Home</RouterLink>
          <span class="breadcrumb-separator">›</span>
          <RouterLink to="/analytics">Analytics</RouterLink>
          <span class="breadcrumb-separator">›</span>
          <span>Users Analytics</span>
        </div>

        <div class="title-line">
          <h1>Users / Participants Analytics</h1>

        </div>
        <p>Understand who is in our community and how they are engaging.</p>
      </div>

      <div class="page-actions">
        <label class="year-control">
          <i class="fas fa-calendar" aria-hidden="true"></i>
          <select v-model.number="selectedYear" aria-label="Select analytics year">
            <option v-for="year in availableYears" :key="year" :value="year">
              {{ year }}
            </option>
          </select>
        </label>

        <div class="analytics-export-stack">
          <AnalyticsExportMenu :options="[SUMMARY_OPTION, DETAILS_OPTION]" :disabled="exportDisabled" @select="exportCsv" />
          <div class="analytics-update-status">
            <AnalyticsRefreshStatus :updated-at="lastUpdated" :refresh-failed="refreshFailed" />
          </div>
        </div>
      </div>
    </div>

    <p v-if="exportError" role="alert">{{ exportError }}</p>

    <AnalyticsPartialNotice :sources="unavailableSources" @retry="loadAnalytics(true)" />

    <AnalyticsDataState
      :loading="isLoading"
      :error="loadError"
      :empty="isEmpty"
      empty-message="No participant records are available in the current database. Generate or load a dataset, then refresh this page."
      @retry="refreshAnalytics"
    >
    <div class="kpi-grid">
      <article class="kpi-card">
        <div class="kpi-icon blue"><i class="fas fa-users"></i></div>
        <div class="kpi-copy">
          <span class="kpi-label">Total Users</span>
          <div class="kpi-value-row analytics-value-row">
            <strong><AnalyticsNumber :value="data.totalUsers" /></strong>
            <AnalyticsYearChange :current="yearComparison.current.total" :previous="yearComparison.previous.total" :label="`vs ${yearComparison.previousYear}`" />
          </div>
          <small>Current participants</small>
        </div>
      </article>

      <article class="kpi-card">
        <div class="kpi-icon blue"><i class="fas fa-graduation-cap"></i></div>
        <div class="kpi-copy">
          <span class="kpi-label">Students</span>
          <div class="kpi-value-row analytics-value-row">
            <strong><AnalyticsNumber :value="data.students" /></strong>
            <AnalyticsYearChange :current="yearComparison.current.students" :previous="yearComparison.previous.students" :label="`vs ${yearComparison.previousYear}`" />
          </div>
          <small>{{ percentage(data.students, data.totalUsers) }}% of users</small>
        </div>
      </article>

      <article class="kpi-card">
        <div class="kpi-icon red"><i class="fas fa-user"></i></div>
        <div class="kpi-copy">
          <span class="kpi-label">Mentors</span>
          <div class="kpi-value-row analytics-value-row">
            <strong><AnalyticsNumber :value="data.mentors" /></strong>
            <AnalyticsYearChange :current="yearComparison.current.mentors" :previous="yearComparison.previous.mentors" :label="`vs ${yearComparison.previousYear}`" />
          </div>
          <small>{{ percentage(data.mentors, data.totalUsers) }}% of users</small>
        </div>
      </article>

      <article class="kpi-card">
        <div class="kpi-icon purple"><i class="fas fa-user-friends"></i></div>
        <div class="kpi-copy">
          <span class="kpi-label">Supervisors</span>
          <div class="kpi-value-row analytics-value-row">
            <strong><AnalyticsNumber :value="data.supervisors" /></strong>
            <AnalyticsYearChange :current="yearComparison.current.supervisors" :previous="yearComparison.previous.supervisors" :label="`vs ${yearComparison.previousYear}`" />
          </div>
          <small>{{ percentage(data.supervisors, data.totalUsers) }}% of users</small>
        </div>
      </article>
    </div>

    <div class="analytics-grid first-row">
      <article class="analytics-card">
        <h2>Users by Role</h2>
        <div class="role-content">
          <div class="role-donut-wrap" @mouseleave="clearRoleSelection">
            <svg
              class="role-donut-svg"
              viewBox="0 0 180 180"
              role="img"
              aria-label="Users by role"
            >
              <circle
                cx="90"
                cy="90"
                r="64"
                pathLength="100"
                fill="none"
                stroke="#e7ebef"
                stroke-width="24"
              />

              <circle
                v-for="segment in roleSegments"
                :key="segment.label"
                cx="90"
                cy="90"
                r="64"
                pathLength="100"
                fill="none"
                :stroke="segment.color"
                stroke-width="24"
                :stroke-dasharray="`${segment.drawPercent} ${100 - segment.drawPercent}`"
                :stroke-dashoffset="-segment.start"
                stroke-linecap="butt"
                class="role-donut-segment"
                :class="{ selected: selectedRole?.label === segment.label }"
                transform="rotate(-90 90 90)"
                @mouseenter="selectRole(segment)"
                @focus="selectRole(segment)"
                @blur="clearRoleSelection"
                tabindex="0"
              />

            </svg>

            <div class="donut-centre role-donut-centre">
              <template v-if="selectedRole">
                <span class="role-centre-label">{{ selectedRole.label }}</span>
                <strong>{{ selectedRole.value.toLocaleString() }}</strong>
                <span>{{ selectedRole.percent }}% of users</span>
              </template>
              <template v-else>
                <strong>{{ data.totalUsers.toLocaleString() }}</strong>
                <span>Total Users</span>
              </template>
            </div>
          </div>

          <div class="legend-list">
            <div
              v-for="segment in roleSegments"
              :key="segment.label"
              class="legend-row interactive-role-row"
              :class="{ selected: selectedRole?.label === segment.label }"
              @mouseenter="selectRole(segment)"
              @mouseleave="clearRoleSelection"
            >
              <span>
                <i class="dot" :style="{ background: segment.color }"></i>
                {{ segment.label }}
              </span>
              <strong>{{ segment.value }} ({{ segment.percent }}%)</strong>
            </div>
          </div>
        </div>
      </article>

      <article class="analytics-card">
        <h2>Users Logged In This Year ({{ currentYear }})</h2>
        <div class="login-rate-grid">
          <div
            v-for="item in loginRates"
            :key="item.label"
            class="login-rate-item interactive-chart-row"
            @mouseenter="showTooltip($event, item.label, `${item.value}% logged in`, 'Current user records')"
            @mousemove="moveTooltip"
            @mouseleave="hideTooltip"
          >
            <span>{{ item.label }}</span>
            <div
              class="rate-ring"
              :style="{
                background: `conic-gradient(${item.color} 0 ${item.value}%, #e8edf0 ${item.value}% 100%)`,
              }"
            >
              <div class="rate-ring-inner">{{ item.value }}%</div>
            </div>
            <small>Current users with a recorded login in {{ currentYear }} (UTC)</small>
          </div>
        </div>
      </article>

      <article class="analytics-card interests-card">
        <div class="interest-heading-row">
          <h2>Top Areas of Interest</h2>
          <button
            type="button"
            class="interest-sort-button"
            :title="interestSortDirection === 'desc' ? 'Highest to lowest' : 'Lowest to highest'"
            :aria-label="interestSortDirection === 'desc' ? 'Sort lowest to highest' : 'Sort highest to lowest'"
            @click="interestSortDirection = interestSortDirection === 'desc' ? 'asc' : 'desc'"
          >
            <i
              class="fas"
              :class="interestSortDirection === 'desc' ? 'fa-caret-down' : 'fa-caret-up'"
              aria-hidden="true"
            ></i>
          </button>
        </div>

        <div class="interest-series-legend" aria-label="Interest chart legend">
          <span><i class="dot interest-student-dot"></i>Student</span>
          <span><i class="dot interest-mentor-dot"></i>Mentor</span>
        </div>

        <div class="interest-list interest-role-list">
          <div v-for="item in sortedInterests" :key="item.name" class="interest-role-row">
            <span class="interest-role-name">{{ item.name }}</span>

            <div class="interest-role-bars">
              <div class="interest-role-track">
                <div
                  class="interest-role-fill interest-student-fill interactive-chart-mark"
                  :style="{ width: `${barWidth(item.students, maxInterest)}%` }"
                  @mouseenter="showTooltip($event, item.name, `${item.students} students`, 'Student interest count')"
                  @mousemove="moveTooltip"
                  @mouseleave="hideTooltip"
                ></div>
              </div>

              <div class="interest-role-track">
                <div
                  class="interest-role-fill interest-mentor-fill interactive-chart-mark"
                  :style="{ width: `${barWidth(item.mentors, maxInterest)}%` }"
                  @mouseenter="showTooltip($event, item.name, `${item.mentors} mentors`, 'Mentor interest count')"
                  @mousemove="moveTooltip"
                  @mouseleave="hideTooltip"
                ></div>
              </div>
            </div>

            <div class="interest-role-values" aria-label="Student and mentor counts">
              <strong>{{ item.students }}</strong>
              <span>{{ item.mentors }}</span>
            </div>
          </div>
        </div>
        <p v-if="sortedInterests.length" class="interest-count">
          {{ sortedInterests.length }} areas of interest · scroll the list to see all
        </p>
      </article>
    </div>

    <section class="analytics-grid user-trend-row">
      <article class="analytics-card last-login-distribution-card">
        <h2>Last Login Distribution</h2>
        <div class="last-login-role-legend" aria-label="Last login distribution roles">
          <span v-for="role in lastLoginRoles" :key="role.key">
            <i :class="`last-login-legend-${role.key}`" aria-hidden="true"></i>
            {{ role.label }}
          </span>
        </div>
        <div class="chart-with-y-axis">
          <div class="y-axis last-login-y-axis">
            <span v-for="tick in lastLoginTicks" :key="tick">{{ tick }}</span>
          </div>
          <div class="y-axis-line">
            <div class="bar-chart vertical-bars">
          <div v-for="item in lastLoginStacks" :key="item.label" class="vertical-bar-item">
            <span class="bar-value">{{ item.total }}</span>
            <div class="bar-track stacked-bar-track">
              <div
                v-for="role in lastLoginRoles"
                :key="role.key"
                class="stacked-bar-segment interactive-chart-mark"
                :class="`stacked-bar-${role.key}`"
                :style="{ height: `${(item[role.key] / lastLoginAxisMax) * 100}%` }"
                @mouseenter="showTooltip($event, item.label, `${item[role.key]} ${role.label.toLowerCase()}${item[role.key] === 1 ? '' : 's'}`, `${item.total} users in total`)"
                @mousemove="moveTooltip"
                @mouseleave="hideTooltip"
              ></div>
            </div>
            <span class="bar-label">{{ item.label }}</span>
          </div>
        </div>
          </div>
        </div>
        <div class="y-axis-title">Number of Users</div>
      </article>

      <article class="analytics-card trend-card">
        <div class="card-heading-row trend-card-heading">
          <h2>User Registration Trend</h2>

          <div class="trend-heading-actions">
            <div class="trend-role-filter" aria-label="Hide registration roles">
              <strong>Hide roles</strong>

              <label>
                <input v-model="hiddenRegistrationRoles" type="checkbox" value="students" />
                <span>Student</span>
              </label>

              <label>
                <input v-model="hiddenRegistrationRoles" type="checkbox" value="mentors" />
                <span>Mentor</span>
              </label>

              <label>
                <input v-model="hiddenRegistrationRoles" type="checkbox" value="supervisors" />
                <span>Supervisor</span>
              </label>
            </div>

            <span class="year-chip">{{ selectedYear }}</span>
          </div>
        </div>

        <div ref="registrationPlot" class="registration-plot">
          <svg
            :viewBox="`0 0 ${registrationChart.width} ${registrationChart.height}`"
            :width="registrationChart.width"
            :height="registrationChart.height"
            role="img"
            aria-label="User registration trend"
          >
            <g v-for="tick in registrationTicks" :key="`tick-${tick}`">
              <line
                :x1="registrationChart.plotLeft"
                :x2="registrationChart.plotRight"
                :y1="registrationY(tick)"
                :y2="registrationY(tick)"
                class="grid-line"
                :class="{ 'registration-baseline': tick === 0 }"
              />
              <text
                :x="registrationChart.plotLeft - 10"
                :y="registrationY(tick)"
                text-anchor="end"
                class="registration-axis-label"
              >{{ tick }}</text>
            </g>

            <polyline v-show="!hiddenRegistrationRoles.includes('students')" :points="trendPoints(visibleRegistrationSeries.students)" class="trend-line students" />
            <polyline v-show="!hiddenRegistrationRoles.includes('mentors')" :points="trendPoints(visibleRegistrationSeries.mentors)" class="trend-line mentors" />
            <polyline
              v-show="!hiddenRegistrationRoles.includes('supervisors')"
              :points="trendPoints(visibleRegistrationSeries.supervisors)"
              class="trend-line supervisors"
            />

            <g v-for="point in registrationDots.students" v-show="!hiddenRegistrationRoles.includes('students')" :key="`students-${point.index}`">
              <circle
                :cx="point.x"
                :cy="point.y"
                r="5"
                class="trend-dot students-dot interactive-svg-point"
                @mouseenter="showTooltip($event, `${months[point.index]} ${selectedYear}`, `${point.value} student registrations`, 'Students')"
                @mousemove="moveTooltip"
                @mouseleave="hideTooltip"
              />
            </g>
            <g v-for="point in registrationDots.mentors" v-show="!hiddenRegistrationRoles.includes('mentors')" :key="`mentors-${point.index}`">
              <circle
                :cx="point.x"
                :cy="point.y"
                r="5"
                class="trend-dot mentors-dot interactive-svg-point"
                @mouseenter="showTooltip($event, `${months[point.index]} ${selectedYear}`, `${point.value} mentor registrations`, 'Mentors')"
                @mousemove="moveTooltip"
                @mouseleave="hideTooltip"
              />
            </g>
            <g v-for="point in registrationDots.supervisors" v-show="!hiddenRegistrationRoles.includes('supervisors')" :key="`supervisors-${point.index}`">
              <circle
                :cx="point.x"
                :cy="point.y"
                r="5"
                class="trend-dot supervisors-dot interactive-svg-point"
                @mouseenter="showTooltip($event, `${months[point.index]} ${selectedYear}`, `${point.value} supervisor registrations`, 'Supervisors')"
                @mousemove="moveTooltip"
                @mouseleave="hideTooltip"
              />
            </g>

            <text
              v-for="(month, index) in visibleRegistrationMonths"
              :key="`month-${month}`"
              :x="trendX(index, visibleRegistrationMonths.length)"
              :y="registrationChart.baseline + 18"
              text-anchor="middle"
              class="trend-month-label"
            >
              {{ month }}
            </text>
          </svg>
        </div>

        <div class="trend-legend">
          <span v-show="!hiddenRegistrationRoles.includes('students')"><i class="dot student"></i>Students</span>
          <span v-show="!hiddenRegistrationRoles.includes('mentors')"><i class="dot mentor"></i>Mentors</span>
          <span v-show="!hiddenRegistrationRoles.includes('supervisors')"><i class="dot supervisor"></i>Supervisors</span>
        </div>
      </article>
    </section>

    <section
      class="analytics-grid expandable-user-row"
      :class="{ 'region-expanded-row': regionExpanded }"
    >
      <article class="analytics-card user-login-compact-card activity-status-role-card">
        <div class="card-title-row">
          <div>
            <h2>Activity Status by Role</h2>
            <p class="card-subtitle">Compare active, inactive and never-logged-in users by role.</p>
          </div>

          <RouterLink
            class="view-detail-link"
            :to="{ name: 'activity-analytics', hash: '#user-activity-details' }"
          >
            View detail <span aria-hidden="true">→</span>
          </RouterLink>
        </div>

        <div class="activity-status-role-table-wrap">
          <table class="activity-status-role-table">
            <colgroup>
              <col class="status-role-name" />
              <col class="status-role-value" />
              <col class="status-role-value" />
              <col class="status-role-never" />
            </colgroup>
            <thead>
              <tr>
                <th>Role</th>
                <th>Active</th>
                <th>Inactive</th>
                <th>Never Logged In</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in activityStatusByRole" :key="row.role">
                <td>
                  <span class="role-pill" :class="`role-${row.role.toLowerCase()}`">{{ row.role }}</span>
                </td>
                <td><strong>{{ row.active }}</strong></td>
                <td><strong>{{ row.inactive }}</strong></td>
                <td><strong>{{ row.never }}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>

        <p class="activity-status-role-note">
          <strong>Active</strong> means the user logged in within the last {{ ACTIVE_STATUS_WINDOW_DAYS }} days
          (up to {{ analyticsAsOfLabel }}). <strong>Inactive</strong> users last logged in before that;
          <strong>Never Logged In</strong> users have no recorded login.
        </p>
      </article>

      <div class="expandable-side-card region-side-card">
        <article
        class="analytics-card region-card"
        :class="{ 'region-card--expanded': regionExpanded }"
      >
        <div class="card-title-row">
          <h2>User Distribution by Region</h2>
          <button
            type="button"
            class="expand-button"
            :aria-label="regionExpanded ? 'Restore region card' : 'Expand region card'"
            :title="regionExpanded ? 'Restore' : 'Expand'"
            @click="toggleRegionExpanded"
          >
            <i :class="regionExpanded ? 'fas fa-compress' : 'fas fa-expand'"></i>
          </button>
        </div>

        <div v-if="!regionExpanded" class="region-list compact-region-list">
          <div v-for="item in compactRegionLocations" :key="item.name" class="horizontal-bar-row">
            <span>{{ item.label }}</span>
            <div class="horizontal-track">
              <div
                class="horizontal-fill blue-fill interactive-chart-mark"
                :style="{ width: `${barWidth(item.value, maxRegion)}%` }"
                @mouseenter="showTooltip($event, item.label, `${item.value} users`, `User distribution in ${selectedYear}`)"
                @mousemove="moveTooltip"
                @mouseleave="hideTooltip"
              ></div>
            </div>
            <strong>{{ item.value }}</strong>
          </div>
        </div>

        <div v-else class="inline-expanded-region">
          <div class="world-map-panel">
            <div class="world-map-stage">
              <div class="map-zoom-controls" aria-label="Map zoom controls">
                <button
                  type="button"
                  aria-label="Zoom in"
                  title="Zoom in"
                  :disabled="mapZoom >= MAP_ZOOM_MAX"
                  @click="zoomMapIn"
                >
                  <i class="fas fa-plus"></i>
                </button>
                <button
                  type="button"
                  aria-label="Zoom out"
                  title="Zoom out"
                  :disabled="mapZoom <= MAP_ZOOM_MIN"
                  @click="zoomMapOut"
                >
                  <i class="fas fa-minus"></i>
                </button>
                <button
                  type="button"
                  aria-label="Reset map zoom"
                  title="Reset zoom"
                  @click="resetMapZoom"
                >
                  <i class="fas fa-rotate-left"></i>
                </button>
              </div>

              <svg
                class="world-map"
                viewBox="0 0 900 430"
                preserveAspectRatio="xMidYMid meet"
                role="img"
                aria-label="World map showing user registrations"
                :class="{ 'world-map--dragging': mapDragging }"
                @wheel.prevent="handleMapWheel"
                @pointerdown="startMapPan"
                @pointermove="moveMapPan"
                @pointerup="endMapPan"
                @pointercancel="endMapPan"
                @pointerleave="endMapPan"
              >
                <g class="world-map-zoom-layer" :transform="mapTransform">
                  <g class="country-registration-layer">
                    <path
                      v-for="(segment, segmentIndex) in worldShapeSegments"
                      :key="`country-segment-${segmentIndex}`"
                      :d="segment.d"
                      :fill="segment.value > 0 ? mapColor(segment.value) : '#f8f9f8'"
                      class="country-registration-shape"
                      :class="{ 'country-registration-shape--highlighted': hoveredCountryName !== null && hoveredCountryName === segment.countryName }"
                      @mouseenter="handleCountryMapEnter($event, segment)"
                      @mousemove="moveTooltip($event)"
                      @mouseleave="handleCountryMapLeave()"
                    />
                  </g>
                  <path
                    :d="worldMapPath"
                    class="reference-world-borders"
                    fill="none"
                    fill-rule="evenodd"
                    clip-rule="evenodd"
                  />
                  <!-- Country totals stay unchanged. While an Australian region is hovered,
                       hide only the Australia country total and show that region's value instead. -->
                  <g class="small-map-value-layer" aria-hidden="true">
                    <text
                      v-for="point in visibleSmallMapValuePoints"
                      :key="`small-map-value-${point.name}`"
                      :x="point.x"
                      :y="point.y"
                      class="small-map-value"
                    >
                      {{ point.value }}
                    </text>
                  </g>

                  <g v-if="hoveredAustraliaRegionShape" class="australia-region-hover-layer" aria-hidden="true">
                    <polygon
                      :points="hoveredAustraliaRegionShape.points"
                      :fill="mapColor(hoveredAustraliaRegionShape.value)"
                      class="australia-region-hover-shape"
                    />
                    <text
                      :x="hoveredAustraliaRegionShape.labelX"
                      :y="hoveredAustraliaRegionShape.labelY"
                      class="australia-region-hover-value"
                    >
                      {{ hoveredAustraliaRegionShape.value }}
                    </text>
                  </g>
                </g>
              </svg>
            </div>

            <div class="map-legend">
              <span>No / lower registrations</span>
              <div class="legend-gradient"></div>
              <span>Higher registrations</span>
            </div>
          </div>

          <aside class="region-ranking">
            <div class="ranking-heading">
              <h3>Registration locations</h3>
              <span class="ranking-note">Highest to lowest</span>
            </div>

            <ol>
              <li
                v-for="(item, index) in smallMapRankedLocations"
                :key="`${item.kind}-${item.name}`"
                class="interactive-chart-row"
                :class="{
                  'region-list-row--highlighted':
                    item.kind === 'region'
                      ? hoveredAustraliaRegion === item.name
                      : hoveredCountryName === item.name,
                }"
                @mouseenter="handleSmallLocationListEnter($event, item, index)"
                @mousemove="moveTooltip($event)"
                @mouseleave="handleSmallLocationListLeave"
              >
                <span class="rank-number">{{ index + 1 }}</span>
                <span class="rank-name">{{ item.label }}</span>
                <div class="rank-track">
                  <span :style="{ width: `${barWidth(item.value, maxSmallMapRankedLocation)}%` }"></span>
                </div>
                <strong>{{ item.value }}</strong>
              </li>
            </ol>
          </aside>
        </div>
      </article>
      </div>
    </section>

    <section v-if="regionExpanded" class="analytics-card full-region-map-card">
      <div class="full-region-map-heading">
        <div>
          <h2>World Registration Map</h2>
          <p>Full view of registration locations and regional counts for {{ selectedYear }}.</p>
        </div>
        <button type="button" class="close-map-button" @click="regionExpanded = false">
          <i class="fas fa-compress"></i>
          Close map
        </button>
      </div>

      <div class="full-map-layout">
          <div class="world-map-panel">
            <div class="world-map-stage">
              <div class="map-zoom-controls" aria-label="Map zoom controls">
                <button
                  type="button"
                  aria-label="Zoom in"
                  title="Zoom in"
                  :disabled="mapZoom >= MAP_ZOOM_MAX"
                  @click="zoomMapIn"
                >
                  <i class="fas fa-plus"></i>
                </button>
                <button
                  type="button"
                  aria-label="Zoom out"
                  title="Zoom out"
                  :disabled="mapZoom <= MAP_ZOOM_MIN"
                  @click="zoomMapOut"
                >
                  <i class="fas fa-minus"></i>
                </button>
                <button
                  type="button"
                  aria-label="Reset map zoom"
                  title="Reset zoom"
                  @click="resetMapZoom"
                >
                  <i class="fas fa-rotate-left"></i>
                </button>
              </div>

              <svg
                class="world-map"
                viewBox="0 0 900 430"
                preserveAspectRatio="xMidYMid meet"
                role="img"
                aria-label="World map showing user registrations"
                :class="{ 'world-map--dragging': mapDragging }"
                @wheel.prevent="handleMapWheel"
                @pointerdown="startMapPan"
                @pointermove="moveMapPan"
                @pointerup="endMapPan"
                @pointercancel="endMapPan"
                @pointerleave="endMapPan"
              >
                <g class="world-map-zoom-layer" :transform="mapTransform">
                  <g class="country-registration-layer">
                    <path
                      v-for="(segment, segmentIndex) in worldShapeSegments"
                      :key="`country-segment-${segmentIndex}`"
                      :d="segment.d"
                      :fill="segment.value > 0 ? mapColor(segment.value) : '#f8f9f8'"
                      class="country-registration-shape"
                      :class="{
                        'country-registration-shape--highlighted': hoveredLargeCountryName !== null && hoveredLargeCountryName === segment.countryName,
                        'continent-registration-shape--highlighted': hoveredWorldRegion === 'International' || (hoveredWorldRegion !== null && segment.worldRegion === hoveredWorldRegion)
                      }"
                      @mouseenter="handleLargeMapCountryEnter($event, segment)"
                      @mousemove="moveTooltip"
                      @mouseleave="handleLargeMapCountryLeave"
                    />
                  </g>
                  <path
                    :d="worldMapPath"
                    class="reference-world-borders"
                    fill="none"
                    fill-rule="evenodd"
                    clip-rule="evenodd"
                  />

                  <g class="large-map-continent-totals">
                    <g
                      v-for="point in largeMapSummaryPoints"
                      :key="`summary-${point.name}`"
                      class="map-summary-point interactive-svg-point"
                      @mouseenter="showTooltip($event, point.name, `${point.value} users`, `Registration Count in ${selectedYear}`)"
                      @mousemove="moveTooltip"
                      @mouseleave="hideTooltip"
                    >
                      <text
                        :x="point.x"
                        :y="point.y"
                        text-anchor="middle"
                        class="large-map-summary-value"
                      >
                        {{ point.value }}
                      </text>
                      <text
                        :x="point.x"
                        :y="point.y + 18"
                        text-anchor="middle"
                        class="large-map-summary-label"
                      >
                        {{ point.name }}
                      </text>
                    </g>
                  </g>
                </g>
              </svg>
            </div>

            <div class="map-legend">
              <span>No / lower registrations</span>
              <div class="legend-gradient"></div>
              <span>Higher registrations</span>
            </div>
          </div>

          <aside class="region-summary-panel">
            <div class="region-summary-heading">
              <h3>Registration Count by Region</h3>
              <span>{{ selectedYear }}</span>
            </div>

            <div class="region-summary-grid">
              <article
                v-for="item in regionSummaryCards"
                :key="item.name"
                class="region-summary-card"
                :class="{
                  'region-summary-card--international': item.name === 'International',
                  'region-summary-card--highlighted': hoveredWorldRegion === item.name
                }"
                @mouseenter="handleRegionSummaryEnter(item)"
                @mouseleave="handleRegionSummaryLeave"
              >
                <div class="region-summary-name">
                  <strong>{{ item.name }}</strong>
                </div>
                <div class="region-summary-value">{{ item.value }}</div>
                <span>Registration Count</span>
              </article>
            </div>
          </aside>

        </div>
    </section>

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
import type { AnalyticsSource } from '@/utils/liveAnalyticsData'
import AnalyticsRefreshStatus from '@/components/analytics/AnalyticsRefreshStatus.vue'
import { useAnalyticsRefresh } from '@/composables/useAnalyticsRefresh'
import { useAnalyticsRefreshState } from '@/composables/useAnalyticsRefreshState'
import { computed, onMounted, ref, watch } from 'vue'
import AnalyticsDataState from '@/components/analytics/AnalyticsDataState.vue'
import AnalyticsYearChange from '@/components/analytics/AnalyticsYearChange.vue'
import AnalyticsNumber from '@/components/analytics/AnalyticsNumber.vue'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import type { UserAnalyticsYear } from '@/types/analytics'
import AnalyticsExportMenu from '@/components/analytics/AnalyticsExportMenu.vue'
import type { AdminUser } from '@/utils/liveAnalyticsApi'
import type { ParticipantAnalyticsBundle } from '@/utils/liveAnalyticsData'
import {
  ACTIVE_WINDOW_DAYS,
  DETAILS_OPTION,
  SUMMARY_OPTION,
  accountStatusLabel,
  activityStatusLabel,
  daysSince,
  detailsCsv,
  exportFileName,
  figure,
  isoDay,
  isoUtc,
  runExport,
  sourceLabels,
  summaryCsv,
  type ExportKind,
  type SummaryRow,
} from '@/utils/analyticsExport'
import {
  analyticsYears,
  buildUsersAnalytics,
  loadUsersAnalyticsBundle,
  participantYearComparison,
  usersAnalyticsAsOf,
} from '@/utils/liveAnalyticsData'

const currentYear = ref(new Date().getFullYear())
const availableYears = ref<number[]>([currentYear.value])
const selectedYear = ref(currentYear.value)
const yearComparison = ref(participantYearComparison([], currentYear.value))
const analyticsAsOf = ref('')
const isCurrentYear = computed(() => selectedYear.value === currentYear.value)
const liveData = ref<UserAnalyticsYear>({
  totalUsers: 0,
  students: 0,
  mentors: 0,
  supervisors: 0,
  totalGrowth: null,
  studentGrowth: null,
  mentorGrowth: null,
  supervisorGrowth: null,
  loginRates: { students: 0, mentors: 0, supervisors: 0 },
  dailyActivity: { labels: [], total: [] },
  lastLogin: [],
  userLastLogins: [],
  registration: { students: [], mentors: [], supervisors: [] },
  regions: [],
  interests: [],
})
const unavailableSources = ref<AnalyticsSource[]>([])
const loadError = ref('')
const isLoading = ref(true)
const isEmpty = ref(false)
const hasLoaded = ref(false)
const exportError = ref('')
const exportDisabled = computed(() => isLoading.value || !!loadError.value || isEmpty.value || !hasLoaded.value)
// Current participants (students, mentors, supervisors) for the details export.
const participants = ref<AdminUser[]>([])
const loadedBundle = ref<ParticipantAnalyticsBundle | null>(null)

function applySelectedYear(year: number) {
  const bundle = loadedBundle.value
  if (!bundle) return

  analyticsAsOf.value = usersAnalyticsAsOf(bundle, year)
  yearComparison.value = participantYearComparison(bundle.users, year)
  liveData.value = buildUsersAnalytics(bundle, year)
  isEmpty.value = liveData.value.totalUsers === 0
}

const analyticsRefreshBusy = ref(false)
const { lastUpdated, refreshFailed, markUpdated, markRefreshFailed } = useAnalyticsRefresh(async () => { if (!analyticsRefreshBusy.value) await loadAnalytics(true, true) })

async function loadAnalytics(force = false, preserveFilters = false) {
  if (analyticsRefreshBusy.value) return
  analyticsRefreshBusy.value = true
  if (!preserveFilters || !lastUpdated.value) isLoading.value = true
  loadError.value = ''
  try {
    const bundle = await loadUsersAnalyticsBundle(force)
    loadedBundle.value = bundle
    unavailableSources.value = bundle.unavailableSources ?? []
    const year = new Date().getUTCFullYear()
    currentYear.value = year
    availableYears.value = analyticsYears(bundle)
    if (!preserveFilters) currentMonthIndex.value = new Date().getUTCMonth()
    if (!preserveFilters || !availableYears.value.includes(selectedYear.value)) {
      selectedYear.value = year
    }
    applySelectedYear(selectedYear.value)
    participants.value = bundle.users.filter((user) =>
      !user.isAdmin && ['student', 'mentor', 'supervisor'].includes((user.role ?? '').toLowerCase()),
    )
    hasLoaded.value = true
    markUpdated()
  } catch (error) {
    if (preserveFilters && lastUpdated.value) { markRefreshFailed(); return }
    console.error('Failed to load user analytics from the backend.', error)
    loadError.value = 'User analytics could not be loaded from the backend. Check the API and try again.'
    hasLoaded.value = false
  } finally {
    analyticsRefreshBusy.value = false
    isLoading.value = false
  }
}

function refreshAnalytics() {
  return loadAnalytics(true)
}

onMounted(() => loadAnalytics())
watch(selectedYear, (year) => applySelectedYear(year))
const currentMonthIndex = ref(new Date().getMonth())

const regionExpanded = ref(false)
const hoveredCountryName = ref<string | null>(null)
const hoveredLargeCountryName = ref<string | null>(null)
const hoveredWorldRegion = ref<string | null>(null)
const hoveredAustraliaRegion = ref<string | null>(null)

const mapZoom = ref(1)
const MAP_ZOOM_MIN = 1
const MAP_ZOOM_MAX = 4
const MAP_ZOOM_STEP = 0.25

const mapPanX = ref(0)
const mapPanY = ref(0)
const mapDragging = ref(false)
let mapPointerId: number | null = null
let mapLastClientX = 0
let mapLastClientY = 0

const MAP_FLATTEN_Y = 0.86

const mapTransform = computed(
  () =>
    `translate(${mapPanX.value} ${mapPanY.value}) ` +
    `translate(450 215) scale(${mapZoom.value} ${mapZoom.value * MAP_FLATTEN_Y}) translate(-450 -215)`,
)

function clampMapPan() {
  if (mapZoom.value <= 1) {
    mapPanX.value = 0
    mapPanY.value = 0
    return
  }

  const maxX = 900 * (mapZoom.value - 1) + 180
  const maxY = 430 * (mapZoom.value - 1) + 120

  mapPanX.value = Math.max(-maxX, Math.min(maxX, mapPanX.value))
  mapPanY.value = Math.max(-maxY, Math.min(maxY, mapPanY.value))
}

function setMapZoom(value: number) {
  mapZoom.value = Math.min(MAP_ZOOM_MAX, Math.max(MAP_ZOOM_MIN, Number(value.toFixed(2))))
  clampMapPan()
}

function toggleRegionExpanded() {
  const nextState = !regionExpanded.value
  hoveredCountryName.value = null
  hoveredLargeCountryName.value = null
  hoveredWorldRegion.value = null
  hoveredAustraliaRegion.value = null
  hideTooltip()
  regionExpanded.value = nextState

}

function zoomMapIn() {
  setMapZoom(mapZoom.value + MAP_ZOOM_STEP)
}

function zoomMapOut() {
  setMapZoom(mapZoom.value - MAP_ZOOM_STEP)
}

function resetMapZoom() {
  mapZoom.value = 1
  mapPanX.value = 0
  mapPanY.value = 0
}

function handleMapWheel(event: WheelEvent) {
  setMapZoom(mapZoom.value + (event.deltaY < 0 ? MAP_ZOOM_STEP : -MAP_ZOOM_STEP))
}

function startMapPan(event: PointerEvent) {
  if (mapZoom.value <= 1) return

  const target = event.currentTarget as SVGSVGElement
  target.setPointerCapture?.(event.pointerId)

  mapDragging.value = true
  mapPointerId = event.pointerId
  mapLastClientX = event.clientX
  mapLastClientY = event.clientY
}

function moveMapPan(event: PointerEvent) {
  if (!mapDragging.value || mapPointerId !== event.pointerId) return

  const svg = event.currentTarget as SVGSVGElement
  const rect = svg.getBoundingClientRect()
  if (!rect.width || !rect.height) return

  const dx = (event.clientX - mapLastClientX) * (900 / rect.width)
  const dy = (event.clientY - mapLastClientY) * (430 / rect.height)

  mapPanX.value += dx
  mapPanY.value += dy

  mapLastClientX = event.clientX
  mapLastClientY = event.clientY

  clampMapPan()
}

function endMapPan(event: PointerEvent) {
  if (mapPointerId !== null && event.pointerId !== mapPointerId) return

  const target = event.currentTarget as SVGSVGElement
  if (mapPointerId !== null && target.hasPointerCapture?.(mapPointerId)) {
    target.releasePointerCapture?.(mapPointerId)
  }

  mapDragging.value = false
  mapPointerId = null
}

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
  if (!tooltip.value.visible) return
  tooltip.value.x = event.clientX
  tooltip.value.y = event.clientY
}

function hideTooltip() {
  tooltip.value.visible = false
}

function handleCountryMapEnter(event: MouseEvent, segment: WorldShapeSegment) {
  if (!segment.countryName) return
  hoveredCountryName.value = segment.countryName
  showTooltip(
    event,
    segment.countryName,
    segment.value > 0 ? `${segment.value} users` : 'No registered users',
    segment.value > 0 ? `Registrations in ${selectedYear.value}` : `No registrations in ${selectedYear.value}`,
  )
}

function handleCountryMapLeave() {
  hoveredCountryName.value = null
  hideTooltip()
}

function handleCountryListEnter(event: MouseEvent, item: { name: string; value: number }, index: number) {
  hoveredCountryName.value = item.name
  showTooltip(event, item.name, `${item.value} users`, `Rank #${index + 1}`)
}

function handleCountryListLeave() {
  hoveredCountryName.value = null
  hideTooltip()
}

type SmallMapLocationItem = {
  kind: 'country' | 'region'
  name: string
  label: string
  value: number
  country?: string
}

function handleSmallLocationListEnter(event: MouseEvent, item: SmallMapLocationItem, index: number) {
  if (item.kind === 'region') {
    hoveredCountryName.value = null
    hoveredAustraliaRegion.value = item.name
    showTooltip(event, item.label, `${item.value} users`, `Australia · Rank #${index + 1}`)
    return
  }

  hoveredAustraliaRegion.value = null
  handleCountryListEnter(event, item, index)
}

function handleSmallLocationListLeave() {
  hoveredAustraliaRegion.value = null
  handleCountryListLeave()
}

function handleLargeMapCountryEnter(event: MouseEvent, segment: WorldShapeSegment) {
  if (!segment.countryName) return
  hoveredLargeCountryName.value = segment.countryName
  showTooltip(
    event,
    segment.countryName,
    segment.value > 0 ? `${segment.value} users` : 'No registered users',
    segment.value > 0 ? `Registrations in ${selectedYear.value}` : `No registrations in ${selectedYear.value}`,
  )
}

function handleLargeMapCountryLeave() {
  hoveredLargeCountryName.value = null
  hideTooltip()
}

function handleRegionSummaryEnter(item: { code: string; name: string; value: number }) {
  hoveredWorldRegion.value = item.name
}

function handleRegionSummaryLeave() {
  hoveredWorldRegion.value = null
}

const data = computed(() => liveData.value)

const loginRates = computed(() => [
  { label: 'Students', value: data.value.loginRates.students, color: '#39687B' },
  { label: 'Mentors', value: data.value.loginRates.mentors, color: '#017151' },
  { label: 'Supervisors', value: data.value.loginRates.supervisors, color: '#5EA99E' },
])

type RoleSegment = {
  label: string
  value: number
  percent: number
  drawPercent: number
  start: number
  color: string
}

const selectedRole = ref<RoleSegment | null>(null)

const roleSegments = computed<RoleSegment[]>(() => {
  const raw = [
    { label: 'Students', value: data.value.students, color: '#39687B' },
    { label: 'Mentors', value: data.value.mentors, color: '#017151' },
    { label: 'Supervisors', value: data.value.supervisors, color: '#5EA99E' },
  ]

  let start = 0
  return raw.map((item, index) => {
    const drawPercent = data.value.totalUsers
      ? (index === raw.length - 1 ? Math.max(0, 100 - start) : (item.value / data.value.totalUsers) * 100)
      : 0
    const segment = {
      ...item,
      percent: percentage(item.value, data.value.totalUsers),
      drawPercent,
      start,
    }
    start += drawPercent
    return segment
  })
})

function selectRole(segment: RoleSegment) {
  selectedRole.value = segment
  hideTooltip()
}

function clearRoleSelection() {
  selectedRole.value = null
}

const lastLoginRoles = [
  { key: 'students', label: 'Student' },
  { key: 'mentors', label: 'Mentor' },
  { key: 'supervisors', label: 'Supervisor' },
] as const

type LastLoginRoleKey = (typeof lastLoginRoles)[number]['key']

function lastLoginBucket(daysInactive: number | null) {
  if (daysInactive === null) return 'Never'
  if (daysInactive < 7) return '< 7 days'
  if (daysInactive <= 14) return '7–14 days'
  if (daysInactive <= 30) return '15–30 days'
  if (daysInactive <= 90) return '31–90 days'
  return '> 90 days'
}

function resolvedDaysInactive(user: UserAnalyticsYear['userLastLogins'][number]) {
  if (user.lastLogin === 'Never' || !user.lastLoginIso) return null
  if (typeof user.daysInactive === 'number') return user.daysInactive

  const lastLogin = Date.parse(user.lastLoginIso)
  const observedThrough = Date.parse(`${analyticsAsOf.value}T00:00:00Z`)
  if (Number.isNaN(lastLogin) || Number.isNaN(observedThrough)) return null
  return Math.max(0, Math.floor((observedThrough - lastLogin) / 86400000))
}

const lastLoginStacks = computed(() => data.value.lastLogin.map((bucket) => {
  const counts: Record<LastLoginRoleKey, number> = {
    students: 0,
    mentors: 0,
    supervisors: 0,
  }

  for (const user of data.value.userLastLogins) {
    if (lastLoginBucket(resolvedDaysInactive(user)) !== bucket.label) continue
    const roleKey = `${user.role.toLowerCase()}s` as LastLoginRoleKey
    if (roleKey in counts) counts[roleKey] += 1
  }

  return {
    label: bucket.label,
    ...counts,
    total: counts.students + counts.mentors + counts.supervisors,
  }
}))

const maxLastLogin = computed(() => Math.max(...lastLoginStacks.value.map((item) => item.total), 1))
const lastLoginAxisMax = computed(() => {
  const rawStep = maxLastLogin.value / 5
  const magnitude = 10 ** Math.floor(Math.log10(rawStep))
  const normalized = rawStep / magnitude
  const niceStep = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10
  return Math.max(1, niceStep * magnitude) * 5
})
const lastLoginTicks = computed(() =>
  Array.from({ length: 6 }, (_, index) => lastLoginAxisMax.value * (5 - index) / 5),
)

// Activity Status by Role uses its own 14-day login window; the daily, weekly
// and monthly active-user windows elsewhere are unchanged.
const ACTIVE_STATUS_WINDOW_DAYS = ACTIVE_WINDOW_DAYS

const analyticsAsOfLabel = computed(() => {
  const date = analyticsAsOf.value ? new Date(`${analyticsAsOf.value}T00:00:00Z`) : null
  return date && !Number.isNaN(date.getTime())
    ? date.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
    : 'the latest recorded date'
})

const activityStatusByRole = computed(() => {
  const roles = ['Student', 'Mentor', 'Supervisor'] as const

  return roles.map((role) => {
    const counts = { role, active: 0, inactive: 0, never: 0 }
    for (const user of data.value.userLastLogins) {
      if (user.role !== role) continue
      const daysInactive = resolvedDaysInactive(user)
      if (daysInactive === null) counts.never += 1
      else if (daysInactive < ACTIVE_STATUS_WINDOW_DAYS) counts.active += 1
      else counts.inactive += 1
    }
    return counts
  })
})

const maxRegistration = computed(() =>
  Math.max(
    ...visibleRegistrationSeries.value.students,
    ...visibleRegistrationSeries.value.mentors,
    ...visibleRegistrationSeries.value.supervisors,
    1,
  ),
)
const registrationAxisMax = computed(() => axisTicks(maxRegistration.value)[0] ?? maxRegistration.value)

const maxRegion = computed(() => Math.max(...data.value.regions.map((item) => item.value), 1))
const hiddenRegistrationRoles = ref<string[]>([])

useAnalyticsRefreshState('users', {
  selectedYear,
  hiddenRegistrationRoles,
  regionExpanded,
}, () => !isLoading.value && hasLoaded.value)

const interestSortDirection = ref<'asc' | 'desc'>('desc')

const sortedInterests = computed(() =>
  [...data.value.interests].sort((a, b) => {
    const aTotal = a.students + a.mentors
    const bTotal = b.students + b.mentors

    return interestSortDirection.value === 'desc'
      ? bTotal - aTotal || a.name.localeCompare(b.name)
      : aTotal - bTotal || a.name.localeCompare(b.name)
  }),
)

const maxInterest = computed(() =>
  Math.max(
    ...data.value.interests.flatMap((item) => [item.students, item.mentors]),
    1,
  ),
)

const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const visibleRegistrationMonths = computed(() =>
  isCurrentYear.value ? months.slice(0, currentMonthIndex.value + 1) : months,
)

const visibleRegistrationSeries = computed(() => {
  const end = isCurrentYear.value ? currentMonthIndex.value + 1 : months.length
  return {
    students: data.value.registration.students.slice(0, end),
    mentors: data.value.registration.mentors.slice(0, end),
    supervisors: data.value.registration.supervisors.slice(0, end),
  }
})

const registrationDots = computed(() => ({
  students: trendDots(visibleRegistrationSeries.value.students),
  mentors: trendDots(visibleRegistrationSeries.value.mentors),
  supervisors: trendDots(visibleRegistrationSeries.value.supervisors),
}))

// The SVG is drawn at the plot's real pixel size so it fills the card at any
// width and keeps its text at a readable, unscaled size.
const registrationPlot = ref<HTMLElement | null>(null)
const registrationPlotSize = ref({ width: 620, height: 260 })
const registrationChart = computed(() => {
  const { width, height } = registrationPlotSize.value
  const plotLeft = 44
  const plotRight = width - 12
  const plotTop = 22
  const baseline = height - 30
  return { width, height, plotLeft, plotRight, plotTop, baseline }
})
const registrationTicks = computed(() => axisTicks(maxRegistration.value))

watch(registrationPlot, (element, _previous, onCleanup) => {
  if (!element || typeof ResizeObserver === 'undefined') return
  const observer = new ResizeObserver(([entry]) => {
    const width = Math.round(entry?.contentRect.width ?? 0)
    const height = Math.round(entry?.contentRect.height ?? 0)
    if (width > 0 && height > 0) registrationPlotSize.value = { width, height }
  })
  observer.observe(element)
  onCleanup(() => observer.disconnect())
})

const countryHoverAnchors = [
  { name: 'Canada', lon: -106, lat: 57 },
  { name: 'Canada', lon: -120, lat: 68 },
  { name: 'Greenland', lon: -42, lat: 72 },
  { name: 'United States', lon: -99, lat: 39 },
  { name: 'United States', lon: -150, lat: 64 },
  { name: 'Mexico', lon: -102, lat: 23 },
  { name: 'Guatemala', lon: -90.2, lat: 15.8 },
  { name: 'Cuba', lon: -79.5, lat: 21.5 },
  { name: 'Dominican Republic', lon: -70.2, lat: 18.9 },
  { name: 'Colombia', lon: -74, lat: 4 },
  { name: 'Venezuela', lon: -66, lat: 7 },
  { name: 'Ecuador', lon: -78.2, lat: -1.4 },
  { name: 'Peru', lon: -75, lat: -9 },
  { name: 'Bolivia', lon: -64.7, lat: -16.7 },
  { name: 'Brazil', lon: -52, lat: -10 },
  { name: 'Chile', lon: -71, lat: -33 },
  { name: 'Argentina', lon: -64, lat: -34 },
  { name: 'Uruguay', lon: -56, lat: -33 },
  { name: 'Iceland', lon: -19, lat: 65 },
  { name: 'Ireland', lon: -8, lat: 53 },
  { name: 'United Kingdom', lon: -2, lat: 54 },
  { name: 'Portugal', lon: -8, lat: 39.5 },
  { name: 'Spain', lon: -4, lat: 40 },
  { name: 'France', lon: 2, lat: 46 },
  { name: 'Belgium', lon: 4.6, lat: 50.8 },
  { name: 'Netherlands', lon: 5.5, lat: 52.2 },
  { name: 'Germany', lon: 10, lat: 51 },
  { name: 'Switzerland', lon: 8.2, lat: 46.8 },
  { name: 'Italy', lon: 12.5, lat: 42.5 },
  { name: 'Austria', lon: 14.2, lat: 47.6 },
  { name: 'Poland', lon: 19, lat: 52 },
  { name: 'Czechia', lon: 15.5, lat: 49.8 },
  { name: 'Hungary', lon: 19.3, lat: 47.2 },
  { name: 'Romania', lon: 25, lat: 46 },
  { name: 'Greece', lon: 22, lat: 39 },
  { name: 'Norway', lon: 8, lat: 61 },
  { name: 'Sweden', lon: 15, lat: 62 },
  { name: 'Finland', lon: 26, lat: 64 },
  { name: 'Ukraine', lon: 31, lat: 49 },
  { name: 'Russia', lon: 95, lat: 61 },
  { name: 'Russia', lon: 45, lat: 58 },
  { name: 'Turkey', lon: 35, lat: 39 },
  { name: 'Morocco', lon: -6, lat: 32 },
  { name: 'Algeria', lon: 2, lat: 28 },
  { name: 'Tunisia', lon: 9.5, lat: 34 },
  { name: 'Libya', lon: 17, lat: 27 },
  { name: 'Egypt', lon: 30, lat: 27 },
  { name: 'Senegal', lon: -14.5, lat: 14.5 },
  { name: 'Ghana', lon: -1.2, lat: 7.9 },
  { name: 'Nigeria', lon: 8, lat: 9 },
  { name: 'Ethiopia', lon: 40, lat: 9 },
  { name: 'Kenya', lon: 37.8, lat: 0.5 },
  { name: 'Tanzania', lon: 35, lat: -6 },
  { name: 'Democratic Republic of the Congo', lon: 23.5, lat: -3 },
  { name: 'Angola', lon: 17.5, lat: -12.5 },
  { name: 'Zambia', lon: 27.8, lat: -13.5 },
  { name: 'Zimbabwe', lon: 29.8, lat: -19 },
  { name: 'South Africa', lon: 24, lat: -29 },
  { name: 'Madagascar', lon: 46.7, lat: -19 },
  { name: 'Saudi Arabia', lon: 45, lat: 24 },
  { name: 'United Arab Emirates', lon: 54.3, lat: 24.3 },
  { name: 'Iran', lon: 53, lat: 32 },
  { name: 'Iraq', lon: 44, lat: 33 },
  { name: 'Israel', lon: 35, lat: 31.5 },
  { name: 'Kazakhstan', lon: 68, lat: 48 },
  { name: 'Pakistan', lon: 69.5, lat: 30 },
  { name: 'India', lon: 78, lat: 22 },
  { name: 'Bangladesh', lon: 90.3, lat: 23.8 },
  { name: 'Sri Lanka', lon: 80.7, lat: 7.8 },
  { name: 'Nepal', lon: 84, lat: 28.2 },
  { name: 'China', lon: 104, lat: 35 },
  { name: 'Mongolia', lon: 103, lat: 46 },
  { name: 'North Korea', lon: 127, lat: 40 },
  { name: 'South Korea', lon: 128, lat: 36 },
  { name: 'Japan', lon: 138, lat: 37 },
  { name: 'Myanmar', lon: 96, lat: 21 },
  { name: 'Thailand', lon: 101, lat: 15 },
  { name: 'Vietnam', lon: 108, lat: 16 },
  { name: 'Cambodia', lon: 105, lat: 12.5 },
  { name: 'Malaysia', lon: 102, lat: 4 },
  { name: 'Singapore', lon: 103.82, lat: 1.35 },
  { name: 'Indonesia', lon: 118, lat: -2 },
  { name: 'Timor-Leste', lon: 125.7, lat: -8.9 },
  { name: 'Philippines', lon: 122, lat: 13 },
  { name: 'Australia', lon: 134, lat: -25 },
  { name: 'New Zealand', lon: 174, lat: -41 },
  { name: 'Papua New Guinea', lon: 145, lat: -6.5 },
].map((country) => ({
  ...country,
  x: ((country.lon + 180) / 360) * 900,
  y: ((90 - country.lat) / 150) * 430,
}))

const worldMapPath = `M896.5,305.7L900.0,305.5L896.8,306.8L896.5,305.7ZM894.2,307.8L896.4,310.0L893.5,310.1L894.2,307.8ZM0.0,304.1L0.2,305.3L0.0,305.5L0.0,304.1ZM534.8,260.7L548.0,271.4L550.8,287.6L548.8,289.2L536.4,291.0L534.3,285.0L526.9,281.9L524.1,276.7L526.0,261.3L534.8,260.7ZM428.3,178.7L428.3,183.8L420.1,183.7L417.7,196.9L407.3,197.8L413.1,196.4L421.5,180.9L428.3,178.7ZM142.9,117.5L135.9,113.5L131.4,112.3L123.7,102.4L125.0,97.7L111.3,86.6L106.4,89.1L97.5,85.1L97.5,58.2L108.7,60.5L129.7,55.9L161.9,60.5L165.3,61.9L161.7,63.3L166.3,64.0L177.8,64.8L179.6,61.2L184.6,60.8L196.4,64.1L205.8,61.4L209.7,65.1L214.4,60.0L208.8,57.1L212.0,51.8L217.8,53.6L223.6,61.7L230.0,61.3L231.6,65.4L236.2,57.7L243.4,58.3L246.8,59.7L246.5,65.6L235.6,67.2L223.2,75.7L214.4,83.4L213.3,89.0L219.3,94.4L244.3,99.9L244.7,105.3L250.2,111.2L253.5,107.3L250.4,101.3L258.6,95.9L253.7,89.4L256.7,86.4L254.7,79.4L265.4,79.0L276.0,83.0L276.8,89.0L280.9,91.1L288.5,85.0L295.5,96.5L306.7,101.4L310.8,108.5L299.9,114.0L284.0,114.0L272.2,123.8L287.4,116.9L288.8,125.4L292.1,126.9L296.2,126.5L298.7,123.2L300.5,126.4L286.6,133.2L284.6,130.5L288.9,128.2L282.2,128.6L280.5,123.1L276.9,122.0L271.2,129.0L262.8,129.0L243.9,138.5L243.6,128.0L229.1,119.5L213.0,116.4L142.9,117.5ZM240.0,79.0L241.9,77.6L245.3,77.7L242.3,79.8L240.0,79.0ZM254.0,49.1L247.9,46.7L259.4,49.2L254.0,49.1ZM250.9,81.3L250.2,79.2L251.8,79.8L250.9,81.3ZM212.9,41.1L214.6,44.2L207.9,43.2L212.9,41.1ZM213.9,34.9L209.6,35.7L208.9,34.9L213.9,34.9ZM203.4,31.9L211.1,33.2L206.7,34.8L203.4,31.9ZM250.4,43.2L218.9,43.5L215.3,39.2L207.2,38.0L250.4,43.2ZM168.2,34.3L175.4,34.4L166.2,35.2L168.2,34.3ZM171.2,32.0L175.8,32.7L168.6,33.2L171.2,32.0ZM311.0,110.9L308.0,115.2L316.3,116.8L317.3,124.3L314.4,121.1L311.5,123.6L301.8,121.5L306.6,112.6L311.0,110.9ZM235.3,69.5L246.1,74.6L249.7,75.3L231.9,75.8L235.3,69.5ZM248.1,51.4L278.0,55.8L282.6,59.7L278.0,61.0L295.4,66.3L290.2,71.7L280.0,68.0L288.3,76.3L278.0,75.3L284.6,80.5L277.8,79.3L262.9,72.6L253.6,72.9L265.1,70.4L268.4,65.1L266.7,62.9L252.6,56.9L228.3,56.2L224.5,50.9L235.4,46.4L235.6,50.1L244.2,46.6L248.1,51.4ZM210.0,47.5L218.9,45.6L223.7,46.3L211.5,51.4L210.0,47.5ZM142.9,39.8L152.2,35.8L159.5,35.4L157.2,38.6L142.9,39.8ZM117.4,104.9L120.6,102.9L122.1,108.4L117.4,104.9ZM186.3,30.7L197.9,32.1L200.8,34.7L187.1,33.3L189.5,32.5L186.3,30.7ZM141.2,118.9L135.9,118.0L129.1,112.5L135.6,113.8L141.2,118.9ZM137.7,45.0L156.1,45.3L161.2,47.4L151.9,50.1L148.9,53.4L142.3,54.7L135.2,52.0L140.2,46.8L137.7,45.0ZM161.5,38.8L185.7,41.6L169.4,44.7L165.3,43.8L170.5,42.5L155.7,42.4L161.5,38.8ZM179.0,48.5L197.3,58.5L166.7,61.5L156.6,57.4L169.0,56.3L151.5,52.9L162.0,47.8L175.2,48.8L179.5,52.6L179.0,48.5ZM198.9,49.6L196.2,47.7L206.6,46.6L204.9,48.8L208.6,50.0L204.1,53.7L193.8,50.1L198.9,49.6ZM183.5,47.0L186.8,46.9L188.8,47.5L186.5,49.4L183.5,47.0ZM203.7,38.1L204.6,43.0L193.7,41.4L193.6,39.2L203.7,38.1ZM208.2,28.2L219.0,25.1L235.5,30.6L217.8,33.4L215.1,32.2L217.1,30.4L208.2,28.2ZM221.0,23.2L251.7,19.7L295.4,21.1L257.7,30.6L261.5,32.9L248.6,39.6L226.3,38.8L230.6,36.8L229.3,34.7L237.6,35.7L230.1,33.3L237.3,30.5L232.7,27.9L245.4,27.3L221.0,23.2ZM262.0,64.7L257.5,65.7L256.9,64.2L260.3,62.2L262.0,64.7ZM204.5,56.9L209.3,60.9L200.5,59.1L204.5,56.9ZM288.7,115.0L292.9,115.5L295.5,117.2L291.0,116.4L288.7,115.0ZM289.6,125.0L290.8,124.6L295.0,124.9L292.8,126.2L289.6,125.0ZM142.9,117.5L213.0,116.4L229.1,119.5L243.6,128.0L243.3,138.5L262.8,129.0L271.2,129.0L276.9,122.0L280.5,123.1L282.6,129.5L274.7,132.8L272.9,136.6L275.1,138.6L261.2,144.8L262.4,147.9L260.1,151.3L259.1,145.8L257.5,148.4L260.7,156.1L246.7,167.9L249.0,185.7L240.7,172.2L234.0,170.9L226.0,171.5L226.5,174.4L213.3,173.5L207.2,178.2L206.2,183.9L197.6,173.8L190.2,174.1L183.7,167.0L157.2,164.7L148.4,158.8L139.0,142.4L138.3,119.9L143.5,123.0L142.9,117.5ZM59.8,201.5L63.0,202.1L60.8,203.8L59.8,201.5ZM58.5,197.8L59.0,199.0L58.2,198.0L58.5,197.8ZM56.9,197.2L58.0,197.6L56.7,197.5L56.9,197.2ZM54.7,196.9L55.9,196.9L55.7,197.0L54.7,196.9ZM51.0,194.3L51.3,195.3L50.5,194.7L51.0,194.3ZM31.4,85.4L35.8,85.2L36.1,86.3L31.4,85.4ZM63.3,93.3L69.6,92.9L63.7,94.6L63.3,93.3ZM97.5,58.2L97.5,85.1L106.4,89.1L111.3,86.6L125.0,97.7L123.7,100.9L114.8,91.4L108.4,91.1L100.3,87.3L82.2,83.5L70.7,88.4L73.4,82.3L53.9,97.5L37.6,101.6L53.3,94.6L57.4,89.1L45.1,89.8L43.7,86.0L36.6,84.5L35.7,80.1L48.1,75.2L48.1,72.3L37.6,73.3L29.7,69.7L45.8,68.5L34.5,60.5L58.5,53.4L97.5,58.2ZM20.7,75.2L23.8,75.4L28.3,76.5L26.2,77.5L20.7,75.2ZM668.4,116.9L662.9,123.3L658.0,122.3L656.1,127.5L649.9,129.2L650.6,136.6L635.5,133.9L621.6,141.4L616.8,140.0L612.3,132.6L605.0,133.3L596.3,127.3L589.8,129.0L589.9,139.6L581.3,138.2L575.8,130.1L582.6,128.3L582.6,123.7L572.8,125.0L566.2,119.3L568.9,113.4L571.4,115.0L576.9,109.8L603.3,112.4L599.9,109.0L604.2,106.1L603.6,103.2L622.7,99.2L633.6,104.7L642.2,101.8L650.1,112.2L658.5,111.6L668.4,116.9ZM589.9,139.6L589.8,129.0L596.3,127.3L605.0,133.3L612.3,132.6L620.6,141.4L627.4,136.8L626.1,139.0L632.6,140.9L619.3,144.5L619.6,151.5L596.6,135.4L589.9,139.6ZM802.5,265.5L819.1,275.4L818.0,279.2L826.7,288.3L819.8,287.0L811.9,279.9L802.6,284.1L802.5,265.5ZM827.3,265.2L832.1,271.7L826.7,265.9L827.3,265.2ZM830.3,269.9L824.3,276.1L820.8,274.5L830.3,269.9ZM836.9,273.3L840.0,276.7L839.7,277.6L837.9,276.7L836.9,273.3ZM802.5,265.5L802.6,284.1L794.0,282.1L796.7,279.0L794.8,273.5L782.5,269.8L780.0,266.1L784.2,264.3L776.3,260.7L785.0,260.2L788.6,267.7L793.6,262.9L802.5,265.5ZM762.4,283.5L761.1,287.1L758.6,287.4L760.0,284.6L762.4,283.5ZM786.8,275.8L785.3,275.6L786.2,273.6L786.8,275.8ZM744.7,246.1L743.3,248.7L747.5,255.4L744.5,255.8L740.4,269.5L725.6,266.4L722.4,256.8L724.2,252.2L726.3,255.8L734.5,254.5L739.7,245.7L744.7,246.1ZM769.7,267.7L776.2,266.9L777.1,269.1L769.7,267.7ZM767.5,267.0L765.5,268.3L765.0,267.1L767.5,267.0ZM769.8,251.8L771.7,254.8L770.3,260.6L768.5,255.1L769.8,251.8ZM752.2,254.2L763.1,253.9L750.1,259.5L752.3,262.0L758.4,259.8L753.8,263.5L757.9,273.3L753.7,271.1L752.4,265.5L749.5,274.3L746.9,266.0L749.6,257.6L752.2,254.2ZM750.7,287.4L747.4,285.4L749.8,284.8L750.7,287.4ZM749.8,283.3L755.0,282.3L757.3,281.2L756.9,282.8L749.8,283.3ZM744.8,281.2L747.8,283.0L741.9,283.9L744.8,281.2ZM715.1,274.9L731.5,277.9L739.3,282.0L713.4,277.6L715.1,274.9ZM693.7,243.0L715.3,266.8L714.5,274.8L706.5,270.1L688.2,242.3L693.7,243.0ZM278.4,408.9L280.6,412.4L287.4,414.8L278.4,415.3L278.4,408.9ZM305.9,344.6L303.8,356.7L308.0,363.8L301.9,369.0L294.2,369.3L293.1,375.6L287.2,375.7L291.4,380.0L281.8,388.6L285.9,393.4L277.2,403.4L279.6,408.1L270.2,407.1L266.5,399.4L271.9,386.4L269.6,379.1L279.0,328.3L284.3,320.6L289.1,323.4L292.9,321.2L305.6,330.1L303.5,335.8L310.8,336.5L314.7,331.2L315.9,335.2L305.9,344.6ZM278.4,408.9L278.4,415.3L282.6,415.4L279.6,417.4L263.3,409.5L272.2,413.0L278.4,408.9ZM276.0,308.4L282.5,323.9L273.7,347.9L275.5,356.0L269.6,379.1L271.9,386.4L266.5,399.4L270.2,407.1L278.6,407.9L271.4,412.4L262.6,407.8L261.0,397.5L264.7,392.6L260.9,391.7L268.2,379.5L264.2,381.9L266.0,364.5L271.4,350.9L276.0,308.4ZM523.3,270.9L526.9,281.9L521.8,282.4L520.9,291.8L524.2,296.0L517.9,291.3L505.4,289.8L504.3,278.9L493.7,281.1L490.8,274.8L480.5,274.6L490.0,268.1L498.7,243.6L506.0,246.4L514.1,242.9L524.3,244.8L527.9,251.7L524.7,256.3L523.3,270.9ZM554.0,262.8L552.5,250.0L562.4,243.7L572.3,230.9L572.4,225.3L577.8,223.5L571.5,242.7L554.0,262.8ZM548.0,271.4L534.8,260.7L537.6,252.5L535.0,245.8L538.2,242.2L545.3,247.7L554.6,246.8L552.5,250.0L554.0,262.8L548.0,271.4ZM511.4,234.4L509.5,233.2L508.6,232.3L504.8,221.9L509.7,213.2L512.5,194.9L542.2,194.9L546.0,206.4L542.1,209.4L534.9,233.1L531.9,222.9L528.4,229.9L512.7,228.5L511.4,234.4ZM509.6,201.9L509.7,213.2L504.8,221.9L507.2,226.1L488.2,236.7L484.9,230.6L488.7,229.4L483.9,216.8L489.8,199.6L487.1,192.5L489.7,190.9L509.6,201.9ZM270.7,201.5L270.7,206.3L263.9,205.4L269.2,204.5L267.0,200.9L270.7,201.5ZM271.5,207.6L271.0,201.0L279.2,204.6L271.5,207.6ZM896.8,54.2L900.0,53.0L900.0,54.9L896.8,54.2ZM572.8,125.0L566.7,130.1L571.5,138.1L569.5,140.0L541.7,128.3L547.9,123.1L545.6,121.7L549.3,120.7L550.2,115.8L529.5,108.6L528.3,105.9L531.7,105.1L527.2,98.8L518.2,93.2L522.8,85.9L520.2,84.6L528.8,77.8L525.1,75.8L525.5,69.4L522.6,66.1L524.9,63.9L521.5,60.0L530.3,57.6L552.6,64.6L546.0,68.8L533.0,67.0L542.5,75.0L542.9,71.3L549.0,73.0L555.2,67.4L559.9,68.6L558.6,61.4L565.6,62.3L565.9,66.9L584.3,60.6L599.9,62.3L602.7,60.4L601.4,57.8L621.3,62.8L623.0,61.3L617.3,58.9L616.7,54.4L624.9,48.6L632.0,51.0L629.6,53.3L634.2,61.9L628.2,67.9L631.1,68.3L637.6,63.8L632.8,53.2L636.6,49.2L640.9,54.0L639.8,52.0L643.9,50.8L653.8,52.3L651.3,46.9L710.9,35.3L735.3,40.6L723.5,45.4L767.4,47.1L778.2,55.1L780.6,52.1L799.7,53.1L797.9,50.4L801.2,49.2L847.5,54.8L852.4,58.9L873.9,61.1L877.0,60.2L876.1,57.1L900.0,60.3L900.0,71.7L893.5,72.8L898.1,79.4L884.2,81.3L875.8,86.3L858.8,86.4L855.0,91.0L858.0,92.8L855.3,100.7L842.0,111.8L839.8,95.3L861.2,78.7L850.3,84.4L848.3,80.9L841.8,81.9L835.5,86.7L837.6,88.5L805.5,88.8L787.8,101.1L803.4,105.8L800.2,119.1L787.2,133.6L776.9,137.0L777.6,129.1L782.7,128.6L787.6,119.0L777.5,121.0L769.1,115.4L764.9,106.7L758.9,104.8L750.4,106.8L751.8,109.0L744.7,116.1L735.9,114.0L721.2,116.7L697.2,108.8L693.1,115.5L680.6,112.4L668.4,116.9L658.5,111.6L650.1,112.2L642.2,101.8L633.6,104.7L622.7,99.2L603.6,103.2L604.2,106.1L599.9,109.0L603.3,112.4L576.9,109.8L571.4,115.0L568.9,113.4L566.2,119.3L572.8,125.0ZM678.0,27.7L689.9,25.1L700.5,29.3L694.4,32.2L678.0,27.7ZM703.2,30.9L713.4,32.4L698.6,34.6L703.2,30.9ZM792.4,42.2L803.7,39.9L812.7,41.4L792.4,42.2ZM820.6,42.0L826.8,42.8L815.3,42.5L820.6,42.0ZM799.7,47.7L805.2,46.3L809.0,48.1L805.2,48.1L799.7,47.7ZM562.1,27.0L575.1,26.0L578.8,26.7L569.0,28.6L562.1,27.0ZM506.8,102.3L502.2,102.3L499.2,102.0L503.2,99.8L506.8,102.3ZM583.8,46.6L602.9,39.4L622.1,38.6L596.2,45.0L588.5,50.5L593.8,55.3L579.0,53.1L586.1,46.9L583.8,46.6ZM807.3,104.0L811.6,117.6L807.9,116.7L808.8,125.7L805.2,126.2L804.2,105.2L807.3,104.0ZM0.0,60.3L25.3,68.9L18.7,70.4L17.6,73.8L3.3,68.5L0.0,71.7L0.0,60.3ZM6.1,53.7L0.0,54.9L0.0,53.0L6.1,53.7ZM531.1,128.1L534.2,125.5L541.3,127.7L534.7,130.8L531.1,128.1ZM252.7,182.3L255.4,181.1L255.4,181.8L252.7,182.3ZM256.7,181.9L257.5,181.8L257.1,183.8L256.7,181.9ZM254.0,187.5L255.3,185.8L256.2,189.9L254.0,187.5ZM297.0,406.6L303.6,404.5L305.6,405.8L301.5,407.6L297.0,406.6ZM476.1,29.7L492.5,28.5L503.9,31.7L489.8,37.9L476.1,29.7ZM527.8,58.6L521.5,60.0L519.3,56.9L511.8,61.2L495.0,61.4L481.4,74.3L480.8,85.7L477.6,89.3L464.2,90.0L462.5,80.3L498.0,57.9L520.4,53.9L528.2,56.0L525.0,56.8L527.8,58.6ZM518.5,28.5L507.6,30.4L493.4,27.8L507.3,26.8L518.5,28.5ZM511.8,34.8L506.2,36.0L501.8,35.3L507.2,33.1L511.8,34.8ZM333.1,21.1L382.2,18.6L397.9,20.9L370.2,22.4L419.5,25.0L399.9,28.2L405.7,28.3L400.7,32.2L403.8,37.3L395.8,38.3L400.4,39.9L398.3,42.6L401.6,45.0L391.1,47.9L394.3,51.1L388.0,50.7L395.6,55.4L386.1,53.2L384.1,56.7L394.1,57.0L350.5,70.4L343.0,78.3L341.6,85.7L329.3,83.5L320.9,75.6L315.1,65.4L322.8,57.5L313.3,58.5L314.1,55.0L321.5,55.7L310.4,52.6L313.2,49.9L303.5,41.5L278.7,40.0L271.5,37.2L283.1,36.2L266.8,34.3L285.7,30.4L279.9,28.3L293.4,23.6L338.7,23.9L333.1,21.1ZM622.3,397.4L626.3,398.7L626.4,399.2L621.9,400.7L622.3,397.4ZM762.7,284.9L764.9,282.2L768.3,282.1L762.7,284.9ZM490.9,339.9L499.7,339.6L499.7,329.0L504.0,334.6L508.3,330.4L514.2,331.1L523.6,321.3L528.0,321.8L529.8,327.9L526.7,334.7L532.1,334.7L520.5,351.9L500.2,357.7L495.9,355.9L490.9,339.9ZM522.4,341.0L520.2,340.7L517.5,343.6L520.3,345.6L522.4,341.0ZM522.4,341.0L520.3,345.6L517.5,343.6L520.2,340.7L522.4,341.0ZM157.2,164.7L183.7,167.0L190.2,174.1L195.8,172.6L202.5,182.4L207.1,183.8L205.3,193.7L210.2,204.0L221.5,203.9L224.3,197.8L232.4,196.2L230.4,205.7L222.5,206.9L223.8,211.9L220.6,211.9L219.4,216.3L215.3,212.3L208.6,213.1L191.2,205.6L167.1,168.6L162.7,168.0L175.4,192.6L162.4,178.5L164.6,176.1L157.2,164.7ZM305.9,344.6L315.5,349.9L315.5,356.6L303.9,355.2L305.9,344.6ZM316.6,354.8L315.5,349.9L305.9,344.6L315.9,332.9L310.5,322.1L305.2,321.3L304.4,304.7L299.6,304.6L298.7,297.5L286.5,291.2L286.7,286.0L273.6,289.6L273.8,285.2L269.5,286.8L265.0,279.6L267.8,273.1L275.3,270.3L275.5,253.1L286.1,255.7L291.6,251.7L288.0,246.4L298.2,243.1L302.4,254.2L317.7,251.9L321.7,245.9L324.0,258.2L337.7,262.4L338.5,265.7L350.1,266.2L361.0,272.8L363.2,279.1L353.3,295.4L347.6,320.9L330.9,329.3L327.8,340.2L316.6,354.8ZM276.2,289.4L286.7,286.0L286.5,291.2L298.7,297.5L299.6,304.6L304.4,304.7L305.4,315.2L295.5,314.3L293.3,321.8L284.3,320.6L280.4,323.6L276.0,308.4L278.3,294.0L276.2,289.4ZM275.3,270.3L267.8,273.1L265.0,279.6L269.5,286.8L273.8,285.2L273.6,289.6L278.3,294.0L277.6,305.3L274.1,310.6L260.0,300.0L246.5,271.6L249.2,267.8L248.9,270.7L253.4,271.0L262.2,258.2L267.3,264.6L274.9,265.8L275.3,270.3ZM282.8,254.4L275.5,253.1L275.3,270.3L274.9,265.8L256.4,256.9L252.5,253.2L257.2,247.0L256.3,233.6L271.5,222.5L266.7,231.8L270.1,238.0L281.6,240.5L282.8,254.4ZM256.6,233.1L255.3,237.3L252.2,232.2L247.8,237.3L242.9,234.9L242.7,230.8L252.4,230.6L256.6,233.1ZM240.9,226.6L242.6,234.4L235.1,226.8L240.9,226.6ZM240.9,226.6L235.7,226.2L230.8,221.0L242.1,215.0L240.9,226.6ZM242.1,215.0L231.7,220.8L226.6,216.7L230.2,212.5L242.1,215.0ZM224.8,218.6L230.7,218.5L230.2,220.3L224.8,218.6ZM219.4,216.3L220.6,211.9L223.8,211.9L222.5,206.9L227.1,206.9L226.9,212.5L229.4,212.9L226.6,216.7L219.4,216.3ZM226.9,212.5L229.7,205.4L227.7,212.5L226.9,212.5ZM298.2,243.1L288.0,246.4L291.6,251.7L284.2,255.9L280.5,249.9L281.6,240.5L270.1,238.0L267.7,228.0L270.1,224.7L271.7,224.2L269.8,229.7L271.8,231.8L271.5,226.6L275.1,223.1L279.5,227.7L295.3,227.3L293.2,228.1L300.6,234.0L296.5,240.9L298.2,243.1ZM308.7,252.6L300.9,252.9L300.0,243.6L296.5,240.9L300.6,234.0L307.1,240.9L304.9,246.4L308.7,252.6ZM313.7,251.4L308.7,252.6L306.0,248.4L307.1,240.9L315.1,241.5L313.7,251.4ZM320.9,246.1L317.7,251.9L313.7,251.4L315.1,241.5L320.9,246.1ZM456.3,111.4L470.2,117.5L465.1,124.1L468.6,132.7L454.6,136.6L445.2,133.5L447.0,126.1L438.5,118.4L446.0,118.6L445.2,115.3L456.3,111.4ZM471.9,138.8L473.5,134.7L473.1,139.4L471.9,138.8ZM261.6,258.4L253.4,271.0L248.9,270.7L249.8,255.8L252.9,254.0L261.6,258.4ZM282.2,204.9L286.0,205.7L282.0,206.6L282.2,204.9ZM254.2,205.8L257.8,205.3L259.5,206.7L254.2,205.8ZM244.3,191.5L254.1,193.5L264.6,199.9L255.6,201.1L257.3,199.5L253.2,196.1L245.5,193.1L237.6,195.2L244.3,191.5ZM528.0,321.8L520.1,319.6L513.2,308.8L517.6,309.4L525.7,302.5L532.1,305.9L531.6,316.2L528.0,321.8ZM523.6,321.3L514.2,331.1L508.3,330.4L504.0,334.6L499.7,329.0L502.3,310.3L513.2,308.8L523.6,321.3ZM502.3,310.3L499.7,339.6L490.9,339.9L479.3,307.6L512.7,308.4L502.3,310.3ZM415.4,219.3L405.9,215.8L413.6,210.4L421.2,222.3L408.3,222.5L415.4,219.3ZM421.2,222.3L420.8,213.9L436.2,213.6L433.9,186.5L460.7,203.1L459.1,213.4L440.0,219.4L436.5,228.3L429.9,228.7L427.2,222.7L421.2,222.3ZM407.3,197.8L417.7,196.9L420.1,183.7L428.3,183.8L428.3,179.5L437.7,186.4L433.9,186.5L436.2,213.6L419.6,216.1L413.6,210.4L408.8,211.7L407.3,197.8ZM459.5,227.2L454.7,240.4L451.9,228.0L457.1,222.9L459.5,227.2ZM487.1,192.5L489.8,199.6L483.9,216.8L485.5,222.2L482.7,219.0L472.5,221.2L463.6,218.3L460.3,219.2L459.0,224.6L452.6,221.2L450.9,215.2L459.1,213.4L460.7,203.1L480.0,190.7L487.1,192.5ZM456.7,240.1L460.9,218.6L472.5,221.2L482.7,219.0L486.4,223.4L479.4,238.0L473.1,239.5L471.3,244.3L464.7,245.8L460.8,240.0L456.7,240.1ZM486.2,221.1L488.7,229.4L484.9,230.6L488.6,235.9L486.2,244.4L489.9,253.0L474.1,251.5L471.9,242.3L479.4,238.0L486.2,221.1ZM452.2,226.5L454.7,240.4L452.7,241.0L449.9,227.3L452.2,226.5ZM450.1,226.4L452.7,241.0L442.9,243.7L442.6,226.6L450.1,226.4ZM429.9,228.7L442.9,230.4L442.9,243.7L430.7,245.5L429.9,228.7ZM415.7,221.9L427.2,222.7L429.3,236.0L423.7,234.1L422.2,229.2L416.9,232.5L412.2,226.4L415.7,221.9ZM408.3,222.5L415.7,221.9L415.6,224.1L412.2,226.4L408.3,222.5ZM424.4,233.9L431.1,241.6L430.7,245.5L421.4,238.5L424.4,233.9ZM416.9,232.5L422.2,229.2L424.4,233.9L421.4,238.5L416.9,232.5ZM436.5,228.3L439.3,220.1L447.3,215.1L450.9,215.2L455.4,221.8L452.2,226.5L442.6,226.6L442.9,230.4L436.5,228.3ZM518.4,243.0L506.0,246.4L498.7,243.6L490.0,251.5L486.1,242.4L488.2,236.7L507.2,226.1L508.6,232.3L518.4,243.0ZM496.1,248.0L490.0,268.1L486.5,272.2L479.8,272.4L478.7,265.9L485.0,265.1L486.1,261.8L482.7,251.5L489.9,253.0L492.8,247.3L496.1,248.0ZM478.2,251.5L485.7,254.6L486.1,261.8L477.7,269.4L472.0,261.2L478.2,251.5ZM474.1,251.5L478.2,251.5L478.2,255.0L473.7,255.1L474.1,251.5ZM526.9,281.9L533.1,285.7L533.0,298.1L525.4,300.4L517.6,309.4L508.0,308.2L504.7,304.1L504.8,295.0L510.0,295.0L509.8,289.3L524.2,296.0L520.9,291.8L521.1,284.3L526.9,281.9ZM531.9,284.5L535.7,287.1L539.2,299.9L537.6,306.2L536.1,299.9L531.7,297.3L531.9,284.5ZM536.4,291.0L550.8,287.6L551.9,300.1L537.0,314.7L538.6,327.2L530.2,334.6L528.0,321.8L531.6,316.2L532.1,305.9L525.4,300.4L533.0,298.1L537.6,306.2L539.2,299.9L536.4,291.0ZM530.2,334.6L526.7,334.7L527.6,331.8L529.6,332.1L530.2,334.6ZM479.8,272.4L481.6,272.3L480.5,274.6L479.8,272.4ZM480.8,275.5L490.8,274.8L493.7,281.1L504.3,278.9L505.4,289.8L510.0,290.2L510.0,295.0L504.8,295.0L504.7,304.1L508.0,308.2L479.3,307.6L484.3,290.4L480.8,275.5ZM526.2,264.9L526.9,267.6L523.3,270.9L522.6,266.1L526.2,264.9ZM539.3,164.2L537.4,166.6L537.3,173.4L535.7,168.5L539.3,164.2ZM541.5,160.0L537.8,163.1L541.1,158.8L541.5,160.0ZM573.9,293.7L575.9,303.0L567.7,329.5L563.5,331.4L558.4,323.3L559.9,307.9L573.9,293.7ZM538.9,165.1L537.3,168.1L538.0,164.7L538.9,165.1ZM407.9,220.3L412.3,218.2L415.4,219.3L407.9,220.3ZM473.7,171.1L468.8,160.3L473.8,150.9L477.6,151.7L475.4,159.6L478.7,163.0L473.7,171.1ZM428.3,179.5L428.3,175.3L446.7,165.5L444.6,157.2L447.0,155.6L471.1,152.1L468.8,160.3L474.5,173.6L473.3,183.2L480.0,190.7L457.9,203.4L428.3,179.5ZM538.9,165.1L547.0,162.3L548.0,165.8L542.5,167.7L545.0,170.5L540.2,174.3L537.3,173.4L538.9,165.1ZM578.9,188.5L585.0,188.9L590.7,184.3L587.5,193.5L580.0,192.1L578.9,188.5ZM579.0,185.7L576.9,185.0L578.2,183.1L579.0,185.7ZM568.3,171.8L571.0,176.2L566.4,174.6L568.3,171.8ZM561.8,174.4L547.0,162.3L552.5,159.3L553.2,153.8L561.9,151.4L565.2,155.7L563.5,160.6L571.4,172.2L561.8,174.4ZM587.5,200.7L591.0,186.5L599.5,194.0L594.2,203.7L582.8,210.3L580.0,203.5L587.5,200.7ZM591.2,182.6L590.2,183.3L590.9,182.3L591.2,182.6ZM868.0,303.6L869.6,305.2L868.8,305.6L868.0,303.6ZM868.2,303.1L866.6,302.1L866.6,299.9L868.2,303.1ZM708.7,227.5L707.5,217.2L716.2,216.2L719.0,219.2L715.6,226.6L708.7,227.5ZM713.0,217.1L707.5,217.2L706.5,223.1L700.2,219.6L698.1,231.5L705.4,240.2L702.9,241.7L695.4,234.1L699.0,223.9L693.4,205.1L700.3,199.5L703.2,202.2L702.6,207.8L708.0,205.5L711.8,208.0L713.0,217.1ZM718.5,217.3L713.0,217.1L709.9,205.7L702.6,207.8L703.2,202.2L700.3,199.5L704.5,197.3L704.1,194.0L711.1,198.5L709.7,202.8L718.3,212.4L718.5,217.3ZM702.9,195.4L693.4,205.1L699.0,223.9L696.4,229.5L692.9,209.5L685.5,212.0L685.8,205.8L680.8,196.4L693.3,177.0L696.7,179.1L694.0,189.5L702.9,195.4ZM710.8,227.9L718.7,222.6L718.9,214.4L709.7,202.8L711.1,198.5L705.4,193.6L713.3,191.1L720.1,196.2L714.2,203.4L722.2,214.2L723.0,224.6L712.9,233.3L710.8,227.9ZM777.0,137.0L777.0,137.0L777.0,137.0L777.0,137.0ZM776.6,136.5L768.8,144.0L770.5,148.0L761.8,148.8L762.7,141.7L776.6,136.5ZM765.4,149.8L770.9,147.3L772.7,157.4L766.2,159.4L765.4,149.8ZM669.4,116.7L680.6,112.4L693.1,115.5L697.2,108.8L721.2,116.7L741.7,115.0L739.4,121.2L749.4,123.1L729.7,128.7L726.0,135.1L712.4,138.8L690.9,135.5L688.3,131.2L677.4,128.2L677.4,123.6L669.4,116.7ZM693.3,177.0L681.7,194.8L677.9,190.6L680.9,186.4L671.4,182.2L672.2,195.8L667.4,196.4L650.8,212.4L649.6,228.3L643.8,235.2L633.8,212.2L631.6,196.8L626.2,198.2L620.4,190.1L627.6,188.2L623.8,180.8L629.4,178.0L638.1,165.5L634.4,159.6L644.6,156.3L646.8,167.7L652.8,171.5L650.2,175.5L658.3,179.6L670.2,182.3L671.8,177.5L674.4,181.4L680.1,181.1L679.2,178.4L690.3,173.6L693.3,177.0ZM681.7,194.8L680.9,198.7L678.5,192.7L672.6,194.8L671.4,182.2L680.9,186.4L677.9,190.6L681.7,194.8ZM675.0,176.9L680.1,181.1L672.1,180.3L675.0,176.9ZM670.3,178.1L668.1,182.3L650.2,175.5L653.8,170.8L670.3,178.1ZM644.6,156.3L634.4,159.6L638.1,165.5L629.4,178.0L623.8,180.8L627.6,188.2L620.4,190.1L615.9,185.1L603.7,186.1L608.3,181.3L602.2,172.5L615.9,172.3L617.3,168.3L623.3,166.5L629.6,153.3L637.9,151.6L644.6,156.3ZM603.0,155.8L623.0,151.5L627.0,147.7L629.6,152.7L637.9,151.6L628.2,154.6L623.3,166.5L617.3,168.3L615.9,172.3L602.2,172.5L604.5,169.9L601.3,163.5L603.0,155.8ZM619.6,151.5L619.3,144.5L626.7,140.6L623.7,144.7L634.2,145.0L637.5,150.7L629.6,152.7L627.0,147.7L619.6,151.5ZM626.1,139.0L635.5,133.9L650.6,136.6L634.2,145.0L623.7,144.7L632.6,140.9L626.1,139.0ZM581.3,138.2L585.2,136.7L592.7,139.5L596.6,135.4L616.3,150.9L605.6,156.9L593.3,149.0L584.8,151.4L581.7,143.2L586.8,140.6L581.3,138.2ZM571.4,172.2L563.5,160.6L565.2,155.7L560.3,145.0L570.2,144.5L577.1,152.3L591.5,148.7L602.8,153.4L601.3,163.5L604.5,169.9L602.2,172.5L608.3,181.3L603.7,186.1L593.5,184.2L592.4,180.7L583.7,181.1L575.3,171.6L571.4,172.2ZM539.3,164.2L541.8,152.5L555.9,151.3L552.5,159.3L539.3,164.2ZM566.3,146.9L559.1,142.6L559.0,140.2L563.9,141.0L566.3,146.9ZM477.6,89.3L481.6,82.3L479.8,77.0L491.9,63.0L501.6,59.9L508.8,63.3L509.8,68.8L494.6,78.1L492.8,82.2L497.0,85.8L489.7,97.2L482.4,99.3L477.6,89.3ZM520.4,97.0L527.2,98.8L531.7,105.1L528.3,105.9L529.5,108.6L508.8,110.1L508.7,103.5L520.4,97.0ZM529.5,108.6L550.2,115.8L549.3,120.7L537.5,126.9L529.2,124.1L521.7,128.1L525.1,124.9L521.7,120.1L505.2,119.2L509.8,113.4L508.8,110.1L529.5,108.6ZM508.7,103.5L510.1,112.6L506.9,117.5L490.4,113.5L485.2,106.1L494.1,100.8L508.7,103.5ZM492.4,120.0L486.6,124.9L473.7,123.0L482.3,121.9L484.0,117.9L492.4,120.0ZM492.4,120.0L506.8,120.7L502.6,125.2L496.1,126.8L490.5,123.7L492.4,120.0ZM516.5,119.8L521.7,120.1L525.1,124.9L520.6,127.6L516.5,119.8ZM520.6,127.6L524.0,128.2L521.4,132.7L507.4,132.4L500.6,125.8L507.9,120.1L516.5,119.8L520.6,127.6ZM516.2,98.6L508.7,103.5L502.6,97.4L512.2,96.4L516.2,98.6ZM518.2,93.2L520.4,97.0L516.2,98.6L502.6,97.4L506.3,92.4L518.2,93.2ZM520.0,87.5L518.2,93.2L510.8,92.3L508.3,88.3L520.0,87.5ZM485.3,103.9L487.5,111.5L480.6,113.9L484.0,117.9L482.3,121.9L468.7,121.5L470.2,117.5L465.1,114.3L467.8,104.1L474.8,100.4L485.3,103.9ZM507.4,139.5L507.4,132.4L521.4,132.7L520.0,137.6L507.4,139.5ZM515.7,156.8L511.8,157.9L508.8,156.9L509.2,155.6L515.7,156.8ZM507.4,139.5L516.5,138.9L506.6,142.6L510.1,150.1L506.2,153.6L500.4,144.4L507.4,139.5ZM561.9,151.4L524.2,154.4L519.1,152.9L515.4,144.9L533.8,137.5L545.9,140.6L556.5,138.8L562.0,144.2L561.9,151.4ZM515.3,138.1L520.0,137.6L522.5,139.6L515.9,142.9L515.3,138.1ZM502.6,140.9L500.4,144.4L498.5,142.6L499.3,135.6L502.6,140.9ZM491.4,124.7L498.5,128.3L489.4,129.5L496.1,136.2L484.1,128.6L491.4,124.7ZM466.8,121.7L475.9,124.7L465.1,125.4L466.8,121.7ZM464.5,114.4L465.5,116.2L464.2,116.0L464.5,114.4ZM465.4,112.4L464.2,116.0L456.3,111.4L462.4,110.4L465.4,112.4ZM467.3,104.7L465.4,112.4L458.3,110.8L461.8,105.8L467.3,104.7ZM427.4,137.9L434.0,139.4L430.4,152.4L426.2,147.0L427.4,137.9ZM431.4,151.7L434.0,139.4L427.4,137.9L426.5,134.7L457.5,136.2L444.6,152.9L436.6,155.0L431.4,151.7ZM434.5,103.6L433.0,108.2L425.1,109.4L425.8,103.5L431.1,100.0L434.5,103.6ZM861.1,315.7L867.8,321.5L860.1,315.6L861.1,315.7ZM854.8,287.9L854.3,289.0L853.3,287.3L854.8,287.9ZM852.3,281.9L853.8,286.0L851.4,281.9L852.3,281.9ZM850.9,284.9L849.6,286.1L849.3,284.5L850.9,284.9ZM845.9,279.0L849.8,282.5L845.5,279.3L845.9,279.0ZM842.9,278.1L843.8,279.1L841.4,276.9L842.9,278.1ZM896.3,366.1L886.6,376.3L888.1,374.0L884.6,371.3L886.7,365.2L881.6,357.0L889.9,365.7L896.3,366.1ZM866.7,390.5L882.0,374.1L885.6,376.5L876.5,389.6L866.7,390.5ZM819.2,375.0L819.8,381.9L815.1,382.8L811.9,374.7L819.2,375.0ZM778.3,348.3L745.1,358.5L737.6,356.0L739.5,350.3L733.3,332.9L735.6,333.4L734.3,322.4L752.1,314.4L764.2,298.8L774.1,300.9L780.9,289.9L791.2,292.0L788.8,301.0L800.5,308.8L806.3,288.6L816.0,312.3L826.8,322.2L833.9,338.6L825.0,365.3L815.8,369.9L812.6,366.6L809.0,369.3L801.6,367.0L795.5,356.6L792.1,359.1L794.5,352.3L790.0,358.0L785.7,351.5L778.3,348.3ZM654.5,236.4L650.9,240.9L650.4,229.8L652.1,231.4L654.5,236.4ZM725.8,204.5L721.6,202.5L727.0,200.4L725.8,204.5ZM650.6,136.6L649.9,129.2L669.4,116.7L677.4,123.6L677.4,128.2L688.3,131.2L690.9,135.5L712.4,138.8L723.1,136.1L729.6,132.6L729.7,128.7L749.2,124.1L738.7,120.0L755.6,104.8L764.9,106.7L769.1,115.4L777.5,121.0L787.6,119.0L782.7,128.6L777.6,129.1L776.6,136.5L752.6,146.5L754.1,140.6L743.8,147.0L749.3,151.5L755.9,150.6L747.9,157.9L754.8,167.1L754.2,177.1L746.6,187.6L726.1,199.7L713.3,191.1L704.1,194.0L704.5,197.3L698.1,194.6L696.7,189.0L694.0,189.5L696.7,179.1L690.3,173.6L672.0,179.7L646.8,167.7L647.3,159.6L634.2,145.0L650.6,136.6ZM753.7,185.5L752.9,192.7L751.9,195.0L750.3,190.5L753.7,185.5ZM467.1,126.2L484.5,124.7L484.8,127.3L480.8,127.9L481.5,131.6L495.9,142.3L495.7,143.9L492.2,142.1L492.6,146.5L489.2,149.3L488.5,143.2L475.5,132.1L468.6,132.7L467.1,126.2ZM486.9,148.7L487.7,153.0L481.1,150.2L481.4,148.7L486.9,148.7ZM470.4,140.6L474.5,141.9L472.0,146.5L470.4,140.6ZM474.8,100.4L471.3,100.4L470.2,95.9L476.5,92.5L474.8,100.4ZM480.9,97.1L480.2,100.9L477.6,99.3L477.3,98.1L480.9,97.1ZM435.8,101.6L431.1,103.0L431.1,100.0L435.8,101.6ZM442.3,104.9L434.6,95.2L437.5,89.9L445.1,92.6L442.2,97.5L454.2,106.8L453.6,111.0L435.6,114.2L441.5,110.6L436.8,109.0L439.4,108.1L438.6,104.6L442.3,104.9ZM413.7,67.5L416.0,71.3L403.4,76.0L393.1,74.6L395.6,73.4L390.1,72.0L394.4,70.6L389.2,69.9L413.7,67.5ZM566.0,138.0L576.0,142.6L572.2,148.1L564.0,143.6L562.4,139.8L566.0,138.0ZM564.3,144.8L563.6,146.6L562.0,144.2L564.3,144.8ZM549.9,133.5L563.7,136.2L566.6,139.9L553.9,138.9L549.9,133.5ZM752.1,221.6L750.8,219.4L753.8,220.5L752.1,221.6ZM757.5,232.1L757.4,226.8L760.2,225.8L757.5,232.1ZM765.9,233.9L763.5,242.0L759.0,235.5L754.8,237.4L763.5,230.0L765.9,233.9ZM749.2,227.7L742.9,234.0L748.8,225.4L749.2,227.7ZM755.8,205.8L754.3,216.9L759.9,218.5L760.2,222.1L751.6,218.3L749.8,213.8L751.8,205.0L755.8,205.8ZM755.0,228.1L754.7,223.9L757.8,224.8L755.0,228.1ZM760.7,222.0L764.5,226.3L762.0,228.9L760.7,222.0ZM700.2,239.5L707.4,242.2L710.6,254.3L703.5,250.1L700.2,239.5ZM748.0,242.5L739.7,245.7L736.6,253.9L724.6,254.2L738.4,245.6L741.8,238.1L748.0,242.5ZM738.6,242.4L738.4,245.6L736.6,246.5L735.5,245.0L738.6,242.4ZM484.5,124.7L490.5,123.7L491.4,124.7L488.3,127.7L484.3,127.6L484.5,124.7ZM519.3,56.9L524.9,63.9L522.6,66.1L527.8,79.2L520.2,84.6L507.2,86.4L503.3,83.9L503.8,76.9L513.5,71.3L508.9,67.7L508.8,63.3L501.6,59.9L511.8,61.2L519.3,56.9ZM506.4,117.3L494.6,121.1L492.2,119.1L496.4,116.1L506.4,117.3ZM487.5,111.5L493.9,113.6L497.1,116.1L485.8,118.8L481.3,116.0L487.5,111.5ZM541.1,216.7L542.1,209.4L546.0,206.4L557.7,221.6L550.1,216.4L541.1,216.7ZM804.7,145.7L800.6,157.3L789.5,162.1L787.7,158.8L777.5,160.9L780.0,163.0L775.5,167.9L773.5,162.6L798.6,148.4L800.8,139.9L803.4,139.4L804.7,145.7ZM804.9,127.4L813.9,134.0L799.9,138.8L804.9,127.4ZM780.9,162.1L784.8,159.5L786.9,161.1L782.5,164.2L780.9,162.1ZM304.6,315.8L305.2,321.3L314.3,326.9L310.8,336.5L303.5,335.8L305.6,330.1L293.3,321.8L295.5,314.3L304.6,315.8ZM580.0,203.5L582.8,210.3L580.4,213.3L558.7,221.8L556.5,214.4L558.5,207.6L567.5,209.4L580.0,203.5ZM537.4,173.8L543.8,172.0L542.5,167.7L548.0,165.8L561.8,174.4L568.6,174.9L580.0,192.1L588.0,192.9L587.5,200.7L572.8,204.6L567.5,209.4L558.5,207.6L556.9,211.1L536.6,177.6L537.4,173.8ZM534.9,157.5L532.4,156.6L536.4,155.7L534.9,157.5ZM532.4,158.9L533.5,157.2L535.0,157.7L532.4,158.9ZM444.6,157.2L446.7,165.5L428.3,175.3L428.0,180.3L421.5,180.9L413.1,196.4L407.4,196.6L413.9,182.7L426.1,172.2L428.4,162.7L435.2,155.5L444.6,157.2ZM542.2,194.9L512.5,194.9L512.9,167.5L535.7,168.5L535.4,178.2L530.8,172.7L542.2,194.9ZM512.3,166.6L512.5,200.7L509.6,201.9L489.7,190.9L485.4,193.5L475.8,188.1L473.3,183.2L474.9,168.1L478.7,163.0L497.7,171.2L502.1,164.2L512.3,166.6ZM569.5,235.1L562.4,243.7L548.9,248.2L540.4,245.2L532.4,235.7L541.1,216.7L544.8,215.1L554.0,219.4L554.4,226.3L559.2,231.7L569.5,235.1ZM554.4,226.3L558.3,222.5L556.9,226.7L554.4,226.3ZM572.4,225.3L569.5,235.1L556.4,227.7L557.9,225.1L560.3,228.1L572.4,225.3ZM534.8,260.7L523.9,261.8L528.1,247.2L536.2,247.8L534.8,260.7ZM526.0,261.3L526.9,264.6L522.6,266.1L523.2,262.6L526.0,261.3ZM496.4,135.7L491.1,131.7L489.9,128.3L498.4,129.4L496.4,135.7ZM501.9,137.5L507.4,139.5L501.5,140.2L501.9,137.5ZM497.1,126.4L506.8,130.2L506.4,136.3L498.0,133.2L497.1,126.4ZM498.0,133.2L498.4,138.0L496.1,136.2L498.0,133.2ZM501.5,138.0L501.6,134.1L504.4,135.6L503.9,136.9L501.5,138.0ZM295.1,229.1L297.8,226.9L297.7,229.0L295.1,229.1ZM527.1,247.9L519.9,245.4L509.7,233.3L514.5,228.2L516.9,230.9L528.4,229.9L533.0,223.1L534.9,233.1L532.4,235.7L538.2,242.2L527.1,247.9Z`

type WorldShapeSegment = { d: string; cx: number; cy: number; countryName: string | null; worldRegion: string | null; value: number }

const countryRegionLookup = new Map<string, string>([
  ...['Canada', 'Greenland', 'United States', 'Mexico', 'Guatemala', 'Cuba', 'Dominican Republic'].map((name) => [name, 'North America'] as const),
  ...['Colombia', 'Venezuela', 'Ecuador', 'Peru', 'Bolivia', 'Brazil', 'Chile', 'Argentina', 'Uruguay'].map((name) => [name, 'South America'] as const),
  ...['Iceland', 'Ireland', 'United Kingdom', 'Portugal', 'Spain', 'France', 'Belgium', 'Netherlands', 'Germany', 'Switzerland', 'Italy', 'Austria', 'Poland', 'Czechia', 'Hungary', 'Romania', 'Greece', 'Norway', 'Sweden', 'Finland', 'Ukraine'].map((name) => [name, 'Europe'] as const),
  ...['Morocco', 'Algeria', 'Tunisia', 'Libya', 'Egypt', 'Senegal', 'Ghana', 'Nigeria', 'Ethiopia', 'Kenya', 'Tanzania', 'Democratic Republic of the Congo', 'Angola', 'Zambia', 'Zimbabwe', 'South Africa', 'Madagascar'].map((name) => [name, 'Africa'] as const),
  ...['Russia', 'Turkey', 'Saudi Arabia', 'United Arab Emirates', 'Iran', 'Iraq', 'Israel', 'Kazakhstan', 'Pakistan', 'India', 'Bangladesh', 'Sri Lanka', 'Nepal', 'China', 'Mongolia', 'North Korea', 'South Korea', 'Japan', 'Myanmar', 'Thailand', 'Vietnam', 'Cambodia', 'Malaysia', 'Singapore', 'Indonesia', 'Timor-Leste', 'Philippines'].map((name) => [name, 'Asia'] as const),
  ...['Australia', 'New Zealand', 'Papua New Guinea'].map((name) => [name, 'Oceania'] as const),
])

const getWorldRegionForCountry = (countryName: string | null): string | null =>
  countryName ? (countryRegionLookup.get(countryName) ?? null) : null

const inferWorldRegionFromMapPosition = (x: number, y: number): string | null => {
  if (x < 405 && y >= 205) return 'South America'

  if (x < 405 && y < 205) return 'North America'

  if (x >= 748 && x <= 782 && y >= 272 && y <= 304) return 'Asia'

  if ((x >= 650 && y >= 300) || (x >= 790 && y >= 265)) return 'Oceania'

  if (x >= 525 && x < 625 && y >= 135 && y < 250) return 'Asia'

  if (x >= 405 && x < 525 && y < 170) return 'Europe'

  if (x >= 405 && x < 565 && y >= 170) return 'Africa'
  if (x >= 565 && x < 600 && y >= 250) return 'Africa'

  if (x >= 525 && y < 300) return 'Asia'

  return null
}

const worldShapeSegments = computed<WorldShapeSegment[]>(() => {
  const values = new Map(countryRankedLocations.value.map((item) => [item.name, item.value]))

  return (worldMapPath.match(/M[^Z]+Z/g) ?? []).map((d) => {
    const coords = [...d.matchAll(/(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/g)]
    const xs = coords.map((m) => Number(m[1]))
    const ys = coords.map((m) => Number(m[2]))
    const cx = xs.length ? (Math.min(...xs) + Math.max(...xs)) / 2 : 0
    const cy = ys.length ? (Math.min(...ys) + Math.max(...ys)) / 2 : 0

    let country = countryHoverAnchors[0] ?? null
    let distance = Number.POSITIVE_INFINITY
    for (const candidate of countryHoverAnchors) {
      const current = Math.hypot(candidate.x - cx, candidate.y - cy)
      if (current < distance) {
        country = candidate
        distance = current
      }
    }

    const countryName = country?.name ?? null
    return {
      d,
      cx,
      cy,
      countryName,
      worldRegion:
        (cx >= 744 && cx <= 792 && cy >= 266 && cy <= 308)
          ? 'Asia'
          : (getWorldRegionForCountry(countryName) ?? inferWorldRegionFromMapPosition(cx, cy)),
      value: countryName ? (values.get(countryName) ?? 0) : 0,
    }
  })
})

const internationalLocations = computed(() =>
  data.value.regions.filter(
    (item) => !australianStateNames.has(item.name) && item.name !== 'Unknown' && item.name !== 'International',
  ),
)

const domesticLocations = computed(() =>
  data.value.regions.filter((item) => item.name !== 'International'),
)

const countryRankedLocations = computed(() => {
  const totals = new Map<string, number>()

  const australiaTotal = domesticLocations.value
    .filter((item) => australianStateNames.has(item.name))
    .reduce((sum, item) => sum + item.value, 0)

  totals.set('Australia', australiaTotal)

  for (const item of internationalLocations.value) {
    totals.set(item.name, (totals.get(item.name) ?? 0) + item.value)
  }

  return [...totals.entries()]
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value || a.name.localeCompare(b.name))
})

const australianRegionFullNames: Record<string, string> = {
  NSW: 'New South Wales',
  VIC: 'Victoria',
  QLD: 'Queensland',
  WA: 'Western Australia',
  SA: 'South Australia',
  ACT: 'Australian Capital Territory',
  TAS: 'Tasmania',
  NT: 'Northern Territory',
}

const compactRegionLocations = computed(() =>
  data.value.regions
    .filter((item) => item.name !== 'International')
    .map((item) => ({
      ...item,
      label: australianRegionFullNames[item.name] ?? item.name,
    }))
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label)),
)

const australiaRegionRankedLocations = computed(() =>
  domesticLocations.value
    .filter((item) => australianStateNames.has(item.name))
    .map((item) => ({
      kind: 'region' as const,
      name: item.name,
      label: australianRegionFullNames[item.name] ?? item.name,
      value: item.value,
      country: 'Australia',
    })),
)

const smallMapRankedLocations = computed<SmallMapLocationItem[]>(() => {
  const countries = countryRankedLocations.value
    .filter((item) => item.name !== 'Australia')
    .map((item) => ({ kind: 'country' as const, name: item.name, label: item.name, value: item.value }))

  return [...australiaRegionRankedLocations.value, ...countries]
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label))
})

const australiaRegionShapes = computed(() => {
  const values = new Map(australiaRegionRankedLocations.value.map((item) => [item.name, item.value]))
  const v = (name: string) => values.get(name) ?? 0

  return [
    { name: 'WA', fullName: 'Western Australia', value: v('WA'), points: '729,289 771,285 771,340 744,349 725,333', labelX: 747, labelY: 317 },
    { name: 'NT', fullName: 'Northern Territory', value: v('NT'), points: '771,285 793,283 793,320 771,320', labelX: 782, labelY: 301 },
    { name: 'SA', fullName: 'South Australia', value: v('SA'), points: '771,320 793,320 805,349 770,347', labelX: 785, labelY: 334 },
    { name: 'QLD', fullName: 'Queensland', value: v('QLD'), points: '793,283 829,289 836,320 807,325 793,320', labelX: 815, labelY: 302 },
    { name: 'NSW', fullName: 'New South Wales', value: v('NSW'), points: '807,325 836,320 833,343 809,349', labelX: 820, labelY: 333 },
    { name: 'VIC', fullName: 'Victoria', value: v('VIC'), points: '805,349 833,343 826,356 808,356', labelX: 816, labelY: 351 },
    { name: 'ACT', fullName: 'Australian Capital Territory', value: v('ACT'), points: '824,337 829,337 829,342 824,342', labelX: 843, labelY: 337, leaderFromX: 827, leaderFromY: 340 },
    { name: 'TAS', fullName: 'Tasmania', value: v('TAS'), points: '816,366 826,367 824,376 817,375', labelX: 821, labelY: 369 },
  ]
})

const hoveredAustraliaRegionShape = computed(() =>
  hoveredAustraliaRegion.value
    ? (australiaRegionShapes.value.find((region) => region.name === hoveredAustraliaRegion.value) ?? null)
    : null,
)

const visibleSmallMapValuePoints = computed(() =>
  hoveredAustraliaRegion.value
    ? smallMapValuePoints.value.filter((point) => point.name !== 'Australia')
    : smallMapValuePoints.value,
)

const worldRegionMeta = [
  { code: 'NA', name: 'North America', x: 200, y: 145 },
  { code: 'SA', name: 'South America', x: 300, y: 300 },
  { code: 'EU', name: 'Europe', x: 488, y: 112 },
  { code: 'AF', name: 'Africa', x: 500, y: 244 },
  { code: 'AS', name: 'Asia', x: 675, y: 158 },
  { code: 'OC', name: 'Oceania', x: 788, y: 330 },
]

const countryToWorldRegion: Record<string, string> = {
  China: 'Asia',
  India: 'Asia',
  Japan: 'Asia',
  Singapore: 'Asia',
  Malaysia: 'Asia',
  Indonesia: 'Asia',

  'United Kingdom': 'Europe',
  Germany: 'Europe',
  France: 'Europe',

  'United States': 'North America',
  Canada: 'North America',

  Brazil: 'South America',

  'South Africa': 'Africa',

  'New Zealand': 'Oceania',
}

const australianStateNames = new Set(['NSW', 'VIC', 'QLD', 'WA', 'SA', 'ACT', 'TAS', 'NT'])

const regionSummaryCards = computed(() => {
  const totals = new Map(worldRegionMeta.map((item) => [item.name, 0]))

  for (const item of domesticLocations.value) {
    if (australianStateNames.has(item.name)) {
      totals.set('Oceania', (totals.get('Oceania') ?? 0) + item.value)
    }
  }

  for (const item of internationalLocations.value) {
    const regionName = countryToWorldRegion[item.name]
    if (regionName) {
      totals.set(regionName, (totals.get(regionName) ?? 0) + item.value)
    }
  }

  const listedInternationalTotal = data.value.regions.find((item) => item.name === 'International')?.value
  const calculatedInternationalTotal = internationalLocations.value.reduce((sum, item) => sum + item.value, 0)

  return [
    { code: 'INTL', name: 'International', value: listedInternationalTotal ?? calculatedInternationalTotal },
    ...worldRegionMeta.map((item) => ({
      code: item.code,
      name: item.name,
      value: totals.get(item.name) ?? 0,
    })),
  ]
})

const largeMapSummaryPoints = computed(() =>
  worldRegionMeta.map((item) => {
    const summary = regionSummaryCards.value.find((card) => card.name === item.name)
    return {
      name: item.name,
      short: item.code,
      value: summary?.value ?? 0,
      lon: 0,
      lat: 0,
      x: item.x,
      y: item.y,
    }
  }),
)

const smallMapValuePoints = computed(() => {
  const anchorByName = new Map(
    countryHoverAnchors.map((anchor) => [anchor.name, anchor]),
  )

  anchorByName.set('Australia', {
    name: 'Australia',
    lon: 134.5,
    lat: -25.5,
    x: ((134.5 + 180) / 360) * 900,
    y: ((90 - (-25.5)) / 150) * 430,
  })

  return countryRankedLocations.value
    .filter((item) => item.value > 0)
    .map((item) => {
      const anchor = anchorByName.get(item.name)
      if (!anchor) return null

      return {
        name: item.name,
        value: item.value,
        x: ((anchor.lon + 180) / 360) * 900,
        y: ((90 - anchor.lat) / 150) * 430,
      }
    })
    .filter((point): point is { name: string; value: number; x: number; y: number } => point !== null)
})

const maxSmallMapRankedLocation = computed(() =>
  Math.max(...smallMapRankedLocations.value.map((item) => item.value), 1),
)

function axisTicks(maxValue: number, steps = 4) {
  const safeMax = Math.max(maxValue, 1)
  const rawStep = safeMax / steps
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep || 1)))
  const normalized = rawStep / magnitude
  const nice = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10
  const step = nice * magnitude
  const top = Math.ceil(safeMax / step) * step
  return Array.from({ length: steps + 1 }, (_, index) => Math.round(top - index * (top / steps)))
}

function percentage(value: number, total: number) {
  if (!total) return 0
  return Number(((value / total) * 100).toFixed(1))
}

function barWidth(value: number, max: number) {
  return Math.max((value / max) * 100, 4)
}

const maxMapValue = computed(() =>
  Math.max(...countryRankedLocations.value.map((item) => item.value), 1),
)

function mapColor(value: number) {
  if (value <= 0) return '#FFFFFF'

  const ratio = value / maxMapValue.value
  if (ratio < 0.2) return '#BAD7B8'
  if (ratio < 0.5) return '#5EA99E'
  if (ratio < 0.75) return '#39687B'
  return '#017151'
}

function trendX(index: number, count: number) {
  const { plotLeft, plotRight } = registrationChart.value
  // Inset the first and last months so their dots and labels clear the axis.
  const left = plotLeft + 14
  const right = plotRight - 14
  if (count <= 1) return (left + right) / 2
  return left + index * ((right - left) / (count - 1))
}

function registrationY(value: number) {
  const { baseline, plotTop } = registrationChart.value
  return baseline - (value / registrationAxisMax.value) * (baseline - plotTop)
}

function trendDots(values: number[]) {
  return values.map((value, index) => ({
    index,
    value,
    x: trendX(index, values.length),
    y: registrationY(value),
  }))
}

function trendPoints(values: number[]) {
  return values
    .map((value, index) => `${trendX(index, values.length)},${registrationY(value)}`)
    .join(' ')
}

const roleTitle = (role: string | null) => {
  const value = (role ?? '').toLowerCase()
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : ''
}

function usersSummary() {
  const current = data.value
  const year = selectedYear.value
  const rows: SummaryRow[] = [
    figure('Users', 'Total users', current.totalUsers, 'users'),
    figure('Users', 'Students', current.students, 'users'),
    figure('Users', 'Mentors', current.mentors, 'users'),
    figure('Users', 'Supervisors', current.supervisors, 'users'),
    ...([
      ['Total users', current.totalGrowth],
      ['Students', current.studentGrowth],
      ['Mentors', current.mentorGrowth],
      ['Supervisors', current.supervisorGrowth],
    ] as const)
      .filter(([, change]) => change !== null)
      .map(([label, change]) => figure('Change vs previous year', label, change, '%', `Compared with ${year - 1}`)),
    ...loginRates.value.map((rate) => figure('Logged in at least once', rate.label, rate.value, '%')),
    ...activityStatusByRole.value.flatMap((row) => [
      figure(`Activity status (${row.role}s)`, 'Active', row.active, 'users', `Logged in within the last ${ACTIVE_WINDOW_DAYS} days`),
      figure(`Activity status (${row.role}s)`, 'Inactive', row.inactive, 'users'),
      figure(`Activity status (${row.role}s)`, 'Never logged in', row.never, 'users'),
    ]),
    ...lastLoginRoles.flatMap((role) =>
      lastLoginStacks.value.map((bucket) => figure(`Last login (${role.label}s)`, bucket.label, bucket[role.key], 'users')),
    ),
    ...(['students', 'mentors', 'supervisors'] as const).flatMap((role) =>
      visibleRegistrationMonths.value.map((_, month) => figure(
        `Registrations (${roleTitle(role.slice(0, -1))}s)`,
        `${year}-${String(month + 1).padStart(2, '0')}`,
        visibleRegistrationSeries.value[role][month] ?? 0,
        'users',
      )),
    ),
    ...sortedInterests.value.flatMap((interest) => [
      figure('Areas of interest (Students)', interest.name, interest.students, 'users'),
      figure('Areas of interest (Mentors)', interest.name, interest.mentors, 'users'),
    ]),
    ...current.regions.map((region) => figure('Users by region', region.name, region.value, 'users')),
    ...current.dailyActivity.labels.map((label, index) =>
      figure('Daily activity', label, current.dailyActivity.total[index] ?? 0, 'users'),
    ),
  ]
  return {
    fileName: exportFileName('users', 'summary', String(year)),
    csv: summaryCsv({
      page: 'Users',
      covers: `Current participants; registrations for ${year}`,
      dataAsOf: analyticsAsOf.value,
      unavailable: sourceLabels(unavailableSources.value),
    }, rows),
  }
}

function usersDetails() {
  const asOfDay = analyticsAsOf.value || isoDay(new Date())
  const asOf = new Date(`${asOfDay}T00:00:00Z`)
  const roleOrder = ['student', 'mentor', 'supervisor']
  const rows = [...participants.value]
    .sort((a, b) =>
      roleOrder.indexOf((a.role ?? '').toLowerCase()) - roleOrder.indexOf((b.role ?? '').toLowerCase())
      || `${a.lastName} ${a.firstName}`.localeCompare(`${b.lastName} ${b.firstName}`),
    )
    .map((user) => {
      const days = daysSince(user.lastLogin, asOf)
      return [
        user.id,
        `${user.firstName} ${user.lastName}`.trim(),
        user.email,
        roleTitle(user.role),
        accountStatusLabel(user.accountStatus, user.isActive),
        activityStatusLabel(days),
        isoUtc(user.lastLogin),
        days,
        isoUtc(user.createdAt ?? user.invitedAt ?? user.activatedAt),
        user.groupName,
        user.schoolName,
        user.country?.countryName,
        user.state?.stateName,
        user.interests.join('; '),
      ]
    })
  return {
    fileName: exportFileName('users', 'details', asOfDay),
    csv: detailsCsv([
      'User ID', 'Name', 'Email', 'Role', 'Account Status', `Activity Status (${ACTIVE_WINDOW_DAYS} days)`,
      'Last Login (UTC)', 'Days Since Last Login', 'Registered (UTC)', 'Group', 'School', 'Country', 'State', 'Interests',
    ], rows),
  }
}

function exportCsv(kind: ExportKind) {
  exportError.value = runExport(kind === 'summary' ? usersSummary : usersDetails)
}
</script>

<style src="@/assets/analytics-theme.css">
/* Fixed column widths for expanded Last Login table */
.full-last-login-card .user-login-table {
  width: 100%;
  table-layout: fixed;
}

.full-last-login-card .user-login-table .login-col-user {
  width: 26%;
}

.full-last-login-card .user-login-table .login-col-role {
  width: 18%;
}

.full-last-login-card .user-login-table .login-col-last-login {
  width: 28%;
}

.full-last-login-card .user-login-table .login-col-days {
  width: 28%;
}

.full-last-login-card .user-login-table th,
.full-last-login-card .user-login-table td {
  box-sizing: border-box;
}

.full-last-login-card .user-login-table td {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Numeric labels for the daily-activity line chart */
.daily-activity-value-label {
  font-size: 10px;
  font-weight: 700;
  paint-order: stroke;
  stroke: #ffffff;
  stroke-width: 3px;
  stroke-linejoin: round;
  pointer-events: none;
}

.daily-activity-value-label {
  fill: #174243;
  font-size: 11px;
}

.trend-chart svg,
.activity-chart-main svg {
  overflow: visible;
}

/* Sort control for Top Areas of Interest */
.interest-heading-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 48px;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.interest-heading-row h2 {
  margin: 0;
  min-width: 0;
}

.interest-sort-button {
  display: inline-grid;
  width: 48px;
  height: 48px;
  place-items: center;
  justify-self: end;
  padding: 0;
  border: 1px solid #BAD7B8;
  border-radius: 12px;
  background: #FFFFFF;
  color: #017151;
  font-size: 17px;
  cursor: pointer;
}

.interest-sort-button:hover {
  background: #f3f8f5;
}

</style>

<style scoped>
.users-analytics-page {
  padding: 28px 32px 40px;
  min-height: 100%;
  background: #f7faf9;
  color: #153f3c;
}

.page-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: 24px;
  margin-bottom: 22px;
}

.heading-copy {
  min-width: 0;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 18px;
  color: #59706e;
  font-size: 14px;
}

.breadcrumb a {
  color: #59706e;
  text-decoration: none;
}

.breadcrumb a:hover {
  color: #08765d;
  text-decoration: underline;
}

.breadcrumb-separator {
  color: #9aaaa7;
}

.title-line {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.title-line h1 {
  margin: 0;
}

.page-heading h1 {
  margin: 0;
  color: #163f3c;
  font-size: 36px;
  line-height: 1.15;
  font-weight: 800;
}

.page-heading p {
  margin: 8px 0 0;
  color: #617572;
  font-size: 16px;
}

.page-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  align-self: start;
  margin: 0;
}

.year-control,
.export-button {
  height: 46px;
  border-radius: 12px;
  background: #ffffff;
  font-size: 14px;
  font-weight: 700;
}

.year-control {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  width: 120px;
  padding: 0 13px;
  border: 1px solid #d7e3e0;
  color: #174844;
}

.year-control select {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.export-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 142px;
  padding: 0 16px;
  border: 1px solid #9fd8c7;
  color: #017151;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease;
}

.export-button:hover {
  background: #ecf8f4;
  border-color: #74c9b3;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.kpi-card,
.analytics-card {
  border: 1px solid #e0e9e7;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 3px 12px rgba(20, 64, 60, 0.04);
}

.kpi-grid .kpi-card {
  display: flex;
  align-items: center !important;
  gap: 18px;
  min-height: 0;
  padding: 16px 20px;
}

.kpi-icon {
  display: grid;
  flex: 0 0 58px;
  width: 58px;
  height: 58px;
  place-items: center;
  border-radius: 13px;
  font-size: 24px;
}

.kpi-grid .kpi-card > .kpi-icon {
  align-self: center !important;
}

.kpi-copy {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  justify-content: center;
}

.kpi-icon.blue { color: #39687B; background: color-mix(in srgb, #39687B 14%, white); }

.kpi-icon.red { color: #017151; background: color-mix(in srgb, #BAD7B8 55%, white); }

.kpi-icon.purple { color: #5EA99E; background: color-mix(in srgb, #5EA99E 14%, white); }

.kpi-grid .kpi-card .kpi-copy > .kpi-label {
  display: block;
  min-height: 0 !important;
  margin: 0 0 5px !important;
  color: #4d6461;
  font-size: 14px;
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.kpi-value-row strong {
  color: #103c38;
  font-size: 32px;
  line-height: 1;
}

.positive {
  color: #0ba969;
  font-size: 13px;
  font-weight: 800;
}

.metric-unavailable {
  color: #667873;
  font-size: 11px;
  font-weight: 700;
}

.kpi-grid .kpi-card .kpi-copy > small {
  display: block;
  min-height: 0 !important;
  margin: 5px 0 0 !important;
  color: #81918f;
  line-height: 1.25;
}

.analytics-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
  align-items: stretch;
}

.analytics-card {
  height: 330px;
  min-width: 0;
  padding: 20px;
  overflow: hidden;
}

.analytics-card h2 {
  margin: 0 0 16px;
  color: #163f3c;
  font-size: 18px;
  line-height: 1.2;
}

.role-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  height: 245px;
}

.donut {
  display: grid;
  flex: 0 0 158px;
  width: 158px;
  height: 158px;
  place-items: center;
  border-radius: 50%;
}

.donut-centre {
  display: grid;
  width: 94px;
  height: 94px;
  place-items: center;
  align-content: center;
  border-radius: 50%;
  background: white;
  text-align: center;
}

.donut-centre strong {
  font-size: 26px;
}

.donut-centre span {
  margin-top: 2px;
  color: #657774;
  font-size: 11px;
}

.legend-list {
  min-width: 175px;
}

.legend-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin: 14px 0;
  font-size: 12px;
}

.legend-row span {
  display: flex;
  align-items: center;
  gap: 7px;
}

.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.dot.student { background: #39687B; }
.dot.mentor { background: #017151; }
.dot.supervisor { background: #5EA99E; }

.login-rate-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  align-items: center;
  height: 238px;
}

.login-rate-item {
  min-width: 0;
  text-align: center;
}

.login-rate-item > span {
  display: block;
  margin-bottom: 10px;
  color: #294f4b;
  font-size: 14px;
  font-weight: 700;
}

.rate-ring {
  display: grid;
  width: 98px;
  height: 98px;
  margin: auto;
  place-items: center;
  border-radius: 50%;
}

.rate-ring-inner {
  position: relative;
  z-index: 2;
  display: grid;
  width: 68px;
  height: 68px;
  place-items: center;
  border-radius: 50%;
  background: white;
  color: #173f3c;
  font-size: 21px;
  font-weight: 800;
}

.login-rate-item small {
  display: block;
  margin-top: 9px;
  color: #7a8b88;
  font-size: 10px;
}

.vertical-bars {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  height: 238px;
  padding-top: 4px;
}

.vertical-bar-item {
  display: grid;
  grid-template-rows: 20px 136px 34px;
  justify-items: center;
  width: 15%;
}

.bar-value {
  color: #315a56;
  font-size: 11px;
  font-weight: 700;
}

.bar-track {
  display: flex;
  align-items: flex-end;
  width: 34px;
  height: 128px;
  border-bottom: 1px solid #dfe7e5;
}

.bar-fill {
  width: 100%;
  min-height: 6px;
  border-radius: 5px 5px 0 0;
  background: #39687B;
}

.bar-label {
  max-width: 58px;
  margin-top: 6px;
  color: #697b79;
  font-size: 9px;
  line-height: 1.2;
  text-align: center;
}

.card-heading-row,
.card-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-heading-row h2,
.card-title-row h2 {
  margin: 0;
}

.year-chip {
  padding: 6px 10px;
  border: 1px solid #dce6e4;
  border-radius: 8px;
  color: #657774;
  font-size: 11px;
}

.trend-chart svg {
  display: block;
  width: 100%;
  height: 178px;
}

.grid-line {
  stroke: #edf1f0;
  stroke-width: 1;
}

.trend-line {
  fill: none;
  stroke-width: 3.2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.trend-line.students { stroke: #39687B; }
.trend-line.mentors { stroke: #017151; }
.trend-line.supervisors { stroke: #5EA99E; }

.month-labels {
  display: grid;
  grid-template-columns: repeat(var(--visible-month-count, 12), 1fr);
  padding: 0;
  color: #748683;
  font-size: 8px;
  text-align: center;
}

.trend-legend {
  display: flex;
  justify-content: center;
  gap: 18px;
  margin-top: 9px;
  color: #59706e;
  font-size: 10px;
}

.trend-legend span {
  display: flex;
  align-items: center;
  gap: 5px;
}

.region-list,
.interest-list {
  display: flex;
  flex-direction: column;
  gap: 11px;
  padding-top: 4px;
}

.horizontal-bar-row {
  display: grid;
  grid-template-columns: 100px minmax(70px, 1fr) 36px;
  align-items: center;
  gap: 10px;
  color: #31514e;
  font-size: 11px;
}

.horizontal-bar-row > span {
  text-align: right;
}

.horizontal-track {
  overflow: hidden;
  height: 12px;
  border-radius: 4px;
  background: #edf1f0;
}

.horizontal-fill {
  height: 100%;
  border-radius: inherit;
}

.blue-fill { background: #39687B; }

.green-fill { background: #5EA99E; }

.expand-button {
  display: inline-grid;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  place-items: center;
  border: 1px solid #d7e3e0;
  border-radius: 9px;
  background: #ffffff;
  color: #174844;
  cursor: pointer;
}

.expand-button:hover {
  border-color: #8bcab9;
  background: #ecf8f4;
}

.second-row {
  transition: grid-template-columns 0.25s ease;
}

.second-row.region-expanded-row {
  grid-template-columns: minmax(150px, 0.46fr) minmax(650px, 2.55fr) minmax(150px, 0.46fr);
  align-items: stretch;
}

.second-row.region-expanded-row .side-card {
  opacity: 0.58;
  transform: scale(0.9);
  transform-origin: center;
  transition:
    transform 0.25s ease,
    opacity 0.25s ease;
}

.second-row.region-expanded-row .analytics-card {
  height: 430px;
}

.region-card {
  transition:
    height 0.25s ease,
    box-shadow 0.25s ease;
}

.region-card--expanded {
  height: 430px;
  overflow: visible;
  box-shadow: 0 14px 36px rgba(17, 67, 60, 0.11);
}

.inline-expanded-region {
  display: grid;
  grid-template-columns: minmax(0, 1.72fr) minmax(230px, 0.78fr);
  gap: 12px;
  height: calc(100% - 48px);
}

.world-map-panel,
.region-ranking {
  border: 1px solid #e0e9e7;
  border-radius: 13px;
  background: #ffffff;
}

.world-map-panel {
  display: flex;
  min-width: 0;
  flex-direction: column;
  padding: 10px 12px 8px;
  overflow: hidden;
}

.world-map-stage {
  position: relative;
  min-height: 0;
  flex: 1;
  overflow: hidden;
  border-radius: 10px;
  background: #FFFFFF;
}

.world-map {
  display: block;
  width: 100%;
  height: 100%;
  min-height: 0;
  cursor: zoom-in;
  background: #FFFFFF;
}

.world-map-zoom-layer {
  transform-box: fill-box;
  transform-origin: center;
}

.world-shape {
  fill: #FFFFFF;
  stroke: #174243;
  stroke-width: 0.75;
  vector-effect: non-scaling-stroke;
}

.map-zoom-controls {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 4;
  display: flex;
  gap: 5px;
}

.map-zoom-controls button {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  padding: 0;
  border: 1px solid #BAD7B8;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
  color: #017151;
  cursor: pointer;
}

.map-zoom-controls button:hover:not(:disabled) {
  background: #BAD7B8;
}

.map-zoom-controls button:disabled {
  color: #96A39E;
  cursor: not-allowed;
  opacity: 0.55;
}

.map-count {
  fill: #FFFFFF;
  font-size: 14px;
  font-weight: 800;
  pointer-events: none;
}

.map-count--zero {
  fill: #174243;
}

.map-label {
  fill: #174243;
  font-size: 9px;
  font-weight: 700;
  pointer-events: none;
}

.map-legend {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  margin-top: 2px;
  color: #687b78;
  font-size: 9px;
}

.legend-gradient {
  width: 150px;
  height: 9px;
  border: 1px solid #D7E2DE;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    #FFFFFF 0%,
    #BAD7B8 30%,
    #5EA99E 58%,
    #39687B 80%,
    #017151 100%
  );
}

.region-ranking {
  overflow: auto;
  padding: 12px;
}

.ranking-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.ranking-heading h3 {
  margin: 0;
  color: #163f3c;
  font-size: 14px;
}

.ranking-heading span {
  color: #7c8d8a;
  font-size: 9px;
}

.region-ranking ol {
  display: grid;
  gap: 7px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.region-ranking li {
  display: grid;
  grid-template-columns: 22px minmax(72px, 1fr) minmax(52px, 0.8fr) 30px;
  align-items: center;
  gap: 7px;
}

.rank-number {
  display: grid;
  width: 21px;
  height: 21px;
  place-items: center;
  border-radius: 6px;
  background: #edf7f4;
  color: #08765d;
  font-size: 9px;
  font-weight: 800;
}

.rank-name {
  overflow: hidden;
  color: #36534f;
  font-size: 10px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank-track {
  overflow: hidden;
  height: 7px;
  border-radius: 999px;
  background: #e8efed;
}

.rank-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #5EA99E;
}

.region-ranking strong {
  color: #234a45;
  font-size: 10px;
  text-align: right;
}

.interactive-chart-mark,
.interactive-chart-row,
.interactive-svg-point {
  cursor: pointer;
}

.interactive-chart-mark {
  transition: filter 0.15s ease, opacity 0.15s ease;
}

.interactive-chart-mark:hover {
  filter: brightness(0.95) saturate(1.08);
}

.interactive-chart-row {
  transition: background-color 0.15s ease;
}

.interactive-chart-row:hover {
  background: rgba(236, 248, 244, 0.62);
}

.interactive-svg-point {
  cursor: pointer;
}

.trend-dot {
  stroke: #ffffff;
  stroke-width: 2;
}

.students-dot { fill: #39687B; }
.mentors-dot { fill: #017151; }
.supervisors-dot { fill: #5EA99E; }

.interactive-svg-point circle,
.interactive-svg-point.trend-dot {
  transition: opacity 0.12s ease;
}

.interactive-svg-point:hover circle,
.interactive-svg-point.trend-dot:hover {
  opacity: 0.82;
}

@media (max-width: 1200px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .analytics-grid {
    grid-template-columns: 1fr;
  }

  .analytics-card {
    height: auto;
    min-height: 330px;
  }

  .second-row.region-expanded-row {
    grid-template-columns: 1fr;
  }

  .second-row.region-expanded-row .side-card {
    opacity: 1;
    transform: none;
  }

  .second-row.region-expanded-row .analytics-card,
  .region-card--expanded {
    height: auto;
    min-height: 560px;
  }

  .inline-expanded-region {
    grid-template-columns: 1fr;
    height: auto;
  }

  .world-map {
    min-height: 360px;
  }
}

@media (max-width: 700px) {
  .users-analytics-page {
    padding: 20px 16px;
  }

  .page-heading {
    grid-template-columns: 1fr;
  }

  .page-actions {
    width: 100%;
  }

  .year-control,
  .export-button {
    flex: 1;
    width: auto;
  }

  .kpi-grid {
    grid-template-columns: 1fr;
  }

  .role-content {
    flex-direction: column;
    height: auto;
  }

  .login-rate-grid {
    grid-template-columns: 1fr;
    height: auto;
  }
}

.role-donut-wrap {
  position: relative;
  isolation: isolate;
  width: 180px;
  height: 180px;
  flex: 0 0 180px;
}

.role-donut-svg {
  position: relative;
  z-index: 1;
  display: block;
  width: 100%;
  height: 100%;
  overflow: visible;
}

.role-donut-segment {
  cursor: pointer;
  transition:
    stroke-width 0.16s ease,
    filter 0.16s ease;
  outline: none;
}

.role-donut-segment:hover,
.role-donut-segment:focus,
.role-donut-segment.selected {
  stroke-width: 28;
  filter: brightness(0.98);
}

.role-donut-centre {
  position: absolute;
  inset: 50% auto auto 50%;
  transform: translate(-50%, -50%);
  width: 102px;
  height: 102px;
  pointer-events: none;
  z-index: 2;
}

.role-centre-label {
  max-width: 88px;
  margin-bottom: 2px;
  color: #506965 !important;
  font-size: 11px !important;
  font-weight: 700;
  line-height: 1.15;
  overflow-wrap: anywhere;
}

.interactive-role-row {
  cursor: pointer;
  border-radius: 7px;
  padding: 4px 5px;
  transition: background-color 0.15s ease;
}

.interactive-role-row:hover,
.interactive-role-row.selected {
  background: #f2f7f5;
}

.chart-with-y-axis {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 8px;
  align-items: stretch;
}

.y-axis {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 2px 0 24px;
  color: #7a8984;
  font-size: 10px;
  line-height: 1;
  text-align: right;
}

.y-axis-line {
  border-left: 1px solid #d9e2df;
  padding-left: 8px;
}

.y-axis-title {
  color: #667975;
  font-size: 10px;
  font-weight: 700;
  text-align: center;
}

/* Final BTF series mapping chart marks and legends intentionally match. */
.trend-line.students { stroke: #39687B !important; }
.trend-line.mentors { stroke: #017151 !important; }
.trend-line.supervisors { stroke: #5EA99E !important; }
.students-dot { fill: #39687B !important; }
.mentors-dot { fill: #017151 !important; }
.supervisors-dot { fill: #5EA99E !important; }
.dot.student { background: #39687B !important; }
.dot.mentor { background: #017151 !important; }
.dot.supervisor { background: #5EA99E !important; }

.bar-fill { background: #39687B !important; }
.blue-fill { background: #39687B !important; }
.green-fill { background: #5EA99E !important; }

/* Official BTF palette for user charts */
.rate-ring-inner { color: #174243; }

.trend-line.students { stroke: #39687B !important; }
.trend-line.mentors { stroke: #017151 !important; }
.trend-line.supervisors { stroke: #5EA99E !important; }

.students-dot { fill: #39687B !important; }
.mentors-dot { fill: #017151 !important; }
.supervisors-dot { fill: #5EA99E !important; }

.dot.student { background: #39687B !important; }
.dot.mentor { background: #017151 !important; }
.dot.supervisor { background: #5EA99E !important; }

/* Single-series charts use different official tertiary colours. */
.bar-fill { background: #39687B !important; }
.blue-fill { background: #39687B !important; }
.green-fill { background: #5EA99E !important; }

.daily-activity-row { grid-template-columns: 1fr; }
.daily-activity-card { min-height: 310px; }
.card-heading-row { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:8px; }
.card-heading-row p { margin:4px 0 0; color:#667873; font-size:13px; }
.activity-chart-with-axis { display:grid; grid-template-columns:42px minmax(0,1fr); gap:8px; align-items:stretch; }
.activity-y-axis { display:flex; height:220px; flex-direction:column; justify-content:space-between; padding:11px 0 8px; color:#697875; font-size:11px; text-align:right; }
.activity-chart-main { min-width:0; }
.activity-chart-main svg { display:block; width:100%; height:220px; overflow:visible; }
.activity-grid-line { stroke:#dfe9e5; stroke-width:1; }
.daily-activity-line { fill:none; stroke:#017151; stroke-width:3; stroke-linecap:round; stroke-linejoin:round; }
.daily-activity-dot { fill:#017151; stroke:#fff; stroke-width:2; cursor:pointer; }
.activity-x-labels { display:grid; grid-template-columns:repeat(10,minmax(0,1fr)); margin-top:-2px; color:#697875; font-size:10px; text-align:center; }
.activity-axis-title { margin-top:8px; color:#667873; font-size:11px; text-align:center; }

.user-login-table-card { margin-bottom:18px; }
.user-login-table-wrap { margin-top:12px; overflow:auto; border:1px solid #e0e8e5; border-radius:12px; }
.user-login-table { width:100%; border-collapse:collapse; font-size:12px; }
.user-login-table th { padding:11px 12px; background:#f0f4f2; color:#174243; text-align:left; }
.user-login-table td { padding:11px 12px; border-top:1px solid #e4ebe8; color:#536762; }
.user-login-table tbody tr:hover td { background:rgba(186,215,184,.35); }
.login-status-pill { display:inline-flex; min-width:54px; min-height:24px; align-items:center; justify-content:center; padding:0 8px; border-radius:999px; font-size:10px; font-weight:700; }
.login-status-pill.recent { background:rgba(186,215,184,.55); color:#017151; }
.login-status-pill.inactive { background:rgba(241,229,166,.7); color:#174243; }
.login-status-pill.never { background:rgba(94,169,158,.15); color:#174243; }

/* Activity + last-login layout: one block + two blocks */
.activity-login-row {
  grid-template-columns: minmax(300px, 1fr) minmax(0, 2fr);
  align-items: stretch;
  gap: 18px;
  margin-bottom: 18px;
}

.activity-login-row .daily-activity-card,
.activity-login-row .user-login-table-card {
  height: 330px;
  min-height: 330px;
  margin-bottom: 0;
}

.activity-login-row .user-login-table-card {
  overflow: hidden;
}

.user-login-table-wrap {
  max-height: 245px;
  overflow-y: auto;
  overflow-x: hidden;
}

/* Use a soft Air Force Blue hover instead of dark green */
.user-login-table tbody tr:hover td {
  background: rgba(57, 104, 123, 0.08);
}

/* Keep the original three cards in one row when the map is opened */
.second-row.region-expanded-row {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-items: stretch;
}

.second-row.region-expanded-row .side-card,
.second-row.region-expanded-row .analytics-card {
  opacity: 1;
  transform: none;
  height: auto;
}

/* Full-width map below Registration / Region / Areas of Interest */
.full-region-map-card {
  width: 100%;
  min-height: 560px;
  margin-bottom: 18px;
  padding: 20px;
  overflow: visible;
}

.full-region-map-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.full-region-map-heading h2 {
  margin: 0;
}

.full-region-map-heading p {
  margin: 5px 0 0;
  color: #667873;
  font-size: 13px;
}

.close-map-button {
  display: inline-flex;
  height: 38px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 12px;
  border: 1px solid #9fd8c7;
  border-radius: 10px;
  background: #ffffff;
  color: #017151;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.close-map-button:hover {
  background: #ecf8f4;
}

.full-map-layout {
  display: grid;
  grid-template-columns: minmax(0, 2.1fr) minmax(360px, 0.9fr);
  gap: 16px;
  min-height: 470px;
}

.full-map-layout .world-map-panel {
  min-height: 470px;
}

.full-map-layout .world-map-stage {
  min-height: 420px;
}

.full-map-layout .world-map {
  min-height: 420px;
}

.region-summary-panel {
  display: flex;
  min-width: 0;
  flex-direction: column;
  padding: 14px;
  border: 1px solid #e0e9e7;
  border-radius: 13px;
  background: #ffffff;
}

.region-summary-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.region-summary-heading h3 {
  margin: 0;
  color: #163f3c;
  font-size: 15px;
}

.region-summary-heading span {
  color: #6c7c78;
  font-size: 11px;
}

.region-summary-grid {
  display: grid;
  flex: 1;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.region-summary-card {
  display: flex;
  min-height: 150px;
  flex-direction: column;
  justify-content: space-between;
  padding: 14px;
  border: 1px solid #dfe8e5;
  border-radius: 10px;
  background: #ffffff;
}

.region-summary-card > strong {
  color: #017151;
  font-size: 14px;
}

.region-summary-value {
  color: #174243;
  font-size: 30px;
  line-height: 1;
  font-weight: 700;
}

.region-summary-card > span {
  color: #667873;
  font-size: 11px;
}

/* Ensure the page itself never traps vertical scrolling */
.users-analytics-page {
  min-height: 100%;
  overflow-x: hidden;
  overflow-y: visible;
}

@media (max-width: 1200px) {
  .activity-login-row {
    grid-template-columns: 1fr;
  }

  .activity-login-row .daily-activity-card,
  .activity-login-row .user-login-table-card {
    height: auto;
    min-height: 330px;
  }

  .full-map-layout {
    grid-template-columns: 1fr;
  }

  .region-summary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 700px) {
  .region-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

/* Final requested layout refinements */
.activity-login-row {
  display: grid !important;
  grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
  gap: 18px !important;
}

.activity-login-row .daily-activity-card {
  grid-column: span 1 !important;
}

.activity-login-row .user-login-table-card {
  grid-column: span 2 !important;
}

/* Hover colour: same light green used across analytics tables */
.user-login-table tbody tr:hover,
.user-login-table tbody tr:hover td {
  background: rgba(186, 215, 184, 0.35) !important;
}

/* Restore original region focus interaction:
   side cards shrink/fade, centre region card expands. */
.second-row.region-expanded-row {
  grid-template-columns: minmax(150px, 0.46fr) minmax(650px, 2.55fr) minmax(150px, 0.46fr) !important;
  align-items: stretch;
}

.second-row.region-expanded-row .side-card {
  opacity: 0.58 !important;
  transform: scale(0.9) !important;
  transform-origin: center;
  transition: transform 0.25s ease, opacity 0.25s ease;
}

.second-row.region-expanded-row .analytics-card {
  height: 430px;
}

.region-card--expanded {
  height: 430px !important;
  overflow: visible !important;
  box-shadow: 0 14px 36px rgba(17, 67, 60, 0.11);
}

.login-table-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 12px;
}

.login-table-heading h2 {
  margin: 0;
}

.login-top-filters {
  display: flex;
  align-items: center;
  gap: 8px;
}

.login-top-filters input,
.login-top-filters select,
.column-filter-heading select {
  height: 34px;
  border: 1px solid #bad7b8;
  border-radius: 9px;
  background: #ffffff;
  color: #174243;
  font-size: 11px;
}

.login-top-filters input {
  width: 165px;
  padding: 0 10px;
}

.login-top-filters select {
  width: 118px;
  padding: 0 8px;
}

.column-filter-heading {
  display: flex;
  align-items: center;
  gap: 8px;
}

.column-filter-heading select {
  width: 112px;
  padding: 0 7px;
  font-weight: 500;
}

.empty-table-state {
  padding: 24px !important;
  color: #75837f !important;
  text-align: center;
  font-weight: 500;
}

@media (max-width: 900px) {
  .login-table-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .login-top-filters {
    width: 100%;
  }

  .login-top-filters input,
  .login-top-filters select {
    width: 100%;
  }
}

/* Last Login controls aligned in the top-right toolbar */
.login-top-filters {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.date-filter-control {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.date-filter-control i {
  position: absolute;
  left: 10px;
  z-index: 1;
  color: #017151;
  font-size: 11px;
  pointer-events: none;
}

.date-filter-control select {
  width: 132px !important;
  padding-left: 28px !important;
}

.login-sort-header {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0;
  border: 0;
  background: transparent;
  color: #174243;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.login-sort-header i {
  color: #5EA99E;
  font-size: 11px;
}

.login-sort-header:hover {
  color: #017151;
}

.days-since-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.days-since-number {
  min-width: 24px;
  color: #174243;
  font-size: 15px;
  font-weight: 800;
  text-align: right;
}

.days-unit {
  color: #667a76;
  font-size: 13px;
}

/* Date query: choose a single day or a custom date range */
.date-query-control {
  display: flex;
  align-items: center;
  gap: 7px;
}

.date-mode-control,
.date-input-control {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.date-mode-control i {
  position: absolute;
  left: 10px;
  z-index: 1;
  color: #017151;
  font-size: 11px;
  pointer-events: none;
}

.date-mode-control select {
  width: 128px !important;
  padding-left: 28px !important;
}

.date-input-control input {
  width: 132px !important;
  height: 34px;
  padding: 0 8px;
  border: 1px solid #bad7b8;
  border-radius: 9px;
  background: #ffffff;
  color: #174243;
  font-size: 11px;
}

.date-range-inputs {
  display: flex;
  align-items: center;
  gap: 5px;
}

.date-range-separator {
  color: #7b8b87;
  font-size: 12px;
}

@media (max-width: 1250px) {
  .login-top-filters {
    max-width: 720px;
  }
}

/* Large region/interest datasets stay inside fixed-height cards */
.compact-region-list,
.interest-list {
  max-height: 220px;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 5px;
}

.compact-region-list .horizontal-bar-row,
.interest-list .horizontal-bar-row {
  flex: 0 0 auto;
}

/* ===== Revised Users page layout ===== */

/* Registration Trend + Areas of Interest move up */
.upper-user-row {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin-bottom: 18px;
}

.upper-user-row > .analytics-card {
  min-height: 330px;
}

/* Daily Activity + Last Login + Region share the next row */
.expandable-user-row {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.35fr) minmax(0, 0.9fr);
  gap: 18px;
  align-items: stretch;
  margin-bottom: 18px;
  transition: grid-template-columns 0.25s ease;
}

.expandable-user-row > * {
  min-width: 0;
}

.expandable-side-card > .analytics-card,
.user-login-compact-card {
  height: 330px;
  min-height: 330px;
  margin: 0;
}

/* Same focus interaction as Region: selected card grows, neighbours shrink */
.expandable-user-row.last-login-expanded-row {
  grid-template-columns: minmax(145px, 0.48fr) minmax(620px, 2.2fr) minmax(145px, 0.48fr);
}

.expandable-user-row.region-expanded-row {
  grid-template-columns: minmax(145px, 0.48fr) minmax(145px, 0.48fr) minmax(620px, 2.2fr);
}

.expandable-user-row.last-login-expanded-row .daily-side-card,
.expandable-user-row.last-login-expanded-row .region-side-card,
.expandable-user-row.region-expanded-row .daily-side-card,
.expandable-user-row.region-expanded-row .user-login-compact-card {
  opacity: 0.58;
  transform: scale(0.92);
  transform-origin: center;
}

.expandable-user-row .daily-side-card,
.expandable-user-row .region-side-card,
.expandable-user-row .user-login-compact-card {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

/* Compact Last Login card */
.user-login-compact-card {
  overflow: hidden;
  padding: 18px;
}

.compact-login-table-wrap {
  max-height: 250px;
  margin-top: 12px;
  overflow: hidden;
  border: 1px solid #e0e8e5;
  border-radius: 12px;
}

.compact-login-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 10px;
}

.compact-login-table th {
  padding: 9px 8px;
  background: #f0f4f2;
  color: #174243;
  text-align: left;
  font-weight: 700;
}

.compact-login-table td {
  padding: 9px 8px;
  border-top: 1px solid #e4ebe8;
  color: #536762;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-login-table th:nth-child(1),
.compact-login-table td:nth-child(1) { width: 28%; }

.compact-login-table th:nth-child(2),
.compact-login-table td:nth-child(2) { width: 18%; }

.compact-login-table th:nth-child(3),
.compact-login-table td:nth-child(3) { width: 34%; }

.compact-login-table th:nth-child(4),
.compact-login-table td:nth-child(4) { width: 20%; }

.compact-login-table tbody tr:hover td {
  background: rgba(186, 215, 184, 0.35);
}

/* Full Last Login panel appears below, like the full Region map */
.full-last-login-card {
  width: 100%;
  margin-bottom: 18px;
  padding: 20px;
  overflow: hidden;
}

.full-last-login-card .login-table-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.expanded-login-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  min-width: 0;
}

.full-last-login-card .login-top-filters {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.close-login-button {
  display: inline-flex;
  height: 34px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 10px;
  border: 1px solid #9fd8c7;
  border-radius: 9px;
  background: #ffffff;
  color: #017151;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}

.close-login-button:hover {
  background: #ecf8f4;
}

.expanded-login-scroll {
  max-height: 390px !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
}

/* Keep the Region expanded view usable in its new right-hand position */
.region-side-card > .region-card {
  width: 100%;
}

.expandable-user-row.region-expanded-row .region-side-card > .region-card {
  height: 430px;
  min-height: 430px;
}

/* The full map below stays full-width */
.full-region-map-card {
  margin-top: 0;
}

@media (max-width: 1250px) {
  .expandable-user-row,
  .expandable-user-row.last-login-expanded-row,
  .expandable-user-row.region-expanded-row {
    grid-template-columns: 1fr;
  }

  .expandable-user-row.last-login-expanded-row .daily-side-card,
  .expandable-user-row.last-login-expanded-row .region-side-card,
  .expandable-user-row.region-expanded-row .daily-side-card,
  .expandable-user-row.region-expanded-row .user-login-compact-card {
    opacity: 1;
    transform: none;
  }

  .expandable-side-card > .analytics-card,
  .user-login-compact-card {
    height: auto;
    min-height: 330px;
  }

  .upper-user-row {
    grid-template-columns: 1fr;
  }

  .full-last-login-card .login-table-heading,
  .expanded-login-actions {
    align-items: flex-start;
    flex-direction: column;
  }
}

/* ===== Corrected requested placement =====
   First row: Registration | Areas of Interest | Daily Activity
   Second row: Last Login | User Distribution by Region
*/
.upper-user-row {
  display: grid !important;
  grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
  gap: 18px !important;
  align-items: stretch;
  margin-bottom: 18px;
}

.upper-user-row > .analytics-card {
  height: 330px !important;
  min-height: 330px !important;
  margin: 0;
}

/* Daily Activity now belongs to the first row */
.upper-user-row .daily-activity-card {
  height: 330px !important;
  min-height: 330px !important;
}

/* Second row contains only the two expandable cards */
.expandable-user-row {
  display: grid !important;
  grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  gap: 18px !important;
  align-items: stretch;
  margin-bottom: 18px;
  transition: grid-template-columns 0.25s ease;
}

.expandable-user-row > * {
  min-width: 0;
}

.expandable-user-row .user-login-compact-card,
.expandable-user-row .region-side-card > .region-card {
  width: 100%;
  height: 330px;
  min-height: 330px;
  margin: 0;
}

/* Expand Last Login: it grows and Region shrinks */
.expandable-user-row.last-login-expanded-row {
  grid-template-columns: minmax(620px, 2.25fr) minmax(180px, 0.65fr) !important;
}

.expandable-user-row.last-login-expanded-row .region-side-card {
  opacity: 0.58;
  transform: scale(0.92);
  transform-origin: center;
}

/* Expand Region: it grows and Last Login shrinks */
.expandable-user-row.region-expanded-row {
  grid-template-columns: minmax(180px, 0.65fr) minmax(620px, 2.25fr) !important;
}

.expandable-user-row.region-expanded-row .user-login-compact-card {
  opacity: 0.58;
  transform: scale(0.92);
  transform-origin: center;
}

.expandable-user-row .region-side-card,
.expandable-user-row .user-login-compact-card {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.expandable-user-row.region-expanded-row .region-side-card > .region-card {
  height: 430px !important;
  min-height: 430px !important;
}

@media (max-width: 1200px) {
  .upper-user-row {
    grid-template-columns: 1fr !important;
  }

  .expandable-user-row,
  .expandable-user-row.last-login-expanded-row,
  .expandable-user-row.region-expanded-row {
    grid-template-columns: 1fr !important;
  }

  .expandable-user-row.last-login-expanded-row .region-side-card,
  .expandable-user-row.region-expanded-row .user-login-compact-card {
    opacity: 1;
    transform: none;
  }

  .upper-user-row > .analytics-card,
  .expandable-user-row .user-login-compact-card,
  .expandable-user-row .region-side-card > .region-card {
    height: auto !important;
    min-height: 330px !important;
  }
}

/* Requested final behaviour:
   - Last Login stays static.
   - Region keeps its current expand behaviour.
   - Last Login card is taller so more rows are visible. */
.expandable-user-row {
  grid-template-columns: minmax(0, 1.65fr) minmax(0, 1fr) !important;
}

.expandable-user-row .user-login-compact-card,
.expandable-user-row .region-side-card > .region-card {
  height: 390px !important;
  min-height: 390px !important;
}

.user-login-compact-card {
  padding: 18px !important;
}

.compact-login-table-wrap {
  max-height: 305px !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
}

.compact-login-table thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #f0f4f2;
}

/* Region remains the only card that expands. */
.expandable-user-row.region-expanded-row {
  grid-template-columns: minmax(180px, 0.65fr) minmax(620px, 2.25fr) !important;
}

.expandable-user-row.region-expanded-row .user-login-compact-card {
  opacity: 0.58;
  transform: scale(0.92);
  transform-origin: center;
}

@media (max-width: 1200px) {
  .expandable-user-row,
  .expandable-user-row.region-expanded-row {
    grid-template-columns: 1fr !important;
  }

  .expandable-user-row.region-expanded-row .user-login-compact-card {
    opacity: 1;
    transform: none;
  }

  .expandable-user-row .user-login-compact-card,
  .expandable-user-row .region-side-card > .region-card {
    height: auto !important;
    min-height: 390px !important;
  }
}

/* Last Login expansion only opens the full-width table below.
   The original compact card does NOT resize or shrink neighbours. */
.expandable-user-row {
  grid-template-columns: minmax(0, 1.65fr) minmax(0, 1fr) !important;
}

.user-login-compact-card {
  transform: none !important;
  opacity: 1 !important;
}

/* Full expanded Last Login table */
.full-last-login-card {
  width: 100%;
  min-height: 560px;
  margin-bottom: 18px;
  padding: 20px;
  overflow: hidden;
}

.full-last-login-card .login-table-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.expanded-login-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  min-width: 0;
}

.full-last-login-card .login-top-filters {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.expanded-login-scroll {
  max-height: 455px !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
}

.expanded-login-scroll thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #f0f4f2;
}

.close-login-button {
  display: inline-flex;
  height: 34px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 10px;
  border: 1px solid #9fd8c7;
  border-radius: 9px;
  background: #ffffff;
  color: #017151;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}

.close-login-button:hover {
  background: #ecf8f4;
}

/* Region expansion remains unchanged */
.expandable-user-row.region-expanded-row {
  grid-template-columns: minmax(180px, 0.65fr) minmax(620px, 2.25fr) !important;
}

.expandable-user-row.region-expanded-row .user-login-compact-card {
  opacity: 0.58 !important;
  transform: scale(0.92) !important;
}

@media (max-width: 1200px) {
  .full-last-login-card .login-table-heading,
  .expanded-login-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .full-last-login-card {
    min-height: 520px;
  }

  .expanded-login-scroll {
    max-height: 410px !important;
  }
}

/* Full world-map refinement:
   smaller markers/labels and a larger expanded viewing area. */
.full-region-map-card {
  min-height: 720px !important;
  padding: 22px !important;
}

.full-map-layout {
  grid-template-columns: minmax(0, 2.55fr) minmax(320px, 0.75fr) !important;
  min-height: 610px !important;
  gap: 18px !important;
}

.full-map-layout .world-map-panel {
  min-height: 610px !important;
}

.full-map-layout .world-map-stage,
.full-map-layout .world-map {
  min-height: 555px !important;
}

.expanded-map-count {
  font-weight: 800;
}

.expanded-map-label {
  font-weight: 700;
}

/* Keep outlines visually light after shrinking the circles. */
.full-region-map-card .map-point circle[fill="none"] {
  stroke-width: 1.2;
}

/* Slightly larger map controls on the full map. */
.full-region-map-card .map-zoom-controls button {
  width: 34px;
  height: 34px;
  font-size: 12px;
}

@media (max-width: 1200px) {
  .full-region-map-card {
    min-height: 650px !important;
  }

  .full-map-layout {
    grid-template-columns: 1fr !important;
    min-height: auto !important;
  }

  .full-map-layout .world-map-panel,
  .full-map-layout .world-map-stage,
  .full-map-layout .world-map {
    min-height: 500px !important;
  }
}

/* Fill the normal Last Login / Region cards more efficiently */
.expandable-user-row .user-login-compact-card,
.expandable-user-row .region-side-card > .region-card {
  height: 360px !important;
  min-height: 360px !important;
}

.user-login-compact-card {
  display: flex;
  flex-direction: column;
}

.user-login-compact-card .card-title-row {
  flex: 0 0 auto;
}

.compact-login-table-wrap {
  flex: 1 1 auto;
  max-height: none !important;
  min-height: 0;
  overflow-y: auto !important;
  overflow-x: hidden !important;
}

.region-side-card > .region-card {
  display: flex;
  flex-direction: column;
}

.region-side-card > .region-card .card-title-row {
  flex: 0 0 auto;
}

.region-side-card > .region-card .compact-region-list {
  flex: 1 1 auto;
  max-height: none !important;
  min-height: 0;
  overflow-y: auto !important;
  overflow-x: hidden !important;
}

/* Keep markers readable at high zoom */
.expanded-map-count {
  font-weight: 800;
}

.expanded-map-label {
  font-weight: 700;
}

/* Drag-to-pan interaction for zoomed maps */
.world-map {
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.world-map--dragging {
  cursor: grabbing;
}

.world-map-zoom-layer {
  will-change: transform;
}

/* Inline expanded Region map also behaves like a zoomable detail map. */
.inline-expanded-region .world-map-panel {
  min-width: 0;
}

.inline-expanded-region .world-map-stage {
  min-height: 300px;
}

.inline-expanded-region .world-map {
  min-height: 280px;
}

/* Both inline and full maps use grab/grabbing while panning. */
.world-map {
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.world-map--dragging {
  cursor: grabbing;
}

/* Flatter world-map presentation */
.world-map-zoom-layer .map-point circle {
  vector-effect: non-scaling-stroke;
}

/* Give the map a little more vertical breathing room after flattening. */
.inline-expanded-region .world-map-stage,
.full-region-map-card .world-map-stage {
  overflow: hidden;
}

/* Reference-map styling: grey ocean, white country borders, filled registration areas. */
.world-map-stage {
  background: #cfd3d4 !important;
  border-radius: 10px;
  overflow: hidden;
}

.world-map {
  background: #cfd3d4 !important;
}

.reference-world-base {
  fill: #f8f9f8 !important;
  stroke: none !important;
}

.choropleth-overlay circle {
  opacity: 0.9;
  pointer-events: none;
}

.reference-world-borders {
  stroke: #ffffff !important;
  stroke-width: 1.25 !important;
  vector-effect: non-scaling-stroke;
  pointer-events: none;
}

.reference-map-count {
  fill: #24312f;
  font-weight: 800;
  dominant-baseline: middle;
  pointer-events: none;
}

.reference-map-count--light {
  fill: #ffffff;
}

.map-value-label {
  cursor: pointer;
}

/* Country totals on the compact map: numbers only, no marker circles. */
.small-map-value-layer {
  pointer-events: none;
}

.small-map-value {
  fill: #174243;
  font-size: 11px;
  font-weight: 800;
  text-anchor: middle;
  dominant-baseline: middle;
  paint-order: stroke;
  stroke: rgba(255, 255, 255, 0.92);
  stroke-width: 2.2px;
  stroke-linejoin: round;
  vector-effect: non-scaling-stroke;
}

/* Keep the legend visually close to the supplied reference. */
.map-legend {
  background: #cfd3d4;
  padding: 6px 10px 8px;
  border-radius: 0 0 10px 10px;
}

.legend-gradient {
  border: 1px solid rgba(255,255,255,0.9);
}

/* The flatter projection requested earlier is retained, but softened. */
.world-map-zoom-layer {
  transform-box: fill-box;
}

/* Corrected map behaviour */
.choropleth-overlay {
  display: none !important;
}

.reference-world-base {
  fill: #f8f9f8 !important;
}

.reference-world-borders {
  stroke: #ffffff !important;
  stroke-width: 1.15 !important;
  vector-effect: non-scaling-stroke;
}

.map-point circle {
  vector-effect: non-scaling-stroke;
}

.large-map-summary-value {
  fill: #174243;
  font-size: 16px;
  font-weight: 800;
}

.large-map-summary-label {
  fill: #174243;
  font-size: 11.5px;
  font-weight: 700;
  paint-order: stroke;
  stroke: rgba(255,255,255,.9);
  stroke-width: 1.6px;
  stroke-linejoin: round;
}

.map-summary-point {
  cursor: pointer;
}

/* Australian state/territory summary cards */
.region-summary-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  gap: 10px !important;
}

.region-summary-card {
  min-height: 168px !important;
  padding: 16px 14px !important;
}

.region-summary-name {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-height: 44px;
}

.region-summary-name strong {
  color: #017151;
  font-size: 16px;
  line-height: 1.1;
}

.region-summary-name small {
  color: #617573;
  font-size: 11px;
  line-height: 1.25;
  font-weight: 500;
}

.region-summary-value {
  margin-top: 10px !important;
}

/* World-region summary cards */
.region-summary-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  gap: 10px !important;
}

.region-summary-card {
  min-height: 160px !important;
  padding: 16px 14px !important;
}

.region-summary-name {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-height: 40px;
}

.region-summary-name strong {
  color: #017151;
  font-size: 16px;
  line-height: 1.1;
}

.region-summary-name small {
  color: #617573;
  font-size: 12px;
  line-height: 1.25;
  font-weight: 500;
}

.clear-login-filters-button {
  display: inline-flex;
  height: 34px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 10px;
  border: 1px solid #bad7b8;
  border-radius: 9px;
  background: #ffffff;
  color: #017151;
  font-size: 11px;
  font-weight: 700;
}

line-expanded-region .world-map {
  min-height: 280px;
}

/* Both inline and full maps use grab/grabbing while panning. */
.world-map {
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.world-map--dragging {
  cursor: grabbing;
}

/* Flatter world-map presentation */
.world-map-zoom-layer .map-point circle {
  vector-effect: non-scaling-stroke;
}

/* Give the map a little more vertical breathing room after flattening. */
.inline-expanded-region .world-map-stage,
.full-region-map-card .world-map-stage {
  overflow: hidden;
}

/* Reference-map styling: grey ocean, white country borders, filled registration areas. */
.world-map-stage {
  background: #cfd3d4 !important;
  border-radius: 10px;
  overflow: hidden;
}

.world-map {
  background: #cfd3d4 !important;
}

.reference-world-base {
  fill: #f8f9f8 !important;
  stroke: none !important;
}

.choropleth-overlay circle {
  opacity: 0.9;
  pointer-events: none;
}

.reference-world-borders {
  stroke: #ffffff !important;
  stroke-width: 1.25 !important;
  vector-effect: non-scaling-stroke;
  pointer-events: none;
}

.reference-map-count {
  fill: #24312f;
  font-weight: 800;
  dominant-baseline: middle;
  pointer-events: none;
}

.reference-map-count--light {
  fill: #ffffff;
}

.map-value-label {
  cursor: pointer;
}

/* Country totals on the compact map: numbers only, no marker circles. */
.small-map-value-layer {
  pointer-events: none;
}

.small-map-value {
  fill: #174243;
  font-size: 11px;
  font-weight: 800;
  text-anchor: middle;
  dominant-baseline: middle;
  paint-order: stroke;
  stroke: rgba(255, 255, 255, 0.92);
  stroke-width: 2.2px;
  stroke-linejoin: round;
  vector-effect: non-scaling-stroke;
}

/* Keep the legend visually close to the supplied reference. */
.map-legend {
  background: #cfd3d4;
  padding: 6px 10px 8px;
  border-radius: 0 0 10px 10px;
}

.legend-gradient {
  border: 1px solid rgba(255,255,255,0.9);
}

/* The flatter projection requested earlier is retained, but softened. */
.world-map-zoom-layer {
  transform-box: fill-box;
}

/* Corrected map behaviour */
.choropleth-overlay {
  display: none !important;
}

.reference-world-base {
  fill: #f8f9f8 !important;
}

.reference-world-borders {
  stroke: #ffffff !important;
  stroke-width: 1.15 !important;
  vector-effect: non-scaling-stroke;
}

.map-point circle {
  vector-effect: non-scaling-stroke;
}

.large-map-summary-value {
  fill: #174243;
  font-size: 16px;
  font-weight: 800;
}

.large-map-summary-label {
  fill: #174243;
  font-size: 11.5px;
  font-weight: 700;
  paint-order: stroke;
  stroke: rgba(255,255,255,.9);
  stroke-width: 1.6px;
  stroke-linejoin: round;
}

.map-summary-point {
  cursor: pointer;
}

/* Australian state/territory summary cards */
.region-summary-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  gap: 10px !important;
}

.region-summary-card {
  min-height: 168px !important;
  padding: 16px 14px !important;
}

.region-summary-name {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-height: 44px;
}

.region-summary-name strong {
  color: #017151;
  font-size: 16px;
  line-height: 1.1;
}

.region-summary-name small {
  color: #617573;
  font-size: 11px;
  line-height: 1.25;
  font-weight: 500;
}

.region-summary-value {
  margin-top: 10px !important;
}

/* World-region summary cards */
.region-summary-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  gap: 10px !important;
}

.region-summary-card {
  min-height: 160px !important;
  padding: 16px 14px !important;
}

.region-summary-name {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-height: 40px;
}

.region-summary-name strong {
  color: #017151;
  font-size: 16px;
  line-height: 1.1;
}

.region-summary-name small {
  color: #617573;
  font-size: 12px;
  line-height: 1.25;
  font-weight: 500;
}

.clear-login-filters-button {
  display: inline-flex;
  height: 34px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 10px;
  border: 1px solid #bad7b8;
  border-radius: 9px;
  background: #ffffff;
  color: #017151;
  font-size: 11px;
  font-weight: 700;
}

nline-expanded-region .world-map {
  min-height: 280px;
}

/* Both inline and full maps use grab/grabbing while panning. */
.world-map {
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.world-map--dragging {
  cursor: grabbing;
}

/* Flatter world-map presentation */
.world-map-zoom-layer .map-point circle {
  vector-effect: non-scaling-stroke;
}

/* Give the map a little more vertical breathing room after flattening. */
.inline-expanded-region .world-map-stage,
.full-region-map-card .world-map-stage {
  overflow: hidden;
}

/* Reference-map styling: grey ocean, white country borders, filled registration areas. */
.world-map-stage {
  background: #cfd3d4 !important;
  border-radius: 10px;
  overflow: hidden;
}

.world-map {
  background: #cfd3d4 !important;
}

.reference-world-base {
  fill: #f8f9f8 !important;
  stroke: none !important;
}

.choropleth-overlay circle {
  opacity: 0.9;
  pointer-events: none;
}

.reference-world-borders {
  stroke: #ffffff !important;
  stroke-width: 1.25 !important;
  vector-effect: non-scaling-stroke;
  pointer-events: none;
}

.reference-map-count {
  fill: #24312f;
  font-weight: 800;
  dominant-baseline: middle;
  pointer-events: none;
}

.reference-map-count--light {
  fill: #ffffff;
}

.map-value-label {
  cursor: pointer;
}

/* Country totals on the compact map: numbers only, no marker circles. */
.small-map-value-layer {
  pointer-events: none;
}

.small-map-value {
  fill: #174243;
  font-size: 11px;
  font-weight: 800;
  text-anchor: middle;
  dominant-baseline: middle;
  paint-order: stroke;
  stroke: rgba(255, 255, 255, 0.92);
  stroke-width: 2.2px;
  stroke-linejoin: round;
  vector-effect: non-scaling-stroke;
}

/* Keep the legend visually close to the supplied reference. */
.map-legend {
  background: #cfd3d4;
  padding: 6px 10px 8px;
  border-radius: 0 0 10px 10px;
}

.legend-gradient {
  border: 1px solid rgba(255,255,255,0.9);
}

/* The flatter projection requested earlier is retained, but softened. */
.world-map-zoom-layer {
  transform-box: fill-box;
}

/* Corrected map behaviour */
.choropleth-overlay {
  display: none !important;
}

.reference-world-base {
  fill: #f8f9f8 !important;
}

.reference-world-borders {
  stroke: #ffffff !important;
  stroke-width: 1.15 !important;
  vector-effect: non-scaling-stroke;
}

.map-point circle {
  vector-effect: non-scaling-stroke;
}

.large-map-summary-value {
  fill: #174243;
  font-size: 16px;
  font-weight: 800;
}

.large-map-summary-label {
  fill: #174243;
  font-size: 11.5px;
  font-weight: 700;
  paint-order: stroke;
  stroke: rgba(255,255,255,.9);
  stroke-width: 1.6px;
  stroke-linejoin: round;
}

.map-summary-point {
  cursor: pointer;
}

/* Australian state/territory summary cards */
.region-summary-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  gap: 10px !important;
}

.region-summary-card {
  min-height: 168px !important;
  padding: 16px 14px !important;
}

.region-summary-name {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-height: 44px;
}

.region-summary-name strong {
  color: #017151;
  font-size: 16px;
  line-height: 1.1;
}

.region-summary-name small {
  color: #617573;
  font-size: 11px;
  line-height: 1.25;
  font-weight: 500;
}

.region-summary-value {
  margin-top: 10px !important;
}

/* World-region summary cards */
.region-summary-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  gap: 10px !important;
}

.region-summary-card {
  min-height: 160px !important;
  padding: 16px 14px !important;
}

.region-summary-name {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-height: 40px;
}

.region-summary-name strong {
  color: #017151;
  font-size: 16px;
  line-height: 1.1;
}

.region-summary-name small {
  color: #617573;
  font-size: 12px;
  line-height: 1.25;
  font-weight: 500;
}

.clear-login-filters-button {
  display: inline-flex;
  height: 34px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 10px;
  border: 1px solid #bad7b8;
  border-radius: 9px;
  background: #ffffff;
  color: #017151;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
}

.clear-login-filters-button:hover {
  background: #ecf8f4;
}

.last-login-year-note { display:flex; flex-direction:column; justify-content:center; min-height:220px; }
.last-login-year-note p { margin:8px 0 0; color:#687a76; line-height:1.5; }
.role-pill { display:inline-flex; align-items:center; min-height:26px; padding:0 10px; border-radius:999px; font-size:11px; font-weight:700; }
.role-student { background:rgba(57,104,123,.14); color:#39687B; }
.role-mentor { background:rgba(1,113,81,.13); color:#017151; }
.role-supervisor { background:rgba(94,169,158,.18); color:#357d73; }
.days-filter-control { display:flex; align-items:center; gap:6px; color:#6a7a76; }
.days-filter-control input { width:92px; height:34px; padding:0 9px; border:1px solid #bad7b8; border-radius:9px; color:#174243; }
.country-registration-shape { stroke:#ffffff; stroke-width:1.15; vector-effect:non-scaling-stroke; cursor:pointer; transition:filter .12s ease, opacity .12s ease; }
.country-registration-shape:hover { filter:brightness(.92); }

/* Linked hover highlighting only. These rules do not change page overflow or scroll behaviour. */
.region-list-row--highlighted {
  background: rgba(241, 229, 166, 0.32) !important;
}

.country-registration-shape--highlighted,
.continent-registration-shape--highlighted {
  stroke: #f0b429 !important;
  stroke-width: 3px !important;
  filter: brightness(1.02) saturate(1.08);
}

.region-summary-card--highlighted {
  border-color: #f0b429 !important;
  background: rgba(241, 229, 166, 0.24) !important;
  box-shadow: 0 0 0 1px rgba(240, 180, 41, 0.14);
}
.users-analytics-page :deep(.chart-tooltip) { min-width:220px; padding:14px 16px; font-size:13px; }
.users-analytics-page :deep(.chart-tooltip strong) { font-size:15px; }

/* Region summary refinements: keep the existing scroll behaviour untouched. */
.region-summary-card--international {
  grid-column: 1 / -1;
  min-height: 96px !important;
}

.region-summary-panel .region-summary-card:not(.region-summary-card--international) {
  min-height: 118px !important;
}

.region-summary-panel .region-summary-name {
  min-height: 0 !important;
}

.region-summary-panel .region-summary-name strong {
  font-size: 14px;
  line-height: 1.2;
}

/* Australia regional detail appears only on hover from the locations list. */
.australia-region-hover-layer {
  pointer-events: none;
}

.australia-region-hover-shape {
  stroke: #f0b429;
  stroke-width: 2.2px;
  vector-effect: non-scaling-stroke;
  filter: brightness(1.03) saturate(1.08);
}

.australia-region-hover-value {
  fill: #174243;
  font-size: 8px;
  font-weight: 800;
  text-anchor: middle;
  dominant-baseline: middle;
  paint-order: stroke;
  stroke: rgba(255, 255, 255, .96);
  stroke-width: 2px;
  stroke-linejoin: round;
}

/* === Final chart-axis alignment fixes === */

/*
 * Use absolute tick positioning instead of flex spacing.
 * This makes the visible labels use the exact same coordinates as each chart.
 */

/* Registration Trend:
 * SVG viewBox = 0 0 620 210
 * plot top = 35, plot bottom = 195
 * rendered SVG height = 178px
 */
.upper-user-row .trend-card .y-axis {
  position: relative !important;
  height: 178px !important;
  padding: 0 !important;
  align-self: start;
}

.upper-user-row .trend-card .y-axis span {
  position: absolute;
  right: 0;
  transform: translateY(-50%);
}

.upper-user-row .trend-card .y-axis span:nth-child(1) { top: 16.6667%; }
.upper-user-row .trend-card .y-axis span:nth-child(2) { top: 35.7143%; }
.upper-user-row .trend-card .y-axis span:nth-child(3) { top: 54.7619%; }
.upper-user-row .trend-card .y-axis span:nth-child(4) { top: 73.8095%; }
.upper-user-row .trend-card .y-axis span:nth-child(5) { top: 92.8571%; }

/* Daily User Activity:
 * SVG viewBox = 0 0 760 220
 * grid lines are y = 18, 63, 108, 153, 198
 */
.upper-user-row .daily-activity-card .activity-y-axis {
  position: relative !important;
  height: 220px !important;
  padding: 0 !important;
}

.upper-user-row .daily-activity-card .activity-y-axis span {
  position: absolute;
  right: 0;
  transform: translateY(-50%);
}

.upper-user-row .daily-activity-card .activity-y-axis span:nth-child(1) { top: 8.1818%; }
.upper-user-row .daily-activity-card .activity-y-axis span:nth-child(2) { top: 28.6364%; }
.upper-user-row .daily-activity-card .activity-y-axis span:nth-child(3) { top: 49.0909%; }
.upper-user-row .daily-activity-card .activity-y-axis span:nth-child(4) { top: 69.5455%; }
.upper-user-row .daily-activity-card .activity-y-axis span:nth-child(5) { top: 90%; }

/* Last Login Distribution:
 * bar value row = 20px, actual bar track = 128px.
 * Keep the Y-axis labels aligned to that exact track.
 */
.last-login-distribution-card .last-login-y-axis {
  position: relative !important;
  height: 128px !important;
  margin-top: 68px !important;
  padding: 0 !important;
  align-self: start;
}

.last-login-distribution-card .last-login-y-axis span {
  position: absolute;
  right: 0;
  transform: translateY(-50%);
}

.last-login-distribution-card .last-login-y-axis span:nth-child(1) { top: 0%; }
.last-login-distribution-card .last-login-y-axis span:nth-child(2) { top: 25%; }
.last-login-distribution-card .last-login-y-axis span:nth-child(3) { top: 50%; }
.last-login-distribution-card .last-login-y-axis span:nth-child(4) { top: 75%; }
.last-login-distribution-card .last-login-y-axis span:nth-child(5) { top: 100%; }

/* === Top Areas of Interest sort control === */
.upper-user-row .interest-heading-row {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  gap: 12px !important;
  width: 100%;
  margin-bottom: 12px;
}

.upper-user-row .interest-heading-row h2 {
  margin: 0 !important;
  flex: 1 1 auto;
}

.upper-user-row .interest-sort-button {
  appearance: none;
  -webkit-appearance: none;
  display: inline-flex !important;
  width: 48px !important;
  min-width: 48px !important;
  max-width: 48px !important;
  height: 48px !important;
  min-height: 48px !important;
  max-height: 48px !important;
  flex: 0 0 48px !important;
  align-items: center !important;
  justify-content: center !important;
  margin: 0 !important;
  padding: 0 !important;
  border: 1px solid #BAD7B8 !important;
  border-radius: 12px !important;
  background: #FFFFFF !important;
  color: #017151 !important;
  font-size: 18px !important;
  line-height: 1 !important;
  cursor: pointer;
}

.upper-user-row .interest-sort-button i {
  display: block;
  margin: 0;
  color: #017151 !important;
  font-size: 18px !important;
  line-height: 1 !important;
}

.last-login-distribution-card .chart-with-y-axis {
  align-items: start;
}

.last-login-distribution-card .y-axis-line {
  height: 238px;
  box-sizing: border-box;
}

/* Registration plot starts at the Y-axis with no artificial 40px SVG inset. */
.upper-user-row .trend-card .y-axis-line {
  padding-left: 0 !important;
}

.upper-user-row .trend-card .trend-chart {
  padding-left: 0 !important;
}

.upper-user-row .trend-card .trend-chart,
.upper-user-row .trend-card .trend-chart svg {
  margin: 0 !important;
  padding: 0 !important;
}

.upper-user-row .trend-card .month-labels {
  padding-left: 0 !important;
  padding-right: 0 !important;
}

.registration-baseline {
  stroke: #d9e2df;
  stroke-width: 1;
}

/* === Users Analytics rearranged chart layout === */

/* First row: Users by Role / Login Rate / Top Areas of Interest */
.users-analytics-page .first-row {
  display: grid !important;
  grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
  gap: 18px !important;
  align-items: stretch;
}

.users-analytics-page .first-row > .analytics-card {
  min-width: 0;
  width: 100%;
  height: 100%;
}

.users-analytics-page .first-row .interests-card {
  opacity: 1 !important;
  transform: none !important;
}

/* Second row: Last Login Distribution : User Registration Trend = 3 : 7 */
.users-analytics-page .user-trend-row {
  display: grid !important;
  grid-template-columns: minmax(300px, 3fr) minmax(0, 7fr) !important;
  gap: 18px !important;
  align-items: stretch;
  margin-bottom: 18px;
}

.users-analytics-page .user-trend-row > .analytics-card {
  min-width: 0;
  width: 100%;
  height: 100%;
}

/* The wide registration card can use the extra horizontal room. */
.users-analytics-page .user-trend-row .trend-card .trend-chart,
.users-analytics-page .user-trend-row .trend-card .trend-chart svg {
  width: 100% !important;
}

/* Interest list fills the card and scrolls inside it, with a scrollbar that
   stays visible so every area of interest is clearly reachable. */
.users-analytics-page .first-row .interests-card {
  display: flex;
  flex-direction: column;
}

.users-analytics-page .first-row .interests-card .interest-list {
  flex: 1 1 0;
  min-height: 180px;
  max-height: none;
  overflow-y: scroll;
}

.users-analytics-page .first-row .interests-card .interest-list::-webkit-scrollbar {
  width: 6px;
}

.users-analytics-page .first-row .interests-card .interest-list::-webkit-scrollbar-track {
  border-radius: 3px;
  background: #eef3f1;
}

.users-analytics-page .first-row .interests-card .interest-list::-webkit-scrollbar-thumb {
  border-radius: 3px;
  background: #9fbfb9;
}

.users-analytics-page .interests-card .interest-count {
  flex: 0 0 auto;
  margin: 8px 0 0;
  color: #7a8c88;
  font-size: 11px;
  text-align: right;
  white-space: nowrap;
}

/* Responsive fallback */
@media (max-width: 1279px) {
  .users-analytics-page .first-row {
    grid-template-columns: 1fr !important;
  }

  .users-analytics-page .first-row > .analytics-card {
    height: auto;
    min-height: 330px;
  }

  .users-analytics-page .user-trend-row {
    grid-template-columns: 1fr !important;
  }
}

/* === Final layout requested for Users Analytics === */

/* Keep three equal cards only when there is enough effective viewport width. */
@media (min-width: 1280px) {
  .users-analytics-page .first-row {
    display: grid !important;
    grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
    gap: 18px !important;
  }
}

/* Top Areas of Interest: match reference with square control on title right. */
.users-analytics-page .interests-card .interest-heading-row {
  display: flex !important;
  align-items: flex-start !important;
  justify-content: space-between !important;
  gap: 12px !important;
  width: 100% !important;
  margin-bottom: 14px !important;
}

.users-analytics-page .interests-card .interest-heading-row h2 {
  margin: 0 !important;
  flex: 1 1 auto !important;
}

.users-analytics-page .interests-card .interest-sort-button {
  appearance: none !important;
  -webkit-appearance: none !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  width: 48px !important;
  min-width: 48px !important;
  max-width: 48px !important;
  height: 48px !important;
  min-height: 48px !important;
  max-height: 48px !important;
  flex: 0 0 48px !important;
  margin: 0 !important;
  padding: 0 !important;
  border: 1px solid #BAD7B8 !important;
  border-radius: 12px !important;
  background: #FFFFFF !important;
  color: #017151 !important;
  font-size: 17px !important;
  cursor: pointer !important;
}

.users-analytics-page .interests-card .interest-sort-button i {
  margin: 0 !important;
  color: #017151 !important;
  font-size: 17px !important;
  line-height: 1 !important;
}

/* Second row:
   Last Login = same width as a first-row card (1/3)
   Registration Trend = remaining 2/3. */
.users-analytics-page .user-trend-row {
  display: grid !important;
  grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
  gap: 18px !important;
  align-items: stretch !important;
  margin-bottom: 18px !important;
}

.users-analytics-page .user-trend-row .last-login-distribution-card {
  grid-column: 1 / 2 !important;
}

.users-analytics-page .user-trend-row .trend-card {
  grid-column: 2 / 4 !important;
}

.users-analytics-page .user-trend-row > .analytics-card {
  min-width: 0 !important;
  width: 100% !important;
}

/* Registration role filter like the reference. */
.users-analytics-page .trend-card-heading {
  display: flex !important;
  align-items: flex-start !important;
  justify-content: space-between !important;
  gap: 16px !important;
  flex-wrap: wrap !important;
}

.users-analytics-page .trend-heading-actions {
  display: flex !important;
  align-items: center !important;
  justify-content: flex-end !important;
  gap: 12px !important;
  flex-wrap: wrap !important;
}

.users-analytics-page .trend-role-filter {
  display: flex !important;
  align-items: center !important;
  gap: 10px !important;
  white-space: nowrap;
  color: #425e59;
  font-size: 12px;
}

.users-analytics-page .trend-role-filter strong {
  color: #174243;
  font-size: 12px;
  font-weight: 700;
}

.users-analytics-page .trend-role-filter label {
  display: inline-flex !important;
  align-items: center !important;
  gap: 5px !important;
  cursor: pointer;
}

.users-analytics-page .trend-role-filter input {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: #017151;
  cursor: pointer;
}

@media (max-width: 1100px) {
  .users-analytics-page .first-row,
  .users-analytics-page .user-trend-row {
    grid-template-columns: 1fr !important;
  }

  .users-analytics-page .trend-heading-actions,
  .users-analytics-page .trend-role-filter {
    justify-content: flex-start !important;
  }

  .users-analytics-page .trend-role-filter {
    flex-wrap: wrap;
  }
}

/* === Exact Last Login Distribution axis/bar alignment ===
   Use one shared 150px plot height for both Y-axis ticks and bar tracks. */
.users-analytics-page .last-login-distribution-card .chart-with-y-axis {
  display: grid !important;
  grid-template-columns: 42px minmax(0, 1fr) !important;
  gap: 8px !important;
  align-items: start !important;
}

.users-analytics-page .last-login-distribution-card .last-login-y-axis {
  position: relative !important;
  height: 150px !important;
  margin-top: 20px !important; /* same 20px value-label row as each bar */
  padding: 0 !important;
  align-self: start !important;
}

.users-analytics-page .last-login-distribution-card .last-login-y-axis span {
  position: absolute !important;
  right: 0 !important;
  transform: translateY(-50%) !important;
}

.users-analytics-page .last-login-distribution-card .last-login-y-axis span:nth-child(1) { top: 0% !important; }
.users-analytics-page .last-login-distribution-card .last-login-y-axis span:nth-child(2) { top: 20% !important; }
.users-analytics-page .last-login-distribution-card .last-login-y-axis span:nth-child(3) { top: 40% !important; }
.users-analytics-page .last-login-distribution-card .last-login-y-axis span:nth-child(4) { top: 60% !important; }
.users-analytics-page .last-login-distribution-card .last-login-y-axis span:nth-child(5) { top: 80% !important; }
.users-analytics-page .last-login-distribution-card .last-login-y-axis span:nth-child(6) { top: 100% !important; }

.users-analytics-page .last-login-distribution-card .y-axis-line {
  min-width: 0 !important;
  height: 204px !important;
  border-left: 1px solid #d9e2df !important;
}

.users-analytics-page .last-login-distribution-card .vertical-bars {
  display: flex !important;
  align-items: flex-start !important;
  justify-content: space-around !important;
  height: 204px !important;
  padding-top: 0 !important;
}

.users-analytics-page .last-login-distribution-card .vertical-bar-item {
  display: grid !important;
  grid-template-rows: 20px 150px 34px !important;
  align-items: end !important;
  justify-items: center !important;
  width: 15% !important;
  height: 204px !important;
}

.users-analytics-page .last-login-distribution-card .bar-value {
  align-self: start !important;
  line-height: 20px !important;
}

.users-analytics-page .last-login-distribution-card .bar-track {
  display: flex !important;
  width: 34px !important;
  height: 150px !important;
  align-items: flex-end !important;
  align-self: stretch !important;
  border-bottom: 1px solid #dfe7e5 !important;
}

.users-analytics-page .last-login-distribution-card .bar-fill {
  width: 100% !important;
  min-height: 0 !important;
}

.users-analytics-page .last-login-distribution-card .bar-label {
  align-self: start !important;
  margin-top: 6px !important;
}

.users-analytics-page .last-login-role-legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  min-height: 20px;
  margin: 8px 0 4px;
  color: #506864;
  font-size: 10px;
  font-weight: 700;
}

.users-analytics-page .last-login-role-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.users-analytics-page .last-login-role-legend i {
  display: block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
}

.users-analytics-page .last-login-legend-students,
.users-analytics-page .stacked-bar-students {
  background: #39687B;
}

.users-analytics-page .last-login-legend-mentors,
.users-analytics-page .stacked-bar-mentors {
  background: #017151;
}

.users-analytics-page .last-login-legend-supervisors,
.users-analytics-page .stacked-bar-supervisors {
  background: #5EA99E;
}

.users-analytics-page .last-login-distribution-card .stacked-bar-track {
  flex-direction: column-reverse;
  justify-content: flex-start;
  overflow: hidden;
  border-radius: 5px 5px 0 0;
}

.users-analytics-page .last-login-distribution-card .stacked-bar-segment {
  width: 100%;
  min-height: 0;
  flex: 0 0 auto;
}

@media (max-width: 1100px) {
  .users-analytics-page .user-trend-row .last-login-distribution-card,
  .users-analytics-page .user-trend-row .trend-card {
    grid-column: auto !important;
  }
}

/* Registration month labels are rendered inside the same SVG as the points,
   so their x positions are guaranteed to match exactly. */
.users-analytics-page .trend-card .trend-month-label {
  fill: #748683;
  font-size: 11px;
  font-weight: 500;
  pointer-events: none;
}

/* Registration trend fills the whole card: the plot takes the space left
   under the heading and the SVG is absolutely positioned inside it, so the
   chart follows the card instead of the card following a fixed SVG size. */
.users-analytics-page .trend-card {
  display: flex !important;
  flex-direction: column;
}

.users-analytics-page .trend-card .registration-plot {
  position: relative;
  flex: 1 1 auto;
  min-height: 240px;
  margin-top: 10px;
}

.users-analytics-page .trend-card .registration-plot svg {
  position: absolute;
  inset: 0;
  display: block;
  overflow: visible;
}

.users-analytics-page .trend-card .registration-axis-label {
  fill: #748683;
  font-size: 11px;
  dominant-baseline: middle;
}

.users-analytics-page .trend-card .trend-legend {
  margin-top: 6px !important;
  font-size: 12px;
}

.users-analytics-page .trend-card .trend-month-label {
  font-size: 11px;
  dominant-baseline: middle;
}

/* Users summary only: operational user-by-user login details live in Activity Analytics. */
.users-analytics-page .activity-status-role-card {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* The table stretches to the card's height so its rows share the space
   instead of leaving an empty band under the last role. */
.users-analytics-page .activity-status-role-table-wrap {
  display: flex;
  flex: 1 1 auto;
  margin-top: 14px;
  overflow: hidden;
  border: 1px solid #e0e8e5;
  border-radius: 12px;
}

.users-analytics-page .activity-status-role-table {
  width: 100%;
  height: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 14px;
}

.users-analytics-page .activity-status-role-table td strong {
  font-size: 18px;
}

.users-analytics-page .activity-status-role-note {
  margin: 12px 2px 0;
  color: #60726f;
  font-size: 12px;
  line-height: 1.5;
}

.users-analytics-page .activity-status-role-note strong {
  color: #174243;
}

.users-analytics-page .activity-status-role-table th {
  padding: 12px;
  background: #edf4ef;
  color: #174243;
  text-align: left;
  white-space: nowrap;
}

.users-analytics-page .activity-status-role-table td {
  padding: 14px 12px;
  border-top: 1px solid #e4ebe8;
  color: #536762;
}

.users-analytics-page .status-role-name { width: 31%; }
.users-analytics-page .status-role-value { width: 19%; }
.users-analytics-page .status-role-never { width: 31%; }

/* Top Areas of Interest: Student / Mentor comparison bars */
.users-analytics-page .interests-card .interest-series-legend {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 18px;
  margin: -2px 0 10px 120px;
  color: #60726f;
  font-size: 10px;
  font-weight: 600;
}

.users-analytics-page .interests-card .interest-series-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.users-analytics-page .interests-card .interest-student-dot {
  background: #39687B;
}

.users-analytics-page .interests-card .interest-mentor-dot {
  background: #017151;
}

.users-analytics-page .interests-card .interest-role-list {
  gap: 10px;
}

.users-analytics-page .interests-card .interest-role-row {
  display: grid;
  grid-template-columns: 110px minmax(80px, 1fr) 32px;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
  color: #31514e;
  font-size: 11px;
}

.users-analytics-page .interests-card .interest-role-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: right;
}

.users-analytics-page .interests-card .interest-role-bars {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.users-analytics-page .interests-card .interest-role-track {
  overflow: hidden;
  height: 7px;
  border-radius: 3px;
  background: #edf1f0;
}

.users-analytics-page .interests-card .interest-role-fill {
  height: 100%;
  min-width: 2px;
  border-radius: inherit;
}

.users-analytics-page .interests-card .interest-student-fill {
  background: #39687B;
}

.users-analytics-page .interests-card .interest-mentor-fill {
  background: #017151;
}

.users-analytics-page .interests-card .interest-role-values {
  display: grid;
  gap: 2px;
  justify-items: end;
  line-height: 1;
}

.users-analytics-page .interests-card .interest-role-values strong {
  color: #39687B;
  font-size: 10px;
}

.users-analytics-page .interests-card .interest-role-values span {
  color: #017151;
  font-size: 10px;
  font-weight: 700;
}

/* Activity Status by Role -> Activity Analytics detail link */
.activity-status-role-card .view-detail-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex: 0 0 auto;
  color: #017151;
  font-size: 12px;
  font-weight: 700;
  text-decoration: none;
  white-space: nowrap;
  transition:
    color 0.15s ease,
    transform 0.15s ease;
}

.activity-status-role-card .view-detail-link:hover {
  color: #005f45;
  text-decoration: underline;
}

.activity-status-role-card .view-detail-link:hover span {
  transform: translateX(2px);
}

.activity-status-role-card .view-detail-link span {
  transition: transform 0.15s ease;
}

@media (max-width: 620px) {
  .activity-status-role-card .card-title-row {
    align-items: flex-start;
  }

  .activity-status-role-card .view-detail-link {
    margin-top: 2px;
  }
}

</style>
