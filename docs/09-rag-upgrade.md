# RAG 解析、分片和检索升级

本轮参考 RAGFlow v0.27.3 的 Python 实现，保留现有 Vue -> Java -> Python 架构。Java 仍负责问答记录、状态管理、Prompt 和大模型调用；Python 不调用付费大模型 API。

## 源码依据

- TXT 分隔、段落合并：[txt_parser.py](https://github.com/infiniflow/ragflow/blob/v0.27.3/deepdoc/parser/txt_parser.py)。
- 按文件类型解析、标题及表格上下文：[naive.py](https://github.com/infiniflow/ragflow/blob/v0.27.3/rag/app/naive.py)。
- 问答资料单独组织：[qa.py](https://github.com/infiniflow/ragflow/blob/v0.27.3/rag/app/qa.py)。
- 页眉页脚等版面噪声：[layout_recognizer.py](https://github.com/infiniflow/ragflow/blob/v0.27.3/deepdoc/vision/layout_recognizer.py)。
- 多路召回及排序：[search.py](https://github.com/infiniflow/ragflow/blob/v0.27.3/rag/nlp/search.py)。

本项目采用 LangChain 递归分片、jieba 分词和 rank-bm25，不直接复制 RAGFlow 源码，也没有引入完整 DeepDoc/OCR 服务。

## 修复的根因

原系统的 pandas 1.5.1 与 numpy 2.2.6 二进制不兼容，导入 sentence-transformers 会报 `numpy.dtype size changed`。旧代码捕获错误后生成哈希向量，接口可以成功但没有真实语义能力。

项目新增 `rag-python/.venv`，复用系统的大型运行库，在隔离环境内安装兼容的 pandas 2.x。启动器优先选择此环境。原多语言 MiniLM 模型保存于 `rag-python/storage/models/multilingual-minilm`，正常 API 请求只加载本地模型，首次模型下载由显式准备命令执行。

当前模型输出 384 维向量，原生上限 128 token。配置 `chunk_max_tokens=256` 是额外上限，实际使用 `min(模型原生上限, 配置上限)`，因此不能通过增大此配置突破模型限制。

## 解析和清洗

| 类型 | 当前处理 |
| --- | --- |
| TXT | 识别 UTF BOM、UTF-8、无 BOM UTF-16 和 GB18030；严格解码，损坏或不支持的编码明确失败，不再丢弃无法解码的字节 |
| DOCX | 按正文顺序读取段落和表格；保留 Heading 层级；表格保留表头，并将数据行序列化为“列名: 值” |
| PDF | 使用 pdfplumber 提取文本、表格和页码；仅对多页且出现在页边区域的重复短行进行保守清理；保留表格旁边的正文 |

清洗统一换行、Unicode NFC、BOM、零宽空格及控制字符，保留中文、数字、单位、标点、段落和必要缩进。不会将所有短文本或所有重复正文删除。

没有可提取文字的扫描 PDF 会明确提示需要 OCR。复杂双栏、公式、图片正文、扫描件 OCR 仍需后续专门解析器；不能将本轮改造等同于完整 DeepDoc。

## 分片

入口为 `splitter.split_document(pages, token_counter=..., max_tokens=..., file_name=...)`，输出 `chunkIndex`、`text` 和 `metadata`。

1. 保留 DOCX 标题、Markdown 标题、明确章节编号；PDF 的显式标题上下文可以延续到下一页。
2. 对第一行明显为课程/讲义/手册标题的 TXT，将该短行作为资料标题。它表示文档主题，不用于推断后续每段的作者。
3. 识别 `Q:/A:`、`问：/答：`、`问题：/答案：`，优先将问答对组织在一起；长答案再次切分，并在预算允许时重复问题。
4. 使用成熟递归分片器，优先段落、换行、句号等边界，再处理长句和无分隔的长文本。
5. 用模型实际 tokenizer 计数，标题和问题前缀也计入预算；过长标题只保留有界上下文，完整标题保留在 metadata 中。
6. 每个最终片段入 Embedding 前再次检查上限，禁止依赖模型静默截断。超长查询可以按查询预算截短。

`chunk_size=800`、`chunk_overlap=120` 继续用于旧 `split_text` 字符接口；新分片采用两者的比值作为重叠比例，同时受到实际 token 预算限制。常见 metadata 包括 `sourceType`、`page`、`blockType`、`titlePath`、`documentTitle`、`tokenCount` 和 `splitterVersion`。

## 检索

- 中文用 jieba 搜索分词，英文转小写，过滤常见问句虚词；BM25Plus 负责词法召回，替代简单子串次数排序。
- BM25 和向量检索各召回至少 20 个候选，默认使用 `max(20, topK * 4)`，最多 200 个。
- 使用 RRF 融合两路排名，去重后返回 topK。关键词结果不再提前占满名额；本轮没有新增付费重排 API。
- `score` 是归一化融合排名分数，不是答案正确概率。metadata 保留两路名次和可用的词法/向量分数。
- BM25 索引保存在内存，索引代次或数据库变化时更新；不再每个请求无条件重建全库分词索引。

## 索引隔离和重建

旧集合 `rag_chunks` 保留，不能直接作为新模型的语义向量使用。新集合名称为 `rag_chunks_v2_<模型指纹>`；指纹包含模型标识、维度、预算以及本地配置和权重内容摘要。

每个文件重建先写入新的 generation，全部写入成功后才更新集合的 `fileGenerations` 元数据。查询只读取已发布的代次，随后清理本文件旧代次。写入或发布失败会保留旧代次，已成功重建的文件不会继续从旧集合重复召回。

当前发布方式适合本地单个 Uvicorn 进程；进程内锁保护并发操作。需要多进程写入时，应先迁移为事务目录或跨进程锁，不能直接增加多个写入 worker。

Embedding 不可用时，`/rag/index` 返回业务码 503，不生成 HashEmbedding。查询可以从旧集合返回明确标注为 `lexical-only`、`degraded` 的 BM25 结果，响应 msg 会说明降级。修复依赖/模型后重启服务，重新索引原文件。

## 操作

在项目根目录执行：

```powershell
# 安装隔离依赖并显式下载免费本地 Embedding 模型
powershell -ExecutionPolicy Bypass -File scripts\prepare-rag.ps1

# 正常启动；服务请求不自动下载模型
powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1

# 为 MySQL 中 SUCCESS 的原文件重建，并同步更新 chunk_count
powershell -ExecutionPolicy Bypass -File scripts\reindex-all.ps1

# 检查真实模型、语义分片数和三层连接
powershell -ExecutionPolicy Bypass -File scripts\health-check.ps1

# 查看新语义索引，或显式查看保留的旧集合
powershell -ExecutionPolicy Bypass -File scripts\show-vector-store.ps1 -Limit 5
powershell -ExecutionPolicy Bypass -File scripts\show-vector-store.ps1 -Legacy -Limit 5

# 不依赖网络或付费 API 的回归测试
cd rag-python
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`GET /health` 不触发模型加载；`GET /health?loadEmbedding=true` 会加载本地模型并返回 readiness、模型指纹、实际 token 上限、语义分片数和旧集合分片数。模型文件、虚拟环境、向量库及备份均不进入 Git。

重建前的原向量库副本保存在 `rag-python/storage/backups/before-structure-v2-*`。SQLite 是二进制容器；用 Chroma 客户端或查看脚本读取 documents/metadata，不用文本编辑器检查其内容。

Java 与前端接口路径及核心字段保持不变：`/api/files/upload`、`/api/files/list`、`/api/chat/ask`；Java 与 Python 仍使用 `/rag/index`、`/rag/search` 及 `fileId/fileName/chunkText/score` 引用字段。
