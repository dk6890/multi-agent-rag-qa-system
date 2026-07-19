# 系统设计

## 总体架构

```text
Vue Frontend
  -> Java Backend
      -> MySQL
      -> Python RAG Service
          -> ChromaDB
      -> LLM Provider
```

## 模块职责

### Frontend Vue

- 提供用户操作界面。
- 调用 Java 后台 API。
- 展示文件状态、问答结果和引用来源。
- 不接触服务器本地文件路径。

### Java Backend

- 提供 `/api/files/upload`、`/api/files/list`、`/api/chat/ask`。
- 负责文件保存、元数据、状态流转、MySQL 持久化。
- 通过 HTTP 调用 Python RAG 服务。
- 调用大模型服务的入口由 `LlmClient` 提供，API Key 只走配置。

### Python RAG

- 提供 `/rag/index`、`/rag/search`。
- 完成文档解析、清洗、切分、embedding、ChromaDB 写入和检索。
- 不写 MySQL，不管理用户会话。

### MySQL

- 保存业务数据：文件、会话、消息、引用快照。
- 不保存 embedding 向量。

### ChromaDB

- 保存 chunk 文本、metadata 和向量。
- 当前使用本地持久化目录，生产部署需规划共享存储。

## 数据流

文件入库：

```text
Frontend upload -> Java save file/metadata -> Python /rag/index -> ChromaDB -> Java update status
```

问答：

```text
Frontend ask -> Java save user message -> Python /rag/search -> Java build prompt -> LLM Client -> save answer/reference -> Frontend display
```

## 安全约束

- 文件类型和大小必须校验。
- 文件名和保存路径必须防路径穿越。
- 本地 `filePath` 仅服务间传递，不返回前端。
- LLM API Key 不写入代码仓库。
- Python RAG 服务部署时不应直接暴露公网。
