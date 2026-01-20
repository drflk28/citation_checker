import asyncio
import time
import uuid
import re
import os
from typing import Dict, Any, List, Optional
from ..models.data_models import (
    AnalysisResult, Citation, BibliographyIssue, BibliographyEntry,
    AnalysisStatus, IssueType, ParsedDocument, TextBlock, TextBlockType
)
from app.document_parser.universal_parser import UniversalDocumentParser
from app.citation_parser.citation_extractor import CitationExtractor
from app.bibliography.checker import BibliographyChecker
from app.bibliography.semantic_matcher import semantic_matcher
from app.services.library_service import library_service
import logging
import requests
import json
class SimpleAnalysisService:
    def __init__(self):
        self.document_parser = UniversalDocumentParser()
        self.citation_extractor = CitationExtractor()
        self.bibliography_checker = BibliographyChecker()
        self.analysis_results: Dict[str, Dict[str, Any]] = {}
        self.analysis_status: Dict[str, Dict[str, Any]] = {}
        self.semantic_matcher = semantic_matcher
        self.logger = logging.getLogger(__name__)

    def update_status(self, doc_id: str, stage: str, progress: int = 0):
        """Обновляет статус анализа"""
        if doc_id not in self.analysis_status:
            self.analysis_status[doc_id] = {
                'stage': stage,
                'progress': progress,
                'last_update': time.time()
            }
        else:
            self.analysis_status[doc_id].update({
                'stage': stage,
                'progress': progress,
                'last_update': time.time()
            })

    def get_analysis_status(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Получает статус анализа"""
        return self.analysis_status.get(doc_id)

    def analyze_document(self, file_path: str, doc_id: str) -> Dict[str, Any]:
        try:
            print(f"🚀 НАЧИНАЕМ АНАЛИЗ ДОКУМЕНТА {doc_id}")
            print(f"📁 Файл: {file_path}")
            print(f"📊 Существует ли файл: {os.path.exists(file_path)}")

            import time
            start_time = time.time()

            temp_result = {
                'doc_id': doc_id,
                'status': 'processing',
                'citations_found': 0,
                'issues_found': 0,
                'bibliography_entries_found': 0,
                'citations': [],
                'issues': [],
                'bibliography_entries': [],
                'summary': {}
            }
            self.analysis_results[doc_id] = temp_result

            # 1. Парсинг документа
            print("🔍 Шаг 1: Парсим документ...")
            try:
                document = self.document_parser.parse_document(file_path)
                print(f"✅ Документ распарсен: {len(document.main_content or [])} блоков")

                if not document.main_content:
                    print("⚠️ ВНИМАНИЕ: main_content пуст!")
                    result = {
                        'doc_id': doc_id,
                        'status': 'completed',
                        'citations_found': 0,
                        'issues_found': 0,
                        'bibliography_entries_found': 0,
                        'citations': [],
                        'issues': [{
                            'type': 'parsing',
                            'description': 'Не удалось извлечь текст из документа',
                            'severity': 'high',
                            'suggestion': 'Попробуйте загрузить документ в другом формате'
                        }],
                        'bibliography_entries': [],
                        'summary': {
                            "total_references": 0,
                            "missing_references": 0,
                            "unused_references": 0,
                            "duplicate_references": 0,
                            "bibliography_entries": 0,
                            "valid_bibliography_entries": 0,
                            "completeness_score": 0
                        },
                        'error_message': None
                    }
                    self.analysis_results[doc_id] = result
                    return result

            except Exception as e:
                print(f"❌ Ошибка парсинга: {e}")
                import traceback
                traceback.print_exc()

                result = {
                    'doc_id': doc_id,
                    'status': 'error',
                    'citations_found': 0,
                    'issues_found': 0,
                    'bibliography_entries_found': 0,
                    'citations': [],
                    'issues': [],
                    'bibliography_entries': [],
                    'summary': {},
                    'error_message': f'Ошибка парсинга документа: {str(e)}'
                }
                self.analysis_results[doc_id] = result
                return result

            # 2. Извлечение цитат
            print("🔍 Шаг 2: Извлекаем цитирования...")
            try:
                citations_result = self.citation_extractor.extract_citations(
                    document.main_content or []
                )
                print(f"✅ Найдено цитат: {citations_result.get('total_unique', 0)}")
                print(f"📝 Примеры цитат: {citations_result.get('citations', [])[:5]}")
            except Exception as e:
                print(f"❌ Ошибка извлечения цитат: {e}")
                citations_result = {
                    'total_unique': 0,
                    'citations': [],
                    'details': []
                }

            # 3. Поиск библиографии
            print("🔍 Шаг 3: Ищем раздел библиографии...")
            try:
                bibliography_blocks = self.bibliography_checker.find_bibliography_section(
                    document.main_content or []
                )
                print(f"✅ Найдено библиографических записей: {len(bibliography_blocks)}")
            except Exception as e:
                print(f"❌ Ошибка поиска библиографии: {e}")
                bibliography_blocks = []

            # 4. Создаем библиографические записи как простые словари
            print("🔍 Шаг 4: Создаем библиографические записи...")
            bibliography_entries = self._create_bibliography_entries(bibliography_blocks)

            # 5. Пропускаем онлайн-поиск для скорости (раскомментируйте если нужно)
            print("🔍 Шаг 5: Улучшаем записи...")
            try:
                enhanced_entries = self.bibliography_checker.enhance_with_online_search(
                    [BibliographyEntry(**entry) for entry in bibliography_entries]
                )

                # Конвертируем обратно в словари
                bibliography_entries = []
                for entry in enhanced_entries:
                    entry_dict = {
                        'id': entry.id,
                        'text': entry.text,
                        'position': entry.position,
                        'is_valid': entry.is_valid,
                        'is_verified': entry.is_verified,
                        'matched_citations': entry.matched_citations,
                        'enhancement_confidence': entry.enhancement_confidence,
                        'search_queries': entry.search_queries,
                        'online_metadata': self._ensure_serializable(entry.online_metadata),
                        'library_match': self._ensure_serializable(entry.library_match)
                    }
                    bibliography_entries.append(entry_dict)

                print(f"✅ Улучшено записей: {len(bibliography_entries)}")
            except Exception as e:
                print(f"⚠️ Ошибка улучшения записей (продолжаем без улучшения): {e}")
                # Продолжаем с оригинальными записями

            # 6. Проверка соответствия
            print("🔍 Шаг 6: Проверяем соответствие цитат и библиографии...")
            try:
                if bibliography_blocks:
                    validation_result = self.bibliography_checker.check_citations_vs_bibliography(
                        citations_result['citations'],
                        bibliography_blocks
                    )

                    # Обновляем библиографические записи информацией о совпадениях
                    bibliography_entries = self._update_bibliography_with_matches(
                        bibliography_entries, validation_result
                    )
                else:
                    validation_result = {
                        'valid_references': [],
                        'missing_references': citations_result['citations'],
                        'valid_count': 0,
                        'missing_count': len(citations_result['citations']),
                        'bibliography_found': False
                    }
            except Exception as e:
                print(f"❌ Ошибка проверки соответствия: {e}")
                validation_result = {
                    'valid_references': [],
                    'missing_references': [],
                    'valid_count': 0,
                    'missing_count': 0,
                    'bibliography_found': False
                }

            # 7. Формируем результат
            print("🔍 Шаг 7: Формируем результат...")
            try:
                analysis_result = self._format_simple_result(
                    doc_id, document, citations_result, validation_result, bibliography_entries
                )

                end_time = time.time()
                print(f"✅ Анализ завершен за {end_time - start_time:.2f} секунд")
                print(
                    f"📊 Результат: {len(analysis_result.get('citations', []))} цитат, {len(analysis_result.get('bibliography_entries', []))} источников")

                self.analysis_results[doc_id] = analysis_result
                return analysis_result

            except Exception as e:
                print(f"❌ Ошибка форматирования результата: {e}")
                import traceback
                traceback.print_exc()

                result = {
                    'doc_id': doc_id,
                    'status': 'error',
                    'citations_found': 0,
                    'issues_found': 0,
                    'bibliography_entries_found': 0,
                    'citations': [],
                    'issues': [],
                    'bibliography_entries': [],
                    'summary': {},
                    'error_message': f'Ошибка формирования результата: {str(e)}'
                }
                self.analysis_results[doc_id] = result
                return result

        except Exception as e:
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА В analyze_document: {e}")
            import traceback
            traceback.print_exc()

            error_result = {
                'doc_id': doc_id,
                'status': 'error',
                'citations_found': 0,
                'issues_found': 0,
                'bibliography_entries_found': 0,
                'citations': [],
                'issues': [],
                'bibliography_entries': [],
                'summary': {},
                'error_message': str(e)
            }
            self.analysis_results[doc_id] = error_result
            return error_result

    def _verify_citation_against_source(self, citation: Dict, source: Dict) -> Dict[str, Any]:
        """Проверяет цитату против конкретного источника"""
        try:
            # Получаем полный текст источника
            source_content = library_service._load_source_content(source['id'])

            if not source_content:
                return {
                    'verified': False,
                    'confidence': 0,
                    'source_id': source['id'],
                    'source_title': source.get('title', 'Unknown'),
                    'reason': 'Текст источника недоступен'
                }

            # Создаем данные для семантического анализа
            citation_data = {
                'text': citation.get('text', ''),
                'context': citation.get('context', ''),
                'full_paragraph': citation.get('full_paragraph', ''),
                'citation_number': citation.get('citation_number')
            }

            source_data = {
                'id': source['id'],
                'title': source.get('title', ''),
                'full_content': source_content
            }

            # Выполняем семантическую проверку
            result = self.semantic_matcher.verify_citation_in_source(
                citation_data, source_data
            )

            return {
                'verified': result['verified'],
                'confidence': result['confidence'],
                'verification_level': result.get('verification_level', 'unknown'),
                'source_id': source['id'],
                'source_title': source.get('title', 'Unknown'),
                'best_match': result.get('best_match'),
                'key_phrases_matched': result.get('best_match', {}).get('key_phrases_matched', [])
            }

        except Exception as e:
            logger.error(f"Error verifying citation against source: {e}")
            return {
                'verified': False,
                'confidence': 0,
                'source_id': source.get('id', 'unknown'),
                'source_title': source.get('title', 'Unknown'),
                'reason': f'Ошибка анализа: {str(e)}'
            }

    def _ensure_serializable(self, data: Any) -> Any:
        """Обеспечивает сериализуемость данных"""
        if data is None:
            return {}
        if isinstance(data, dict):
            return {k: self._ensure_serializable(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self._ensure_serializable(item) for item in data]
        if isinstance(data, (str, int, float, bool)):
            return data
        # Конвертируем любые другие типы в строку
        return str(data)

    def _create_bibliography_entries(self, bibliography_blocks: List[TextBlock]) -> List[Dict[str, Any]]:
        """Создает библиографические записи как простые словари"""
        entries = []
        for i, block in enumerate(bibliography_blocks):
            entry = {
                'id': f"bib_{i}",
                'text': block.text,
                'position': {
                    'page': block.page_num,
                    'block_type': block.block_type.value
                },
                'is_valid': False,
                'is_verified': False,
                'matched_citations': [],
                'online_metadata': {},  # Начинаем с пустого словаря
                'enhancement_confidence': 0.0,
                'search_queries': []
            }
            entries.append(entry)
        return entries

    def _update_bibliography_with_matches(self, bibliography_entries: List[Dict], validation_result: Dict) -> List[
        Dict]:
        valid_refs = set(validation_result.get('valid_references', []))

        print(f"ПРОВЕРКА СООТВЕТСТВИЯ БИБЛИОГРАФИИ И ЦИТАТ")
        print(f"   Валидные цитаты: {sorted(valid_refs)}")
        print(f"   Всего записей библиографии: {len(bibliography_entries)}")

        # Сбрасываем статусы
        for entry in bibliography_entries:
            entry['matched_citations'] = []
            entry['is_valid'] = False

        # Для библиографии без явных номеров используем простую логику:
        # Если есть N записей, то они соответствуют номерам 1..N
        entry_number_mapping = {}
        total_entries = len(bibliography_entries)

        print(f"   СОЗДАЕМ СООТВЕТСТВИЯ (1..{total_entries}):")
        for i in range(total_entries):
            number = str(i + 1)
            entry_number_mapping[number] = bibliography_entries[i]
            print(f"      Номер {number} -> Запись #{i + 1}")

        # Сопоставляем цитаты с записями
        matched_count = 0
        for ref in valid_refs:
            print(f"   Сопоставляем цитату '[{ref}]'...")
            if ref in entry_number_mapping:
                entry = entry_number_mapping[ref]
                entry['matched_citations'].append(ref)
                entry['is_valid'] = True
                matched_count += 1
                print(f"      Цитата [{ref}] -> Запись #{bibliography_entries.index(entry) + 1}")
            else:
                print(f"      Цитата [{ref}] выходит за пределы библиографии (1..{total_entries})")

        # Статистика
        valid_count = len([e for e in bibliography_entries if e['is_valid']])
        print(f"ИТОГ: {valid_count} из {total_entries} записей используются")

        return bibliography_entries

    def _format_simple_result(self, doc_id: str, document: ParsedDocument, citations_result: Dict,
                              validation_result: Dict, bibliography_entries: List[Dict]) -> Dict[str, Any]:
        """Форматирует результат как простой словарь"""

        print(f"\n{'=' * 80}")
        print("🔍 ФОРМИРОВАНИЕ ЦИТАТ ДЛЯ ФРОНТЕНДА:")

        # Получаем details
        details_data = citations_result.get('details', [])

        # Формируем цитаты
        citations = []

        if isinstance(details_data, list):
            print(f"   Найдено {len(details_data)} детализированных записей о цитатах")

            for i, detail in enumerate(details_data):
                if not isinstance(detail, dict):
                    continue

                citation_num = detail.get('citation', '')

                # ====== ФИЛЬТР: игнорируем невалидные цитаты ======
                if not citation_num.isdigit():
                    print(f"   Пропускаем не-цифровую цитату: [{citation_num}]")
                    continue

                # ====== Получаем данные о цитате ======
                full_paragraph = detail.get('merged_paragraph', '')
                if not full_paragraph and detail.get('paragraphs'):
                    full_paragraph = detail['paragraphs'][0] if detail['paragraphs'] else ''

                # Номер страницы
                page_num = 1
                occurrences = detail.get('occurrences', [])
                if occurrences:
                    page_num = occurrences[0].get('page', 1)

                # ====== Извлекаем предложение с цитатой (для citation.text) ======
                citation_text = f"[{citation_num}]"  # По умолчанию
                context_text = ""

                if full_paragraph:
                    # Ищем цитату в тексте
                    citation_marker = f"[{citation_num}]"
                    if citation_marker in full_paragraph:
                        # Находим позицию цитаты
                        pos = full_paragraph.find(citation_marker)

                        # 1. Находим начало предложения (для citation.text)
                        sentence_start = pos
                        for j in range(pos - 1, max(-1, pos - 300), -1):
                            if j < 0:
                                sentence_start = 0
                                break
                            if full_paragraph[j] in '.!?':
                                sentence_start = j + 1
                                # Пропускаем пробелы
                                while sentence_start < len(full_paragraph) and full_paragraph[
                                    sentence_start] in ' \t\n':
                                    sentence_start += 1
                                break

                        # 2. Находим конец предложения
                        sentence_end = pos + len(citation_marker)
                        for j in range(sentence_end, min(len(full_paragraph), sentence_end + 300)):
                            if full_paragraph[j] in '.!?':
                                sentence_end = j + 1
                                # Включаем закрывающие кавычки
                                while sentence_end < len(full_paragraph) and full_paragraph[sentence_end] in '"»\u201d':
                                    sentence_end += 1
                                break

                        # 3. Извлекаем полное предложение с цитатой
                        full_sentence = full_paragraph[sentence_start:sentence_end].strip()

                        if full_sentence:
                            citation_text = full_sentence
                            print(f"   Цитата [{citation_num}]: {full_sentence[:80]}...")

                        # 4. Создаем расширенный контекст (для citation.context)
                        # Берем 100 символов до и после цитаты
                        context_start = max(0, pos - 100)
                        context_end = min(len(full_paragraph), pos + len(citation_marker) + 100)
                        context_text = full_paragraph[context_start:context_end]

                        # Добавляем многоточия если обрезали
                        if context_start > 0:
                            context_text = "..." + context_text
                        if context_end < len(full_paragraph):
                            context_text = context_text + "..."

                    else:
                        # Если не нашли цитату в тексте, берем начало абзаца
                        citation_text = full_paragraph[:150] + "..." if len(full_paragraph) > 150 else full_paragraph
                        context_text = full_paragraph

                # ====== Формируем объект цитаты для фронтенда ======
                citations.append({
                    'id': f"cit_{len(citations)}",
                    'text': citation_text,  # Предложение с цитатой
                    'context': context_text,  # Расширенный контекст
                    'full_paragraph': full_paragraph,  # Полный абзац
                    'page': page_num,
                    'style': 'numeric',
                    'citation_number': int(citation_num)
                })

        print(f"✅ Сформировано {len(citations)} валидных цитат")

        # ====== Формируем проблемы ======
        issues = []

        # Пропущенные ссылки (только цифровые)
        valid_missing_refs = []
        for missing_ref in validation_result.get('missing_references', []):
            if isinstance(missing_ref, str) and missing_ref.isdigit():
                valid_missing_refs.append(missing_ref)
            else:
                print(f"   Игнорируем не-цифровую пропущенную ссылку: '{missing_ref}'")

        for missing_ref in valid_missing_refs:
            issue = {
                'type': 'missing',
                'description': f"Ссылка '[{missing_ref}]' отсутствует в библиографии",
                'severity': "high",
                'suggestion': "Добавьте запись в раздел библиографии"
            }
            issues.append(issue)

        # Неиспользуемые библиографические записи
        unused_entries = [entry for entry in bibliography_entries if not entry.get('is_valid', False)]
        for entry in unused_entries:
            issue = {
                'type': 'unused',
                'description': f"Библиографическая запись не связана с цитатами: {entry.get('text', '')[:100]}...",
                'severity': "medium",
                'suggestion': "Удалите запись или добавьте соответствующую цитату в текст"
            }
            issues.append(issue)

        # ====== Вычисляем статистику ======
        total_citations = len(citations)  # Используем отфильтрованный список
        valid_count = len(validation_result.get('valid_references', []))

        completeness_score = valid_count / max(1, total_citations) if total_citations > 0 else 0.0

        summary = {
            "total_references": total_citations,
            "missing_references": len(valid_missing_refs),
            "unused_references": len(unused_entries),
            "duplicate_references": 0,
            "bibliography_entries": len(bibliography_entries),
            "valid_bibliography_entries": len([e for e in bibliography_entries if e.get('is_valid', False)]),
            "completeness_score": round(completeness_score * 100, 2)  # В процентах
        }

        result = {
            'doc_id': doc_id,
            'status': 'completed',
            'citations_found': len(citations),
            'issues_found': len(issues),
            'bibliography_entries_found': len(bibliography_entries),
            'citations': citations,
            'issues': issues,
            'bibliography_entries': bibliography_entries,
            'summary': summary,
            'error_message': None
        }

        print(f"{'=' * 80}\n")
        return result

    def get_analysis_result(self, doc_id: str) -> Optional[Dict[str, Any]]:
        return self.analysis_results.get(doc_id)

    async def perform_semantic_check(self, doc_id: str) -> Dict[str, Any]:
        """Выполняет семантическую проверку с таймаутами"""
        try:
            # Добавляем таймаут
            timeout_seconds = 30

            # Создаем задачу с таймаутом
            task = asyncio.create_task(self._perform_semantic_check_internal(doc_id))

            try:
                result = await asyncio.wait_for(task, timeout=timeout_seconds)
                return result
            except asyncio.TimeoutError:
                print(f"❌ Семантическая проверка превысила таймаут {timeout_seconds} секунд")
                task.cancel()  # Отменяем задачу
                return {
                    'success': False,
                    'error': 'Превышено время ожидания',
                    'doc_id': doc_id
                }

        except Exception as e:
            print(f"❌ Ошибка при семантической проверке: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
                'doc_id': doc_id
            }

    async def _perform_semantic_check_internal(self, doc_id: str) -> Dict[str, Any]:
        """Внутренняя логика семантической проверки"""
        print(f"\n🔍 НАЧИНАЕМ СЕМАНТИЧЕСКУЮ ПРОВЕРКУ ДЛЯ ДОКУМЕНТА {doc_id}")

        # Получаем существующий результат анализа
        analysis_result = self.analysis_results.get(doc_id)
        if not analysis_result:
            return {'success': False, 'error': 'Analysis result not found'}

        # Получаем все источники из библиотеки
        user_id = "demo_user"

        # ЗДЕСЬ ВАЖНО: Проверяем доступность library_service
        if not hasattr(self, 'library_service') or self.library_service is None:
            return {'success': False, 'error': 'Library service not available'}

        user_sources = getattr(self.library_service, 'sources', {}).get(user_id, [])
        print(f"📚 Проверяем {len(analysis_result['citations'])} цитат против {len(user_sources)} источников")

        if not user_sources:
            return {
                'success': True,
                'doc_id': doc_id,
                'verified_citations': 0,
                'total_citations': len(analysis_result['citations']),
                'message': 'Библиотека пуста'
            }

        enhanced_citations = []
        processed_count = 0

        # Для каждой цитаты ищем семантические совпадения в источниках
        for citation in analysis_result['citations']:
            citation_verifications = []
            processed_count += 1

            print(f"🔍 Проверка цитаты {processed_count}/{len(analysis_result['citations'])}")

            # Проверяем в каждом источнике
            for source in user_sources:
                if source.get('has_content'):
                    try:
                        verification_result = await self._verify_citation_against_source_async(
                            citation, source
                        )

                        if verification_result['verified']:
                            citation_verifications.append(verification_result)
                            # Останавливаемся после первого успешного совпадения
                            break
                    except Exception as e:
                        print(f"⚠️ Ошибка при проверке источника {source.get('id')}: {e}")
                        continue

            # Добавляем информацию о верификации к цитате
            citation['semantic_verifications'] = citation_verifications
            citation['verified_count'] = len(citation_verifications)
            citation['is_verified'] = len(citation_verifications) > 0

            enhanced_citations.append(citation)

        # Обновляем результат анализа
        analysis_result['citations'] = enhanced_citations

        # Обновляем статистику
        verified_citations = [c for c in enhanced_citations if c.get('is_verified')]
        analysis_result['semantic_verification_stats'] = {
            'total_citations': len(enhanced_citations),
            'verified_citations': len(verified_citations),
            'verification_rate': len(verified_citations) / len(enhanced_citations) if enhanced_citations else 0,
            'sources_checked': len(user_sources),
            'status': 'completed'
        }
        analysis_result['semantic_check_pending'] = False

        print(
            f"✅ Семантическая проверка завершена: {len(verified_citations)} из {len(enhanced_citations)} цитат верифицированы"
        )

        return {
            'success': True,
            'doc_id': doc_id,
            'verified_citations': len(verified_citations),
            'total_citations': len(enhanced_citations)
        }