import os
import re
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import tempfile

from app.document_parser.universal_parser import UniversalDocumentParser


class SimpleSourceProcessor:
    """Улучшенный процессор для извлечения текста и метаданных из файлов источников"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.uploads_dir = self.base_dir / "uploads" / "sources"
        self.document_parser = UniversalDocumentParser()

        self._ensure_directory_exists_sync()
        print(f"EnhancedSourceProcessor initialized. Uploads dir: {self.uploads_dir}")
        print(f"Directory exists: {self.uploads_dir.exists()}")

    def _ensure_directory_exists_sync(self):
        """Создает директорию для загрузок"""
        try:
            print(f"Creating directory: {self.uploads_dir}")
            self.uploads_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"CRITICAL: Cannot create directory {self.uploads_dir}: {e}")
            # Fallback directory в текущей директории
            self.uploads_dir = Path.cwd() / "temp_sources"
            self.uploads_dir.mkdir(exist_ok=True)
            print(f"Using fallback directory: {self.uploads_dir}")

    async def process_uploaded_source(self, file, user_id: str) -> Dict[str, Any]:
        """Обрабатывает загруженный файл источника и извлекает текст и метаданные"""
        try:
            print(f"Processing file: {file.filename} for user: {user_id}")

            # Сохраняем оригинальное имя файла
            original_filename = file.filename

            # Сохраняем файл во временную директорию сначала
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
                temp_path = Path(temp_file.name)
                content = await file.read()
                temp_file.write(content)
                print(f"File temporarily saved to: {temp_path}")

            try:
                # Извлекаем текст из файла
                text_content = await self.extract_text_from_file(temp_path)
                print(f"Text extracted from temp file: {len(text_content)} characters")

                # Извлекаем улучшенные метаданные
                metadata = await self.extract_enhanced_metadata(temp_path, text_content, original_filename)

                # Генерируем ID
                file_id = f"source_{user_id}_{int(datetime.now().timestamp())}"

                # Копируем в постоянное хранилище если нужно
                permanent_path = None
                try:
                    if self.uploads_dir.exists():
                        permanent_path = self.uploads_dir / f"{file_id}{Path(original_filename).suffix}"
                        import shutil
                        shutil.copy2(temp_path, permanent_path)
                        print(f"File copied to permanent storage: {permanent_path}")
                except Exception as copy_error:
                    print(f"Could not copy to permanent storage: {copy_error}")
                    permanent_path = temp_path  # Используем временный файл

                return {
                    "success": True,
                    "file_path": str(permanent_path or temp_path),
                    "filename": original_filename,
                    "metadata": metadata,
                    "file_id": file_id,
                    "text_content": text_content
                }

            finally:
                # Пытаемся удалить временный файл, если он не используется как постоянный
                try:
                    if temp_path.exists() and (not permanent_path or temp_path != permanent_path):
                        temp_path.unlink()
                        print(f"Temporary file deleted: {temp_path}")
                except:
                    pass

        except Exception as e:
            print(f"Error processing source: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    async def extract_text_from_file(self, file_path: Path) -> str:
        """Извлекает текст из файла с помощью UniversalDocumentParser"""
        try:
            print(f"Extracting text from: {file_path}")
            print(f"File exists: {file_path.exists()}")

            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            # Определяем тип файла по расширению
            file_extension = file_path.suffix.lower()

            if file_extension in ['.pdf', '.doc', '.docx', '.rtf']:
                # Для поддерживаемых форматов используем UniversalDocumentParser
                print(f"Using UniversalDocumentParser for {file_extension}")
                document = self.document_parser.parse_document(str(file_path))

                if not document:
                    print("Document parser returned None")
                    return ""

                full_text = self._extract_text_from_document(document)
                print(f"Extracted {len(full_text)} characters from {file_extension}")

                return full_text

            elif file_extension in ['.txt']:
                # Для текстовых файлов просто читаем
                print("Reading text file directly")
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
                print(f"Extracted {len(text)} characters from text file")
                return text

            else:
                # Для других форматов пробуем как текстовые
                print(f"Trying to read {file_extension} as text file")
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read()
                    print(f"Extracted {len(text)} characters from {file_extension} file")
                    return text
                except Exception as e:
                    print(f"Cannot read {file_extension} as text: {e}")
                    return f"[Binary file: {file_extension}, size: {file_path.stat().st_size} bytes]"

        except Exception as e:
            print(f"Error extracting text from file: {e}")
            import traceback
            traceback.print_exc()
            return f"[Error extracting text: {str(e)}]"

    def _extract_text_from_document(self, document) -> str:
        """Извлекает текст из документа UniversalDocumentParser"""
        try:
            if not document:
                return ""

            full_text = ""

            # Проверяем структуру документа
            if hasattr(document, 'main_content') and document.main_content:
                print(f"Document has {len(document.main_content)} content blocks")

                for i, block in enumerate(document.main_content):
                    if hasattr(block, 'text') and block.text:
                        block_text = block.text.strip()
                        if block_text:
                            full_text += block_text + "\n\n"

            # Если нет main_content, пробуем другие атрибуты
            elif hasattr(document, 'text') and document.text:
                print("Document has direct text attribute")
                full_text = document.text
            elif hasattr(document, 'content') and document.content:
                print("Document has content attribute")
                full_text = document.content

            # Если текст слишком короткий, пробуем raw_text
            if len(full_text.strip()) < 100 and hasattr(document, 'raw_text'):
                print("Using raw_text attribute")
                full_text = document.raw_text

            result = full_text.strip()
            print(f"Total extracted text length: {len(result)} characters")

            return result

        except Exception as e:
            print(f"Error extracting text from document: {e}")
            return ""

    async def extract_enhanced_metadata(self, file_path: Path, text_content: str, filename: str) -> Dict[str, Any]:
        """Создает улучшенные метаданные из файла"""
        print(f"Creating enhanced metadata for: {filename}")

        # Определяем тип файла
        file_extension = file_path.suffix.lower()

        if file_extension in ['.docx', '.doc']:
            # Для DOCX используем улучшенное извлечение
            metadata = self._extract_docx_metadata(file_path, text_content, filename)
        else:
            # Для других форматов используем общий подход
            metadata = self._extract_general_metadata(text_content, filename)

        print(f"Enhanced metadata extracted:")
        print(f"  Title: {metadata['title']}")
        print(f"  Authors: {metadata['authors']}")
        print(f"  Year: {metadata['year']}")
        print(f"  Type: {metadata['source_type']}")
        print(f"  Text length: {metadata['text_length']}")

        return metadata

    def _extract_docx_metadata(self, file_path: Path, text_content: str, filename: str) -> Dict[str, Any]:
        """Извлекает метаданные из DOCX файлов"""
        try:
            # Пытаемся проанализировать DOCX структуру
            print(f"Analyzing DOCX structure for metadata extraction...")

            # Читаем первые 5000 символов для анализа
            preview_text = text_content[:5000] if len(text_content) > 5000 else text_content

            # Извлекаем авторов с улучшенным алгоритмом
            authors = self._extract_authors_enhanced(preview_text, filename)

            # Извлекаем заголовок с улучшенным алгоритмом
            title = self._extract_title_enhanced(preview_text, filename, authors)

            # Извлекаем год
            year = self._extract_year_enhanced(preview_text)

            # Определяем тип источника
            source_type = self._detect_source_type_enhanced(preview_text, filename)

            # Извлекаем издательство/журнал
            publisher = self._extract_publisher(preview_text)
            journal = self._extract_journal(preview_text)

            return {
                "title": title,
                "authors": authors,
                "year": year,
                "source_type": source_type,
                "publisher": publisher,
                "journal": journal,
                "keywords": self._extract_keywords(preview_text),
                "abstract": self._extract_abstract(preview_text),
                "extracted_from_content": True,
                "pages_count": self._estimate_pages(text_content),
                "has_text": len(text_content.strip()) > 0,
                "text_length": len(text_content),
                "original_filename": filename
            }

        except Exception as e:
            print(f"Error extracting DOCX metadata: {e}")
            # Возвращаем базовые метаданные при ошибке
            return self._extract_general_metadata(text_content, filename)

    def _extract_general_metadata(self, text_content: str, filename: str) -> Dict[str, Any]:
        """Извлекает общие метаданные для всех типов файлов"""
        title = self._extract_title_enhanced(text_content, filename, [])
        authors = self._extract_authors_enhanced(text_content, filename)

        return {
            "title": title,
            "authors": authors,
            "year": self._extract_year_enhanced(text_content),
            "source_type": self._detect_source_type_enhanced(text_content, filename),
            "publisher": "",
            "journal": "",
            "keywords": [],
            "abstract": "",
            "extracted_from_content": True,
            "pages_count": self._estimate_pages(text_content),
            "has_text": len(text_content.strip()) > 0,
            "text_length": len(text_content),
            "original_filename": filename
        }

    def _extract_authors_enhanced(self, text: str, filename: str) -> List[str]:
        """Улучшенное извлечение авторов из текста"""
        if not text or len(text.strip()) < 100:
            return self._extract_authors_from_filename(filename)

        print("=== ИЗВЛЕЧЕНИЕ АВТОРОВ ===")
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        authors = []

        # 1. Проверяем первую строку - часто там автор
        if lines:
            first_line = lines[0]
            if self._looks_like_russian_fio(first_line):
                print(f"✅ Найден автор в первой строке: {first_line}")
                authors.append(first_line)

                # Пробуем извлечь фамилию и инициалы
                parts = first_line.split()
                if len(parts) >= 2:
                    surname = parts[0]
                    # Пробуем создать вариант с инициалами
                    if len(parts) >= 3:
                        name_initial = parts[1][0] if parts[1] else ''
                        patronymic_initial = parts[2][0] if len(parts) > 2 else ''
                        initials = f"{name_initial}.{patronymic_initial}."
                        authors.append(f"{surname} {initials}")

        # 2. Ищем в тексте паттерны типа "Автор:", "Authors:"
        for i, line in enumerate(lines[:20]):
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in ['автор:', 'авторы:', 'author:', 'authors:']):
                print(f"Найдена строка с указанием автора [{i}]: {line}")
                # Извлекаем авторов после ключевого слова
                parts = re.split(r'[:\-]', line, maxsplit=1)
                if len(parts) > 1:
                    authors_part = parts[1].strip()
                    # Разделяем нескольких авторов
                    author_candidates = re.split(r'[;,и]', authors_part)
                    for candidate in author_candidates:
                        candidate = candidate.strip()
                        if candidate and len(candidate) > 3:
                            authors.append(candidate)

        # 3. Убираем дубли
        unique_authors = []
        seen = set()
        for author in authors:
            if author and author not in seen:
                unique_authors.append(author)
                seen.add(author)

        print(f"Извлечено авторов: {unique_authors}")
        return unique_authors[:8]  # Ограничиваем количество

    def _looks_like_russian_fio(self, text: str) -> bool:
        """Проверяет, похож ли текст на русское ФИО"""
        text = text.strip()

        # Должно быть 2-3 слова
        parts = text.split()
        if len(parts) not in [2, 3]:
            return False

        # Каждое слово должно начинаться с заглавной русской буквы
        for part in parts:
            if not re.match(r'^[А-ЯЁ][а-яё]*$', part):
                return False

        # Проверяем типичные окончания
        if len(parts) >= 1:
            surname = parts[0]
            common_endings = ['ов', 'ев', 'ин', 'ын', 'ий', 'ой', 'ая', 'ская', 'цкая']
            if any(surname.endswith(ending) for ending in common_endings):
                print(f"  -> Определено как ФИО по окончанию фамилии")
                return True

        # Проверяем по словарю типичных имен и отчеств
        russian_names = ['анна', 'мария', 'елена', 'ольга', 'наталья', 'ирина',
                         'светлана', 'татьяна', 'юлия', 'александра']
        russian_patronymics = ['михайловна', 'владимировна', 'сергеевна', 'андреевна',
                               'александровна', 'дмитриевна', 'ивановна', 'николаевна']

        if len(parts) == 3:
            name = parts[1].lower()
            patronymic = parts[2].lower()
            if name in russian_names and patronymic in russian_patronymics:
                print(f"  -> Определено как ФИО по словарю имен")
                return True

        return False

    def _extract_authors_from_filename(self, filename: str) -> List[str]:
        """Пытается извлечь авторов из имени файла"""
        try:
            # Пробуем найти паттерны авторов в имени файла
            name_without_ext = Path(filename).stem

            # Паттерны типа "Иванов_статья.docx" или "Smith_paper.pdf"
            patterns = [
                r'^([А-ЯЁ][а-яё]+)(?:_|\s|-)',  # Иванов_...
                r'^([A-Z][a-z]+)(?:_|\s|-)',  # Smith_...
            ]

            for pattern in patterns:
                match = re.match(pattern, name_without_ext)
                if match:
                    author = match.group(1)
                    if len(author) >= 3:
                        return [author]

        except Exception as e:
            print(f"Error extracting authors from filename: {e}")

        return []

    def _extract_title_enhanced(self, text: str, filename: str, authors: List[str]) -> str:
        """Улучшенное извлечение заголовка из текста"""
        if not text:
            return self._extract_title_from_filename(filename)

        print("=== НАЧАЛО ИЗВЛЕЧЕНИЯ ЗАГОЛОВКА ===")
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        print(f"Всего строк: {len(lines)}")
        print("Первые 5 строк:")
        for i, line in enumerate(lines[:5]):
            print(f"  [{i}] '{line}'")

        # Пропускаем первую строку, если она похожа на ФИО
        start_index = 0
        if lines and self._looks_like_russian_fio(lines[0]):
            print(f"Пропускаем первую строку (похожа на ФИО): '{lines[0]}'")
            start_index = 1

        # Ищем заголовок в следующих строках
        for i, line in enumerate(lines[start_index:start_index + 10], start=start_index):
            print(f"Анализируем строку [{i}]: '{line[:50]}...'")

            # Проверяем, что это не пустая строка
            if not line or len(line.strip()) < 5:
                continue

            # Пропускаем служебные строки
            if any(word in line.lower() for word in ['глава', 'часть', 'раздел', 'chapter', 'section', 'введение']):
                print(f"  -> Пропускаем (служебная)")
                continue

            # Проверяем критерии для заголовка
            if self._is_likely_title(line):
                clean_title = self._clean_title(line)
                if clean_title:
                    print(f"✅ НАЙДЕН ЗАГОЛОВОК в строке {i}: '{clean_title[:100]}...'")
                    return clean_title[:250]

        # Если ничего не нашли, смотрим строки с заглавными буквами
        print("=== ИЩЕМ ЗАГОЛОВКИ В ЗАГЛАВНЫХ БУКВАХ ===")
        for i, line in enumerate(lines[start_index:start_index + 10], start=start_index):
            if line and any(c.isupper() for c in line) and 20 <= len(line) <= 200:
                # Проверяем, что не слишком много заглавных (не весь текст заглавный)
                uppercase_ratio = sum(1 for c in line if c.isupper()) / len(line)
                if 0.1 < uppercase_ratio < 0.8:  # Не слишком мало и не слишком много
                    clean_title = self._clean_title(line)
                    if clean_title:
                        print(f"✅ НАЙДЕН ЗАГОЛОВОК (по заглавным) в строке {i}: '{clean_title[:100]}...'")
                        return clean_title[:250]

        print("=== НИЧЕГО НЕ НАЙДЕНО, ИСПОЛЬЗУЕМ ИМЯ ФАЙЛА ===")
        # Если ничего не нашли, используем имя файла
        return self._extract_title_from_filename(filename)

    def _is_likely_not_title(self, line: str, authors: List[str]) -> bool:
        """Проверяет, что строка вероятно НЕ является заголовком"""
        line_lower = line.lower()

        # Слишком короткая или слишком длинная
        if len(line) < 10 or len(line) > 300:
            return True

        # Содержит служебные слова
        if any(word in line_lower for word in [
            'аннотация', 'abstract', 'введение', 'оглавление',
            'содержание', 'литература', 'references', 'summary',
            'ключевые слова', 'keywords', 'реферат', 'рис.',
            'табл.', 'стр.', 'страница', 'page', '©', 'рисунок',
            'таблица', 'chapter', 'contents', 'literature'
        ]):
            return True

        # Начинается со знака препинания или цифры
        if re.match(r'^[–—\-\.\d\s]', line):
            # Исключение: если это тире перед заголовком
            clean_line = re.sub(r'^[–—\-\.\d\s]+', '', line)
            if len(clean_line) < 10:
                return True

        # Содержит только одного из авторов (не заголовок целиком)
        for author in authors:
            if len(author) > 5 and author in line and len(line) < len(author) + 20:
                return True

        # Слишком много точек, запятых или других знаков препинания
        punctuation_count = sum(1 for char in line if char in ',.;:!?')
        if punctuation_count > 3:
            return True

        return False

    def _is_likely_title(self, line: str) -> bool:
        """Проверяет, что строка вероятно является заголовком"""
        line = line.strip()

        # Должна быть достаточно длинной
        if len(line) < 10 or len(line) > 200:
            return False

        # Не должна заканчиваться точкой (обычно заголовки без точек)
        if line.endswith('.'):
            return False

        # Должна содержать осмысленные слова
        words = line.split()
        if len(words) < 2:
            return False

        # Проверяем наличие заглавных букв (но не все буквы заглавные)
        has_uppercase = any(c.isupper() for c in line)
        is_all_uppercase = line.isupper()

        if not has_uppercase or is_all_uppercase:
            return False

        # Проверяем, что это не нумерованный список
        if re.match(r'^\d+[\.\)]', line):
            return False

        # Проверяем, что это не просто дата или цифры
        if re.match(r'^\d+[\s\-]', line):
            return False

        # Должно быть минимум 2 слова длиной больше 3 букв
        long_words = sum(1 for word in words if len(word) >= 4)
        if long_words < 2:
            return False

        return True

    def _clean_title(self, title: str) -> str:
        """Очищает заголовок от мусора"""
        # Убираем служебные символы в начале
        clean_title = re.sub(r'^[–—\-\s\d\.]+', '', title).strip()

        # Убираем лишние пробелы
        clean_title = re.sub(r'\s+', ' ', clean_title)

        # Убираем кавычки по краям если они есть
        if (clean_title.startswith('"') and clean_title.endswith('"')) or \
                (clean_title.startswith('«') and clean_title.endswith('»')):
            clean_title = clean_title[1:-1].strip()

        return clean_title

    def _extract_title_from_filename(self, filename: str) -> str:
        """Извлекает заголовок из имени файла"""
        try:
            name_without_ext = Path(filename).stem

            # Убираем цифры в начале и конце
            clean_name = re.sub(r'^\d+[_\-\s]*|[_\-\s]*\d+$', '', name_without_ext)

            # Заменяем разделители пробелами
            for sep in ['_', '-', '.', '+']:
                clean_name = clean_name.replace(sep, ' ')

            # Убираем повторяющиеся пробелы
            clean_name = re.sub(r'\s+', ' ', clean_name).strip()

            # Если имя слишком короткое или содержит только цифры
            if not clean_name or len(clean_name) < 3 or re.match(r'^[\d\W]+$', clean_name):
                return "Загруженный документ"

            # Делаем первую букву заглавной
            if clean_name and clean_name[0].islower():
                clean_name = clean_name[0].upper() + clean_name[1:]

            return clean_name

        except Exception as e:
            print(f"Error extracting title from filename: {e}")
            return "Загруженный документ"

    def _extract_year_enhanced(self, text: str) -> Optional[str]:
        """Улучшенное извлечение года"""
        if not text:
            return None

        # Ищем в первых 2000 символах
        sample = text[:2000]

        # Паттерны для года
        patterns = [
            r'\b(19[0-9]{2}|20[0-2][0-9])\b',  # 1999, 2023
            r'\((\d{4})\)',  # (2023)
            r'©\s*(\d{4})',  # © 2023
            r'год[:\s]+(\d{4})',  # год: 2023
            r'Year[:\s]+(\d{4})',  # Year: 2023
        ]

        current_year = datetime.now().year
        found_years = []

        for pattern in patterns:
            matches = re.findall(pattern, sample, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                try:
                    year = int(match)
                    if 1900 <= year <= current_year:
                        found_years.append(year)
                except:
                    pass

        if found_years:
            # Возвращаем самый частый или первый
            from collections import Counter
            year_counts = Counter(found_years)
            most_common = year_counts.most_common(1)
            if most_common:
                return str(most_common[0][0])

        return None

    def _detect_source_type_enhanced(self, text: str, filename: str) -> str:
        """Определяет тип источника"""
        if not text:
            return "book"

        text_lower = text.lower()
        filename_lower = filename.lower()

        # Проверяем ключевые слова
        type_keywords = {
            'thesis': ['диссертация', 'автореферат', 'кандидатск', 'докторск', 'phd', 'dissertation'],
            'book': ['монография', 'учебник', 'книга', 'book', 'textbook', 'учебное пособие'],
            'conference': ['конференция', 'сборник', 'proceedings', 'conference', 'труды'],
            'report': ['отчет', 'исследование', 'report', 'research', 'аналитический'],
            'article': ['журнал', 'статья', 'article', 'journal', 'научная статья', 'публикация'],
            'standard': ['стандарт', 'гост', 'норматив', 'regulation', 'standard'],
        }

        for source_type, keywords in type_keywords.items():
            if any(keyword in text_lower for keyword in keywords) or \
                    any(keyword in filename_lower for keyword in keywords):
                return source_type

        # По умолчанию
        return "book"

    def _extract_publisher(self, text: str) -> str:
        """Извлекает издательство"""
        if not text:
            return ""

        sample = text[:2000]

        # Паттерны для издательств
        patterns = [
            r'Издательство[:\s]+([^\n\.]{3,50})',
            r'Publisher[:\s]+([^\n\.]{3,50})',
            r'\(Изд[\.\-\s]+([^\)]{3,50})\)',
            r'([А-ЯЁA-Z][\w\s]+(?:университет|институт|академия|издательство|press))',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, sample, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                match = match.strip()
                if 3 <= len(match) <= 100:
                    return match

        return ""

    def _extract_journal(self, text: str) -> str:
        """Извлекает журнал"""
        if not text:
            return ""

        sample = text[:2000]

        # Паттерны для журналов
        patterns = [
            r'Журнал[:\s]+"([^"]{3,50})"',
            r'Journal[:\s]+"([^"]{3,50})"',
            r'В\s+журнале\s+"([^"]{3,50})"',
            r'In\s+journal\s+"([^"]{3,50})"',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, sample, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                match = match.strip()
                if 3 <= len(match) <= 100:
                    return match

        return ""

    def _extract_keywords(self, text: str) -> List[str]:
        """Извлекает ключевые слова"""
        if not text:
            return []

        sample = text[:3000]
        keywords = []

        # Ищем секцию с ключевыми словами
        keyword_patterns = [
            r'Ключевые слова[:\s]+([^\n\.]{10,200})',
            r'Keywords[:\s]+([^\n\.]{10,200})',
            r'Ключевые\s+слова[:\s]+([^\n\.]{10,200})',
        ]

        for pattern in keyword_patterns:
            matches = re.findall(pattern, sample, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                # Разделяем на отдельные ключевые слова
                words = re.split(r'[,\;\.]', match)
                for word in words:
                    word = word.strip()
                    if word and len(word) >= 3:
                        keywords.append(word)

        return keywords[:10]  # Ограничиваем количество

    def _extract_abstract(self, text: str) -> str:
        """Извлекает аннотацию/реферат"""
        if not text:
            return ""

        # Ищем аннотацию в начале текста
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        for i, line in enumerate(lines[:20]):
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in ['аннотация', 'abstract', 'реферат']):
                # Собираем следующий абзац или несколько строк
                abstract_lines = []
                for j in range(i + 1, min(i + 10, len(lines))):
                    next_line = lines[j]
                    # Пропускаем пустые строки
                    if not next_line:
                        continue
                    # Если встречаем новый заголовок, останавливаемся
                    if len(next_line) < 100 and any(
                            keyword in next_line.lower() for keyword in
                            ['введение', 'оглавление', 'содержание', '1.', '1 ']
                    ):
                        break
                    abstract_lines.append(next_line)

                if abstract_lines:
                    return ' '.join(abstract_lines)[:500] + '...'

        return ""

    def _estimate_pages(self, text: str) -> Optional[int]:
        """Оценивает количество страниц по длине текста"""
        if not text:
            return None

        # Примерно 2500 символов на страницу
        chars_per_page = 2500
        estimated_pages = max(1, len(text) // chars_per_page)

        return estimated_pages

    def _is_common_word(self, word: str) -> bool:
        """Проверяет, является ли слово служебным или общеупотребительным"""
        common_words = {
            'рис', 'табл', 'стр', 'с', 'г', 'д', 'см', 'т', 'т.д', 'т.п',
            'fig', 'table', 'page', 'p', 'ch', 'chapter', 'section',
            'и', 'или', 'на', 'в', 'с', 'по', 'для', 'из', 'от', 'до',
            'the', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'from'
        }

        word_lower = word.lower()
        for common in common_words:
            if common in word_lower and len(word_lower) <= len(common) + 2:
                return True

        return False