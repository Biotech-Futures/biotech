-- =============================================
-- POSTGRESQL DDL FOR TARGET SCHEMA (new_schema.txt)
-- + NECESSARY COLUMNS ADDED FOR MATCHING ALGORITHM
-- =============================================
-- Additions (marked with comments) are drawn from our previous ERD
-- to enable better matching logic:
--   • year_min / year_max on groups          → year-level compatibility
--   • country_id / state_id on profiles      → geo / regional matching
--   • background on mentor_profile           → expertise / background scoring
--   • preassigned_group on student_profile   → pre-assignment handling
--   • New group_interest junction table      → group-level interest matching
-- All original columns, types, constraints, and relationships from new_schema.txt are preserved.

-- 1. Base / Lookup tables
CREATE TABLE countries (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    country_name VARCHAR(255) UNIQUE NOT NULL
);

CREATE TABLE roles (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    slug VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE areas_of_interest (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    interest_desc VARCHAR(255) UNIQUE NOT NULL
);

CREATE TABLE certificate_type (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name VARCHAR(255) UNIQUE NOT NULL,
    requires_number BOOLEAN NOT NULL,
    requires_expiry BOOLEAN NOT NULL
);

-- 2. Location & Track hierarchy
CREATE TABLE country_states (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    country_id BIGINT NOT NULL REFERENCES countries(id) ON DELETE RESTRICT,
    state_name VARCHAR(255) NOT NULL,
    UNIQUE (country_id, state_name)
);

CREATE TABLE tracks (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    track_code VARCHAR(100) UNIQUE NOT NULL,
    state_id BIGINT NOT NULL REFERENCES country_states(id) ON DELETE RESTRICT
);

-- 3. Core users
CREATE TABLE users (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    email VARCHAR(255) UNIQUE NOT NULL,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    track_id BIGINT NOT NULL REFERENCES tracks(id) ON DELETE RESTRICT,
    account_status VARCHAR(50) NOT NULL,
    invited_at TIMESTAMPTZ,
    activated_at TIMESTAMPTZ
);

-- 4. Role & Admin
CREATE TABLE user_role_assignment (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    UNIQUE (user_id, role_id, valid_from)
);

CREATE TABLE admin_scope (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    track_id BIGINT REFERENCES tracks(id) ON DELETE SET NULL,
    is_global BOOLEAN NOT NULL DEFAULT false
);

-- 5. Profiles (1:1 with users)
CREATE TABLE supervisor_profile (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    school_name VARCHAR(255) NOT NULL
);

CREATE TABLE mentor_profile (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    institution VARCHAR(255),
    max_group_count INT NOT NULL DEFAULT 3,
    -- === ADDED FOR MATCHING ALGORITHM ===
    country_id BIGINT REFERENCES countries(id) ON DELETE SET NULL,
    state_id BIGINT REFERENCES country_states(id) ON DELETE SET NULL,
    background VARCHAR(120),
    region VARCHAR(80)
);

CREATE TABLE student_profile (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    supervisor_user_id BIGINT REFERENCES supervisor_profile(user_id) ON DELETE SET NULL,
    school_name VARCHAR(255),
    year_level SMALLINT,
    join_permission_received BOOLEAN NOT NULL DEFAULT false,
    join_permission_response_id VARCHAR(255),
    -- === ADDED FOR MATCHING ALGORITHM ===
    country_id BIGINT REFERENCES countries(id) ON DELETE SET NULL,
    state_id BIGINT REFERENCES country_states(id) ON DELETE SET NULL,
    preassigned_group VARCHAR(64)
);

-- 6. Interests & Availability
CREATE TABLE student_interest (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    student_user_id BIGINT NOT NULL REFERENCES student_profile(user_id) ON DELETE CASCADE,
    interest_id BIGINT NOT NULL REFERENCES areas_of_interest(id) ON DELETE CASCADE
);

CREATE TABLE mentor_interest (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    mentor_user_id BIGINT NOT NULL REFERENCES mentor_profile(user_id) ON DELETE CASCADE,
    interest_id BIGINT NOT NULL REFERENCES areas_of_interest(id) ON DELETE CASCADE,
    UNIQUE (mentor_user_id, interest_id)
);

CREATE TABLE mentor_availability (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    mentor_user_id BIGINT NOT NULL REFERENCES mentor_profile(user_id) ON DELETE CASCADE,
    weekday SMALLINT NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    UNIQUE (mentor_user_id, weekday, start_time, end_time)
);

-- 7. Groups & Membership (core for matching)
CREATE TABLE groups (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    group_name VARCHAR(255) NOT NULL,
    track_id BIGINT NOT NULL REFERENCES tracks(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    -- === ADDED FOR MATCHING ALGORITHM ===
    year_min SMALLINT,
    year_max SMALLINT,
    lead_mentor_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    max_members INT DEFAULT 8
);

CREATE TABLE group_membership (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    group_id BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    membership_role VARCHAR(50),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    left_at TIMESTAMPTZ
);

-- === NEW JUNCTION TABLE (from our previous ERD) ===
CREATE TABLE group_interest (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    group_id BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    interest_id BIGINT NOT NULL REFERENCES areas_of_interest(id) ON DELETE CASCADE,
    UNIQUE (group_id, interest_id)
);

-- 8. Communication & Resources
CREATE TABLE messages (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    group_id BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    sender_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    message_text TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    edited_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
);

CREATE TABLE resources (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    uploader_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    track_id BIGINT REFERENCES tracks(id) ON DELETE SET NULL,
    visibility_scope VARCHAR(50) NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE resource_audience (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    resource_id BIGINT NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    role_id BIGINT REFERENCES roles(id) ON DELETE SET NULL,
    track_id BIGINT REFERENCES tracks(id) ON DELETE SET NULL
);

-- 9. Events & Announcements
CREATE TABLE events (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    host_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    track_id BIGINT REFERENCES tracks(id) ON DELETE SET NULL,
    event_type VARCHAR(100),
    start_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE event_rsvp (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rsvp_status VARCHAR(50) NOT NULL,
    responded_at TIMESTAMPTZ
);

CREATE TABLE announcements (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    author_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    track_id BIGINT REFERENCES tracks(id) ON DELETE SET NULL,
    visibility_scope VARCHAR(50) NOT NULL,
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ
);

CREATE TABLE announcement_audience (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    announcement_id BIGINT NOT NULL REFERENCES announcements(id) ON DELETE CASCADE,
    role_id BIGINT REFERENCES roles(id) ON DELETE SET NULL,
    track_id BIGINT REFERENCES tracks(id) ON DELETE SET NULL
);

-- 10. Certificates
CREATE TABLE mentor_certificate (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    mentor_profile_id BIGINT NOT NULL REFERENCES mentor_profile(user_id) ON DELETE CASCADE,
    certificate_type_id BIGINT NOT NULL REFERENCES certificate_type(id) ON DELETE RESTRICT,
    certificate_number VARCHAR(255),
    issued_by VARCHAR(255),
    issued_at DATE NOT NULL,
    expires_at DATE,
    file_url VARCHAR(500),
    verified_at TIMESTAMPTZ,
    verified_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL
);

-- 11. Sessions, Alerts, Audit, Matching
CREATE TABLE user_session (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);

CREATE TABLE alert (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    session_id BIGINT NOT NULL REFERENCES user_session(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_reason VARCHAR(255) NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT false,
    resolved_at TIMESTAMPTZ
);

CREATE TABLE audit_log (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    actor_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id BIGINT NOT NULL,
    action VARCHAR(100) NOT NULL,
    before_state JSONB,
    after_state JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE match_run (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    initiated_by_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    track_id BIGINT REFERENCES tracks(id) ON DELETE SET NULL,
    run_type VARCHAR(100) NOT NULL,
    rules_snapshot JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE match_recommendation (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    match_run_id BIGINT NOT NULL REFERENCES match_run(id) ON DELETE CASCADE,
    group_id BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    mentor_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    score DECIMAL(10,4),
    explanation JSONB,
    accepted BOOLEAN NOT NULL DEFAULT false
);