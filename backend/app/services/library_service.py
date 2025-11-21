import json
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path


class LibraryService:
    def __init__(self):
        self.data_dir = Path("data/library")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.data_file = self.data_dir / "sources.json"
        self.user_sources = self._load_data()

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

    async def add_source(self, user_id: str, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """Добавляет источник в библиотеку пользователя"""
        try:
            if user_id not in self.user_sources:
                self.user_sources[user_id] = []

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
                'created_at': datetime.now().isoformat(),
                'last_used': datetime.now().isoformat()
            }

            self.user_sources[user_id].append(full_source)
            self._save_data()

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

    async def search_sources(self, user_id: str, query: str, page: int = 1) -> Dict[str, Any]:
        """Поиск источников в библиотеке пользователя"""
        try:
            user_sources = self.user_sources.get(user_id, [])

            # Простой поиск по заголовку и авторам
            filtered_sources = []
            query_lower = query.lower()

            for source in user_sources:
                if (query_lower in source.get('title', '').lower() or
                        any(query_lower in author.lower() for author in source.get('authors', [])) or
                        (source.get('publisher') and query_lower in source['publisher'].lower()) or
                        (source.get('journal') and query_lower in source['journal'].lower()) or
                        (source.get('year') and query_lower in str(source['year']))):
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
                "sources": [
                    {
                        "id": source['id'],
                        "title": source['title'],
                        "authors": source['authors'],
                        "year": source['year'],
                        "source_type": source['source_type'],
                        "publisher": source.get('publisher'),
                        "journal": source.get('journal'),
                        "confidence": 0.8
                    }
                    for source in paginated_sources
                ]
            }
        except Exception as e:
            print(f"Error searching sources: {e}")
            return {
                "success": False,
                "message": f"Ошибка при поиске: {str(e)}"
            }

    async def get_user_sources(self, user_id: str, page: int = 1) -> Dict[str, Any]:
        """Получает все источники пользователя с пагинацией"""
        try:
            user_sources = self.user_sources.get(user_id, [])

            # Пагинация
            limit = 20
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated_sources = user_sources[start_idx:end_idx]

            return {
                "success": True,
                "page": page,
                "total_sources": len(user_sources),
                "sources": [
                    {
                        "id": source['id'],
                        "title": source['title'],
                        "authors": source['authors'],
                        "year": source['year'],
                        "source_type": source['source_type'],
                        "publisher": source.get('publisher'),
                        "journal": source.get('journal'),
                        "url": source.get('url'),
                        "doi": source.get('doi'),
                        "isbn": source.get('isbn'),
                        "created_at": source['created_at'],
                        "last_used": source['last_used']
                    }
                    for source in paginated_sources
                ]
            }
        except Exception as e:
            print(f"Error getting user sources: {e}")
            return {
                "success": False,
                "message": f"Ошибка при получении источников: {str(e)}"
            }

    async def delete_source(self, user_id: str, source_id: str) -> Dict[str, Any]:
        """Удаляет источник из библиотеки пользователя"""
        try:
            if user_id not in self.user_sources:
                return {
                    "success": False,
                    "message": "Библиотека пользователя не найдена"
                }

            # Ищем и удаляем источник
            initial_count = len(self.user_sources[user_id])
            self.user_sources[user_id] = [
                source for source in self.user_sources[user_id]
                if source['id'] != source_id
            ]

            if len(self.user_sources[user_id]) < initial_count:
                self._save_data()
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

    async def get_source_by_id(self, user_id: str, source_id: str) -> Optional[Dict[str, Any]]:
        """Получает источник по ID"""
        try:
            user_sources = self.user_sources.get(user_id, [])
            for source in user_sources:
                if source['id'] == source_id:
                    return source
            return None
        except Exception as e:
            print(f"Error getting source by ID: {e}")
            return None


# Глобальный экземпляр сервиса
library_service = LibraryService()