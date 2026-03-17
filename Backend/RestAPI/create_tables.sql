drop TABLE users if exists;
drop TABLE groups if exists;
drop TABLE group_members if exists;
drop TABLE transactions if exists;
drop TABLE transaction_splits if exists;
drop TABLE refresh_tokens if exists;


CREATE TABLE users (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    password TEXT NOT NULL
);


CREATE TABLE groups (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE group_members (
    group_id UUID NOT NULL,
    user_id UUID NOT NULL,
    joined_at TIMESTAMP NOT NULL,

    PRIMARY KEY (group_id, user_id),

    FOREIGN KEY (group_id)
        REFERENCES groups(id)
        ON DELETE CASCADE,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

CREATE INDEX idx_group_members_user
ON group_members(user_id); -- para cuando se busque a que grupos pertenece un usuario


CREATE TABLE transactions (
    id UUID PRIMARY KEY,

    group_id UUID NOT NULL,
    paid_by UUID NOT NULL,

    description TEXT,
    amount NUMERIC(12,2) NOT NULL,

    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP,

    FOREIGN KEY (group_id)
        REFERENCES groups(id)
        ON DELETE CASCADE,

    FOREIGN KEY (group_id, paid_by)
        REFERENCES group_members (group_id, user_id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_transactions_group_created
ON transactions(group_id, created_at DESC);

CREATE TABLE transaction_splits (
    transaction_id UUID NOT NULL,
    user_id UUID NOT NULL,

    amount NUMERIC(12,2) NOT NULL,

    PRIMARY KEY (transaction_id, user_id),

    FOREIGN KEY (transaction_id)
        REFERENCES transactions(id)
        ON DELETE CASCADE,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
);

CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);
