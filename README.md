# multi-agent-rag-qa-system

多 Agent 协作的 RAG 智能问答系统，包含 Vue 前端、Java Spring Boot 后台、Python FastAPI RAG 服务、MySQL 业务库、ChromaDB 向量库和项目文档。

## 模块职责

- `frontend-vue/`：Vue3 + Vite 前端页面，负责文件上传、文件列表、问答和引用展示。
- `backend-java/`：Spring Boot 3 + MyBatis-Plus 后台，负责业务接口、MySQL 持久化、调用 Python RAG、调用大模型。
- `rag-python/`：FastAPI + ChromaDB RAG 服务，负责文档解析、清洗、分片、Embedding、向量检索。
- `sql/init.sql`：MySQL 初始化脚本。
- `prompts/`：Master / Frontend / Backend / Python RAG / Supervisor Agent Prompt。
- `docs/`：需求、设计、接口、测试、部署等文档。
- `scripts/`：本地 harness 脚本，用于统一启动、停止、检查和重建索引。

## Harness 脚本

在项目根目录执行：

```powershell
# 首次准备依赖和本地语义模型
powershell -ExecutionPolicy Bypass -File scripts\prepare-rag.ps1

# 日常启动
powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1
```

启动全部服务：

- Frontend: `http://127.0.0.1:5173/`
- Backend: `http://127.0.0.1:8080`
- Python RAG: `http://127.0.0.1:8000`

常用脚本：

```powershell
# 停止 5173 / 8080 / 8000
powershell -ExecutionPolicy Bypass -File scripts\stop-all.ps1

# 启动全部服务
powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1

# 启动并按 MySQL 中 SUCCESS 文件重建向量索引
powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1 -Reindex

# 健康检查：前台、后台、Python、Chroma chunk 数量
powershell -ExecutionPolicy Bypass -File scripts\health-check.ps1

# 将 MySQL 中 SUCCESS 文件重新写入 ChromaDB
powershell -ExecutionPolicy Bypass -File scripts\reindex-all.ps1

# 查看 ChromaDB 中可读 chunk 内容
powershell -ExecutionPolicy Bypass -File scripts\show-vector-store.ps1 -Limit 5 -PreviewChars 300
```

## 本地配置

Java 后台默认读取：

- MySQL: `jdbc:mysql://127.0.0.1:3306/rag_qa`
- 用户名: `root`
- 密码: `1234`
- Python RAG: `http://localhost:8000`

大模型密钥放在本地文件：

```text
backend-java/config/local-secret.yml
```

该文件已加入 `.gitignore`，不要提交。

## RAG 流程

文件入库：

1. 前端调用 `POST /api/files/upload`。
2. Java 保存文件到 `backend-java/storage/uploads`。
3. Java 写入 MySQL `knowledge_file`。
4. Java 调 Python `/rag/index`。
5. Python 解析文件、清洗文本、切分 chunk、生成 embedding。
6. Python 写入 ChromaDB。
7. Java 更新文件状态和 chunk 数量。

智能问答：

1. 前端调用 `POST /api/chat/ask`。
2. Java 调 Python `/rag/search`。
3. Python 从 ChromaDB 检索相关片段。
4. Java 构造 RAG Prompt。
5. Java 调 DeepSeek 兼容接口。
6. Java 保存问答记录和引用来源。
7. 前端展示回答和 references。

## 分片策略

配置在 `rag-python/config.py`：

```python
chunk_size = 800
chunk_overlap = 120
default_top_k = 5
```

文件类型：

- `.txt`：严格读取 UTF-8、UTF-16/32 BOM、GB18030 等编码，保留标题和问答结构。
- `.pdf`：使用 `pdfplumber` 提取正文、表格及页码，保守清理重复页边文本；扫描件需要 OCR。
- `.docx`：按顺序提取段落、章节标题和表格，表格数据保留列名。

新分片使用递归段落/句子切分，标题、问题和正文一起按实际模型 tokenizer 限长。当前多语言 MiniLM 为 384 维、原生上限 128 token；800/120 仍兼容旧字符接口，新入口按其比值控制重叠。检索使用中文分词 BM25 + 向量召回 + RRF 融合。

实现、参数、索引迁移和限制见 [RAG 升级说明](docs/09-rag-upgrade.md)。

## 向量库查看

当前 ChromaDB 路径：

```text
rag-python/storage/vector_store/chroma.sqlite3
```

不要用文本编辑器打开 SQLite 文件，看到乱码是正常的。推荐用脚本查看可读内容：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\show-vector-store.ps1
```

## 已知说明

- 启动器优先使用 `rag-python/.venv`，解决系统 pandas/numpy 不兼容问题；本地模型位于 `rag-python/storage/models/multilingual-minilm`。
- 不再自动使用 HashEmbedding 入库。模型不可用时索引明确失败，查询仅作有标记的 BM25 降级。
- 新语义索引使用 `rag_chunks_v2_<模型指纹>`，旧 `rag_chunks` 保留且只用于尚未迁移文件的词法检索。升级后要重建原文件，脚本会同步更新 MySQL 分片数。
- 如果 MySQL 里文件是 `SUCCESS`，但 Chroma chunk 数量为 0，执行 `scripts\reindex-all.ps1`。
- 如果前台接口异常，先执行 `scripts\health-check.ps1` 判断是哪一段服务断了。
