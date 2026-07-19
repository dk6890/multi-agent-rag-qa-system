# 数据库设计

数据库使用 MySQL，默认库名为 `rag_qa`，字符集为 `utf8mb4`。本文档只描述 Java 后台业务数据库；Python RAG 的向量数据由 ChromaDB 等向量库维护，不在 MySQL 中保存 embedding 向量。

## 通用约定

- 主键统一使用 `BIGINT AUTO_INCREMENT`。
- 时间字段统一使用 `created_at`、`updated_at`。
- 文件状态枚举统一为 `UPLOADED`、`PROCESSING`、`SUCCESS`、`FAILED`。
- 表名使用小写下划线，字段名使用小写下划线。
- 业务接口对外返回驼峰字段，由 Backend Agent 在 DTO 层转换。

## 表关系

```text
knowledge_file 1 ---- n qa_reference
qa_session     1 ---- n qa_message
qa_message     1 ---- n qa_reference
```

## knowledge_file

保存用户上传文件的元数据和 RAG 入库状态。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK, AUTO_INCREMENT | 文件 ID。 |
| file_name | VARCHAR(255) | NOT NULL | 原始文件名。 |
| file_type | VARCHAR(32) | NOT NULL | 文件扩展类型，如 txt、pdf、docx。 |
| file_size | BIGINT | NOT NULL DEFAULT 0 | 文件大小，单位 byte。 |
| file_path | VARCHAR(1024) | NOT NULL | 服务端保存路径，不返回前端。 |
| status | VARCHAR(32) | NOT NULL | UPLOADED、PROCESSING、SUCCESS、FAILED。 |
| chunk_count | INT | NOT NULL DEFAULT 0 | 入库成功后的 chunk 数量。 |
| error_msg | TEXT | NULL | 入库失败原因。 |
| created_at | DATETIME | NOT NULL | 创建时间。 |
| updated_at | DATETIME | NOT NULL | 更新时间。 |

索引：

- `idx_status(status)`：按状态筛选文件。
- `idx_created_at(created_at)`：文件列表倒序查询。

## qa_session

保存问答会话。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK, AUTO_INCREMENT | 会话 ID。 |
| title | VARCHAR(255) | NOT NULL | 会话标题，默认可取用户首个问题前若干字符。 |
| created_at | DATETIME | NOT NULL | 创建时间。 |
| updated_at | DATETIME | NOT NULL | 更新时间。 |

索引：

- `idx_updated_at(updated_at)`：会话列表倒序查询预留。

## qa_message

保存用户消息和助手回答。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK, AUTO_INCREMENT | 消息 ID。 |
| session_id | BIGINT | NOT NULL | 所属会话 ID。 |
| role | VARCHAR(32) | NOT NULL | 消息角色：USER 或 ASSISTANT。 |
| content | TEXT | NOT NULL | 消息内容。 |
| created_at | DATETIME | NOT NULL | 创建时间。 |

索引：

- `idx_session_id(session_id)`：按会话查询消息。
- `idx_session_created_at(session_id, created_at)`：按会话时间顺序查询。

外键：

- `session_id` 引用 `qa_session(id)`。

## qa_reference

保存某条助手回答引用的检索来源。引用来源结构必须与 API 文档保持一致：`fileId`、`fileName`、`chunkText`、`score` 必填，可扩展 `chunkId`、`metadata`。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK, AUTO_INCREMENT | 引用 ID。 |
| message_id | BIGINT | NOT NULL | 助手回答消息 ID，对应 `qa_message.id`。 |
| file_id | BIGINT | NOT NULL | 来源文件 ID，对应 `knowledge_file.id`。 |
| file_name | VARCHAR(255) | NOT NULL | 来源文件名，冗余保存便于历史展示。 |
| chunk_id | VARCHAR(128) | NULL | Python RAG 侧 chunk 标识。 |
| chunk_text | TEXT | NOT NULL | 被引用的文本片段。 |
| score | DECIMAL(10,6) | NOT NULL DEFAULT 0 | 检索分数。 |
| metadata | JSON | NULL | 页码、标题、段落等扩展信息。 |
| created_at | DATETIME | NOT NULL | 创建时间。 |

索引：

- `idx_message_id(message_id)`：按消息查询引用。
- `idx_file_id(file_id)`：按文件追溯引用。

外键：

- `message_id` 引用 `qa_message(id)`。
- `file_id` 引用 `knowledge_file(id)`。

## 数据留存边界

- MySQL 保存文件元数据、问答记录和引用快照。
- MySQL 不保存文件二进制内容，不保存 embedding 向量。
- 文件物理路径仅用于后端与 Python RAG 服务间调用，不应返回给前端。
- API Key、模型配置、向量库路径等敏感配置不进入业务表，应通过配置文件或环境变量管理。
