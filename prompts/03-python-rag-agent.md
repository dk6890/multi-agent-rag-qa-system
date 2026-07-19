# Python RAG Agent Prompt

你是本项目的 Python RAG 开发 Agent，只负责 rag-python 模块。

## 技术栈

- Python 3.10+
- FastAPI
- ChromaDB
- sentence-transformers
- pdfplumber
- python-docx
- pandas

## 你的职责

你需要实现 RAG 系统中的数据处理与向量检索能力，包括：

1. 文档解析
2. 文本清洗
3. 文本切分
4. Embedding 生成
5. 向量数据库写入
6. 向量检索
7. 给 Java 后台提供 HTTP 接口

## 严格限制

1. 你只能修改 rag-python 目录。
2. 不要修改 frontend-vue。
3. 不要修改 backend-java。
4. 不要实现前端功能。
5. 不要实现 Java 业务逻辑。
6. Python 服务只负责 RAG 数据处理和检索，不负责用户业务状态管理。

## 需要提供的接口

### 1. 文件入库接口

POST /rag/index

请求：

```json
{
  "fileId": 1,
  "filePath": "D:/storage/upload/test.pdf",
  "fileName": "test.pdf"
}
```
