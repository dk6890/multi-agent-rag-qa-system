CREATE DATABASE IF NOT EXISTS rag_qa DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE rag_qa;

CREATE TABLE IF NOT EXISTS knowledge_file (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(32) NOT NULL,
    file_size BIGINT NOT NULL DEFAULT 0,
    file_path VARCHAR(1024) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'UPLOADED',
    chunk_count INT NOT NULL DEFAULT 0,
    error_msg TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    CONSTRAINT chk_knowledge_file_status CHECK (status IN ('UPLOADED', 'PROCESSING', 'SUCCESS', 'FAILED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS qa_session (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS qa_message (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id BIGINT NOT NULL,
    role VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_id (session_id),
    INDEX idx_session_created_at (session_id, created_at),
    CONSTRAINT chk_qa_message_role CHECK (role IN ('USER', 'ASSISTANT')),
    CONSTRAINT fk_qa_message_session FOREIGN KEY (session_id) REFERENCES qa_session (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS qa_reference (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    message_id BIGINT NOT NULL,
    file_id BIGINT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    chunk_id VARCHAR(128) NULL,
    chunk_text TEXT NOT NULL,
    score DECIMAL(10, 6) NOT NULL DEFAULT 0,
    metadata JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_message_id (message_id),
    INDEX idx_file_id (file_id),
    CONSTRAINT fk_qa_reference_message FOREIGN KEY (message_id) REFERENCES qa_message (id),
    CONSTRAINT fk_qa_reference_file FOREIGN KEY (file_id) REFERENCES knowledge_file (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
