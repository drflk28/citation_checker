import fitz  # PyMuPDF
import asyncio
from typing import Optional


class AlternativePDFParser:
    """Альтернативный парсер PDF для сложных случаев"""

    @staticmethod
    async def parse_pdf(file_path: str) -> Optional[str]:
        """Парсит PDF используя PyMuPDF с улучшенными настройками"""
        try:
            print(f"Alternative parsing PDF: {file_path}")
            doc = fitz.open(file_path)
            full_text = ""

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)

                # Пробуем разные методы извлечения текста
                text_options = [
                    page.get_text(),  # Обычный метод
                    page.get_text("words"),  # По словам
                    page.get_text("blocks"),  # По блокам
                ]

                # Выбираем метод с наибольшим количеством текста
                best_text = ""
                for text in text_options:
                    if isinstance(text, str) and len(text) > len(best_text):
                        best_text = text
                    elif isinstance(text, list):
                        # Для списков слов или блоков
                        text_str = " ".join([str(item) for item in text])
                        if len(text_str) > len(best_text):
                            best_text = text_str

                full_text += best_text + "\n\n"

            doc.close()
            print(f"Alternative parser extracted {len(full_text)} characters")
            return full_text

        except Exception as e:
            print(f"Alternative parser failed: {e}")
            return None