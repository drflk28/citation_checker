from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class TextBlockType(str, Enum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    FOOTNOTE = "footnote"
    BIBLIOGRAPHY = "bibliography"
    CAPTION = "caption"
    UNKNOWN = "unknown"

class CitationStyle(str, Enum):
    GOST = "gost"
    APA = "apa"
    IEEE = "ieee"
    CHICAGO = "chicago"
    UNKNOWN = "unknown"

class IssueType(str, Enum):
    MISSING = "missing"
    UNUSED = "unused"
    DUPLICATE = "duplicate"
    FORMAT = "format"

class AnalysisStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

# Модели для парсинга
class TextBlock(BaseModel):
    text: str
    block_type: TextBlockType
    page_num: int
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 100.0, 100.0)
    font_size: Optional[float] = None
    font_name: Optional[str] = None
    is_bold: bool = False
    is_italic: bool = False

class ParsedDocument(BaseModel):
    metadata: Optional[Dict[str, Any]] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    main_content: Optional[List[TextBlock]] = None
    footnotes: Optional[List[TextBlock]] = None
    bibliography: Optional[List[TextBlock]] = None
    raw_text: Optional[str] = None

# Модели для веб-API
class Citation(BaseModel):
    id: str
    text: str
    position: Optional[Dict[str, Any]] = None
    context: str
    style: Optional[CitationStyle] = None

class BibliographyIssue(BaseModel):
    type: IssueType
    description: str
    severity: str = "medium"
    position: Optional[Dict[str, Any]] = None
    suggestion: Optional[str] = None

class BibliographyEntry(BaseModel):
    id: str
    text: str
    position: Optional[Dict[str, Any]] = None
    is_valid: bool = True
    is_verified: bool = False
    matched_citations: List[str] = Field(default_factory=list)
    online_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    library_match: Optional[Dict[str, Any]] = Field(default_factory=dict)
    enhancement_confidence: float = 0.0
    search_queries: List[str] = Field(default_factory=list)

    class Config:
        # Это обеспечит правильную сериализацию
        json_encoders = {
            # Добавьте специальные обработчики если нужно
        }

class DocumentMetadata(BaseModel):
    id: str
    filename: str
    file_path: str
    file_size: int
    upload_date: str
    status: str = "uploaded"

class AnalysisResult(BaseModel):
    doc_id: str
    status: AnalysisStatus
    citations_found: int = 0
    issues_found: int = 0
    bibliography_entries_found: int = 0
    citations: Optional[List[Citation]] = None
    issues: Optional[List[BibliographyIssue]] = None
    bibliography_entries: Optional[List[BibliographyEntry]] = None
    summary: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    def __init__(self, **data):
        # Устанавливаем значения по умолчанию для Optional полей
        if data.get('citations') is None:
            data['citations'] = []
        if data.get('issues') is None:
            data['issues'] = []
        if data.get('bibliography_entries') is None:
            data['bibliography_entries'] = []
        if data.get('summary') is None:
            data['summary'] = {}
        super().__init__(**data)

class SourceType(str, Enum):
    ARTICLE = "article"
    BOOK = "book"
    THESIS = "thesis"
    CONFERENCE = "conference"
    WEBSITE = "website"
    OTHER = "other"

class UserSource(BaseModel):
    id: str
    user_id: str
    title: str
    authors: List[str]
    year: Optional[int] = None
    source_type: SourceType
    journal: Optional[str] = None
    publisher: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    isbn: Optional[str] = None
    custom_citation: Optional[str] = None
    tags: List[str] = []
    created_at: datetime
    last_used: datetime

class SearchMatch(BaseModel):
    source: UserSource
    confidence: float
    matched_fields: List[str]
