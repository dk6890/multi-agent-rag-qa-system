from typing import Any

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: Any = None


class RagIndexRequest(BaseModel):
    fileId: int = Field(..., gt=0)
    filePath: str = Field(..., min_length=1)
    fileName: str = Field(..., min_length=1)


class RagIndexData(BaseModel):
    fileId: int
    chunkCount: int


class RagSearchRequest(BaseModel):
    question: str = Field(..., min_length=1)
    topK: int = Field(default=5, ge=1, le=50)


class Reference(BaseModel):
    fileId: int
    fileName: str
    chunkText: str
    score: float
    chunkId: str | None = None
    metadata: dict[str, Any] | None = None


class RagSearchData(BaseModel):
    references: list[Reference]
