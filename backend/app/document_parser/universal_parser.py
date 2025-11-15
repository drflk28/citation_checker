from pathlib import Path
from typing import Union
from .pdf_parser import PDFDocumentParser
from .docx_parser import DOCXDocumentParser
from ..models.data_models import ParsedDocument


class UniversalDocumentParser:
    """Универсальный парсер для разных форматов документов"""

    def __init__(self):
        self.pdf_parser = PDFDocumentParser()
        self.docx_parser = DOCXDocumentParser()

    def parse_document(self, file_path: str) -> ParsedDocument:
        """Парсит документ любого поддерживаемого формата"""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Файл {file_path} не найден")

        if path.suffix.lower() == '.pdf':
            return self.pdf_parser.parse_pdf(file_path)
        elif path.suffix.lower() in ['.docx', '.doc']:
            return self.docx_parser.parse_docx(file_path)
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {path.suffix}")