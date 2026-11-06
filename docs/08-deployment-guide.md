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

```powershell
# 项目根目录：首次安装隔离依赖并下载免费本地 Embedding 模型
powershell -ExecutionPolicy Bypass -File scripts\prepare-rag.ps1

# 日常可直接统一启动前端、Java 和 Python
powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1

# 单独运行 Python 时使用项目虚拟环境
cd rag-python
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

可选环境变量：

- `VECTOR_STORE_PATH`：向量库目录
- `EMBEDDING_MODEL_NAME`：embedding 模型名
- `EMBEDDING_LOCAL_PATH`：本地模型路径，默认 `storage/models/multilingual-minilm`

普通请求默认不联网下载模型。模型和虚拟环境在 D 盘项目内；首次安装脚本复用系统大型运行库，同时在项目环境中覆盖不兼容的 pandas。更换模型名称时应同时设置匹配的本地模型目录，并重新索引，不能继续读取旧模型的语义向量。

验证：

```bash
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/health?loadEmbedding=true"
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

本机大模型配置已采用 `backend-java/config/local-secret.yml`，通过 Spring 配置导入读取，该文件被 Git 忽略。不要将密钥写入版本库或部署文档。

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
- 模型不可用时索引明确失败，不再生成 HashEmbedding；查询只允许有标记的 BM25 词法降级。
- 当前本地 MiniLM 的原生输入上限是 128 token，新索引与旧集合隔离；升级后执行 `scripts/reindex-all.ps1` 重建，并同步 MySQL 分片数量。
- 扫描 PDF 暂无 OCR；复杂双栏、公式和图片正文需要后续专用解析器。当前索引发布使用单 Uvicorn 写入进程。
- 本地部署使用本地上传目录和本地 ChromaDB，生产环境需规划共享存储、权限隔离、日志和监控。

完整参数、备份与回归说明见 [09-rag-upgrade.md](09-rag-upgrade.md)。
