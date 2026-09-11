CREATE TABLE IF NOT EXISTS images (
    id UUID PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(64) NOT NULL,
    upload_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(32) NOT NULL,
    segmentation_method VARCHAR(16) NOT NULL,
    confidence_score DOUBLE PRECISION,
    original_path TEXT NOT NULL,
    extracted_path TEXT,
    error_code VARCHAR(64),
    owner_subject VARCHAR(255) NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    width INTEGER,
    height INTEGER
);

CREATE INDEX IF NOT EXISTS ix_images_owner_uploaded ON images (owner_subject, upload_date DESC);

CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_subject VARCHAR(255) NOT NULL,
    action VARCHAR(80) NOT NULL,
    image_id UUID REFERENCES images(id) ON DELETE SET NULL,
    outcome VARCHAR(32) NOT NULL,
    correlation_id VARCHAR(64) NOT NULL,
    client_ip_hash VARCHAR(64),
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);