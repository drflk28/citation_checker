import uuid
import re
from typing import Dict, Any, List, Optional
from ..models.data_models import (
    AnalysisResult, Citation, BibliographyIssue, BibliographyEntry,
    AnalysisStatus, IssueType, ParsedDocument, TextBlock, TextBlockType
)
from app.document_parser.universal_parser import UniversalDocumentParser
from app.citation_parser.citation_extractor import CitationExtractor
from app.bibliography.checker import BibliographyChecker
import requests
import json

class SimpleAnalysisService:
    def __init__(self):
        self.document_parser = UniversalDocumentParser()
        self.citation_extractor = CitationExtractor()
        self.bibliography_checker = BibliographyChecker()
        self.analysis_results: Dict[str, Dict[str, Any]] = {}

    def analyze_document(self, file_path: str, doc_id: str) -> Dict[str, Any]:
        try:
            print(f"Начинаем анализ документа {doc_id}")
            print(f"Файл: {file_path}")

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
            print("Парсим документ...")
            document = self.document_parser.parse_document(file_path)
            print(f"Документ распарсен: {len(document.main_content or [])} блоков")

            # 2. Извлечение цитат
            print("Извлекаем цитирования...")
            citations_result = self.citation_extractor.extract_citations(
                document.main_content or []
            )
            print(f"Найдено цитат: {citations_result['total_count']}")

            # 3. Поиск библиографии
            print("Ищем раздел библиографии...")
            bibliography_blocks = self.bibliography_checker.find_bibliography_section(
                document.main_content or []
            )
            print(f"Найдено библиографических записей: {len(bibliography_blocks)}")

            # 4. Создаем библиографические записи как простые словари
            bibliography_entries = self._create_bibliography_entries(bibliography_blocks)

            # 5. Улучшаем записи онлайн-поиском
            print("🔍 Улучшаем библиографические записи онлайн-поиском...")
            enhanced_entries = self.bibliography_checker.enhance_with_online_search(
                [BibliographyEntry(**entry) for entry in bibliography_entries]
            )

            # Конвертируем обратно в словари с правильной сериализацией
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
                    'library_match': self._ensure_serializable(entry.library_match)  # Добавляем library_match
                }
                bibliography_entries.append(entry_dict)

            # Логируем статистику по найденным в библиотеке
            library_matches = [e for e in bibliography_entries if e.get('library_match')]
            print(f"📚 Найдено {len(library_matches)} совпадений в локальной библиотеке")

            for match in library_matches[:3]:  # Показываем первые 3 совпадения
                lib_match = match.get('library_match', {})
                print(f"   - {lib_match.get('title', 'No title')} (ID: {lib_match.get('source_id')})")

            # 6. Проверка соответствия
            print("Проверяем соответствие цитат и библиографии...")
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

            # 7. Формируем веб-дружественный результат как простой словарь
            analysis_result = self._format_simple_result(
                doc_id, document, citations_result, validation_result, bibliography_entries
            )

            print(f" Анализ завершен для {doc_id}")
            print(f"   - Цитат: {analysis_result['citations_found']}")
            print(f"   - Проблем: {analysis_result['issues_found']}")
            print(f"   - Записей библиографии: {analysis_result['bibliography_entries_found']}")

            self.analysis_results[doc_id] = analysis_result
            return analysis_result

        except Exception as e:
            print(f"Ошибка анализа: {e}")
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

        # ОТЛАДКА: Проверяем данные перед отправкой
        print("🔍 ПРОВЕРКА ДАННЫХ ДЛЯ ФРОНТЕНДА:")
        entries_with_metadata = [e for e in bibliography_entries if e.get('online_metadata')]
        print(f"   Всего записей: {len(bibliography_entries)}")
        print(f"   Записей с online_metadata: {len(entries_with_metadata)}")

        for i, entry in enumerate(entries_with_metadata[:3]):
            metadata = entry.get('online_metadata', {})
            print(f"   Запись {i}: {metadata.get('title', 'No title')}")
            print(f"      source: {metadata.get('source')}")
            print(f"      url: {metadata.get('url')}")

        # Формируем цитаты
        citations = []
        for i, citation_detail in enumerate(citations_result.get('details', [])):
            citation = {
                'id': f"cit_{i}",
                'text': citation_detail['citation'],
                'position': {
                    'page': citation_detail['page'],
                    'context': citation_detail['context']
                },
                'context': citation_detail['context']
            }
            citations.append(citation)

        # Формируем проблемы
        issues = []

        # Пропущенные ссылки
        for missing_ref in validation_result.get('missing_references', []):
            issue = {
                'type': 'missing',
                'description': f"Ссылка '{missing_ref}' отсутствует в библиографии",
                'severity': "high",
                'suggestion': "Добавьте запись в раздел библиографии"
            }
            issues.append(issue)

        # Неиспользуемые библиографические записи
        unused_entries = [entry for entry in bibliography_entries if not entry['is_valid']]
        for entry in unused_entries:
            issue = {
                'type': 'unused',
                'description': f"Библиографическая запись не связана с цитатами: {entry['text'][:100]}...",
                'severity': "medium",
                'suggestion': "Удалите запись или добавьте соответствующую цитату в текст"
            }
            issues.append(issue)

        summary = {
            "total_references": len(citations_result.get('citations', [])),
            "missing_references": len(validation_result.get('missing_references', [])),
            "unused_references": len(unused_entries),
            "duplicate_references": 0,
            "bibliography_entries": len(bibliography_entries),
            "valid_bibliography_entries": len([e for e in bibliography_entries if e['is_valid']]),
            "completeness_score": validation_result.get('valid_count', 0) /
                                  max(1, len(citations_result.get('citations', [])))
        }

        if summary["completeness_score"] is None:
            summary["completeness_score"] = 0.0

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

        return result

    def get_analysis_result(self, doc_id: str) -> Optional[Dict[str, Any]]:
        return self.analysis_results.get(doc_id)