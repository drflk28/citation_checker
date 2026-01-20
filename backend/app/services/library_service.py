import json
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
import re
import os
import hashlib
import logging
from app.document_parser.universal_parser import UniversalDocumentParser
from app.services.simple_source_processor import SimpleSourceProcessor

class LibraryService:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.data_dir = self.base_dir / "data" / "library"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sources_file = self.data_dir / "bibliography_sources.json"
        self.content_dir = self.data_dir / "content"
        self.content_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.source_processor = SimpleSourceProcessor()  # Изменено здесь

        # Инициализируем sources (ранее называлось user_sources)
        self.sources = self._load_sources()

        print(f"LibraryService initialized. Data dir: {self.data_dir}")
        print(f"Total users: {len(self.sources)}")

    async def add_source_from_file(self, user_id: str, file) -> Dict[str, Any]:
        """Добавляет источник из загруженного файла"""
        try:
            print(f"Adding source from file: {file.filename}")

            # Генерируем уникальный ID на основе содержимого файла
            content = await file.read()
            file_hash = hashlib.md5(content).hexdigest()[:8]

            # Проверяем, нет ли уже такого файла
            if user_id in self.sources:
                for existing_source in self.sources[user_id]:
                    if existing_source.get('file_hash') == file_hash:
                        return {
                            "success": False,
                            "message": "Такой файл уже существует в библиотеке",
                            "source_id": existing_source['id']
                        }

            # Возвращаем указатель файла в начало для обработки
            await file.seek(0)

            # Обрабатываем файл через SimpleSourceProcessor
            process_result = await self.source_processor.process_uploaded_source(file, user_id)

            if not process_result['success']:
                return {
                    "success": False,
                    "message": f"Ошибка обработки файла: {process_result.get('error')}"
                }

            # Создаем запись источника
            metadata = process_result['metadata']
            source_id = process_result['file_id']
            text_content = process_result.get('text_content', '')

            # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ ДЛЯ ОТЛАДКИ
            print(f"DEBUG: Text content length: {len(text_content)}")
            print(f"DEBUG: Text content preview (first 500): {text_content[:500]}")
            print(f"DEBUG: Has text content: {bool(text_content.strip())}")

            # Полный текст для сохранения
            full_text_content = text_content if text_content else ""

            source_data = {
                'id': source_id,
                'user_id': user_id,
                'title': metadata['title'],
                'authors': metadata['authors'],
                'year': metadata['year'],
                'source_type': metadata['source_type'],
                'journal': metadata.get('journal', ''),
                'publisher': metadata.get('publisher', ''),
                'url': '',
                'doi': '',
                'isbn': '',
                'custom_citation': '',
                'tags': [],
                'file_path': process_result['file_path'],
                'filename': process_result['filename'],
                'original_filename': metadata.get('original_filename', process_result['filename']),
                'file_hash': file_hash,  # Сохраняем хэш для проверки дубликатов
                'has_file': True,
                'extracted_from_file': True,
                'has_content': len(full_text_content.strip()) > 0,
                'content_preview': full_text_content[:500] + '...' if len(
                    full_text_content) > 500 else full_text_content,
                'text_length': len(full_text_content),
                'created_at': datetime.now().isoformat(),
                'last_used': datetime.now().isoformat()
            }

            # Сохраняем в библиотеку
            if user_id not in self.sources:
                self.sources[user_id] = []

            self.sources[user_id].append(source_data)
            self._save_sources()

            # Также сохраняем полный текст в отдельный файл
            if full_text_content.strip():
                self._save_source_content(source_id, full_text_content)
                print(f"DEBUG: Full content saved for source {source_id}")
            else:
                print(f"WARNING: No text content to save for source {source_id}")

            print(f"Source added successfully: {source_id}")

            return {
                "success": True,
                "source_id": source_id,
                "message": "Файл источника успешно добавлен в библиотеку",
                "metadata": metadata
            }

        except Exception as e:
            print(f"Error adding source from file: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "message": f"Ошибка при добавлении источника из файла: {str(e)}"
            }

    async def _extract_content_from_file(self, file_path: str) -> Optional[str]:
        """Извлекает текст из файла источника"""
        try:
            document = self.document_parser.parse_document(file_path)
            if document and document.main_content:
                # Объединяем весь текст из блоков контента
                full_text = ""
                for block in document.main_content:
                    if hasattr(block, 'text') and block.text:
                        full_text += block.text + "\n\n"
                return full_text.strip()
            return None
        except Exception as e:
            print(f"Error extracting content from file {file_path}: {e}")
            return None

    def _load_data(self) -> Dict[str, List[Dict]]:
        """Загружает данные из файла"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error loading library data: {e}")
            return {}

    def _save_data(self):
        """Сохраняет данные в файл"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_sources, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving library data: {e}")

    def _save_source_content(self, source_id: str, content: str):
        """Сохраняет полный текст источника"""
        try:
            self.content_dir.mkdir(exist_ok=True)

            content_file = self.content_dir / f"{source_id}.txt"
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Content saved for source {source_id}: {len(content)} chars")
        except Exception as e:
            print(f"Error saving source content: {e}")

    def _load_source_content(self, source_id: str) -> Optional[str]:
        """Загружает контент источника БЕЗ создания нового экземпляра"""
        content_path = self.content_dir / f"{source_id}.txt"

        if content_path.exists():
            try:
                with open(content_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error loading content for {source_id}: {e}")
                return None
        return None

    async def add_source(self, user_id: str, source_data: Dict[str, Any], content: str = None) -> Dict[str, Any]:
        """Добавляет источник в библиотеку с возможным содержанием"""
        try:
            if user_id not in self.sources:
                self.sources[user_id] = []

            # Создаем полную запись источника
            full_source = {
                'id': str(uuid.uuid4()),
                'user_id': user_id,
                'title': source_data.get('title', ''),
                'authors': source_data.get('authors', []),
                'year': source_data.get('year'),
                'source_type': source_data.get('source_type', 'book'),
                'journal': source_data.get('journal'),
                'publisher': source_data.get('publisher'),
                'url': source_data.get('url'),
                'doi': source_data.get('doi'),
                'isbn': source_data.get('isbn'),
                'custom_citation': source_data.get('custom_citation'),
                'tags': source_data.get('tags', []),
                'has_content': content is not None,
                'content_preview': content[:200] + '...' if content and len(content) > 200 else content,
                'created_at': datetime.now().isoformat(),
                'last_used': datetime.now().isoformat()
            }

            self.sources[user_id].append(full_source)
            self._save_sources()

            # Сохраняем содержание если есть
            if content:
                self._save_source_content(full_source['id'], content)

            return {
                "success": True,
                "source_id": full_source['id'],
                "message": "Источник успешно добавлен в библиотеку"
            }
        except Exception as e:
            print(f"Error adding source: {e}")
            return {
                "success": False,
                "message": f"Ошибка при добавлении источника: {str(e)}"
            }

    async def get_user_sources(self, user_id: str, page: int = 1) -> Dict[str, Any]:
        """Получает все источники пользователя"""
        try:
            user_sources = self.sources.get(user_id, [])

            # Сортируем по дате добавления (новые сначала)
            sorted_sources = sorted(user_sources, key=lambda x: x['created_at'], reverse=True)

            # Пагинация
            limit = 20
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated_sources = sorted_sources[start_idx:end_idx]

            return {
                "success": True,
                "page": page,
                "total_sources": len(user_sources),
                "sources": paginated_sources
            }
        except Exception as e:
            print(f"Error getting user sources: {e}")
            return {
                "success": False,
                "message": f"Ошибка при получении источников: {str(e)}"
            }

    async def search_sources(self, user_id: str, query: str, page: int = 1) -> Dict[str, Any]:
        """Поиск источников в библиотеке пользователя"""
        try:
            user_sources = self.sources.get(user_id, [])

            filtered_sources = []
            query_lower = query.lower()

            for source in user_sources:
                # Поиск по всем текстовым полям
                search_fields = [
                    source.get('title', ''),
                    ' '.join(source.get('authors', [])),
                    source.get('journal', ''),
                    source.get('publisher', ''),
                    source.get('doi', ''),
                    source.get('custom_citation', '')
                ]

                if any(query_lower in str(field).lower() for field in search_fields if field):
                    filtered_sources.append(source)

            # Пагинация
            limit = 20
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated_sources = filtered_sources[start_idx:end_idx]

            return {
                "success": True,
                "query": query,
                "page": page,
                "total_results": len(filtered_sources),
                "sources": paginated_sources
            }
        except Exception as e:
            print(f"Error searching sources: {e}")
            return {
                "success": False,
                "message": f"Ошибка при поиске: {str(e)}"
            }

    async def delete_source(self, user_id: str, source_id: str) -> Dict[str, Any]:
        """Удаляет источник из библиотеки"""
        try:
            if user_id not in self.sources:
                return {
                    "success": False,
                    "message": "Библиотека пользователя не найдена"
                }

            initial_count = len(self.sources[user_id])
            self.sources[user_id] = [
                source for source in self.sources[user_id]
                if source['id'] != source_id
            ]

            if len(self.sources[user_id]) < initial_count:
                self._save_sources()

                # Также удаляем файл с текстом
                try:
                    content_file = self.content_dir / f"{source_id}.txt"
                    if content_file.exists():
                        content_file.unlink()
                        print(f"Deleted content file: {content_file}")
                except Exception as e:
                    print(f"Error deleting content file: {e}")

                return {
                    "success": True,
                    "message": "Источник успешно удален"
                }
            else:
                return {
                    "success": False,
                    "message": "Источник не найден"
                }
        except Exception as e:
            print(f"Error deleting source: {e}")
            return {
                "success": False,
                "message": f"Ошибка при удалении источника: {str(e)}"
            }

    def _load_sources(self) -> Dict[str, List[Dict]]:
        """Загружает источники из файла"""
        try:
            if self.sources_file.exists():
                with open(self.sources_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"Loaded {sum(len(v) for v in data.values())} sources from file")
                    return data
            return {}
        except Exception as e:
            print(f"Error loading sources: {e}")
            return {}

    def _save_sources(self):
        """Сохраняет источники в файл"""
        try:
            with open(self.sources_file, 'w', encoding='utf-8') as f:
                json.dump(self.sources, f, ensure_ascii=False, indent=2)
            print(f"Saved sources to {self.sources_file}")
        except Exception as e:
            print(f"Error saving sources: {e}")

    async def get_source_details(self, user_id: str, source_id: str) -> Dict[str, Any]:
        """Получает детальную информацию об источнике"""
        try:
            user_sources = self.sources.get(user_id, [])
            source = next((s for s in user_sources if s['id'] == source_id), None)

            if not source:
                return {
                    "success": False,
                    "message": "Источник не найден"
                }

            # Загружаем полное содержание
            full_content = self._load_source_content(source_id)

            print(f"DEBUG: Loading content for source {source_id}")
            print(f"DEBUG: Content exists: {full_content is not None}")
            print(f"DEBUG: Content length: {len(full_content) if full_content else 0}")

            if full_content:
                print(f"DEBUG: First 200 chars: {full_content[:200]}")
            else:
                print(f"DEBUG: No content found for source {source_id}")

                # Попробуем извлечь текст из файла заново, если его нет
                if source.get('file_path') and os.path.exists(source['file_path']):
                    print(f"DEBUG: Attempting to re-extract text from file: {source['file_path']}")
                    try:
                        from app.services.simple_source_processor import SimpleSourceProcessor
                        processor = SimpleSourceProcessor()
                        reextracted_text = await processor.extract_text_from_file(Path(source['file_path']))
                        if reextracted_text.strip():
                            self._save_source_content(source_id, reextracted_text)
                            full_content = reextracted_text
                            print(f"DEBUG: Re-extracted {len(reextracted_text)} characters")
                    except Exception as e:
                        print(f"DEBUG: Failed to re-extract text: {e}")

            return {
                "success": True,
                "source": {
                    **source,
                    'full_content': full_content,
                    'content_length': len(full_content) if full_content else 0,
                    'has_full_content': bool(full_content and full_content.strip())
                }
            }
        except Exception as e:
            print(f"Error getting source details: {e}")
            return {
                "success": False,
                "message": f"Ошибка при получении информации об источнике: {str(e)}"
            }

    async def _extract_content_from_file(self, file_path: str) -> Optional[str]:
        """Извлекает текст из файла источника"""
        try:
            from app.document_parser.universal_parser import UniversalDocumentParser
            parser = UniversalDocumentParser()
            document = parser.parse_document(file_path)

            if document and document.main_content:
                full_text = ""
                for block in document.main_content:
                    if hasattr(block, 'text') and block.text:
                        full_text += block.text + "\n\n"
                return full_text.strip()
            return None
        except Exception as e:
            print(f"Error extracting content from file {file_path}: {e}")
            return None

    async def get_source_content(self, user_id: str, source_id: str) -> Dict[str, Any]:
        """Получает содержание источника"""
        try:
            user_sources = self.sources.get(user_id, [])
            source = next((s for s in user_sources if s['id'] == source_id), None)

            if not source:
                return {
                    "success": False,
                    "message": "Источник не найден"
                }

            content = self._load_source_content(source_id)

            return {
                "success": True,
                "source": source,
                "content": content
            }
        except Exception as e:
            print(f"Error getting source content: {e}")
            return {
                "success": False,
                "message": f"Ошибка при получении содержания: {str(e)}"
            }

    async def verify_citation_content(self, user_id: str, citation_text: str, source_id: str) -> Dict[str, Any]:
        """Проверяет соответствие цитаты содержанию источника"""
        try:
            # Получаем содержание источника
            content_result = await self.get_source_content(user_id, source_id)
            if not content_result['success'] or not content_result['content']:
                return {
                    "success": False,
                    "message": "Содержание источника недоступно для проверки"
                }

            source_content = content_result['content']
            citation_text_clean = self._clean_text(citation_text)
            source_content_clean = self._clean_text(source_content)

            # Проверяем различные типы совпадений
            verification_result = self._check_content_matches(citation_text_clean, source_content_clean)

            return {
                "success": True,
                "citation_text": citation_text,
                "source_id": source_id,
                "verification": verification_result,
                "source_preview": source_content[:500] + '...' if len(source_content) > 500 else source_content
            }
        except Exception as e:
            print(f"Error verifying citation content: {e}")
            return {
                "success": False,
                "message": f"Ошибка при проверке содержания: {str(e)}"
            }

    def _clean_text(self, text: str) -> str:
        """Очищает текст для сравнения"""
        if not text:
            return ""
        # Убираем лишние пробелы, приводим к нижнему регистру
        text = re.sub(r'\s+', ' ', text.strip().lower())
        return text

    def _check_content_matches(self, citation: str, source_content: str) -> Dict[str, Any]:
        """Проверяет различные типы совпадений между цитатой и содержанием"""

        # 1. Точное совпадение
        exact_match = citation in source_content

        # 2. Поиск похожих фраз (упрощенный подход)
        similar_matches = self._find_similar_phrases(citation, source_content)

        # 3. Проверка ключевых слов
        keyword_matches = self._check_keywords(citation, source_content)

        # Расчет уверенности
        confidence = self._calculate_confidence(exact_match, similar_matches, keyword_matches)

        return {
            "exact_match": exact_match,
            "similar_matches": similar_matches,
            "keyword_matches": keyword_matches,
            "confidence_score": confidence,
            "issues": self._identify_issues(exact_match, confidence)
        }

    def _find_similar_phrases(self, citation: str, source_content: str) -> List[Dict]:
        """Находит похожие фразы в содержании"""
        if not citation or not source_content:
            return []

        # Упрощенная реализация - разбиваем на слова и ищем совпадения
        citation_words = [word for word in citation.split() if len(word) > 2]
        source_words = source_content.split()

        matches = []
        window_size = min(10, len(citation_words) + 5)

        for i in range(len(source_words) - window_size + 1):
            window = source_words[i:i + window_size]
            window_text = ' '.join(window)
            window_words = set(window)

            # Простой расчет схожести
            common_words = set(citation_words).intersection(window_words)
            similarity = len(common_words) / max(len(citation_words), 1)

            if similarity > 0.3:  # Порог схожести
                matches.append({
                    "text": window_text,
                    "similarity": similarity,
                    "position": i
                })

        return sorted(matches, key=lambda x: x["similarity"], reverse=True)[:5]  # Топ-5 совпадений

    def _check_keywords(self, citation: str, source_content: str) -> Dict[str, Any]:
        """Проверяет совпадение ключевых слов"""
        if not citation or not source_content:
            return {"matching": [], "missing": [], "coverage": 0}

        citation_words = set([word for word in citation.split() if len(word) > 3])
        source_words = set(source_content.split())

        matching_keywords = citation_words.intersection(source_words)
        missing_keywords = citation_words - source_words

        return {
            "matching": list(matching_keywords),
            "missing": list(missing_keywords),
            "coverage": len(matching_keywords) / max(len(citation_words), 1)
        }

    def _calculate_confidence(self, exact_match: bool, similar_matches: List, keyword_matches: Dict) -> float:
        """Рассчитывает уверенность в соответствии"""
        confidence = 0.0

        if exact_match:
            confidence += 0.8

        # Добавляем за лучшие похожие совпадения
        if similar_matches:
            best_similarity = similar_matches[0]["similarity"] if similar_matches else 0
            confidence += best_similarity * 0.6

        # Добавляем за покрытие ключевых слов
        confidence += keyword_matches.get("coverage", 0) * 0.3

        return min(confidence, 1.0)

    def _identify_issues(self, exact_match: bool, confidence: float) -> List[str]:
        """Определяет потенциальные проблемы"""
        issues = []

        if not exact_match:
            issues.append("Точное совпадение не найдено")

        if confidence < 0.5:
            issues.append("Низкая уверенность в соответствии")

        if confidence < 0.3:
            issues.append("Возможно, цитата не соответствует источнику")

        return issues

    def get_all_sources_count(self) -> int:
        """Получает общее количество источников у всех пользователей"""
        return sum(len(sources) for sources in self.sources.values())

    async def update_source_last_used(self, user_id: str, source_id: str) -> bool:
        """Обновляет время последнего использования источника"""
        try:
            if user_id in self.sources:
                for source in self.sources[user_id]:
                    if source['id'] == source_id:
                        source['last_used'] = datetime.now().isoformat()
                        self._save_sources()
                        return True
            return False
        except Exception as e:
            print(f"Error updating source last used: {e}")
            return False

    async def get_source_content_with_fallback(self, user_id: str, source_id: str):
        """Получает контент источника с отказоустойчивостью"""
        try:
            # Сначала проверяем кэш
            cache_key = f"{user_id}:{source_id}:content"
            if cache_key in self.content_cache:
                return self.content_cache[cache_key]

            # Загружаем из файла
            content = self._load_source_content(source_id)
            if content:
                self.content_cache[cache_key] = content
                return content

            # Если файла нет, пытаемся извлечь из оригинального файла
            source = await self.get_source_details(user_id, source_id)
            if source["success"] and source["source"].get("file_path"):
                content = await self.extract_text_from_file(Path(source["source"]["file_path"]))
                if content:
                    # Сохраняем для будущего использования
                    await self.save_source_content(source_id, content)
                    self.content_cache[cache_key] = content
                    return content

            return None
        except Exception as e:
            logger.error(f"Error getting source content: {e}")
            return None

# Глобальный экземпляр сервиса
library_service = LibraryService()