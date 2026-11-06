import logging

from fastapi import FastAPI
from pydantic import ValidationError

from config import settings
from embedding import EmbeddingUnavailableError
from retrieval import RagService
from schemas import ApiResponse, RagIndexData, RagIndexRequest, RagSearchData, RagSearchRequest

app = FastAPI(title="RAG QA Service")
rag_service = RagService()


@app.get("/health")
def health(loadEmbedding: bool = False):
    return {"status": "ok", "appName": settings.app_name,
            **rag_service.health_status(load_embedding=loadEmbedding)}


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
        return ApiResponse(code=200, msg=msg, data=data.model_dump())
    except EmbeddingUnavailableError as exc:
        return ApiResponse(code=503, msg=str(exc), data={"fileId": request.fileId})
    except FileNotFoundError:
        return ApiResponse(code=400, msg="source file not found", data={"fileId": request.fileId})
    except (ValueError, ValidationError) as exc:
        return ApiResponse(code=400, msg=str(exc), data={"fileId": request.fileId})
    except Exception as exc:
        logging.exception("Indexing failed for fileId=%s", request.fileId)
        return ApiResponse(code=500, msg="index failed; see the RAG service log", data={"fileId": request.fileId})


@app.post("/rag/search", response_model=ApiResponse)
def search(request: RagSearchRequest):
    try:
        references = rag_service.search(question=request.question, top_k=request.topK)
        data = RagSearchData(references=references)
        msg = "search success"
        if rag_service.last_search_warning:
            msg = f"{msg}; {rag_service.last_search_warning}"
        return ApiResponse(code=200, msg=msg, data=data.model_dump())
    except ValueError as exc:
        return ApiResponse(code=400, msg=str(exc), data={"references": []})
    except Exception as exc:
        logging.exception("Retrieval failed")
        return ApiResponse(code=500, msg="search failed; see the RAG service log", data={"references": []})
