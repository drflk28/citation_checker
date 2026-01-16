import os
import re
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import tempfile

from app.document_parser.universal_parser import UniversalDocumentParser


class SimpleSourceProcessor:
    """Простой процессор для извлечения текста из файлов источников"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.uploads_dir = self.base_dir / "uploads" / "sources"
        self.document_parser = UniversalDocumentParser()

        self._ensure_directory_exists_sync()
        print(f"SimpleSourceProcessor initialized. Uploads dir: {self.uploads_dir}")
        print(f"Directory exists: {self.uploads_dir.exists()}")

    def _ensure_directory_exists_sync(self):
        """Создает директорию для загрузок"""
        try:
            print(f"Creating directory: {self.uploads_dir}")

            # Создаем всю цепочку директорий
            self.uploads_dir.mkdir(parents=True, exist_ok=True)

            # Проверяем, что директория создана
            if not self.uploads_dir.exists():
                print(f"Failed to create directory: {self.uploads_dir}")
                # Создаем в текущей директории
                self.uploads_dir = Path("temp_sources")
                self.uploads_dir.mkdir(exist_ok=True)
                print(f"Using fallback directory: {self.uploads_dir}")
            else:
                print(f"Directory created successfully: {self.uploads_dir}")

        except Exception as e:
            print(f"CRITICAL: Cannot create directory {self.uploads_dir}: {e}")
            # Fallback directory в текущей директории
            self.uploads_dir = Path.cwd() / "temp_sources"
            self.uploads_dir.mkdir(exist_ok=True)
            print(f"Using fallback directory: {self.uploads_dir}")

    async def process_uploaded_source(self, file, user_id: str) -> Dict[str, Any]:
        """Обрабатывает загруженный файл источника и извлекает текст"""
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
                # Теперь обрабатываем из временного файла
                text_content = await self.extract_text_from_file(temp_path)
                print(f"Text extracted from temp file: {len(text_content)} characters")

                # Создаем метаданные
                metadata = await self.extract_simple_metadata(temp_path, text_content, original_filename)

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
                    if temp_path.exists():
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

                # Сохраняем для отладки
                debug_file = file_path.with_suffix('.extracted.txt')
                try:
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(full_text)
                    print(f"Debug text saved to: {debug_file}")
                except Exception as debug_error:
                    print(f"Could not save debug file: {debug_error}")

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

                    # Логируем первые 3 блока для отладки
                    if i < 3 and hasattr(block, 'text') and block.text:
                        print(f"  Block {i}: '{block.text[:100]}...'")

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

    async def extract_simple_metadata(self, file_path: Path, text_content: str, filename: str) -> Dict[str, Any]:
        """Создает простые метаданные из имени файла и содержания"""
        print(f"Creating simple metadata for: {filename}")

        # Сначала пытаемся извлечь заголовок из текста
        title = self._extract_title_from_text(text_content, filename)

        # Если заголовок слишком общий, пробуем улучшить
        if title in ["Загруженный документ", "Документ", "Источник"] and text_content:
            # Пытаемся найти более конкретный заголовок
            first_meaningful_line = None
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
            for line in lines[:20]:
                if (len(line) >= 20 and
                        re.search(r'[а-яА-Яa-zA-Z]', line) and
                        not any(word in line.lower() for word in
                                ['аннотация', 'abstract', 'введение', 'содержание'])):
                    first_meaningful_line = line[:100]
                    break

            if first_meaningful_line:
                title = first_meaningful_line

        metadata = {
            "title": title,
            "authors": self._extract_authors_from_text(text_content),
            "year": self._extract_year_from_text(text_content),
            "source_type": self._detect_source_type(text_content),
            "publisher": "",
            "journal": "",
            "extracted_from_content": True,
            "pages_count": self._estimate_pages(text_content),
            "keywords": [],
            "has_text": len(text_content.strip()) > 0,
            "text_length": len(text_content),
            "original_filename": filename
        }

        print(f"Metadata extracted:")
        print(f"  Title: {metadata['title']}")
        print(f"  Authors: {metadata['authors']}")
        print(f"  Year: {metadata['year']}")
        print(f"  Type: {metadata['source_type']}")
        print(f"  Text length: {metadata['text_length']}")

        return metadata

    def _extract_title_from_filename(self, filename: str) -> str:
        """Извлекает заголовок из имени файла или текста"""
        try:
            print(f"Extracting title from filename: {filename}")

            # Убираем расширение
            name_without_ext = Path(filename).stem

            print(f"Filename without extension: {name_without_ext}")

            # Если это техническое имя (source_...), пытаемся извлечь смысл
            if name_without_ext.startswith('source_'):
                parts = name_without_ext.split('_')
                print(f"Technical filename parts: {parts}")

                # Формат: source_userid_timestamp или source_userid_timestamp_originalname
                if len(parts) >= 3:
                    # Пробуем найти оригинальное имя после timestamp
                    if len(parts) > 3:
                        # Части после timestamp могут быть оригинальным именем
                        possible_name = '_'.join(parts[3:])
                        if possible_name and len(possible_name) > 2:
                            clean_name = re.sub(r'[_-]', ' ', possible_name)
                            clean_name = re.sub(r'\s+', ' ', clean_name).strip()
                            if len(clean_name) >= 3:
                                print(f"Extracted title from technical name: {clean_name}")
                                return clean_name

            # Пробуем разные стратегии очистки
            clean_name = name_without_ext

            # Убираем common patterns
            patterns_to_remove = [
                r'^\d+[-_]?',  # Числа в начале
                r'[-_]\d+$',  # Числа в конце
                r'[\[\]\(\)\{\}]',  # Скобки
                r'^\s+|\s+$',  # Пробелы по краям
                r'\s{2,}',  # Множественные пробелы
            ]

            for pattern in patterns_to_remove:
                clean_name = re.sub(pattern, ' ', clean_name)

            # Заменяем разделители пробелами
            separators = ['_', '-', '.', ',']
            for sep in separators:
                clean_name = clean_name.replace(sep, ' ')

            # Убираем повторяющиеся пробелы
            clean_name = re.sub(r'\s+', ' ', clean_name).strip()

            # Проверяем качество имени
            print(f"Cleaned name: '{clean_name}'")

            if not clean_name or len(clean_name) < 3:
                # Если имя слишком короткое или пустое
                print("Filename too short, returning default")
                return "Загруженный документ"

            # Если имя состоит только из цифр или бессмысленных символов
            if re.match(r'^[\d\W]+$', clean_name):
                print("Filename contains only digits/symbols, returning default")
                return "Загруженный документ"

            # Проверяем, есть ли в имени русские или английские буквы
            if not re.search(r'[а-яА-Яa-zA-Z]', clean_name):
                print("No meaningful letters in filename, returning default")
                return "Загруженный документ"

            # Делаем первую букву заглавной, если это русское слово
            if clean_name and clean_name[0].islower():
                # Проверяем, начинается ли с русской буквы
                if clean_name[0] in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя':
                    clean_name = clean_name[0].upper() + clean_name[1:]

            print(f"Final title: {clean_name}")
            return clean_name

        except Exception as e:
            print(f"Error extracting title from filename: {e}")
            return "Загруженный документ"

    def _extract_title_from_text(self, text: str, filename: str) -> str:
        """Пытается извлечь заголовок из текста документа"""
        try:
            if not text or len(text.strip()) < 100:
                return self._extract_title_from_filename(filename)

            print("Attempting to extract title from text content...")

            # Разбиваем текст на строки
            lines = [line.strip() for line in text.split('\n') if line.strip()]

            if not lines:
                return self._extract_title_from_filename(filename)

            # Стратегия 1: Ищем заголовок в первых строках
            # Часто заголовок - это первая осмысленная строка
            for i, line in enumerate(lines[:15]):
                # Пропускаем служебные строки
                if any(ignore in line.lower() for ignore in
                       ['–', '—', 'рис.', 'табл.', 'рисунок', 'таблица',
                        'стр.', 'страница', 'page', '©', '©']):
                    continue

                # Критерии для заголовка
                if (30 <= len(line) <= 200 and  # Длина заголовка
                        re.search(r'[А-ЯЁA-Z]', line) and  # Есть заглавные буквы
                        not line.endswith('.') and  # Не заканчивается точкой
                        not line.endswith(',') and  # Не заканчивается запятой
                        not any(word in line.lower() for word in  # Не служебные строки
                                ['аннотация', 'abstract', 'введение', 'оглавление',
                                 'содержание', 'литература', 'references', 'summary',
                                 'ключевые слова', 'keywords', 'реферат'])):

                    print(f"Found potential title in line {i}: {line[:100]}...")

                    # Очищаем от мусора в начале
                    clean_line = re.sub(r'^[–—\-\s\d\.]+', '', line).strip()
                    if clean_line and len(clean_line) >= 20:
                        return clean_line[:150]
                    else:
                        return line[:150]

            # Стратегия 2: Ищем строку с максимальной длиной и заглавными буквами
            candidate_lines = []
            for i, line in enumerate(lines[:20]):
                if 40 <= len(line) <= 250:
                    # Оцениваем вероятность того, что это заголовок
                    score = 0
                    if re.search(r'[А-ЯЁ]', line):  # Заглавные русские буквы
                        score += 3
                    if re.search(r'[A-Z]', line):  # Заглавные английские буквы
                        score += 2
                    if re.search(r'[а-яa-z]', line):  # Строчные буквы
                        score += 1
                    if not re.search(r'[а-я][А-Я]', line):  # Не много CamelCase
                        score += 1
                    if not line.isupper():  # Не весь верхний регистр
                        score += 1
                    if not any(word in line.lower() for word in
                               ['рис.', 'табл.', 'с.', 'г.', 'рисунок', 'таблица']):
                        score += 2

                    # Высокий штраф за служебные символы в начале
                    if re.match(r'^[–—\-\s\d\.]+', line):
                        score -= 1

                    candidate_lines.append((line, score, i))

            if candidate_lines:
                # Сортируем по score (выше лучше) и позиции (раньше лучше)
                candidate_lines.sort(key=lambda x: (x[1], -x[2]), reverse=True)
                best_candidate = candidate_lines[0][0]

                # Очищаем от мусора в начале
                clean_candidate = re.sub(r'^[–—\-\s\d\.]+', '', best_candidate).strip()
                if clean_candidate and len(clean_candidate) >= 20:
                    print(f"Selected best cleaned title candidate: {clean_candidate[:100]}...")
                    return clean_candidate[:150]
                else:
                    print(f"Selected best title candidate: {best_candidate[:100]}...")
                    return best_candidate[:150]

            # Стратегия 3: Ищем в тексте упоминания названия статьи/работы
            title_patterns = [
                r'"([^"]{10,150})"',  # В кавычках
                r'«([^»]{10,150})»',  # В русских кавычках
                r'Статья[:\s]+"([^"]{10,150})"',
                r'Название[:\s]+"([^"]{10,150})"',
                r'Title[:\s]+"([^"]{10,150})"',
            ]

            for pattern in title_patterns:
                matches = re.findall(pattern, text[:5000])
                for match in matches:
                    if len(match) >= 20:
                        print(f"Found title in pattern '{pattern}': {match[:100]}...")
                        return match[:150]

            # Если ничего не нашли, возвращаем первую осмысленную строку
            for line in lines:
                if (len(line) >= 30 and
                        re.search(r'[А-ЯЁA-Z]', line) and
                        not any(word in line.lower() for word in
                                ['аннотация', 'abstract', 'введение', 'оглавление'])):
                    clean_line = re.sub(r'^[–—\-\s\d\.]+', '', line).strip()
                    if clean_line:
                        return clean_line[:150]

            # Если все еще ничего не нашли, возвращаем заголовок из имени файла
            return self._extract_title_from_filename(filename)

        except Exception as e:
            print(f"Error extracting title from text: {e}")
            return self._extract_title_from_filename(filename)

    def _extract_authors_from_text(self, text: str) -> List[str]:
        """Извлекает авторов из текста (простая реализация)"""
        if not text or len(text.strip()) < 100:
            return []

        # Ищем в первых 3000 символах
        sample = text[:3000]
        authors = []

        # Паттерны для русских авторов
        patterns = [
            r'[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ]\.){1,2}',  # Иванов И.И.
            r'[А-ЯЁ]\.[А-ЯЁ]\.\s+[А-ЯЁ][а-яё]+',  # И.И. Иванов
        ]

        for pattern in patterns:
            matches = re.findall(pattern, sample)
            for match in matches:
                # Простая валидация
                if 6 <= len(match) <= 100 and re.search(r'[А-ЯЁа-яё]', match):
                    # Проверяем, что это не часть другого слова
                    if not any(bad_word in match.lower() for bad_word in ['рис.', 'табл.', 'стр.', 'с.', 'г.']):
                        authors.append(match)

        # Убираем дубли и ограничиваем
        unique_authors = []
        seen = set()
        for author in authors:
            if author not in seen:
                unique_authors.append(author)
                seen.add(author)

        return unique_authors[:5]

    def _extract_year_from_text(self, text: str) -> Optional[str]:
        """Извлекает год из текста"""
        if not text:
            return None

        # Ищем четырехзначные числа в диапазоне 1900-2024
        year_pattern = r'\b(19[0-9]{2}|20[0-2][0-9])\b'
        matches = re.findall(year_pattern, text[:5000])

        current_year = datetime.now().year
        for match in matches:
            year = int(match)
            if 1900 <= year <= current_year:
                return str(year)

        return None

    def _detect_source_type(self, text: str) -> str:
        """Определяет тип источника по тексту"""
        if not text:
            return "article"

        text_lower = text.lower()

        # Проверяем ключевые слова
        if any(word in text_lower for word in ['диссертация', 'автореферат', 'кандидатск', 'докторск']):
            return "thesis"
        elif any(word in text_lower for word in ['монография', 'учебник', 'книга']):
            return "book"
        elif any(word in text_lower for word in ['конференция', 'сборник', 'proceedings']):
            return "conference"
        elif any(word in text_lower for word in ['отчет', 'исследование', 'report']):
            return "report"
        elif any(word in text_lower for word in ['журнал', 'статья', 'article', 'journal']):
            return "article"

        return "article"

    def _estimate_pages(self, text: str) -> Optional[int]:
        """Оценивает количество страниц по длине текста"""
        if not text:
            return None

        # Примерно 2500 символов на страницу
        chars_per_page = 2500
        estimated_pages = max(1, len(text) // chars_per_page)

        return estimated_pages