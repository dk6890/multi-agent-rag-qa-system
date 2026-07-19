# API 设计

本文档固化 Frontend、Backend、Python RAG 三方协作契约。后续实现阶段不得随意变更接口路径、请求字段、响应字段和状态枚举；如确需调整，必须先由 Master Agent 统一更新契约文档。

## 通用响应格式

所有 Java 后台对前端接口、Python RAG 对 Java 后台接口均使用统一响应外壳：

```json
{
  "code": 200,
  "msg": "success",
  "data": {}
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| code | integer | 是 | 业务状态码。200 表示成功，非 200 表示失败。 |
| msg | string | 是 | 面向调用方的结果说明或错误原因。 |
| data | object/null | 是 | 响应数据。无数据时返回 null 或空对象。 |

## 状态枚举

文件处理状态统一使用以下枚举：

| 状态 | 说明 |
| --- | --- |
| UPLOADED | 文件已上传，元数据已保存，尚未开始 RAG 入库处理。 |
| PROCESSING | 文件正在解析、切分、向量化或写入向量库。 |
| SUCCESS | 文件入库成功，可参与问答检索。 |
| FAILED | 文件入库失败，需记录失败原因。 |

## 引用来源结构

问答结果中的引用来源统一使用 `references` 数组，单条引用结构如下：

```json
{
  "fileId": 1,
  "fileName": "test.pdf",
  "chunkText": "被引用的文本片段",
  "score": 0.87,
  "chunkId": "1-0001",
  "metadata": {
    "page": 1
  }
}
```

必填字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| fileId | integer | 来源文件 ID，对应 `knowledge_file.id`。 |
| fileName | string | 来源文件名。 |
| chunkText | string | 命中的文本片段。 |
| score | number | 检索相似度或相关性分数。 |

可选字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| chunkId | string | Python RAG 侧生成的 chunk 标识。 |
| metadata | object | 页码、段落、标题等扩展元数据。 |

## 前端调用 Java 后台接口

### 1. 上传文件

`POST /api/files/upload`

请求类型：`multipart/form-data`

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| file | file | 是 | 待上传文件。建议支持 txt、pdf、docx。 |

成功响应：

```json
{
  "code": 200,
  "msg": "上传成功",
  "data": {
    "fileId": 1,
    "fileName": "test.pdf",
    "status": "PROCESSING"
  }
}
```

失败响应示例：

```json
{
  "code": 400,
  "msg": "文件类型不支持",
  "data": null
}
```

### 2. 文件列表

`GET /api/files/list`

请求参数：无。

成功响应：

```json
{
  "code": 200,
  "msg": "success",
  "data": [
    {
      "fileId": 1,
      "fileName": "test.pdf",
      "fileType": "pdf",
      "fileSize": 102400,
      "status": "SUCCESS",
      "chunkCount": 12,
      "errorMsg": null,
      "createdAt": "2026-06-30 10:00:00",
      "updatedAt": "2026-06-30 10:01:00"
    }
  ]
}
```

排序要求：按 `createdAt` 倒序返回。

### 3. 智能问答

`POST /api/chat/ask`

请求类型：`application/json`

请求体：

```json
{
  "question": "用户问题",
  "sessionId": 1
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| question | string | 是 | 用户问题。 |
| sessionId | integer | 否 | 已存在会话 ID。为空时 Java 后台创建新会话。 |

成功响应：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "sessionId": 1,
    "question": "用户问题",
    "answer": "模型回答",
    "references": [
      {
        "fileId": 1,
        "fileName": "test.pdf",
        "chunkText": "被引用的文本片段",
        "score": 0.87,
        "chunkId": "1-0001",
        "metadata": {
          "page": 1
        }
      }
    ]
  }
}
```

## Java 后台调用 Python RAG 接口

### 1. 文件入库

`POST /rag/index`

请求类型：`application/json`

请求体：

```json
{
  "fileId": 1,
  "filePath": "D:/storage/upload/test.pdf",
  "fileName": "test.pdf"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| fileId | integer | 是 | Java 后台数据库文件 ID。 |
| filePath | string | 是 | Java 后台保存的服务端文件路径，仅服务间传递，不返回前端。 |
| fileName | string | 是 | 原始文件名。 |

成功响应：

```json
{
  "code": 200,
  "msg": "index success",
  "data": {
    "fileId": 1,
    "chunkCount": 12
  }
}
```

失败响应示例：

```json
{
  "code": 500,
  "msg": "parse file failed",
  "data": {
    "fileId": 1
  }
}
```

### 2. 向量检索

`POST /rag/search`

请求类型：`application/json`

请求体：

```json
{
  "question": "用户问题",
  "topK": 5
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| question | string | 是 | 用户问题。 |
| topK | integer | 否 | 返回片段数量，默认建议 5。 |

成功响应：

```json
{
  "code": 200,
  "msg": "search success",
  "data": {
    "references": [
      {
        "fileId": 1,
        "fileName": "test.pdf",
        "chunkText": "被引用的文本片段",
        "score": 0.87,
        "chunkId": "1-0001",
        "metadata": {
          "page": 1
        }
      }
    ]
  }
}
```

## 错误处理约定

- 参数缺失或格式错误：`code=400`。
- 认证、授权类问题预留：`code=401` 或 `403`。
- 资源不存在：`code=404`。
- 服务内部错误：`code=500`。
- Python RAG 服务不可用时，Java 后台应返回非 200，并记录文件状态或问答错误。
- 前端不得依赖 HTTP 状态码判断业务成功，必须优先读取统一响应外壳中的 `code`。
