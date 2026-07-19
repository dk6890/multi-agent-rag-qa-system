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
| RAG-05 | embedding 模型不可用 | 明确提示 fallback，接口仍可用于联调 |

## Frontend 测试

| 编号 | 用例 | 预期 |
| --- | --- | --- |
| FE-01 | 首页加载 | 工作台正常渲染 |
| FE-02 | 上传文件 | 调用 `/api/files/upload`，展示状态 |
| FE-03 | 文件列表 | 展示文件名、类型、大小、状态、chunk 数和错误信息 |
| FE-04 | 提交问题 | 展示回答和引用来源 |
| FE-05 | 后端返回业务错误 | 展示 `msg`，页面不崩溃 |

## 已知测试限制

- 当前 `LlmClient` 是壳子，尚未验证真实大模型回答质量。
- 当前环境 `sentence-transformers` 存在 numpy 二进制兼容问题，Python RAG 会降级到 HashEmbedding fallback。
- HashEmbedding 可验证流程闭环，不代表真实语义检索质量。
