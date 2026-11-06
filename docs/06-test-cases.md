# 测试用例

## 已执行验证

| 编号 | 范围 | 命令或操作 | 结果 |
| --- | --- | --- | --- |
| T-01 | Backend 编译 | `mvn -q -DskipTests compile` | 通过 |
| T-02 | Frontend 构建 | `npm run build` | 通过 |
| T-03 | Python 语法 | AST 解析 15 个 `.py` 文件 | 通过 |
| T-04 | Python 健康检查 | `GET /health` | 返回 `status=ok` |
| T-05 | Python 入库 | `POST /rag/index` 上传 txt 测试文件 | 返回 `code=200`、`chunkCount=1` |
| T-06 | Python 检索 | `POST /rag/search` | 返回 `references` |
| T-07 | Java 文件上传联调 | `POST /api/files/upload` | 返回 `SUCCESS` |
| T-08 | Java 问答联调 | `POST /api/chat/ask` | 返回 `code=200`、`answer`、`references` |

## Backend 测试

| 编号 | 用例 | 预期 |
| --- | --- | --- |
| BE-01 | 空文件上传 | 返回 `code=400`，不调用 Python |
| BE-02 | 不支持文件类型 | 返回失败，文件不进入可用状态 |
| BE-03 | 合法 txt 上传 | 保存文件和元数据，状态最终为 `SUCCESS` |
| BE-04 | Python 不可用时上传 | 文件状态更新为 `FAILED`，保存错误信息 |
| BE-05 | 文件列表 | 按创建时间倒序返回，不包含本地 `filePath` |
| BE-06 | 空问题问答 | 返回 `code=400` |
| BE-07 | 合法问答 | 保存 session、USER 消息、ASSISTANT 消息和引用快照 |

## Python RAG 测试

| 编号 | 用例 | 预期 |
| --- | --- | --- |
| RAG-01 | `/rag/index` 处理 txt | 返回 `fileId` 和 `chunkCount` |
| RAG-02 | `/rag/index` 处理 pdf/docx | 正确解析文本并写入向量库 |
| RAG-03 | `/rag/search` 检索 | 返回 `fileId`、`fileName`、`chunkText`、`score` |
| RAG-04 | 空向量库检索 | 返回空 `references`，不抛未处理异常 |
| RAG-05 | embedding 模型不可用 | 入库返回业务码 503，不生成哈希向量；查询允许有明确标记的 BM25 降级 |

## Frontend 测试

| 编号 | 用例 | 预期 |
| --- | --- | --- |
| FE-01 | 首页加载 | 工作台正常渲染 |
| FE-02 | 上传文件 | 调用 `/api/files/upload`，展示状态 |
| FE-03 | 文件列表 | 展示文件名、类型、大小、状态、chunk 数和错误信息 |
| FE-04 | 提交问题 | 展示回答和引用来源 |
| FE-05 | 后端返回业务错误 | 展示 `msg`，页面不崩溃 |

## 2026-11-06 RAG 升级回归

前面的 T-01 至 T-08 为历史阶段验证记录，不表示本轮重新调用了付费大模型。

执行命令：在 `rag-python` 运行 `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`。当前 46 项标准库 unittest 用例全部通过，使用临时文件和临时向量库，不访问生产知识库或付费 API。

| 范围 | 覆盖 |
| --- | --- |
| 清洗、编码 | 短正文、数字和单位保留；清洗幂等；UTF-8/16/32、无 BOM UTF-16、GB18030；损坏字节和 NUL 拒绝 |
| 文件解析 | Word 段落/表格顺序、表头和零值；PDF 页码、空页和普通重复正文；扫描 PDF 的 OCR 提示 |
| 结构分片 | 标题及正文共同限长；长问答保留问题；多页引用；长标题、无分隔长文本和多字节 token 计数；边界不吞字 |
| 检索融合 | 向量独有候选不被关键词挤出；共享结果融合且不重复；中文 BM25、缓存失效 |
| 持久化 | 空库及 topK 大于总量；重建清理本文件旧尾块、不影响其他文件；发布失败保留旧数据；模型指纹隔离 |
| 模型失败 | 不写入伪语义向量；明确词法降级；健康检查默认不触发加载 |
| HTTP 契约 | 索引失败码、空问题校验、Java 所需引用字段和统一响应保持兼容 |

现场验证：真实本地多语言 MiniLM（384 维、128 token），MySQL 的 5 个原文件重建为 29 个语义片段，课程文件 25 片。原问题“我想学一下sun教的内容”、“sun老师教什么”和改述问题“怎样提高英文写作能力”均返回课程资料并包含向量召回贡献。前端首页、前端 `/api/files/list` 代理、Java 文件列表、Python 健康检查均通过。

本轮没有调用 DeepSeek，未重新评估最终回答质量。复杂 PDF 版面、OCR 和多进程写入仍不属于已验证范围。
