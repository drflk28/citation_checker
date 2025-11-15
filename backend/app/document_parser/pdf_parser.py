from typing import List

import fitz
import re
from pathlib import Path
from ..models.data_models import TextBlock, TextBlockType, ParsedDocument


class PDFDocumentParser:
    def parse_pdf(self, file_path: str) -> ParsedDocument:
        """Парсит PDF файл с объединением библиографических записей"""
        print(f"Парсим PDF: {file_path}")

        doc = fitz.open(file_path)
        metadata = doc.metadata
        blocks = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Получаем текст с сохранением позиций для лучшего разбиения
            text = page.get_text("text", sort=True)

            # Разбиваем на строки, но объединяем связанные
            lines = text.split('\n')
            merged_lines = self._merge_bibliography_lines(lines)

            for line in merged_lines:
                line = line.strip()
                if line:  # Пропускаем пустые строки
                    block_type = self._classify_line(line, page_num)

                    text_block = TextBlock(
                        text=line,
                        block_type=block_type,
                        page_num=page_num + 1,
                        bbox=(0, 0, 100, 100)  # упрощенный bbox
                    )
                    blocks.append(text_block)

        doc.close()

        print(f"PDF распарсен: {len(blocks)} блоков")
        return ParsedDocument(
            metadata=metadata,
            main_content=blocks,
            raw_text="\n".join(block.text for block in blocks)
        )

    def _merge_bibliography_lines(self, lines: List[str]) -> List[str]:
        """Объединяет строки библиографических записей в целые записи"""
        merged = []
        current_entry = []
        in_bibliography_entry = False

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Начало библиографической записи (начинается с цифры и точки)
            if re.match(r'^\d+\.\s*$', line) or re.match(r'^\d+\.\s+[А-ЯЁA-Z]', line):
                if current_entry:
                    merged.append(' '.join(current_entry))
                    current_entry = []
                in_bibliography_entry = True
                current_entry.append(line)

            # Продолжение библиографической записи
            elif in_bibliography_entry:
                # Если строка короткая и не начинается с цифры - это продолжение
                if (len(line) < 100 and
                        not re.match(r'^\d+\.', line) and
                        not any(keyword in line.lower() for keyword in [
                            'список используемых источников', 'библиография', 'приложение'
                        ])):
                    current_entry.append(line)
                else:
                    # Конец текущей записи, начало новой
                    if current_entry:
                        merged.append(' '.join(current_entry))
                    current_entry = []
                    in_bibliography_entry = False
                    merged.append(line)

            else:
                merged.append(line)

        # Добавляем последнюю запись
        if current_entry:
            merged.append(' '.join(current_entry))

        return merged

    def _classify_line(self, line: str, page_num: int) -> TextBlockType:
        """Классифицирует строку по типу"""
        line_lower = line.lower()

        # Заголовки
        if any(keyword in line_lower for keyword in [
            'abstract', 'introduction', 'methods', 'results', 'references',
            'аннотация', 'введение', 'методы', 'методология', 'результаты',
            'заключение', 'список используемых источников', 'список литературы',
            'библиография', 'литература'
        ]):
            return TextBlockType.HEADING

        # Библиографические записи (начинаются с цифры и точки)
        if re.match(r'^\d+\.\s+', line):
            return TextBlockType.BIBLIOGRAPHY

        # Обычный текст
        return TextBlockType.PARAGRAPH