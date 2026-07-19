# 部署指南

## 依赖

- JDK 17
- Maven
- Python 3.10+
- Node.js 18+
- MySQL 8.x 或兼容版本

## 1. 初始化数据库

```bash
mysql -u root -p < sql/init.sql
```

默认库名：`rag_qa`。

核心表：

- `knowledge_file`
- `qa_session`
- `qa_message`
- `qa_reference`

## 2. 启动 Python RAG

```bash
cd rag-python
pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

可选环境变量：

- `VECTOR_STORE_PATH`：向量库目录
- `EMBEDDING_MODEL_NAME`：embedding 模型名

验证：

```bash
curl http://127.0.0.1:8000/health
```

## 3. 启动 Java Backend

```bash
cd backend-java
mvn spring-boot:run
```

常用配置：

- `DB_URL`
- `DB_USERNAME`
- `DB_PASSWORD`
- `RAG_PYTHON_SERVICE_URL`
- `LLM_API_KEY`

验证：

```bash
curl http://127.0.0.1:8080/api/files/list
```

## 4. 启动 Frontend

```bash
cd frontend-vue
npm install
npm run dev
```

生产构建：

```bash
npm run build
```

## 联调顺序

1. 启动 MySQL。
2. 执行 `sql/init.sql`。
3. 启动 Python RAG。
4. 启动 Java Backend。
5. 启动 Frontend。
6. 上传 txt/pdf/docx 文件。
7. 确认文件状态为 `SUCCESS`。
8. 提问并确认返回 `answer` 与 `references`。

## 已知限制

- 未配置具体 LLM 供应商时，Java 返回占位回答，但仍会完成问题记录、检索和引用保存。
- 若 `sentence-transformers` 或模型下载不可用，Python RAG 会降级到 HashEmbedding fallback。
- 本地部署使用本地上传目录和本地 ChromaDB，生产环境需规划共享存储、权限隔离、日志和监控。
