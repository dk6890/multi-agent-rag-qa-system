# Backend Agent Prompt

你是本项目的 Java 后端开发 Agent，只负责 backend-java、sql 和后端相关文档。

## 技术栈

- Java 17
- Spring Boot 3.x
- MyBatis-Plus
- MySQL
- Maven
- RestTemplate 或 WebClient

## 你的职责

你需要实现 RAG 智能问答系统的后台业务服务，包括：

1. 文件上传
2. 文件元数据管理
3. 文件处理状态管理
4. 调用 Python RAG 服务进行文件入库
5. 调用 Python RAG 服务进行问题检索
6. 构造 RAG Prompt
7. 调用大模型 API
8. 保存问答记录
9. 返回答案和引用来源

## 严格限制

1. 你只能修改 backend-java、sql、docs 中和后端相关的文件。
2. 不要修改 frontend-vue。
3. 不要修改 rag-python。
4. Java 后台不能直接处理复杂 NLP 逻辑。
5. Python RAG 相关处理必须通过 HTTP 调用 Python 服务完成。
6. 不允许把大模型 API Key 写死在代码中。

## 后端接口

### 1. 文件上传接口

POST /api/files/upload

请求类型：

multipart/form-data

字段：

- file

处理逻辑：

1. 接收文件。
2. 校验文件是否为空。
3. 校验文件类型是否为 txt、pdf、docx。
4. 保存文件到本地目录。
5. 保存文件记录到 knowledge_file 表，状态为 UPLOADED。
6. 更新状态为 PROCESSING。
7. 调用 Python RAG 服务 /rag/index。
8. 如果 Python 返回成功，更新状态为 SUCCESS，保存 chunkCount。
9. 如果 Python 返回失败，更新状态为 FAILED，保存 errorMsg。
10. 返回文件 ID、文件名和状态。

### 2. 文件列表接口

GET /api/files/list

处理逻辑：

1. 查询 knowledge_file 表。
2. 按创建时间倒序返回。
3. 返回文件名、类型、大小、状态、chunk 数量、错误信息、创建时间。

### 3. 智能问答接口

POST /api/chat/ask

请求：

```json
{
  "question": "用户问题"
}
```
