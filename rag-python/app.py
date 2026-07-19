from fastapi import FastAPI
from pydantic import ValidationError

from config import settings
from retrieval import RagService
from schemas import ApiResponse, RagIndexData, RagIndexRequest, RagSearchData, RagSearchRequest

app = FastAPI(title="RAG QA Service")
rag_service = RagService()


@app.get("/health")
def health():
    return {"status": "ok", "appName": settings.app_name}


@app.post("/rag/index", response_model=ApiResponse)
def index_file(request: RagIndexRequest):
    try:
        chunk_count = rag_service.index_file(
            file_id=request.fileId,
            file_path=request.filePath,
            file_name=request.fileName,
        )
        data = RagIndexData(fileId=request.fileId, chunkCount=chunk_count)
        msg = "index success"
        fallback_error = rag_service.embedding_provider.last_error
        if fallback_error:
            msg = f"{msg}; {fallback_error}"
        return ApiResponse(code=200, msg=msg, data=data.model_dump())
    except (FileNotFoundError, ValueError, ValidationError) as exc:
        return ApiResponse(code=400, msg=str(exc), data={"fileId": request.fileId})
    except Exception as exc:
        return ApiResponse(code=500, msg=f"index failed: {exc}", data={"fileId": request.fileId})


@app.post("/rag/search", response_model=ApiResponse)
def search(request: RagSearchRequest):
    try:
        references = rag_service.search(question=request.question, top_k=request.topK)
        data = RagSearchData(references=references)
        msg = "search success"
        fallback_error = rag_service.embedding_provider.last_error
        if fallback_error:
            msg = f"{msg}; {fallback_error}"
        return ApiResponse(code=200, msg=msg, data=data.model_dump())
    except ValueError as exc:
        return ApiResponse(code=400, msg=str(exc), data={"references": []})
    except Exception as exc:
        return ApiResponse(code=500, msg=f"search failed: {exc}", data={"references": []})
