# 开发记录

## 2026-06-30 契约设计与骨架补齐阶段

本阶段由 Master Agent 固化跨 Agent 协作契约，仅修改文档和数据库初始化脚本，未进入前端、后端或 Python RAG 业务实现。

已固化决策：

- 统一响应格式为 `code`、`msg`、`data`。
- 文件状态枚举为 `UPLOADED`、`PROCESSING`、`SUCCESS`、`FAILED`。
- 前端调用 Java 后台接口固定为 `POST /api/files/upload`、`GET /api/files/list`、`POST /api/chat/ask`。
- Java 调用 Python RAG 接口固定为 `POST /rag/index`、`POST /rag/search`。
- 问答引用来源固定包含 `fileId`、`fileName`、`chunkText`、`score`，可扩展 `chunkId`、`metadata`。
- MySQL 业务表固定包含 `knowledge_file`、`qa_session`、`qa_message`、`qa_reference`。

后续建议：

- Backend Agent 下一阶段先实现接口壳子、DTO、数据库实体和 Mapper，不要提前实现复杂 RAG 或大模型逻辑。
- Python RAG Agent 应严格对齐 `/rag/index` 和 `/rag/search` 的请求与响应结构。
- Frontend Agent 应通过统一响应外壳读取业务结果，不直接依赖 HTTP 状态码。
- Supervisor Agent 应在各 Agent 完成骨架后复核接口字段、状态枚举和 SQL 表结构一致性。

## 2026-06-30 Backend 接口壳子和数据库层

本阶段由 Backend Agent 在后端边界内实现 Spring Boot 接口壳子和数据库访问层，未修改 `frontend-vue`、`rag-python` 和 `prompts`。

已完成：

- 将后端依赖调整为 MyBatis-Plus Spring Boot 3 starter。
- 添加 Mapper 扫描和配置属性扫描。
- 新增统一响应、业务异常、错误码、全局异常处理、文件状态枚举。
- 新增 `knowledge_file`、`qa_session`、`qa_message`、`qa_reference` 实体和 Mapper。
- 新增文件上传、文件列表、智能问答相关 DTO/VO。
- 新增 `FileController`、`ChatController`。
- 新增 `FileService`、`ChatService` 及实现类，覆盖文件校验、安全保存、状态流转、问答记录保存骨架。
- 新增 `PythonRagClient` 对齐 `/rag/index`、`/rag/search` 契约。
- 新增 `LlmClient` 配置化壳子，不硬编码 API Key。

验证：

- 使用项目内临时 Maven 仓库执行 `mvn -Dmaven.repo.local=..\\.m2\\repository -q -DskipTests compile` 编译通过。
- 编译生成的 `.m2` 和 `backend-java/target` 已清理。

后续建议：

- Python RAG Agent 实现 `/rag/index` 和 `/rag/search` 后，需用 Postman 或集成测试验证 Java 调 Python。
- 大模型提供商确定后，再补充 `LlmClient` 的真实 HTTP 请求结构。

## 2026-07-08 Python RAG、Frontend 与联调完成

本轮完成 Python RAG 服务、Vue 前端工作台和端到端联调。

已完成：

- Python RAG 实现 `GET /health`、`POST /rag/index`、`POST /rag/search`。
- Python RAG 支持 txt/pdf/docx 解析、清洗、切分、embedding、ChromaDB 入库与检索。
- embedding 优先使用 `sentence-transformers`，不可用时降级到确定性 HashEmbedding fallback。
- Frontend 实现文件上传、文件列表、问答、引用来源展示和加载/错误/空状态。
- Java Backend、Python RAG、Frontend 均完成基础构建或语法检查。
- Java 上传文件可调用 Python 入库，文件状态更新为 `SUCCESS`。
- Java 问答可调用 Python 检索并返回引用来源。

验证：

- Backend：`mvn -q -DskipTests compile` 通过。
- Frontend：`npm run build` 通过。
- Python：AST 语法检查通过。
- Python HTTP：`/health`、`/rag/index`、`/rag/search` 通过。
- Java HTTP：`/api/files/upload`、`/api/files/list`、`/api/chat/ask` 通过。

剩余限制：

- `LlmClient` 尚未绑定具体大模型供应商，当前返回配置化占位回答。
- 当前环境中 `sentence-transformers` 存在 numpy 二进制兼容问题，已降级 HashEmbedding fallback。
- 生产环境仍需补充鉴权、日志、监控、对象存储和容器化部署。

## 2026-11-06 结构分片、真实向量和混合检索升级

- 尝试恢复原 Master、Python RAG、Supervisor 子 Agent，旧会话受账户用量限制；当前监督任务继续完成修改和联调，未新建替代 Agent。
- 参考 RAGFlow v0.27.3 的解析、QA 分片和检索源码，保持 Java/Vue 核心接口兼容。
- 修复 pandas 1.5.1 与 numpy 2.2.6 的 ABI 冲突，在项目隔离环境安装 pandas 2.x；下载并验证原多语言 MiniLM，384 维、原生 128 token。
- 禁止模型失败自动生成 HashEmbedding；提供明确失败和词法降级标记，健康接口可查看模型 readiness。
- 增加严格编码读取、保守清洗、Word 标题与表格、PDF 页码与页边噪声处理，以及结构/问答分片；标题与正文共同受实际 tokenizer 上限约束。
- 使用 jieba + BM25Plus + 向量召回 + RRF 排名融合，保留排名诊断信息。
- 新集合按权重等内容指纹隔离；文件新代次写完再发布，失败保留旧代次，成功后清理旧尾块。原 `rag_chunks` 及目录备份保留。
- 更新准备、启动、检查、可读查看和重建脚本；重建同步 MySQL `chunk_count`。
- 46 项回归测试通过。实际 5 个原文件重建成功，语义分片共 29 条，其中课程文件 25 条；原 sun 问题及写作改述问题均召回课程资料和真实向量结果。
- 三项服务及前端文件列表代理通过健康检查。本轮未调用付费 LLM；最终回答评估和复杂 PDF/OCR 留待专项验证。
