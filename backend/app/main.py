import os
import shutil
import logging
import uuid
import sys
import os
import asyncio
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
sys.path.append(os.path.join(os.path.dirname(__file__), '../../app'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from .auth.dependencies import get_current_user, get_current_user_optional
from .services.library_service import library_service
from .models.user_models import User
from app.citation_parser.citation_extractor import CitationExtractor
from app.bibliography.checker import BibliographyChecker
from app.services.simple_analysis_service import SimpleAnalysisService
from app.services.library_service import library_service

# Модели данных
from enum import Enum
from pydantic import BaseModel

# логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# очистка при запуске
def clear_all_data():
    uploads_dir = "uploads"
    if os.path.exists(uploads_dir):
        shutil.rmtree(uploads_dir)
    os.makedirs(uploads_dir, exist_ok=True)
    print("все данные очищены")


clear_all_data()

app = FastAPI(title="Citation Checker API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalysisStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class DocumentMetadata(BaseModel):
    id: str
    filename: str
    file_path: str
    file_size: int
    upload_date: str

class Citation(BaseModel):
    id: str
    text: str
    context: str
    style: Optional[str] = None

class Issue(BaseModel):
    type: str
    description: str
    severity: str
    suggestion: Optional[str] = None

class BibliographyEntry(BaseModel):
    id: str
    text: str

class Summary(BaseModel):
    total_references: int
    missing_references: int
    bibliography_entries: int
    completeness_score: float

class AnalysisResult(BaseModel):
    doc_id: str
    status: AnalysisStatus
    citations_found: Optional[int] = 0
    issues_found: Optional[int] = 0
    bibliography_entries_found: Optional[int] = 0
    citations: Optional[List[Citation]] = None
    issues: Optional[List[Issue]] = None
    bibliography_entries: Optional[List[BibliographyEntry]] = None
    summary: Optional[Summary] = None
    error_message: Optional[str] = None

# Хранилища данных
documents_store = {}
analysis_results = {}
analysis_status = {}

print(f"Хранилища инициализированы: documents_store={len(documents_store)}")

class TextBlock:
    def __init__(self, text: str, page_num: int = 1, block_type: str = "paragraph"):
        self.text = text
        self.page_num = page_num
        self.block_type = block_type

# глобальный анализатор
# document_analyzer = AnalysisService()
analysis_service = SimpleAnalysisService()
@app.get("/")
async def root():
    return {"message": "Citation Checker API", "version": "1.0.0"}


@app.post("/upload", response_model=DocumentMetadata)
async def upload_document(file: UploadFile = File(...)):
    logger.info(f"Upload request for file: {file.filename}")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    allowed_extensions = {'.pdf', '.docx', '.doc', '.txt'}
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    doc_id = str(uuid.uuid4())
    file_path = f"uploads/{doc_id}{file_extension}"

    try:
        content = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        logger.info(f"File saved: {file_path} ({len(content)} bytes)")
    except Exception as e:
        logger.error(f"File save error: {e}")
        raise HTTPException(status_code=500, detail="File save failed")

    metadata = DocumentMetadata(
        id=doc_id,
        filename=file.filename,
        file_path=file_path,
        file_size=len(content),
        upload_date=datetime.now().isoformat()
    )

    documents_store[doc_id] = metadata
    analysis_status[doc_id] = AnalysisStatus.PROCESSING

    logger.info(f"Document stored: {doc_id}")
    return metadata

# список всех доков
@app.get("/documents", response_model=List[DocumentMetadata])
async def list_documents():
    logger.info(f"Returning {len(documents_store)} documents")
    return list(documents_store.values())

# анализ документа
# анализ документа
@app.post("/documents/{doc_id}/analyze")
async def analyze_document(doc_id: str):
    # Получаем документ из хранилища (которое является словарем)
    document = documents_store.get(doc_id)  # Используем .get() для словаря
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = document.file_path  # Используем атрибут, а не ключ словаря
    result = analysis_service.analyze_document(file_path, doc_id)

    return result

@app.get("/documents/{doc_id}/analysis")
async def get_analysis(doc_id: str):
    result = analysis_service.get_analysis_result(doc_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return result

# фоновая задача анализа
async def run_analysis(doc_id: str):
    logger.info(f"Starting analysis for: {doc_id}")

    try:
        doc_metadata = documents_store[doc_id]

        analysis_result = analysis_service.analyze_document(doc_metadata.file_path, doc_id)

        analysis_results[doc_id] = analysis_result
        analysis_status[doc_id] = AnalysisStatus.COMPLETED

        logger.info(f"✅ Analysis completed for: {doc_id}")

    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")
        error_result = AnalysisResult(
            doc_id=doc_id,
            status=AnalysisStatus.ERROR,
            error_message=str(e),
            citations=[],
            issues=[],
            bibliography_entries=[],
            summary=Summary(
                total_references=0,
                missing_references=0,
                bibliography_entries=0,
                completeness_score=0.0
            )
        )
        analysis_results[doc_id] = error_result
        analysis_status[doc_id] = AnalysisStatus.ERROR

@app.options("/{rest_of_path:path}")
async def options_handler(rest_of_path: str):
    return JSONResponse(
        content={"message": "CORS preflight"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.post("/api/library/sources")
async def add_to_library(source_data: dict):
    """Добавление источника в библиотеку"""
    try:
        # Используем демо-пользователя или IP как идентификатор
        user_id = "demo_user"
        return await library_service.add_source(user_id, source_data)
    except Exception as e:
        logger.error(f"Error adding source: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/library/sources")
async def get_library_sources(query: Optional[str] = None, page: int = 1):
    """Поиск в библиотеке"""
    try:
        user_id = "demo_user"
        if query:
            return await library_service.search_sources(user_id, query, page)
        else:
            return await library_service.get_user_sources(user_id, page)
    except Exception as e:
        logger.error(f"Error getting sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/library/sources/{source_id}")
async def delete_from_library(source_id: str):
    """Удаление источника из библиотеки"""
    try:
        user_id = "demo_user"
        return await library_service.delete_source(user_id, source_id)
    except Exception as e:
        logger.error(f"Error deleting source: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/")
async def root():
    return {"message": "Citation Checker API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)