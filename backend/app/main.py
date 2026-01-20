import os
import shutil
import platform
import logging
import uuid
import sys
import os
import asyncio
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
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

def check_dependencies():
    """Проверка всех зависимостей при запуске приложения"""
    print("=" * 50)
    print("🔍 ПРОВЕРКА ЗАВИСИМОСТЕЙ")
    print("=" * 50)

    # Проверка PyMuPDF (fitz)
    try:
        import fitz
        print("✅ PyMuPDF (fitz) - OK")
    except ImportError:
        print("❌ PyMuPDF (fitz) - НЕ УСТАНОВЛЕН")
        print("   Установите: pip install PyMuPDF")

    # Проверка Tesseract
    tesseract_available = shutil.which("tesseract") is not None
    if tesseract_available:
        print("✅ Tesseract - OK")
    else:
        print("❌ Tesseract - НЕ УСТАНОВЛЕН")
        print("   Установите для лучшего распознавания текста")

    # Проверка pytesseract
    try:
        import pytesseract
        print("✅ pytesseract - OK")
    except ImportError:
        print("❌ pytesseract - НЕ УСТАНОВЛЕН")
        print("   Установите: pip install pytesseract")

    # Проверка Pillow
    try:
        from PIL import Image
        print("✅ Pillow - OK")
    except ImportError:
        print("❌ Pillow - НЕ УСТАНОВЛЕН")
        print("   Установите: pip install pillow")

    print("=" * 50)

check_dependencies()

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
analysis_service = SimpleAnalysisService()
@app.get("/")
async def root():
    return {"message": "Citation Checker API", "version": "1.0.0"}


@app.put("/api/library/sources/{source_id}")
async def update_source(source_id: str, update_data: dict):
    """Обновляет информацию об источнике"""
    try:
        user_id = "demo_user"

        # Получаем текущий источник
        result = await library_service.get_source_details(user_id, source_id)
        if not result["success"]:
            raise HTTPException(status_code=404, detail="Источник не найден")

        source = result["source"]

        # Обновляем только разрешенные поля
        allowed_fields = ['title', 'authors', 'year', 'source_type',
                          'journal', 'publisher', 'url', 'doi', 'isbn',
                          'custom_citation', 'tags']

        updated = False
        for field in allowed_fields:
            if field in update_data:
                source[field] = update_data[field]
                updated = True

        if updated:
            # Сохраняем обновления
            if user_id in library_service.sources:
                for i, s in enumerate(library_service.sources[user_id]):
                    if s['id'] == source_id:
                        library_service.sources[user_id][i] = source
                        break

                library_service._save_sources()

        return {
            "success": True,
            "message": "Источник успешно обновлен",
            "source": source
        }

    except Exception as e:
        logger.error(f"Error updating source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/library/sources/check-duplicate")
async def check_duplicate_source(check_data: dict):
    """Проверяет, есть ли уже такой источник в библиотеке"""
    try:
        user_id = "demo_user"
        user_sources = library_service.sources.get(user_id, [])

        # Проверяем по разным критериям
        title = check_data.get('title', '').lower().strip()
        authors = check_data.get('authors', [])
        year = check_data.get('year')

        duplicates = []
        for source in user_sources:
            match_score = 0

            # Проверка названия
            if title and source.get('title', '').lower().strip() == title:
                match_score += 3

            # Проверка авторов
            source_authors = [a.lower() for a in source.get('authors', [])]
            check_authors = [a.lower() for a in authors]
            common_authors = set(source_authors) & set(check_authors)
            if common_authors:
                match_score += len(common_authors)

            # Проверка года
            if year and str(source.get('year')) == str(year):
                match_score += 1

            if match_score >= 2:  # Порог совпадения
                duplicates.append({
                    "id": source['id'],
                    "title": source.get('title'),
                    "authors": source.get('authors', []),
                    "year": source.get('year'),
                    "match_score": match_score
                })

        return {
            "success": True,
            "has_duplicates": len(duplicates) > 0,
            "duplicates": duplicates[:5]  # Ограничиваем количество
        }

    except Exception as e:
        logger.error(f"Error checking duplicates: {e}")
        return {
            "success": False,
            "error": str(e)
        }

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


@app.get("/api/debug/bibliography-search")
async def debug_bibliography_search(entry_text: str = "Грачев, С. А., Гундорова, М. А. Бизнес-планирование"):
    """Тестирование поиска в библиотеке для отладки"""
    try:
        from app.bibliography.checker import BibliographyChecker

        checker = BibliographyChecker()

        # Тестируем поиск
        result = checker._search_in_library(entry_text, [entry_text])

        return {
            "success": True,
            "entry_text": entry_text,
            "library_match": result,
            "library_service_available": hasattr(checker, 'library_service') and checker.library_service is not None,
            "user_sources_count": len(checker.library_service.sources.get("demo_user", [])) if hasattr(checker,
                                                                                                       'library_service') else 0
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/library/sources/{source_id}")
async def get_source_details(source_id: str):
    """Получить детальную информацию об источнике"""
    try:
        user_id = "demo_user"
        result = await library_service.get_source_details(user_id, source_id)

        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["message"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting source details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/library/sources/{source_id}/download")
async def download_source_file(source_id: str):
    """Скачать файл источника"""
    try:
        user_id = "demo_user"
        source_result = await library_service.get_source_details(user_id, source_id)

        if not source_result['success']:
            raise HTTPException(status_code=404, detail="Источник не найден")

        source = source_result['source']
        file_path = source.get('file_path')

        if not file_path or not os.path.exists(file_path):
            print(f"⚠️ Файл не найден: {file_path}")
            raise HTTPException(status_code=404, detail="Файл источника не найден")

        # Получаем оригинальное имя файла или используем имя из пути
        filename = source.get('filename') or os.path.basename(file_path)

        print(f"✅ Скачивание файла: {file_path}")
        print(f"📁 Имя файла для скачивания: {filename}")
        print(f"📊 Размер файла: {os.path.getsize(file_path) if os.path.exists(file_path) else 0} байт")

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/octet-stream',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка при скачивании файла: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка при скачивании файла: {str(e)}")


@app.get("/api/debug/source-files")
async def debug_source_files():
    """Отладка файлов источников"""
    try:
        user_id = "demo_user"
        user_sources = library_service.sources.get(user_id, [])

        file_info = []

        for source in user_sources:
            file_path = source.get('file_path')
            exists = os.path.exists(file_path) if file_path else False

            file_info.append({
                'id': source.get('id'),
                'title': source.get('title'),
                'filename': source.get('filename'),
                'file_path': file_path,
                'exists': exists,
                'has_file': source.get('has_file', False),
                'size': os.path.getsize(file_path) if exists and file_path else 0
            })

        return {
            "success": True,
            "total_sources": len(user_sources),
            "files": file_info
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.delete("/api/library/sources/{source_id}")
async def delete_from_library(source_id: str):
    """Удаление источника из библиотеки"""
    try:
        user_id = "demo_user"
        return await library_service.delete_source(user_id, source_id)
    except Exception as e:
        logger.error(f"Error deleting source: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/library/sources/{source_id}/full-content")
async def get_source_full_content(source_id: str):
    """Получает полный текст источника"""
    try:
        user_id = "demo_user"
        result = await library_service.get_source_details(user_id, source_id)

        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["message"])

        source = result["source"]
        full_content = source.get('full_content', '')

        if not full_content:
            raise HTTPException(status_code=404, detail="Текст источника не найден")

        return {
            "success": True,
            "source_id": source_id,
            "title": source.get("title"),
            "full_content": full_content,
            "content_length": len(full_content)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting full content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/library/sources/{source_id}/content")
async def get_source_content(source_id: str):
    """Получить содержание источника"""
    try:
        user_id = "demo_user"
        result = await library_service.get_source_content(user_id, source_id)

        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["message"])

        return result
    except Exception as e:
        logger.error(f"Error getting source content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/library/verify-citation")
async def verify_citation_content(verification_data: dict):
    """Проверить соответствие цитаты содержанию источника"""
    try:
        user_id = "demo_user"
        citation_text = verification_data.get('citation_text')
        source_id = verification_data.get('source_id')

        if not citation_text or not source_id:
            raise HTTPException(status_code=400, detail="Необходимы citation_text и source_id")

        return await library_service.verify_citation_content(user_id, citation_text, source_id)
    except Exception as e:
        logger.error(f"Error verifying citation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/library/sources/with-content")
async def add_source_with_content(source_data: dict):
    """Добавить источник с содержанием"""
    try:
        user_id = "demo_user"
        content = source_data.pop('content', None)  # Извлекаем содержание если есть

        return await library_service.add_source(user_id, source_data, content)
    except Exception as e:
        logger.error(f"Error adding source with content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/library/sources/upload")
async def upload_source_file(file: UploadFile = File(...)):
    """Загружает файл источника в библиотеку"""
    try:
        user_id = "demo_user"
        print(f"API: Uploading source file: {file.filename}")

        # Логируем информацию о файле
        print(f"API: File size: {file.size if hasattr(file, 'size') else 'unknown'}")
        print(f"API: File content type: {file.content_type}")

        result = await library_service.add_source_from_file(user_id, file)

        print(f"API: Upload result: {result}")

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message", "Upload failed"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading source file: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка при загрузке файла: {str(e)}")

@app.post("/api/library/sources/manual")
async def add_manual_source(source_data: dict):
    """Добавляет источник через ручной ввод"""
    try:
        user_id = "demo_user"
        return await library_service.add_source(user_id, source_data)
    except Exception as e:
        logger.error(f"Error adding manual source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/debug/sources/{source_id}/parse-info")
async def debug_parse_info(source_id: str):
    """Отладочная информация о парсинге источника"""
    try:
        user_id = "demo_user"
        result = await library_service.get_source_details(user_id, source_id)

        if not result["success"]:
            return {
                "success": False,
                "message": result["message"]
            }

        source = result["source"]

        debug_info = {
            "source_id": source_id,
            "title": source.get("title"),
            "has_file": source.get("has_file", False),
            "file_path": source.get("file_path"),
            "file_exists": os.path.exists(source.get("file_path", "")) if source.get("file_path") else False,
            "has_content": source.get("has_content", False),
            "has_full_content": source.get("has_full_content", False),
            "content_length": source.get("content_length", 0),
            "content_preview_length": len(source.get("content_preview", "")),
            "text_length": source.get("text_length", 0)
        }

        # Попробуем перепарсить файл для отладки
        if source.get("file_path") and os.path.exists(source.get("file_path")):
            try:
                from app.services.simple_source_processor import SimpleSourceProcessor
                from pathlib import Path

                processor = SimpleSourceProcessor()
                file_path = Path(source['file_path'])

                debug_info["file_info"] = {
                    "size": file_path.stat().st_size if file_path.exists() else 0,
                    "extension": file_path.suffix,
                    "exists": file_path.exists(),
                    "last_modified": datetime.fromtimestamp(
                        file_path.stat().st_mtime).isoformat() if file_path.exists() else None
                }

                # Пробуем извлечь текст заново
                reextracted = await processor.extract_text_from_file(file_path)
                debug_info["reparse"] = {
                    "success": bool(reextracted and reextracted.strip()),
                    "length": len(reextracted),
                    "preview": reextracted[:200] if reextracted else ""
                }

                # Сравниваем с сохраненным текстом
                saved_content = source.get('full_content', '')
                debug_info["comparison"] = {
                    "same_length": len(reextracted) == len(saved_content),
                    "reextracted_length": len(reextracted),
                    "saved_length": len(saved_content),
                    "difference": abs(len(reextracted) - len(saved_content))
                }

            except Exception as e:
                debug_info["reparse_error"] = str(e)

        return {
            "success": True,
            "debug_info": debug_info
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/debug/storage")
async def debug_storage():
    """Отладочная информация о хранилище"""
    try:
        data_dir = Path("data/library")
        contents_dir = data_dir / "contents"

        storage_info = {
            "data_dir": str(data_dir),
            "data_dir_exists": data_dir.exists(),
            "contents_dir": str(contents_dir),
            "contents_dir_exists": contents_dir.exists(),
            "total_sources": library_service.get_all_sources_count() if hasattr(library_service,
                                                                                'get_all_sources_count') else "N/A"
        }

        if contents_dir.exists():
            content_files = list(contents_dir.glob("*.txt"))
            storage_info["content_files"] = {
                "count": len(content_files),
                "files": [str(f.name) for f in content_files[:10]],  # Первые 10 файлов
                "total_size": sum(f.stat().st_size for f in content_files)
            }

        return {
            "success": True,
            "storage_info": storage_info
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/library/stats")
async def get_library_stats():
    """Статистика библиотеки"""
    try:
        user_id = "demo_user"
        user_sources = library_service.sources.get(user_id, [])

        stats = {
            "total_sources": len(user_sources),
            "sources_with_files": len([s for s in user_sources if s.get('has_file')]),
            "sources_with_content": len([s for s in user_sources if s.get('has_content')]),
            "sources_by_type": {},
            "total_content_size": 0
        }

        # Считаем по типам
        for source in user_sources:
            source_type = source.get('source_type', 'unknown')
            stats["sources_by_type"][source_type] = stats["sources_by_type"].get(source_type, 0) + 1

            if source.get('text_length'):
                stats["total_content_size"] += source.get('text_length', 0)

        # Добавляем временные метки
        if user_sources:
            stats["oldest_source"] = min(s.get('created_at', '') for s in user_sources)
            stats["newest_source"] = max(s.get('created_at', '') for s in user_sources)

        return {
            "success": True,
            "stats": stats
        }

    except Exception as e:
        logger.error(f"Error getting library stats: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/check-citations-in-library")
async def check_citations_in_library(check_request: dict):
    """Проверяет цитаты из документа в локальной библиотеке"""
    try:
        user_id = "demo_user"

        # Получаем все источники пользователя
        user_sources = library_service.sources.get(user_id, [])

        if not user_sources:
            return {
                "success": False,
                "message": "Библиотека пользователя пуста",
                "results": []
            }

        # Извлекаем тексты источников
        source_texts = []
        for source in user_sources:
            if source.get('has_content'):
                source_texts.append({
                    'id': source['id'],
                    'title': source.get('title', ''),
                    'full_content': source.get('full_content', ''),
                    'authors': source.get('authors', []),
                    'year': source.get('year')
                })

        checker = BibliographyChecker()
        results = []

        # Проходим по всем цитатам из запроса
        for citation_data in check_request.get('citations', []):
            citation_text = citation_data.get('text', '')
            context = citation_data.get('context', '')

            if citation_text and context:
                result = checker.find_citation_in_sources(citation_text, context, source_texts)
                results.append(result)

        return {
            "success": True,
            "total_citations_checked": len(results),
            "total_sources_searched": len(source_texts),
            "results": results
        }

    except Exception as e:
        logger.error(f"Error checking citations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/find-specific-citation")
async def find_specific_citation(citation_data: dict):
    """Ищет конкретную цитату в библиотеке"""
    try:
        user_id = "demo_user"
        citation_text = citation_data.get('citation_text', '')
        context = citation_data.get('context', '')

        if not citation_text or not context:
            raise HTTPException(
                status_code=400,
                detail="Необходимы citation_text и context"
            )

        # Получаем все источники пользователя
        user_sources = library_service.sources.get(user_id, [])

        if not user_sources:
            return {
                "success": False,
                "message": "Библиотека пользователя пуста",
                "citation_text": citation_text
            }

        # Извлекаем тексты источников
        source_texts = []
        for source in user_sources:
            if source.get('has_content'):
                source_texts.append({
                    'id': source['id'],
                    'title': source.get('title', ''),
                    'full_content': source.get('full_content', ''),
                    'authors': source.get('authors', []),
                    'year': source.get('year')
                })

        checker = BibliographyChecker()
        result = checker.find_citation_in_sources(citation_text, context, source_texts)

        return {
            "success": True,
            "citation_text": citation_text,
            "context": context,
            "search_results": result
        }

    except Exception as e:
        logger.error(f"Error finding citation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/verify-citation-semantically")
async def verify_citation_semantically(verification_data: dict):
    """Семантическая проверка цитаты в источнике"""
    try:
        user_id = "demo_user"

        citation_data = verification_data.get('citation_data')
        source_id = verification_data.get('source_id')

        if not citation_data or not source_id:
            raise HTTPException(
                status_code=400,
                detail="Необходимы citation_data и source_id"
            )

        # Получаем данные источника
        source_result = await library_service.get_source_details(user_id, source_id)
        if not source_result["success"]:
            raise HTTPException(status_code=404, detail="Источник не найден")

        # Выполняем семантическую проверку
        from app.bibliography.checker import BibliographyChecker
        checker = BibliographyChecker()

        result = checker.verify_citation_semantically(citation_data, source_result["source"])

        return {
            "success": True,
            "verification_result": result,
            "citation_preview": citation_data.get('text', '')[:100],
            "source_title": source_result["source"].get('title')
        }

    except Exception as e:
        logger.error(f"Error in semantic verification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/batch-verify-citations")
async def batch_verify_citations(batch_data: dict):
    """Пакетная семантическая проверка нескольких цитат"""
    try:
        user_id = "demo_user"

        citations = batch_data.get('citations', [])
        source_id = batch_data.get('source_id')

        if not citations or not source_id:
            raise HTTPException(
                status_code=400,
                detail="Необходимы citations и source_id"
            )

        # Получаем данные источника
        source_result = await library_service.get_source_details(user_id, source_id)
        if not source_result["success"]:
            raise HTTPException(status_code=404, detail="Источник не найден")

        # Выполняем пакетную проверку
        from app.semantic_matcher import semantic_matcher

        result = semantic_matcher.batch_verify_citations(citations, source_result["source"])

        return {
            "success": True,
            "batch_result": result,
            "source_info": {
                "id": source_id,
                "title": source_result["source"].get('title')
            }
        }

    except Exception as e:
        logger.error(f"Error in batch verification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/debug/semantic-match/{source_id}/{citation_id}")
async def debug_semantic_match(source_id: str, citation_id: str):
    """Отладочный эндпоинт для семантического сопоставления"""
    try:
        user_id = "demo_user"

        # Получаем данные источника
        source_result = await library_service.get_source_details(user_id, source_id)
        if not source_result["success"]:
            return {
                "success": False,
                "error": "Источник не найден"
            }

        # В реальном приложении здесь нужно получить цитату по citation_id
        # Для демо используем тестовую цитату
        test_citation = {
            "id": citation_id,
            "text": "Методы анализа данных в экономических исследованиях",
            "context": "В современных экономических исследованиях все большее значение приобретают методы анализа данных...",
            "full_paragraph": "В современных экономических исследованиях все большее значение приобретают методы анализа данных, которые позволяют выявлять скрытые закономерности и делать обоснованные прогнозы."
        }

        from app.semantic_matcher import semantic_matcher

        # Находим семантические совпадения
        matches = semantic_matcher.find_semantic_matches(
            test_citation['full_paragraph'],
            source_result['source'].get('full_content', '')
        )

        # Вычисляем схожесть
        similarity = semantic_matcher.calculate_semantic_similarity(
            test_citation['full_paragraph'],
            source_result['source'].get('full_content', '')
        )

        return {
            "success": True,
            "source_id": source_id,
            "citation": test_citation,
            "semantic_similarity": similarity,
            "matches_found": len(matches),
            "top_matches": matches[:3] if matches else []
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/documents/{doc_id}/semantic-check")
async def start_semantic_check(doc_id: str, background_tasks: BackgroundTasks):
    """Запускает семантическую проверку в фоновом режиме"""
    try:
        # Получаем результат анализа
        result = analysis_service.get_analysis_result(doc_id)
        if not result:
            raise HTTPException(status_code=404, detail="Document analysis not found")

        # Запускаем семантическую проверку в фоне
        background_tasks.add_task(
            analysis_service.perform_semantic_check,
            doc_id
        )

        return {
            "success": True,
            "message": "Семантическая проверка запущена в фоновом режиме",
            "doc_id": doc_id
        }

    except Exception as e:
        logger.error(f"Error starting semantic check: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/{doc_id}/semantic-status")
async def get_semantic_status(doc_id: str):
    """Получает статус семантической проверки"""
    try:
        result = analysis_service.get_analysis_result(doc_id)
        if not result:
            raise HTTPException(status_code=404, detail="Document analysis not found")

        semantic_stats = result.get('semantic_verification_stats', {})

        return {
            "success": True,
            "doc_id": doc_id,
            "semantic_check_available": result.get('semantic_check_available', False),
            "semantic_check_pending": result.get('semantic_check_pending', True),
            "semantic_stats": semantic_stats,
            "citations_count": len(result.get('citations', [])),
            "verified_citations": len([c for c in result.get('citations', []) if c.get('is_verified', False)])
        }

    except Exception as e:
        logger.error(f"Error getting semantic status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/")
async def root():
    return {"message": "Citation Checker API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)