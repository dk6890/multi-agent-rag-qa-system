param(
    [int]$Limit = 10,
    [int]$PreviewChars = 300,
    [switch]$Legacy
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PythonExecutable = Join-Path $Root "rag-python\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonExecutable)) { $PythonExecutable = "python" }
$env:RAG_SHOW_LIMIT = "$Limit"
$env:RAG_SHOW_PREVIEW_CHARS = "$PreviewChars"
$env:RAG_SHOW_LEGACY = "$($Legacy.IsPresent)"
$code = @'
import os
from vector_store import ChromaVectorStore
from embedding import EmbeddingProvider

limit = int(os.environ.get("RAG_SHOW_LIMIT", "10"))
preview_chars = int(os.environ.get("RAG_SHOW_PREVIEW_CHARS", "300"))
legacy = os.environ.get("RAG_SHOW_LEGACY", "False").lower() == "true"
store = ChromaVectorStore(None if legacy else EmbeddingProvider().model_fingerprint)
generations = store._generations()
if store._collection is None or (not legacy and not generations):
    result = {"documents": [], "metadatas": []}
else:
    options = {} if legacy else {"where": store._active_where(generations)}
    result = store._collection.get(include=["documents", "metadatas"], **options)
documents = result.get("documents", [])
metadatas = result.get("metadatas", [])
print(f"count={len(documents)}")
print(f"collection={store.collection_name}, legacy={legacy}")
for index, (document, metadata) in enumerate(zip(documents, metadatas), start=1):
    if index > limit:
        break
    text = (document or "").replace("\n", " ")
    print("---")
    print(metadata)
    print(text[:preview_chars])
'@

Push-Location (Join-Path $Root "rag-python")
try {
    $code | & $PythonExecutable -
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect the vector store" }
} finally {
    Pop-Location
    Remove-Item Env:RAG_SHOW_LIMIT -ErrorAction SilentlyContinue
    Remove-Item Env:RAG_SHOW_PREVIEW_CHARS -ErrorAction SilentlyContinue
    Remove-Item Env:RAG_SHOW_LEGACY -ErrorAction SilentlyContinue
}
