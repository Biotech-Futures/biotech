<template>
  <div class="admin-users">
    <!-- Top actions: search + add (supervisors) or add only (users) -->
    <div
      class="admin-users__actions"
      :class="{ 'admin-users__actions--with-search': isSupervisorMode }"
    >
      <template v-if="isSupervisorMode">
        <div class="admin-users__search">
          <i class="fas fa-magnifying-glass admin-users__search-icon" aria-hidden="true"></i>
          <input
            v-model="searchInput"
            type="search"
            class="admin-users__search-input"
            placeholder="Search supervisors..."
            aria-label="Search supervisors"
          />
        </div>
      </template>
      <template v-if="isStudentMode">
        <button type="button" class="btn btn-outline" title="CSV import coming soon">
          <i class="fas fa-file-arrow-up" aria-hidden="true"></i>
          <span>Import Students CSV</span>
        </button>
      </template>
      <button type="button" class="btn btn-primary" :disabled="loading" @click="openCreate">
        <i class="fas fa-plus" aria-hidden="true"></i>
        <span>{{ addLabel }}</span>
      </button>
    </div>

    <!-- Users tab filters: search / role / country / state / status -->
    <section v-if="!isSupervisorMode" class="admin-users__filters card" aria-label="Filter and search">
      <div class="admin-users__filter">
        <label class="admin-users__filter-label" for="user-search">Search</label>
        <div class="admin-users__search">
          <i class="fas fa-magnifying-glass admin-users__search-icon" aria-hidden="true"></i>
          <input
            id="user-search"
            v-model="searchInput"
            type="search"
            class="admin-users__search-input"
            placeholder="Name or email"
            aria-label="Search users"
          />
        </div>
      </div>

      <div v-if="!isRoleFixed" class="admin-users__filter">
        <label class="admin-users__filter-label" for="role-filter">Role</label>
        <select id="role-filter" v-model="filters.role" @change="onFilterChange">
          <option value="all">All roles</option>
          <option v-for="r in USER_ROLES" :key="r" :value="r">{{ roleLabel(r) }}</option>
        </select>
      </div>

      <div class="admin-users__filter">
        <label class="admin-users__filter-label" for="country-filter">Country</label>
        <select id="country-filter" v-model="filters.country" @change="onCountryFilterChange">
          <option value="all">All countries</option>
          <option v-for="name in filterCountryNames" :key="name" :value="name">{{ name }}</option>
        </select>
      </div>

      <div class="admin-users__filter">
        <label class="admin-users__filter-label" for="state-filter">State</label>
        <select id="state-filter" v-model="filters.state" @change="onFilterChange">
          <option value="all">All states</option>
          <option v-for="s in visibleStates" :key="s.id" :value="s.stateName">
            {{ stateOptionLabel(s) }}
          </option>
        </select>
      </div>

      <div v-if="isStudentMode" class="admin-users__filter">
        <label class="admin-users__filter-label" for="in-group-filter">In group</label>
        <select id="in-group-filter" v-model="filters.inGroup" @change="onFilterChange">
          <option value="all">All students</option>
          <option value="yes">In a group</option>
          <option value="no">Not in a group</option>
        </select>
      </div>

      <div class="admin-users__filter">
        <label class="admin-users__filter-label" for="status-filter">Status</label>
        <select id="status-filter" v-model="filters.status" @change="onFilterChange">
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>
    </section>

    <p v-if="error" class="admin-users__error" role="alert">
      <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
      <span>{{ error }}</span>
    </p>

    <!-- Bulk actions bar -->
    <BulkActionsBar
      v-if="bulkCount && !loading"
      :count="bulkCount"
      :noun="noun"
      :disabled="busy"
      @clear="clearSelection"
    >
      <span v-if="selectAllMatching" class="admin-users__select-all-hint">
        All matching {{ pluralNoun }} selected
      </span>
      <template v-if="isStudentMode">
        <span :title="groupActionsHint">
          <button type="button" class="btn btn-sm btn-outline" :disabled="busy || selectAllMatching" @click="openBatchAssign">
            <i class="fas fa-users" aria-hidden="true"></i>
            Assign to group
          </button>
        </span>
        <span :title="removeGroupActionsHint">
          <button
            type="button"
            class="btn btn-sm btn-outline"
            :disabled="busy || selectAllMatching || groupedCount === 0"
            @click="openBatchRemove"
          >
            <i class="fas fa-user-minus" aria-hidden="true"></i>
            Remove from group{{ groupedCount > 0 ? ` (${groupedCount})` : '' }}
          </button>
        </span>
      </template>
      <button type="button" class="btn btn-sm btn-outline" :disabled="busy" @click="confirmBulkStatus(true)">
        <i class="fas fa-user-check" aria-hidden="true"></i>
        Activate
      </button>
      <button type="button" class="btn btn-sm btn-outline" :disabled="busy" @click="confirmBulkStatus(false)">
        <i class="fas fa-user-xmark" aria-hidden="true"></i>
        Deactivate
      </button>
      <button
        v-if="!isSupervisorMode"
        type="button"
        class="btn btn-sm btn-danger"
        :disabled="busy"
        @click="confirmBulkDelete"
      >
        <i class="fas fa-trash-can" aria-hidden="true"></i>
        Delete
      </button>
    </BulkActionsBar>

    <!-- Selection banner: "all matching" state / "select all matching" offer -->
    <div v-if="selectionBanner" class="admin-users__selection-banner" aria-live="polite">
      <template v-if="selectAllMatching">
        <span>
          <i class="fas fa-check-double admin-users__selection-icon" aria-hidden="true"></i>
          <span v-if="excludedCount > 0">
            {{ effectiveSelectAllCount }} of {{ totalCount }} {{ pluralNoun }} selected.
          </span>
          <span v-else>All {{ totalCount }} {{ pluralNoun }} matching these filters are selected.</span>
        </span>
        <button type="button" class="admin-users__selection-link" @click="clearSelection">
          Clear selection
        </button>
      </template>
      <template v-else>
        <span>
          <i class="fas fa-circle-info admin-users__selection-icon" aria-hidden="true"></i>
          <span>All {{ pageRows }} {{ pluralNoun }} on this page are selected.</span>
        </span>
        <button type="button" class="admin-users__selection-link" @click="selectAllMatchingNow">
          Select all {{ totalCount }} {{ pluralNoun }} matching these filters
        </button>
      </template>
    </div>

    <AdminDataTable
      :columns="columns"
      :rows="rows"
      row-key="id"
      :loading="loading"
      selectable
      :selected="displaySelected"
      :sort-state="sortState"
      :show-pagination="true"
      :page="page"
      :page-size="limit"
      :total-count="totalCount"
      :page-size-options="PAGE_SIZE_OPTIONS"
      :empty-message="emptyMessage"
      pager-label="Users pagination"
      :select-all-label="`Select all ${pluralNoun} on this page`"
      @update:selected="onSelectedChange"
      @update:sort="onSortChange"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
      @row-click="onRowClick"
    >
      <template #cell-name="{ row }">
        <button type="button" class="admin-users__name-btn" @click.stop="openView(asUser(row))">
          {{ userName(asUser(row)) }}
        </button>
      </template>
      <template #cell-email="{ row }">
        <span class="admin-users__email">{{ asUser(row).email || '—' }}</span>
      </template>
      <template #cell-role="{ row }">
        <span class="admin-users__role-badge">{{ roleLabel(asUser(row).role) }}</span>
      </template>
      <template #cell-student="{ row }">
        <div class="admin-users__student-cell">
          <button type="button" class="admin-users__name-btn" @click.stop="openView(asUser(row))">
            {{ userName(asUser(row)) }}
          </button>
          <span class="admin-users__email">{{ asUser(row).email || '—' }}</span>
        </div>
      </template>
      <template #cell-school="{ row }">
        {{ asUser(row).schoolName || '—' }}
      </template>
      <template #cell-year="{ row }">
        {{ asUser(row).yearLevel ?? '—' }}
      </template>
      <template #cell-country="{ row }">
        {{ labelizeCountry(asUser(row).country) }}
      </template>
      <template #cell-state="{ row }">
        {{ labelizeState(asUser(row).state) }}
      </template>
      <template v-if="isStudentMode" #cell-group="{ row }">
        <span :title="asUser(row).groupId ? `Group ID ${asUser(row).groupId}` : undefined">
          {{ asUser(row).groupName || '—' }}
        </span>
      </template>
      <template #cell-interests="{ row }">
        <div class="admin-users__interests" :title="asUser(row).interests?.join(', ') || undefined">
          <template v-if="asUser(row).interests?.length">
            <span v-for="interest in visibleInterests(asUser(row))" :key="interest" class="admin-users__interest-chip">
              {{ interest }}
            </span>
            <span v-if="asUser(row).interests!.length > 3" class="admin-users__interest-more">
              +{{ asUser(row).interests!.length - 3 }}
            </span>
          </template>
          <span v-else>—</span>
        </div>
      </template>
      <template #cell-status="{ row }">
        <span
          class="admin-users__status-badge"
          :class="{ 'admin-users__status-badge--inactive': !asUser(row).isActive }"
        >
          {{ asUser(row).isActive ? 'Active' : 'Inactive' }}
        </span>
      </template>
      <template #cell-loggedIn="{ row }">
        <div class="admin-users__logged-in">
          <span
            v-if="asUser(row).hasLoggedIn"
            class="admin-users__logged-in-badge admin-users__logged-in-badge--yes"
            :title="formatFullDate(asUser(row).lastLogin)"
          >
            Yes
          </span>
          <span v-else class="admin-users__logged-in-badge">No</span>
          <span v-if="asUser(row).hasLoggedIn && asUser(row).lastLogin" class="admin-users__logged-in-date">
            {{ formatLoginDate(asUser(row).lastLogin) }}
          </span>
        </div>
      </template>
      <template #cell-actions="{ row }">
        <div class="admin-users__row-actions" @click.stop>
          <button
            v-if="isStudentMode"
            type="button"
            class="btn btn-sm"
            :class="asUser(row).groupId ? 'btn-outline' : 'btn-primary'"
            :title="asUser(row).groupId ? 'Remove from group' : 'Assign to a group'"
            @click="onGroupAction(asUser(row))"
          >
            {{ asUser(row).groupId ? 'Remove' : 'Assign' }}
          </button>
          <button type="button" class="btn btn-sm btn-outline" @click="openEdit(asUser(row))">
            Edit
          </button>
          <button
            type="button"
            class="btn btn-sm"
            :class="asUser(row).isActive ? 'btn-outline' : 'btn-primary'"
            :title="asUser(row).isActive ? 'Deactivate account' : 'Activate account'"
            @click="onToggleActive(asUser(row))"
          >
            {{ asUser(row).isActive ? 'Deactivate' : 'Activate' }}
          </button>
        </div>
      </template>
    </AdminDataTable>

    <!-- Bulk status confirm -->
    <ConfirmDialog
      v-model="bulkStatus.open"
      :title="bulkStatus.title"
      :message="bulkStatus.message"
      :confirm-label="bulkStatus.confirmLabel"
      :variant="bulkStatus.action === 'deactivate' ? 'warning' : 'default'"
      :busy="busy"
      @confirm="runBulkStatus"
    />

    <!-- Bulk delete confirm (forces the DELETE keyword when select-all / force) -->
    <ConfirmDialog
      v-model="bulkDelete.open"
      title="Delete users"
      :message="bulkDeleteMessage"
      confirm-label="Delete"
      variant="danger"
      :busy="busy"
      :disabled="deleteConfirmBlocked"
      @confirm="runBulkDelete"
    >
      <label class="admin-users__force-toggle">
        <input v-model="bulkForce" type="checkbox" />
        <span>
          Force delete — also permanently delete each user's chat messages, uploaded resources,
          workshops, and match runs. Required to remove accounts that have any activity.
        </span>
      </label>
      <p v-if="bulkForce" class="admin-users__force-warning">
        This destroys their content for everyone, not just the account, and cannot be undone.
      </p>
      <div class="admin-users__delete-type">
        <label class="admin-users__filter-label" for="bulk-delete-confirm">
          Type <span class="admin-users__delete-keyword">DELETE</span> to confirm
        </label>
        <input
          id="bulk-delete-confirm"
          v-model="deleteConfirmText"
          class="form-input"
          autocomplete="off"
          placeholder="DELETE"
        />
      </div>
    </ConfirmDialog>

    <!-- Single delete confirm -->
    <ConfirmDialog
      v-model="singleDelete.open"
      title="Delete user"
      :message="singleDelete.message"
      confirm-label="Delete"
      variant="danger"
      :busy="busy"
      @confirm="runSingleDelete"
    />

    <!-- Single deactivate confirm -->
    <ConfirmDialog
      v-model="singleToggle.open"
      title="Deactivate user"
      :message="singleToggle.message"
      confirm-label="Deactivate"
      variant="warning"
      :busy="busy"
      @confirm="runSingleToggle"
    />

    <!-- Assign student(s) to a group (single + batch share this surface) -->
    <StudentAssignDialog
      v-model:open="assignOpen"
      :students="assignStudents"
      @confirmed="onAssignConfirmed"
    />

    <!-- Single remove-from-group confirm -->
    <ConfirmDialog
      v-model="singleRemove.open"
      title="Remove from group"
      :message="singleRemove.message"
      confirm-label="Remove"
      variant="danger"
      :busy="busy"
      @confirm="runSingleRemove"
    />

    <!-- Batch remove-from-group confirm -->
    <ConfirmDialog
      v-model="batchRemoveConfirm.open"
      :title="batchRemoveTitle"
      :message="batchRemoveMessage"
      confirm-label="Remove"
      variant="danger"
      :busy="busy"
      @confirm="runBatchRemove"
    />

    <!-- Create / Edit sheet -->
    <FormSheet
      v-model="formOpen"
      :title="isEditing ? `Edit ${userNoun}` : `Add ${userNoun}`"
      :description="isEditing ? 'Update the account details below.' : 'Manage role, state, and account status without touching other modules.'"
      width="min(100vw, 680px)"
      @close="onFormClose"
    >
      <form class="admin-users-form" novalidate @submit.prevent="submitForm">
        <p v-if="formError" class="admin-users-form__error" role="alert">{{ formError }}</p>

        <div class="admin-users-form__grid">
          <div class="form-field">
            <label class="form-label" for="f-first">First name *</label>
            <input id="f-first" v-model.trim="form.firstName" class="form-input" />
          </div>
          <div class="form-field">
            <label class="form-label" for="f-last">Last name *</label>
            <input id="f-last" v-model.trim="form.lastName" class="form-input" />
          </div>
          <div class="form-field" :class="{ 'form-field--full': isEditing }">
            <label class="form-label" for="f-email">Email *</label>
            <input
              id="f-email"
              v-model.trim="form.email"
              type="email"
              class="form-input"
              :disabled="isEditing"
              :readonly="isEditing"
            />
          </div>
          <div v-if="!isEditing" class="form-field">
            <label class="form-label" for="f-role">Role *</label>
            <select id="f-role" v-model="form.role" class="form-input" :disabled="!!fixedRole">
              <option v-for="r in USER_ROLES" :key="r" :value="r">{{ roleLabel(r) }}</option>
            </select>
          </div>
          <div v-if="isEditing" class="form-field">
            <label class="form-label" for="f-role-edit">Role</label>
            <select id="f-role-edit" v-model="form.role" class="form-input" :disabled="!!fixedRole">
              <option v-for="r in USER_ROLES" :key="r" :value="r">{{ roleLabel(r) }}</option>
            </select>
          </div>

          <template v-if="form.role !== 'admin'">
            <div class="form-field">
              <label class="form-label" for="f-country">Country *</label>
              <select id="f-country" v-model="form.countryId" class="form-input" @change="onFormCountryChange">
                <option :value="undefined">Unassigned</option>
                <option v-for="c in countries" :key="c.id" :value="c.id">{{ c.countryName }}</option>
              </select>
            </div>
            <div v-if="formStates.length" class="form-field">
              <label class="form-label" for="f-state">State</label>
              <select id="f-state" v-model="form.stateId" class="form-input">
                <option :value="undefined">None</option>
                <option v-for="s in formStates" :key="s.id" :value="s.id">{{ s.stateName }}</option>
              </select>
            </div>
          </template>
        </div>

        <template v-if="form.role === 'student'">
          <div class="admin-users-form__section">Student details</div>
          <div class="admin-users-form__grid">
            <div class="form-field">
              <label class="form-label" for="f-school">School *</label>
              <input id="f-school" v-model.trim="form.schoolName" class="form-input" />
            </div>
            <div class="form-field">
              <label class="form-label" for="f-year">Year level *</label>
              <input
                id="f-year"
                v-model.number="form.yearLevel"
                type="number"
                min="9"
                max="12"
                class="form-input"
              />
            </div>
            <div class="form-field form-field--full">
              <label class="form-label" for="f-supervisor">Supervisor (optional)</label>
              <input
                id="f-supervisor"
                v-model.trim="form.supervisorEmail"
                list="user-supervisor-datalist"
                class="form-input"
                placeholder="Search by name or email"
              />
              <datalist id="user-supervisor-datalist">
                <option v-for="sup in supervisors" :key="sup.id" :value="sup.email">{{ userName(sup) }}</option>
              </datalist>
            </div>
          </div>
        </template>

        <template v-if="form.role === 'supervisor'">
          <div class="admin-users-form__section">Supervisor details</div>
          <div class="admin-users-form__grid">
            <div class="form-field form-field--full">
              <label class="form-label" for="f-sschool">School (optional)</label>
              <input id="f-sschool" v-model.trim="form.supervisorSchoolName" class="form-input" />
            </div>
          </div>
        </template>

        <template v-if="form.role === 'mentor'">
          <div class="admin-users-form__section">Mentor details</div>
          <div class="admin-users-form__grid">
            <div class="form-field">
              <label class="form-label" for="f-minst">Institution *</label>
              <input id="f-minst" v-model.trim="form.mentorInstitution" class="form-input" />
            </div>
            <div class="form-field">
              <label class="form-label" for="f-mmax">Max groups *</label>
              <input id="f-mmax" v-model.number="form.mentorMaxGroupCount" type="number" min="0" class="form-input" />
            </div>
            <div class="form-field form-field--full">
              <label class="form-label" for="f-mbg">Background</label>
              <input id="f-mbg" v-model.trim="form.mentorBackground" class="form-input" placeholder="e.g. Research" />
            </div>
            <div class="form-field form-field--full">
              <label class="form-label" for="f-mreason">Mentor reason *</label>
              <textarea
                id="f-mreason"
                v-model.trim="form.mentorReason"
                class="form-input"
                rows="2"
                placeholder="Supporting student research projects"
              ></textarea>
            </div>
          </div>
        </template>

        <template v-if="roleUsesInterests">
          <div class="admin-users-form__section">
            {{ form.role === 'mentor' ? 'Interests / Expertise' : 'Interests' }} *
          </div>
          <fieldset class="admin-users-form__interests">
            <legend class="sr-only">Select areas of interest</legend>
            <label v-for="option in INTEREST_OPTIONS" :key="option" class="admin-users-form__interest">
              <input
                type="checkbox"
                :value="option"
                :checked="form.interests.includes(option)"
                @change="onInterestToggle(option, $event)"
              />
              <span>{{ option }}</span>
            </label>
          </fieldset>
        </template>

        <div class="admin-users-form__section">Account</div>
        <div v-if="!isEditing" class="form-field">
          <label class="form-label">
            <input id="f-active" v-model="form.active" type="checkbox" class="form-checkbox" />
            Active (displays in the list immediately)
          </label>
        </div>

        <div class="admin-users-form__footer">
          <button
            v-if="isEditing && !isSupervisorMode"
            type="button"
            class="btn btn-danger"
            :disabled="busy"
            @click="confirmEditorDelete"
          >
            <i class="fas fa-trash-can" aria-hidden="true"></i>
            Delete
          </button>
          <span v-if="isEditing && !isSupervisorMode" class="admin-users-form__footer-spacer"></span>
          <button type="button" class="btn btn-outline" :disabled="busy" @click="onFormClose">
            Cancel
          </button>
          <button type="submit" class="btn btn-primary" :disabled="busy">
            <span v-if="busy" class="admin-users-form__spinner" aria-hidden="true"></span>
            {{ isEditing ? 'Save Changes' : 'Create User' }}
          </button>
        </div>
      </form>
    </FormSheet>

    <!-- View detail sheet -->
    <FormSheet
      v-model="viewOpen"
      :title="detailTitle"
      description="Account details"
      width="min(100vw, 620px)"
      @close="onViewClose"
    >
      <div class="admin-users-detail">
        <section v-if="detailUser" class="admin-users-detail__section">
          <h3>Account</h3>
          <dl class="admin-users-detail__list">
            <div class="admin-users-detail__item">
              <dt>Email</dt>
              <dd>{{ detailUser.email || '—' }}</dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>Role</dt>
              <dd><span class="admin-users__role-badge">{{ roleLabel(detailUser.role) }}</span></dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>Country</dt>
              <dd>{{ labelizeCountry(detailUser.country) }}</dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>State</dt>
              <dd>{{ labelizeState(detailUser.state) }}</dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>Status</dt>
              <dd>
                <span class="admin-users__status-badge" :class="{ 'admin-users__status-badge--inactive': !detailUser.isActive }">
                  {{ detailUser.isActive ? 'Active' : 'Inactive' }}
                </span>
              </dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>Has logged in</dt>
              <dd>
                <span class="admin-users__logged-in-badge" :class="{ 'admin-users__logged-in-badge--yes': detailUser.hasLoggedIn }">
                  {{ detailUser.hasLoggedIn ? 'Yes' : 'No' }}
                </span>
              </dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>Last login</dt>
              <dd>{{ detailUser.lastLogin ? formatFullDate(detailUser.lastLogin) : 'Never' }}</dd>
            </div>
          </dl>
        </section>

        <section v-if="detailUser?.role === 'student'" class="admin-users-detail__section">
          <h3>Student Profile</h3>
          <dl class="admin-users-detail__list">
            <div class="admin-users-detail__item">
              <dt>School</dt>
              <dd>{{ detailUser.schoolName || '—' }}</dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>Year level</dt>
              <dd>{{ detailUser.yearLevel ?? '—' }}</dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>Interests</dt>
              <dd>{{ joinInterests(detailUser.interests) }}</dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>Group</dt>
              <dd>{{ detailUser.groupName || '—' }}</dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>Supervisor</dt>
              <dd>{{ supervisorLabel(detailUser) }}</dd>
            </div>
          </dl>
        </section>

        <section v-if="detailUser?.role === 'mentor'" class="admin-users-detail__section">
          <h3>Mentor Profile</h3>
          <dl class="admin-users-detail__list">
            <div class="admin-users-detail__item">
              <dt>Interests / Expertise</dt>
              <dd>{{ joinInterests(detailUser.interests) }}</dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>Institution</dt>
              <dd>{{ detailUser.mentorInstitution || '—' }}</dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>Background</dt>
              <dd>{{ detailUser.mentorBackground || '—' }}</dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>Mentor reason</dt>
              <dd>{{ detailUser.mentorReason || '—' }}</dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>Max groups</dt>
              <dd>{{ detailUser.mentorMaxGroupCount ?? '—' }}</dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>Group</dt>
              <dd>{{ detailUser.groupName || '—' }}</dd>
            </div>
          </dl>
        </section>

        <section v-if="detailUser?.role === 'supervisor'" class="admin-users-detail__section">
          <h3>Supervisor Profile</h3>
          <dl class="admin-users-detail__list">
            <div class="admin-users-detail__item">
              <dt>School</dt>
              <dd>{{ detailUser.schoolName || '—' }}</dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>Group</dt>
              <dd>{{ detailUser.groupName || '—' }}</dd>
            </div>
            <div class="admin-users-detail__item">
              <dt>Supervisees</dt>
              <dd class="admin-users-detail__supervisees">
                <span v-if="!detailUser.supervisees?.length">—</span>
                <span v-else>{{ superviseesLabel(detailUser) }}</span>
              </dd>
            </div>
          </dl>
        </section>

        <section v-if="detailUser?.role === 'admin'" class="admin-users-detail__section">
          <h3>Admin Profile</h3>
          <dl class="admin-users-detail__list">
            <div class="admin-users-detail__item">
              <dt>Scope</dt>
              <dd>Admin</dd>
            </div>
          </dl>
        </section>
      </div>

      <div class="admin-users-detail__footer">
        <button type="button" class="btn btn-outline" @click="onViewClose">Close</button>
        <button v-if="detailUser" type="button" class="btn btn-primary" @click="openEditFromView">Edit</button>
      </div>
    </FormSheet>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import AdminDataTable, { type AdminColumn, type SortState } from '@/components/admin/AdminDataTable.vue'
import BulkActionsBar from '@/components/admin/BulkActionsBar.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import StudentAssignDialog from '@/components/admin/StudentAssignDialog.vue'
import {
  type AdminUser,
  type AdminUserCountry,
  type AdminUserState,
  type UserListFilters,
  type CreateUserPayload,
  fetchAdminUsers,
  createAdminUser,
  updateAdminUser,
  deleteAdminUser,
  setAdminUserActive,
  bulkSetUsersActive,
  bulkDeleteUsers,
  fetchAdminCountries,
  fetchAdminStates,
  removeGroupMember
} from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'

const USER_ROLES = ['student', 'mentor', 'supervisor', 'admin'] as const
type UserRole = (typeof USER_ROLES)[number]

const INTEREST_OPTIONS = [
  'Biomedical Innovations',
  'Environmental Sustainability & Climate Tech',
  'Space & Astrobiology',
  'AI & Robotics and Smart Systems',
  'Nanotechnology & Materials Science',
  'Food & Agriculture Technology',
  'Neuroscience & Mental Health Tech',
  'Water & Energy Tech',
  'Ethical & Societal Impacts of Emerging Tech'
]

const PAGE_SIZE_OPTIONS = [25, 50, 100, 200]

const props = withDefaults(
  defineProps<{
    title: string
    noun: string
    /** When set (e.g. 'supervisor'), the list is filtered to this role and the role cannot be changed. */
    roleFilter?: string
  }>(),
  {
    roleFilter: ''
  }
)

const fixedRole = computed(() => props.roleFilter || '')
// Any role-fixed tab (students / mentors / supervisors) locks the role.
const isRoleFixed = computed(() => Boolean(props.roleFilter))
// Supervisors alone use the compact top-bar layout and are locked down
// (no bulk delete, no delete from the editor).
const isSupervisorMode = computed(() => props.roleFilter === 'supervisor')
// Students get the group-assignment mode: Group column, Assign/Remove actions,
// an "In group" filter, and batch assign/remove.
const isStudentMode = computed(() => props.roleFilter === 'student')
const userNoun = computed(() => props.noun)
const pluralNoun = computed(() => props.noun + 's')
const addLabel = computed(() => `Add ${props.noun.charAt(0).toUpperCase() + props.noun.slice(1)}`)
const roleUsesInterests = computed(() => form.role === 'student' || form.role === 'mentor')

const roleLabel = (role: string | null | undefined) =>
  role ? role.charAt(0).toUpperCase() + role.slice(1) : '—'
const labelizeCountry = (country: AdminUserCountry | null | undefined) =>
  country?.countryName ?? 'Unassigned'
const labelizeState = (state: AdminUserState | null | undefined) =>
  state?.stateName ?? '-'

// The backend list payload has firstName/lastName, not a combined `name`.
const userName = (user: AdminUser | null | undefined) =>
  [user?.firstName, user?.lastName].filter(Boolean).join(' ').trim() || '—'

// AdminDataTable slots hand rows out as Record<string, unknown>.
const asUser = (row: Record<string, unknown>): AdminUser => row as unknown as AdminUser

/** First few interests for the table cell, with the overflow hidden behind a "+n". */
const visibleInterests = (user: AdminUser) => (user.interests ?? []).slice(0, 3)

const loading = ref(false)
const busy = ref(false)
const error = ref('')

const rows = ref<AdminUser[]>([])
const totalCount = ref(0)
const page = ref(1)
const limit = ref(25)
const sortState = ref<SortState>({
  key: isStudentMode.value ? 'student' : props.roleFilter ? 'name' : 'createdAt',
  direction: props.roleFilter ? 'asc' : 'desc'
})

const countries = ref<AdminUserCountry[]>([])
const filterCountries = ref<AdminUserCountry[]>([])
const states = ref<AdminUserState[]>([])
const supervisors = ref<AdminUser[]>([])

const searchInput = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null
const appliedSearch = ref('')

const filters = reactive<{
  role: UserRole | 'all'
  country: string
  state: string
  inGroup: 'all' | 'yes' | 'no'
  status: 'all' | 'active' | 'inactive'
}>({
  role: 'all',
  country: 'all',
  state: 'all',
  inGroup: 'all',
  status: 'all'
})

const filterCountryNames = computed(() =>
  [...new Set(filterCountries.value.map((c) => c.countryName))].sort((a, b) => a.localeCompare(b))
)

const visibleStates = computed(() => {
  if (filters.country === 'all') return states.value
  return states.value.filter((s) => s.countryName === filters.country)
})

const stateOptionLabel = (s: AdminUserState) =>
  filters.country === 'all' && s.countryName ? `${s.stateName} · ${s.countryName}` : s.stateName

// Filters shared by the list query and "select all matching" bulk actions.
const currentFilters = computed<UserListFilters>(() => ({
  search: appliedSearch.value || undefined,
  role: fixedRole.value || (filters.role === 'all' ? undefined : filters.role),
  country: filters.country === 'all' ? undefined : filters.country,
  state: filters.state === 'all' ? undefined : filters.state,
  active: filters.status === 'all' ? undefined : filters.status,
  inGroup: isStudentMode.value && filters.inGroup !== 'all' ? filters.inGroup : undefined
}))

// Bulk endpoints expect `active` as a boolean, not the list-query string.
const bulkFilters = computed<UserListFilters>(() => ({
  ...currentFilters.value,
  active: filters.status === 'all' ? undefined : filters.status === 'active'
}))

// Selection. Keep a snapshot of each selected row so group-actions (assign /
// remove) can read group info for selections that span pages; the table only
// emits ids, so snapshots are rebuilt from that set and refreshed on refetch.
const selectedMap = ref<Map<number, AdminUser>>(new Map())
const selectAllMatching = ref(false)
const excludedIds = ref<Set<string>>(new Set())

const selectedIds = computed(() => Array.from(selectedMap.value.keys()))

const pageIds = computed(() => rows.value.map((r) => String(r.id)))
const pageRows = computed(() => rows.value.length)

const displaySelected = computed<Array<string | number>>(() => {
  if (selectAllMatching.value) {
    return pageIds.value.filter((id) => !excludedIds.value.has(id))
  }
  return selectedIds.value
})

const excludedCount = computed(() => excludedIds.value.size)
const effectiveSelectAllCount = computed(() => Math.max(0, totalCount.value - excludedCount.value))
const bulkCount = computed(() =>
  selectAllMatching.value ? effectiveSelectAllCount.value : selectedMap.value.size
)

// The students really in a group, from the selected snapshots.
const groupedSelected = computed(() =>
  Array.from(selectedMap.value.values()).filter((user) => Boolean(user.groupId))
)
const groupedCount = computed(() => groupedSelected.value.length)

const allOnPageSelected = computed(() => {
  const shown = new Set(displaySelected.value.map((id) => String(id)))
  return pageIds.value.length > 0 && pageIds.value.every((id) => shown.has(id))
})

const selectionBanner = computed(
  () => selectAllMatching.value || (allOnPageSelected.value && totalCount.value > pageRows.value)
)

const emptyMessage = computed(() =>
  loading.value
    ? ''
    : `No ${pluralNoun.value} found${hasActiveFilters.value ? ' for the current filters.' : '.'}`
)

const hasActiveFilters = computed(
  () =>
    Boolean(
      filters.role !== 'all' ||
        filters.country !== 'all' ||
        filters.state !== 'all' ||
        filters.status !== 'all' ||
        (isStudentMode.value && filters.inGroup !== 'all') ||
        appliedSearch.value
    )
)

// Columns (name/email sortable, matching the portal). Single-role tabs
// (students / mentors) drop the redundant Role column; users & supervisors keep it.
// Students get their own layout: a single Student column (name with email
// subtext, like the mentors tab) plus School / Year / Interests and a Group
// column for the assignment features.
const columns = computed<AdminColumn[]>(() => {
  const base: AdminColumn[] = [
    { key: 'name', label: 'Name', sortable: true },
    { key: 'email', label: 'Email', sortable: true },
    { key: 'country', label: 'Country' },
    { key: 'state', label: 'State' },
    { key: 'status', label: 'Status' },
    { key: 'loggedIn', label: 'Logged In' },
    { key: 'actions', label: 'Actions', align: 'right' }
  ]
  if (isRoleFixed.value && !isSupervisorMode.value) {
    if (isStudentMode.value) {
      return [
        { key: 'student', label: 'Student', sortable: true },
        { key: 'school', label: 'School' },
        { key: 'year', label: 'Year' },
        { key: 'country', label: 'Country' },
        { key: 'state', label: 'State' },
        { key: 'group', label: 'Group' },
        { key: 'interests', label: 'Interests' },
        { key: 'loggedIn', label: 'Logged In' },
        { key: 'actions', label: 'Actions', align: 'right' }
      ]
    }
    return base
  }
  return [base[0], base[1], { key: 'role', label: 'Role' }, ...base.slice(2)]
})

const sortByFromKey: Record<string, string> = {
  name: 'name',
  email: 'email',
  student: 'name'
}

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchAdminUsers({
      page: page.value,
      limit: limit.value,
      search: appliedSearch.value || undefined,
      role: currentFilters.value.role,
      state: currentFilters.value.state,
      country: currentFilters.value.country,
      active: filters.status === 'all' ? undefined : filters.status,
      inGroup: currentFilters.value.inGroup,
      sortBy: sortByFromKey[sortState.value.key] || 'createdAt',
      sortOrder: sortState.value.direction
    })
    rows.value = data.items
    totalCount.value = data.total
  } catch (loadError) {
    logApiError('admin.users.list', loadError)
    error.value =
      loadError instanceof Error ? loadError.message : `${pluralNoun.value} could not be loaded right now.`
    rows.value = []
    totalCount.value = 0
  } finally {
    loading.value = false
  }
}

const reload = () => {
  page.value = 1
  void load()
}

// Filters / search / sort redefine the matching set, so drop the selection.
const clearSelection = () => {
  selectedMap.value = new Map()
  selectAllMatching.value = false
  excludedIds.value = new Set()
}

const onFilterChange = () => {
  clearSelection()
  reload()
}

const onCountryFilterChange = () => {
  filters.state = 'all'
  onFilterChange()
}

watch(searchInput, (value) => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    appliedSearch.value = value.trim()
    clearSelection()
    reload()
  }, 350)
})

const onSortChange = (next: SortState) => {
  sortState.value = next
  clearSelection()
  reload()
}

const onPageChange = (next: number) => {
  page.value = next
  void load()
}

const onPageSizeChange = (size: number) => {
  limit.value = size
  page.value = 1
  void load()
}

const onSelectedChange = (value: Array<string | number>) => {
  if (selectAllMatching.value) {
    const next = new Set(excludedIds.value)
    pageIds.value.forEach((id) => {
      if (value.includes(id)) next.delete(id)
      else next.add(id)
    })
    excludedIds.value = next
    return
  }
  // Rebuild the snapshots, keeping any we already had so off-page selections
  // retain their group info for the remove/assign bulk actions.
  const rowById = new Map(rows.value.map((row) => [row.id, row]))
  const next = new Map<number, AdminUser>()
  for (const id of value) {
    const numericId = Number(id)
    const existing = selectedMap.value.get(numericId)
    next.set(
      numericId,
      existing ?? rowById.get(numericId) ?? ({ id: numericId } as AdminUser)
    )
  }
  selectedMap.value = next
}

// Refresh snapshots for rows that just reloaded, so group changes made
// elsewhere (assignments, removals) are reflected in the bulk-action counts.
watch(rows, (list) => {
  if (selectedMap.value.size === 0) return
  let changed = false
  const next = new Map(selectedMap.value)
  for (const row of list) {
    if (next.has(row.id)) {
      next.set(row.id, row)
      changed = true
    }
  }
  if (changed) selectedMap.value = next
})

const selectAllMatchingNow = () => {
  selectedMap.value = new Map()
  excludedIds.value = new Set()
  selectAllMatching.value = true
}

// Row click opens detail
const onRowClick = (row: Record<string, unknown>) => {
  openView(row as unknown as AdminUser)
}

// Detail sheet
const viewOpen = ref(false)
const detailUser = ref<AdminUser | null>(null)

const detailTitle = computed(() => userName(detailUser.value) || 'User details')

const openView = (user: AdminUser) => {
  detailUser.value = user
  viewOpen.value = true
}

const onViewClose = () => {
  viewOpen.value = false
  detailUser.value = null
}

const openEditFromView = () => {
  const user = detailUser.value
  if (!user) return
  viewOpen.value = false
  detailUser.value = null
  openEdit(user)
}

// Create / Edit form
const formOpen = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const editingOriginalActive = ref(false)
const formError = ref('')

interface UserForm {
  firstName: string
  lastName: string
  email: string
  role: UserRole
  countryId?: number
  stateId?: number
  schoolName: string
  yearLevel?: number
  interests: string[]
  supervisorEmail: string
  supervisorSchoolName: string
  mentorBackground: string
  mentorInstitution: string
  mentorReason: string
  mentorMaxGroupCount?: number
  active: boolean
}

const defaultForm = (): UserForm => ({
  firstName: '',
  lastName: '',
  email: '',
  role: (props.roleFilter as UserRole) || 'student',
  countryId: undefined,
  stateId: undefined,
  schoolName: '',
  yearLevel: undefined,
  interests: [],
  supervisorEmail: '',
  supervisorSchoolName: '',
  mentorBackground: '',
  mentorInstitution: '',
  mentorReason: '',
  mentorMaxGroupCount: 2,
  active: true
})

const form = reactive<UserForm>(defaultForm())

const formStates = computed(() => {
  if (!form.countryId) return []
  const country = countries.value.find((c) => c.id === form.countryId)
  if (!country) return []
  return states.value.filter((s) => s.countryName === country.countryName)
})

const onFormCountryChange = () => {
  form.stateId = undefined
}

const onInterestToggle = (option: string, event: Event) => {
  const checked = (event.target as HTMLInputElement).checked
  const next = new Set(form.interests)
  if (checked) next.add(option)
  else next.delete(option)
  form.interests = [...next]
}

const openCreate = () => {
  isEditing.value = false
  editingId.value = null
  formError.value = ''
  Object.assign(form, defaultForm())
  formOpen.value = true
}

const openEdit = (user: AdminUser) => {
  isEditing.value = true
  editingId.value = user.id
  editingOriginalActive.value = Boolean(user.isActive)
  formError.value = ''
  Object.assign(form, {
    firstName: user.firstName || '',
    lastName: user.lastName || '',
    email: user.email || '',
    role: (user.role as UserRole) || props.roleFilter || 'student',
    countryId: user.country?.id,
    stateId: user.state?.id,
    schoolName: user.role === 'student' ? user.schoolName || '' : '',
    yearLevel: user.role === 'student' ? (user.yearLevel ?? undefined) : undefined,
    interests: (user.interests || []).filter((i) => INTEREST_OPTIONS.includes(i)),
    supervisorEmail: user.role === 'student' ? (user.supervisorEmail || '') : '',
    supervisorSchoolName: user.role === 'supervisor' ? user.schoolName || '' : '',
    mentorBackground: user.role === 'mentor' ? (user.mentorBackground || '') : '',
    mentorInstitution: user.role === 'mentor' ? (user.mentorInstitution || '') : '',
    mentorReason: user.role === 'mentor' ? (user.mentorReason || '') : '',
    mentorMaxGroupCount: user.role === 'mentor' ? (user.mentorMaxGroupCount ?? 2) : 2,
    active: user.isActive
  })
  formOpen.value = true
}

const onFormClose = () => {
  formOpen.value = false
  editingId.value = null
}

const isValidEmail = (email: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)

const validateForm = (): boolean => {
  const role = form.role
  if (!form.firstName.trim()) {
    formError.value = 'First name is required.'
    return false
  }
  if (!form.lastName.trim()) {
    formError.value = 'Last name is required.'
    return false
  }
  if (!form.email.trim()) {
    formError.value = 'Email is required.'
    return false
  }
  if (!isValidEmail(form.email.trim())) {
    formError.value = 'Invalid email format.'
    return false
  }
  if (role !== 'admin' && form.countryId === undefined) {
    formError.value = 'Country is required for non-admin users.'
    return false
  }
  if (role === 'student') {
    if (!form.schoolName.trim()) {
      formError.value = 'School is required for student users.'
      return false
    }
    if (!form.yearLevel || form.yearLevel < 9 || form.yearLevel > 12) {
      formError.value = 'Year level must be between 9 and 12.'
      return false
    }
  }
  if (role === 'mentor') {
    if (!form.mentorInstitution.trim()) {
      formError.value = 'Institution is required for mentor users.'
      return false
    }
    if (!form.mentorReason.trim()) {
      formError.value = 'Mentor reason is required for mentor users.'
      return false
    }
    if (form.mentorMaxGroupCount === undefined || form.mentorMaxGroupCount < 0) {
      formError.value = 'Max group count must be 0 or greater.'
      return false
    }
  }
  if (roleUsesInterests.value && form.interests.length === 0) {
    formError.value = `At least one interest is required for ${role} users.`
    return false
  }
  return true
}

const submitForm = async () => {
  formError.value = ''
  if (!validateForm()) return

  const role = form.role
  const resolveCountryName = (id?: number) => {
    if (id === undefined) return undefined
    return countries.value.find((c) => c.id === id)?.countryName
  }
  const resolveStateName = (id?: number) => {
    if (id === undefined) return undefined
    return states.value.find((s) => s.id === id)?.stateName
  }

  busy.value = true
  try {
    if (isEditing.value && editingId.value !== null) {
      const payload: Record<string, unknown> = {
        firstName: form.firstName,
        lastName: form.lastName,
        role,
        countryId: role === 'admin' ? null : form.countryId,
        stateId: role === 'admin' ? null : form.stateId
      }
      if (role === 'student') {
        payload.schoolName = form.schoolName
        payload.yearLevel = form.yearLevel
        payload.interests = form.interests
        payload.supervisorEmail = form.supervisorEmail || undefined
      } else if (role === 'supervisor') {
        payload.supervisorSchoolName = form.supervisorSchoolName || null
      } else if (role === 'mentor') {
        payload.mentorBackground = form.mentorBackground || null
        payload.mentorInstitution = form.mentorInstitution
        payload.mentorReason = form.mentorReason
        payload.mentorMaxGroupCount = form.mentorMaxGroupCount
        payload.interests = form.interests
      }

      const activeWasChanged = form.active !== editingOriginalActive.value
      await updateAdminUser(editingId.value, payload)
      if (activeWasChanged) {
        await setAdminUserActive(editingId.value, form.active)
      }
      formOpen.value = false
      editingId.value = null
      void load()
      return
    }

    const payload: Record<string, unknown> = {
      email: form.email,
      firstName: form.firstName,
      lastName: form.lastName,
      role,
      active: form.active
    }
    const countryName = resolveCountryName(form.countryId)
    const stateName = role === 'admin' ? undefined : resolveStateName(form.stateId)
    if (countryName) payload.country = countryName
    if (stateName) payload.state = stateName

    if (role === 'student') {
      payload.schoolName = form.schoolName
      payload.yearLevel = form.yearLevel
      payload.supervisorEmail = form.supervisorEmail || undefined
      payload.interests = form.interests
    } else if (role === 'supervisor') {
      payload.supervisorSchoolName = form.supervisorSchoolName || null
    } else if (role === 'mentor') {
      payload.mentorInstitution = form.mentorInstitution
      payload.mentorReason = form.mentorReason
      payload.mentorMaxGroupCount = form.mentorMaxGroupCount
      payload.mentorBackground = form.mentorBackground || null
      payload.interests = form.interests
    }

    await createAdminUser(payload as CreateUserPayload)
    formOpen.value = false
    void load()
  } catch (submitError) {
    logApiError('admin.users.save', submitError)
    formError.value =
      submitError instanceof Error ? submitError.message : 'Unable to save the user right now.'
  } finally {
    busy.value = false
  }
}

// Single actions
const singleToggle = reactive({ open: false, userId: 0, message: '' })

const onToggleActive = (user: AdminUser) => {
  // Deactivating locks someone out, so confirm it; reactivating is non-destructive.
  if (user.isActive) {
    singleToggle.userId = user.id
    singleToggle.message = `${userName(user)} will no longer be able to sign in. You can reactivate them at any time.`
    singleToggle.open = true
    return
  }
  void runActiveChange(user.id, true)
}

const runActiveChange = async (userId: number, isActive: boolean): Promise<boolean> => {
  busy.value = true
  try {
    await setAdminUserActive(userId, isActive)
    void load()
    return true
  } catch (toggleError) {
    logApiError('admin.users.toggle', toggleError)
    return false
  } finally {
    busy.value = false
  }
}

const runSingleToggle = async () => {
  if (!singleToggle.userId) return
  const ok = await runActiveChange(singleToggle.userId, false)
  if (ok) singleToggle.open = false
}

const singleDelete = reactive({ open: false, userId: 0, message: '' })

const confirmEditorDelete = () => {
  if (!isEditing.value || editingId.value === null) return
  singleDelete.userId = editingId.value
  singleDelete.message =
    'This permanently removes the account and all related data. This cannot be undone.'
  singleDelete.open = true
}

const runSingleDelete = async () => {
  busy.value = true
  try {
    await deleteAdminUser(singleDelete.userId)
    singleDelete.open = false
    viewOpen.value = false
    formOpen.value = false
    detailUser.value = null
    clearSelection()
    void load()
  } catch (deleteError) {
    logApiError('admin.users.delete', deleteError)
  } finally {
    busy.value = false
  }
}

// Bulk actions
const bulkStatus = reactive({
  open: false,
  action: 'activate' as 'activate' | 'deactivate',
  title: '',
  message: '',
  confirmLabel: ''
})

const confirmBulkStatus = (isActive: boolean) => {
  const action = isActive ? 'activate' : 'deactivate'
  bulkStatus.action = action
  bulkStatus.confirmLabel = isActive ? 'Activate' : 'Deactivate'
  bulkStatus.title = `${isActive ? 'Activate' : 'Deactivate'} ${bulkCount.value} ${pluralNoun.value}?`
  bulkStatus.message = isActive
    ? 'The selected users will be able to sign in again.'
    : 'The selected users will no longer be able to sign in. You can reactivate them at any time.'
  bulkStatus.open = true
}

const runBulkStatus = async () => {
  busy.value = true
  try {
    const isActive = bulkStatus.action === 'activate'
    if (selectAllMatching.value) {
      await bulkSetUsersActive({
        isActive,
        selectAll: true,
        filters: bulkFilters.value,
        excludeIds: [...excludedIds.value].map(Number),
        userIds: []
      })
    } else {
      await bulkSetUsersActive({
        isActive,
        userIds: selectedIds.value
      })
    }
    bulkStatus.open = false
    clearSelection()
    void load()
  } catch (bulkError) {
    logApiError('admin.users.bulk-status', bulkError)
  } finally {
    busy.value = false
  }
}

const bulkDelete = reactive({ open: false })
const bulkForce = ref(false)
const deleteConfirmText = ref('')

const bulkDeleteMessage = computed(() => {
  const count = bulkCount.value
  const base = `This permanently removes the selected ${count === 1 ? 'account' : 'accounts'} and all related data. This cannot be undone.`
  if (selectAllMatching.value) {
    return `${base} Every account matching the current filters will be ${count === 1 ? 'deleted' : 'deleted'}; admin accounts are protected and skipped.`
  }
  return base
})

const deleteConfirmBlocked = computed(
  () => (selectAllMatching.value || bulkForce.value) && deleteConfirmText.value !== 'DELETE'
)

const confirmBulkDelete = () => {
  bulkForce.value = false
  deleteConfirmText.value = ''
  bulkDelete.open = true
}

const runBulkDelete = async () => {
  busy.value = true
  try {
    if (selectAllMatching.value) {
      await bulkDeleteUsers({
        userIds: [],
        force: bulkForce.value,
        selectAll: true,
        filters: bulkFilters.value,
        excludeIds: [...excludedIds.value].map(Number),
        expectedCount: bulkCount.value
      })
    } else {
      await bulkDeleteUsers({
        userIds: selectedIds.value,
        force: bulkForce.value
      })
    }
    bulkDelete.open = false
    clearSelection()
    void load()
  } catch (bulkError) {
    logApiError('admin.users.bulk-delete', bulkError)
  } finally {
    busy.value = false
  }
}

// Student group actions -- single and batch assignment share one surface; the
// student assign dialog owns group fetching, capacity, and the confirm POST.
const assignOpen = ref(false)
const assignStudents = ref<AdminUser[]>([])

const openAssign = (user: AdminUser) => {
  assignStudents.value = [user]
  assignOpen.value = true
}

const openBatchAssign = () => {
  assignStudents.value = Array.from(selectedMap.value.values())
  assignOpen.value = true
}

const onAssignConfirmed = () => {
  clearSelection()
  reload()
}

const onGroupAction = (user: AdminUser) => {
  if (user.groupId) {
    singleRemove.user = user
    singleRemove.message = `Remove ${userName(user)} from ${user.groupName || 'their group'}? They will become ungrouped and can be reassigned at any time.`
    singleRemove.open = true
    return
  }
  openAssign(user)
}

const singleRemove = reactive({ open: false, user: null as AdminUser | null, message: '' })

const runSingleRemove = async () => {
  const user = singleRemove.user
  if (!user || !user.groupId) return
  busy.value = true
  let failure = ''
  try {
    await removeGroupMember(user.groupId, user.id)
    singleRemove.open = false
    singleRemove.user = null
  } catch (removeError) {
    logApiError('admin.students.remove', removeError)
    failure =
      removeError instanceof Error
        ? removeError.message
        : 'Unable to remove the student from their group.'
  } finally {
    busy.value = false
  }
  void load().then(() => {
    if (failure) error.value = failure
  })
}

const batchRemoveConfirm = reactive({ open: false })

const batchRemoveTitle = computed(() => {
  const count = groupedCount.value
  return `Remove ${count} ${count === 1 ? 'student' : 'students'} from ${count === 1 ? 'their group' : 'their groups'}?`
})

const batchRemoveMessage =
  'They will become ungrouped and can be reassigned at any time.'

const openBatchRemove = () => {
  batchRemoveConfirm.open = true
}

const runBatchRemove = async () => {
  const targets = groupedSelected.value
  if (!targets.length) {
    batchRemoveConfirm.open = false
    return
  }
  busy.value = true
  let removedCount = 0
  let failedCount = 0
  const removedIds = new Set<number>()
  try {
    // Settle every removal independently so one failure doesn't strand the rest.
    const outcomes = await Promise.allSettled(
      targets.map((user) => removeGroupMember(user.groupId!, user.id))
    )
    outcomes.forEach((outcome, index) => {
      if (outcome.status === 'fulfilled') {
        removedCount += 1
        removedIds.add(targets[index].id)
      } else {
        failedCount += 1
        logApiError('admin.students.batch-remove', outcome.reason)
      }
    })
    if (removedCount) {
      // Drop only the students we actually removed; keep other selections.
      const next = new Map(selectedMap.value)
      removedIds.forEach((id) => next.delete(id))
      selectedMap.value = next
    }
    batchRemoveConfirm.open = false
  } finally {
    busy.value = false
  }
  const failure =
    failedCount > 0
      ? `Removed ${removedCount}, but ${failedCount} could not be removed.`
      : ''
  void load().then(() => {
    if (failure) error.value = failure
  })
}

// Bulk-bar title hints for the group actions (disabled state explanation first).
const groupActionsHint = computed(() =>
  selectAllMatching.value
    ? 'Select students individually to assign or remove from groups'
    : undefined
)

const removeGroupActionsHint = computed(() => {
  if (selectAllMatching.value) return groupActionsHint.value
  if (groupedCount.value === 0) return 'None of the selected students are in a group'
  return undefined
})

// Detail helpers
const joinInterests = (interests: string[] | undefined | null) =>
  interests && interests.length ? interests.join(', ') : '—'

const supervisorLabel = (user: AdminUser) => {
  if (!user.supervisorName && !user.supervisorEmail) return '—'
  return [user.supervisorName, user.supervisorEmail ? `(${user.supervisorEmail})` : '']
    .filter(Boolean)
    .join(' ')
}

const superviseesLabel = (user: AdminUser) =>
  (user.supervisees || []).map((s) => `${s.name} (${s.email})`).join(', ')

const formatLoginDate = (value: string | null) => {
  if (!value) return ''
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString()
}

const formatFullDate = (value: string | null | undefined) => {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString()
}

watch(
  () => props.roleFilter,
  () => {
    filters.role = 'all'
    clearSelection()
    reload()
  }
)

onMounted(async () => {
  void load()
  try {
    const [allCountries, inUseCountries, allStates] = await Promise.all([
      fetchAdminCountries(),
      fetchAdminCountries({ inUse: true }),
      fetchAdminStates()
    ])
    countries.value = allCountries
    filterCountries.value = inUseCountries
    states.value = allStates
  } catch (metaError) {
    logApiError('admin.users.meta', metaError)
  }
  if (!isSupervisorMode.value) {
    try {
      const data = await fetchAdminUsers({ page: 1, limit: 200, role: 'supervisor' })
      supervisors.value = data.items
    } catch (supError) {
      logApiError('admin.users.supervisors', supError)
    }
  }
})
</script>

<style scoped>
.admin-users__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.admin-users__actions .btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.admin-users__actions--with-search {
  justify-content: space-between;
}

.admin-users__filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
  padding: 1rem;
  margin-bottom: 1rem;
}

.admin-users__filter {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.admin-users__filter select {
  height: 40px;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
  width: 100%;
}

.admin-users__filter-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.admin-users__search {
  position: relative;
  width: 100%;
}

.admin-users__actions--with-search .admin-users__search {
  flex: 0 1 320px;
  width: auto;
}

.admin-users__search-input {
  width: 100%;
  height: 40px;
  padding: 0.5rem 0.75rem 0.5rem 2rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
}

.admin-users__search-icon {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 0.85rem;
  pointer-events: none;
}

.admin-users__error {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
  padding: 1rem 1.25rem;
  color: var(--danger);
  border-left: 4px solid var(--danger);
  background-color: rgba(220, 53, 69, 0.06);
}

.admin-users__select-all-hint {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--dark-green);
}

.admin-users__selection-banner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.6rem 1rem;
  margin-bottom: 0.75rem;
  border: 1px solid rgba(1, 113, 81, 0.25);
  border-radius: 8px;
  background-color: rgba(1, 113, 81, 0.07);
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--charcoal);
}

.admin-users__selection-icon {
  color: var(--dark-green);
}

.admin-users__selection-link {
  border: none;
  background: transparent;
  padding: 0;
  color: var(--dark-green);
  font-size: 0.9rem;
  font-weight: 600;
  text-decoration: underline;
  cursor: pointer;
}

.admin-users__name-btn {
  border: none;
  background: transparent;
  padding: 0;
  font: inherit;
  font-weight: 600;
  color: var(--charcoal);
  text-align: left;
  cursor: pointer;
  transition: color 0.15s ease;
}

.admin-users__name-btn:hover {
  color: var(--dark-green);
  text-decoration: underline;
}

.admin-users__email {
  color: var(--text-muted);
}

.admin-users__student-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.1rem;
}

.admin-users__interests {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.3rem;
}

.admin-users__interest-chip {
  padding: 0.15rem 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background-color: var(--light-green);
  font-size: 0.8rem;
  white-space: nowrap;
}

.admin-users__interest-more {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.admin-users__role-badge,
.admin-users__status-badge {
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background-color: var(--light-green);
  color: var(--dark-green);
  text-transform: capitalize;
}

.admin-users__status-badge--inactive {
  background-color: var(--bg-light);
  color: var(--text-muted);
}

.admin-users__logged-in {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.admin-users__logged-in-badge {
  display: inline-block;
  width: fit-content;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background-color: var(--bg-light);
  color: var(--text-muted);
  text-transform: capitalize;
}

.admin-users__logged-in-badge--yes {
  background-color: rgba(16, 185, 129, 0.12);
  color: #047857;
}

.admin-users__logged-in-date {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.admin-users__row-actions {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.admin-users__force-toggle {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-top: 0.9rem;
  font-size: 0.85rem;
  color: var(--charcoal);
  cursor: pointer;
  line-height: 1.4;
}

.admin-users__force-toggle input {
  margin-top: 0.15rem;
  accent-color: var(--danger);
}

.admin-users__force-warning {
  margin: 0.5rem 0 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--danger);
}

.admin-users__delete-type {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-top: 0.9rem;
}

.admin-users__delete-keyword {
  font-weight: 700;
}

.admin-users-form__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.9rem;
}

.admin-users-form__section {
  margin: 1.4rem 0 0.6rem;
  padding-bottom: 0.35rem;
  border-bottom: 1px solid var(--border-light);
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--dark-green);
}

.admin-users-form__interests {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.45rem;
  border: none;
  padding: 0;
  margin: 0.4rem 0 0;
}

.admin-users-form__interest {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 0.9rem;
  color: var(--charcoal);
  cursor: pointer;
}

.admin-users-form__interest input {
  margin-top: 0.2rem;
  accent-color: var(--dark-green);
}

.form-field--full {
  grid-column: 1 / -1;
}

.form-label {
  display: block;
  margin-bottom: 0.3rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--charcoal);
}

.form-input {
  width: 100%;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
  font: inherit;
}

.form-input:disabled {
  background-color: var(--bg-light);
  color: var(--text-muted);
  cursor: not-allowed;
}

.form-checkbox {
  width: 16px;
  height: 16px;
  margin-right: 0.5rem;
  accent-color: var(--dark-green);
  vertical-align: -2px;
}

.admin-users-form__error {
  margin: 0 0 1rem;
  padding: 0.7rem 0.9rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
}

.admin-users-form__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-light);
}

.admin-users-form__footer-spacer {
  flex: 1;
}

.admin-users-form__spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  margin-right: 0.5rem;
  vertical-align: -2px;
  border: 2px solid rgba(255, 255, 255, 0.5);
  border-top-color: var(--white);
  border-radius: 50%;
  animation: admin-users-spin 0.8s linear infinite;
}

.admin-users-detail__section h3 {
  margin: 0 0 0.4rem;
  font-size: 0.9rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--dark-green);
}

.admin-users-detail__list {
  margin: 0;
}

.admin-users-detail__item {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--border-light);
}

.admin-users-detail__item dt {
  font-weight: 600;
  color: var(--text-muted);
  flex-shrink: 0;
}

.admin-users-detail__item dd {
  margin: 0;
  color: var(--charcoal);
  text-align: right;
  overflow-wrap: anywhere;
}

.admin-users-detail__supervisees {
  text-align: right;
}

.admin-users-detail__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 1.5rem;
}

@keyframes admin-users-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .admin-users-form__spinner {
    animation: none;
  }
}

@media (max-width: 640px) {
  .admin-users-form__grid {
    grid-template-columns: 1fr;
  }
  .admin-users__actions,
  .admin-users__actions--with-search {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>