# Multi-Agent RAG QA System

本项目采用多 Agent 协作方式搭建 RAG 问答系统。

## Agent 分工

- Master Agent：统筹任务、拆解需求、协调其他 Agent。
- Frontend Agent：负责 Vue 前端页面、交互与接口接入。
- Backend Agent：负责 Java 后台服务、业务接口与数据持久化。
- Python RAG Agent：负责文档处理、向量化、检索与生成链路。
- Supervisor Agent：负责需求、设计、测试、部署等文档输出与质量监督。

详细 Prompt 位于 `prompts/` 目录。
