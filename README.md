# multi-agent-rag-qa-system

多 Agent 协作的 RAG 智能问答系统，包含 Java 后台、Python RAG 服务、Vue3 前端、数据库脚本和项目文档。

## 功能

- 文件上传与文件元数据管理
- 文档解析、清洗、切分
- Embedding 生成与 ChromaDB 向量存储
- 向量检索与引用来源返回
- Java 后台问答编排、状态流转、问答记录保存
- Vue3 单页工作台：上传、文件列表、问答、引用展示

## 模块

- `backend-java/`：Spring Boot 3 + MyBatis-Plus 后台
- `rag-python/`：FastAPI + ChromaDB RAG 服务
- `frontend-vue/`：Vue3 + Vite 前端
- `sql/init.sql`：MySQL 初始化脚本
- `docs/`：需求、设计、接口、测试、部署文档
- `prompts/`：Master/Frontend/Backend/Python RAG/Supervisor Agent Prompt

## 本地启动

1. 初始化 MySQL：

```bash
mysql -u root -p < sql/init.sql
```

2. 启动 Python RAG：

```bash
cd rag-python
pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

3. 启动 Java 后台：

```bash
cd backend-java
mvn spring-boot:run
```

4. 启动前端：

```bash
cd frontend-vue
npm install
npm run dev
```

默认地址：

- Backend: `http://127.0.0.1:8080`
- Python RAG: `http://127.0.0.1:8000`
- Frontend: Vite 输出地址

## 已验证

- Backend Maven 编译通过
- Frontend `npm run build` 通过
- Python RAG AST 语法检查通过
- Python `/rag/index`、`/rag/search` HTTP 接口通过
- Java 上传文件可调用 Python 入库，文件状态为 `SUCCESS`
- Java 问答可调用 Python 检索并返回 `references`

## 已知限制

- `LlmClient` 当前为配置化壳子，未绑定具体大模型供应商。
- 当前 Python 环境中 `sentence-transformers` 可能因 numpy 二进制兼容问题降级到 HashEmbedding fallback，可用于流程联调，不代表真实语义检索质量。
- Python RAG 与 Java Backend 目前使用本地文件路径和本地向量库，生产部署需规划共享存储或对象存储。
