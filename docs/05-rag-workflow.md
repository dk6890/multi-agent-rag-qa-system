# RAG 工作流

本文档固化文件入库流程和问答流程，作为 Backend Agent、Python RAG Agent、Frontend Agent 后续实现边界。

## 文件入库流程

1. 前端通过 `POST /api/files/upload` 上传文件，字段名固定为 `file`。
2. Java 后台校验文件：
   - 文件不能为空。
   - 文件类型应限制为 txt、pdf、docx 等约定类型。
   - 文件大小应受配置限制。
   - 文件名和保存路径必须避免路径穿越。
3. Java 后台将文件保存到服务端本地上传目录。
4. Java 后台写入 `knowledge_file`：
   - `status=UPLOADED`
   - 保存 `file_name`、`file_type`、`file_size`、`file_path`
5. Java 后台将文件状态更新为 `PROCESSING`。
6. Java 后台调用 Python RAG：`POST /rag/index`。
7. Python RAG 按固定职责处理文件：
   - 读取 `fileId`、`filePath`、`fileName`。
   - 解析 txt、pdf、docx 文档。
   - 清洗文本。
   - 切分 chunk。
   - 生成 embedding。
   - 写入 ChromaDB 等向量库。
   - 返回 `fileId` 和 `chunkCount`。
8. Java 后台根据 Python RAG 响应更新 `knowledge_file`：
   - 成功：`status=SUCCESS`，写入 `chunk_count`，清空 `error_msg`。
   - 失败：`status=FAILED`，写入 `error_msg`。
9. Java 后台向前端返回统一响应：
   - `code`
   - `msg`
   - `data.fileId`
   - `data.fileName`
   - `data.status`
10. 前端通过 `GET /api/files/list` 刷新文件列表并展示处理状态。

## 文件状态流转

```text
UPLOADED -> PROCESSING -> SUCCESS
                       -> FAILED
```

约束：

- `UPLOADED` 表示元数据已落库。
- `PROCESSING` 表示 Java 已发起或准备发起 RAG 入库。
- `SUCCESS` 表示向量库已写入成功。
- `FAILED` 表示入库链路失败，必须保存失败原因。

## 问答流程

1. 前端通过 `POST /api/chat/ask` 提交问题。
2. Java 后台校验问题不能为空。
3. Java 后台处理会话：
   - 请求包含 `sessionId` 时，使用已有会话。
   - 请求不包含 `sessionId` 时，创建 `qa_session`。
4. Java 后台保存用户问题到 `qa_message`，`role=USER`。
5. Java 后台调用 Python RAG：`POST /rag/search`。
6. Python RAG 执行向量检索：
   - 将问题向量化。
   - 从向量库检索 topK 相关 chunk。
   - 返回统一 `references` 结构。
7. Java 后台基于用户问题和 `references` 构造 Prompt。
8. Java 后台调用大模型生成回答。
9. Java 后台保存助手回答到 `qa_message`，`role=ASSISTANT`。
10. Java 后台将引用来源保存到 `qa_reference`：
    - `file_id`
    - `file_name`
    - `chunk_id`
    - `chunk_text`
    - `score`
    - `metadata`
11. Java 后台向前端返回统一响应，包含：
    - `sessionId`
    - `question`
    - `answer`
    - `references`
12. 前端展示回答和引用来源。

## Java 与 Python 的边界

- Java 负责上传、元数据、状态流转、问答记录、大模型调用和对前端 API。
- Python RAG 负责文档解析、文本清洗、chunk 切分、embedding、向量库写入和向量检索。
- Python RAG 不直接写 MySQL，不管理用户会话，不调用大模型。
- Java 不直接实现复杂 NLP、embedding 或向量检索逻辑。

## 异常处理要求

- 文件为空：Java 直接返回 `code=400`。
- 文件类型不支持：Java 直接返回 `code=400`。
- 文件保存失败：Java 返回非 200，不调用 Python RAG。
- Python RAG 服务不可用：Java 将文件状态置为 `FAILED` 或返回问答失败。
- Python RAG 入库失败：Java 将文件状态置为 `FAILED` 并保存 `error_msg`。
- 向量库为空或检索结果为空：Java 仍可调用大模型，但必须返回空 `references`，并在 Prompt 中说明未检索到可靠上下文。
- 大模型调用失败：Java 返回非 200，并保留用户问题记录；助手回答可不落库或落库为失败占位，具体由 Backend Agent 实现时细化。
- 数据库保存失败：Java 返回非 200，并记录服务日志。

## 安全要求

- 不得将 API Key 写死在代码或文档示例中。
- 不得把服务器本地绝对文件路径返回给前端。
- 上传文件名必须做安全处理，避免路径穿越。
- 文件类型和文件大小必须有限制。
- Python RAG 接口仅作为服务间接口使用，部署时应避免直接暴露到公网。
