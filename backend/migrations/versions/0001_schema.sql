CREATE TABLE blobs (
	sha256 VARCHAR(64) NOT NULL,
	storage_key VARCHAR(100) NOT NULL,
	size_bytes INTEGER NOT NULL,
	media_type VARCHAR(50) NOT NULL,
	PRIMARY KEY (sha256)
)

;


CREATE TABLE users (
	id VARCHAR(36) NOT NULL,
	username VARCHAR(80) NOT NULL,
	password_hash TEXT NOT NULL,
	role VARCHAR(20) NOT NULL,
	active BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (username)
)

;


CREATE TABLE documents (
	id VARCHAR(36) NOT NULL,
	name VARCHAR(255) NOT NULL,
	blob_hash VARCHAR(64) NOT NULL,
	created_by VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	status VARCHAR(20) NOT NULL,
	kind VARCHAR(20) NOT NULL,
	classification JSONB NOT NULL,
	duplicate_of VARCHAR(36),
	deleted BOOLEAN NOT NULL,
	index_status VARCHAR(30) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(blob_hash) REFERENCES blobs (sha256),
	FOREIGN KEY(created_by) REFERENCES users (id),
	FOREIGN KEY(duplicate_of) REFERENCES documents (id)
)

;


CREATE TABLE export_batches (
	id VARCHAR(36) NOT NULL,
	created_by VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	format VARCHAR(10) NOT NULL,
	content_hash VARCHAR(64) NOT NULL,
	revision_ids JSONB NOT NULL,
	content TEXT NOT NULL,
	idempotency_key VARCHAR(100) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(created_by) REFERENCES users (id),
	UNIQUE (idempotency_key)
)

;


CREATE TABLE login_sessions (
	token_hash VARCHAR(64) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	csrf_token VARCHAR(80) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (token_hash),
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;


CREATE TABLE audit_events (
	id VARCHAR(36) NOT NULL,
	actor_id VARCHAR(36),
	document_id VARCHAR(36),
	action VARCHAR(80) NOT NULL,
	details JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(actor_id) REFERENCES users (id),
	FOREIGN KEY(document_id) REFERENCES documents (id)
)

;


CREATE TABLE document_chunks (
	id VARCHAR(36) NOT NULL,
	document_id VARCHAR(36) NOT NULL,
	page_number INTEGER NOT NULL,
	position INTEGER NOT NULL,
	text TEXT NOT NULL,
	embedding VECTOR(768),
	model VARCHAR(120),
	PRIMARY KEY (id),
	UNIQUE (document_id, page_number, position),
	FOREIGN KEY(document_id) REFERENCES documents (id)
)

;


CREATE TABLE invoices (
	id VARCHAR(36) NOT NULL,
	document_id VARCHAR(36) NOT NULL,
	version INTEGER NOT NULL,
	review_status VARCHAR(20) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (document_id),
	FOREIGN KEY(document_id) REFERENCES documents (id)
)

;


CREATE TABLE jobs (
	id VARCHAR(36) NOT NULL,
	document_id VARCHAR(36) NOT NULL,
	state VARCHAR(20) NOT NULL,
	stage VARCHAR(30) NOT NULL,
	attempts INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	started_at TIMESTAMP WITH TIME ZONE,
	finished_at TIMESTAMP WITH TIME ZONE,
	lease_until TIMESTAMP WITH TIME ZONE,
	heartbeat_at TIMESTAMP WITH TIME ZONE,
	error VARCHAR(500),
	PRIMARY KEY (id),
	FOREIGN KEY(document_id) REFERENCES documents (id)
)

;


CREATE TABLE extraction_runs (
	id VARCHAR(36) NOT NULL,
	job_id VARCHAR(36) NOT NULL,
	document_id VARCHAR(36) NOT NULL,
	result JSONB NOT NULL,
	duration_ms INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (job_id),
	FOREIGN KEY(job_id) REFERENCES jobs (id),
	FOREIGN KEY(document_id) REFERENCES documents (id)
)

;


CREATE TABLE invoice_revisions (
	id VARCHAR(36) NOT NULL,
	invoice_id VARCHAR(36) NOT NULL,
	version INTEGER NOT NULL,
	vendor_name VARCHAR(256),
	invoice_number VARCHAR(256),
	invoice_date DATE,
	currency VARCHAR(3),
	total NUMERIC(18, 2),
	payload JSONB NOT NULL,
	issues JSONB NOT NULL,
	created_by VARCHAR(36) NOT NULL,
	reason VARCHAR(500) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (invoice_id, version),
	FOREIGN KEY(invoice_id) REFERENCES invoices (id),
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;


CREATE TABLE approvals (
	id VARCHAR(36) NOT NULL,
	revision_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	decision VARCHAR(20) NOT NULL,
	reason VARCHAR(500) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (revision_id),
	FOREIGN KEY(revision_id) REFERENCES invoice_revisions (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;


CREATE TABLE pages (
	id VARCHAR(36) NOT NULL,
	run_id VARCHAR(36) NOT NULL,
	document_id VARCHAR(36) NOT NULL,
	number INTEGER NOT NULL,
	text TEXT NOT NULL,
	data JSONB NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (run_id, number),
	FOREIGN KEY(run_id) REFERENCES extraction_runs (id),
	FOREIGN KEY(document_id) REFERENCES documents (id)
)

;

CREATE INDEX ix_documents_created_by ON documents (created_by);

CREATE INDEX ix_documents_blob_hash ON documents (blob_hash);

CREATE INDEX ix_documents_status ON documents (status);

CREATE INDEX ix_audit_events_document_id ON audit_events (document_id);

CREATE INDEX ix_document_chunks_document_id ON document_chunks (document_id);

CREATE INDEX ix_invoices_review_status ON invoices (review_status);

CREATE INDEX ix_jobs_state ON jobs (state);

CREATE INDEX ix_jobs_document_id ON jobs (document_id);

CREATE INDEX ix_job_claim ON jobs (state, created_at);

CREATE INDEX ix_extraction_runs_document_id ON extraction_runs (document_id);

CREATE INDEX ix_invoice_revisions_invoice_id ON invoice_revisions (invoice_id);

CREATE INDEX ix_pages_document_id ON pages (document_id);
