# 需求分析

## 项目目标

建设一个多 Agent 协作开发的 RAG 智能问答系统，支持用户上传知识文件，系统完成文档入库、向量检索、问答生成和引用来源展示。

## 核心需求

1. 文件上传：支持 `txt`、`pdf`、`docx`。
2. 文件元数据管理：记录文件名、类型、大小、状态、chunk 数量、错误信息。
3. 文档处理：由 Python RAG 服务完成解析、清洗、切分、embedding 和向量库写入。
4. 文件状态流转：统一使用 `UPLOADED`、`PROCESSING`、`SUCCESS`、`FAILED`。
5. 智能问答：Java 接收问题，调用 Python 检索，构造 Prompt，并调用大模型壳子。
6. 引用来源展示：返回 `fileId`、`fileName`、`chunkText`、`score`、可选 `chunkId`、`metadata`。
7. 前端工作台：提供上传、文件列表、问答、引用展示、错误和加载状态。
8. 文档与测试：输出设计文档、API 文档、测试用例、部署说明和开发记录。

## 非目标

- Python RAG 不管理用户会话和 MySQL 业务表。
- Java 后台不直接实现复杂 NLP、embedding 或向量检索。
- 当前阶段不绑定具体 LLM 供应商，不提交 API Key。

## 验收口径

- Java、Python、Frontend 三个服务可分别启动或构建。
- Java 上传接口可调用 Python `/rag/index` 并更新文件状态。
- Java 问答接口可调用 Python `/rag/search` 并返回引用来源。
- 前端能按统一响应 `code/msg/data` 展示上传、列表、问答和引用。
