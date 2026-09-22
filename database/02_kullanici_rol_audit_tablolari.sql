
-- 1. ROLES
CREATE TABLE roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) UNIQUE NOT NULL
);


-- 2. USERS
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,

    role_id INT NOT NULL
        REFERENCES roles(role_id),

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


-- 3. STAFF
CREATE TABLE staff (
    staff_id SERIAL PRIMARY KEY,

    user_id INT UNIQUE NOT NULL
        REFERENCES users(user_id),

    staff_code VARCHAR(50) UNIQUE NOT NULL,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


-- 4. AUDIT EVENT TYPES
CREATE TYPE audit_event_type AS ENUM (
    'LOGIN',
    'LOGIN_FAILED',
    'CREATE',
    'UPDATE',
    'CANCEL',
    'ROLE_CHANGE',
    'DEVICE_STATUS_CHANGE'
);


-- 5. AUDIT LOGS
CREATE TABLE audit_logs (
    audit_id BIGSERIAL PRIMARY KEY,

    user_id INT
        REFERENCES users(user_id),

    event_type audit_event_type NOT NULL,

    target_table VARCHAR(100),

    target_record_id INT,

    created_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
); 