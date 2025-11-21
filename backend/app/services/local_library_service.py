# app/services/local_library_service.py
import sqlite3
import json
import uuid
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from fuzzywuzzy import fuzz

from app.search.base_searcher import BaseSearcher
from app.models.data_models import UserSource, SearchMatch, SourceType


class LocalLibraryService(BaseSearcher):
    def __init__(self, user_id: str):
        self.user_id = user_id
        # Создаем директорию если не существует
        os.makedirs("data/users", exist_ok=True)
        self.db_path = f"data/users/{user_id}/library.db"
        self._init_db()

    def _init_db(self):
        """Инициализация БД пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                title TEXT,
                authors_json TEXT,
                year INTEGER,
                source_type TEXT,
                journal TEXT,
                publisher TEXT,
                url TEXT,
                doi TEXT,
                isbn TEXT,
                custom_citation TEXT,
                tags_json TEXT,
                created_at TIMESTAMP,
                last_used TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def _row_to_source(self, row) -> UserSource:
        """Конвертирует строку БД в UserSource"""
        return UserSource(
            id=row[0],
            user_id=row[1],
            title=row[2],
            authors=json.loads(row[3]) if row[3] else [],
            year=row[4],
            source_type=SourceType(row[5]) if row[5] else SourceType.OTHER,
            journal=row[6],
            publisher=row[7],
            url=row[8],
            doi=row[9],
            isbn=row[10],
            custom_citation=row[11],
            tags=json.loads(row[12]) if row[12] else [],
            created_at=datetime.fromisoformat(row[13]),
            last_used=datetime.fromisoformat(row[14])
        )

    async def search(self, query: str, limit: int = 10) -> List[SearchMatch]:
        """Поиск в локальной библиотеке"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM sources WHERE user_id = ?', (self.user_id,))
        rows = cursor.fetchall()
        conn.close()

        matches = []
        for row in rows:
            source = self._row_to_source(row)
            score, matched_fields = self._calculate_match_score(source, query)
            if score > 0.3:  # порог схожести
                matches.append(SearchMatch(
                    source=source,
                    confidence=score,
                    matched_fields=matched_fields
                ))

        # Сортируем по уверенности и обновляем время использования
        sorted_matches = sorted(matches, key=lambda x: x.confidence, reverse=True)[:limit]
        for match in sorted_matches:
            await self._update_last_used(match.source.id)

        return sorted_matches

    def _calculate_match_score(self, source: UserSource, query: str) -> tuple:
        """Вычисление релевантности"""
        scores = []
        matched_fields = []

        # Поиск по названию
        if source.title:
            title_score = fuzz.partial_ratio(query.lower(), source.title.lower())
            if title_score > 70:
                scores.append(title_score / 100)
                matched_fields.append("title")

        # Поиск по авторам
        if source.authors:
            author_scores = [fuzz.partial_ratio(query.lower(), author.lower())
                             for author in source.authors]
            max_author_score = max(author_scores) if author_scores else 0
            if max_author_score > 70:
                scores.append(max_author_score / 100)
                matched_fields.append("authors")

        # Поиск по году
        if query.isdigit() and source.year:
            year_match = abs(int(query) - source.year) <= 2
            if year_match:
                scores.append(0.8)
                matched_fields.append("year")

        avg_score = sum(scores) / len(scores) if scores else 0
        return avg_score, matched_fields

    async def _update_last_used(self, source_id: str):
        """Обновление времени последнего использования"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE sources SET last_used = ? WHERE id = ?',
            (datetime.now().isoformat(), source_id)
        )
        conn.commit()
        conn.close()

    async def add_source(self, source_data: Dict[str, Any]) -> bool:
        """Добавление источника в библиотеку"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO sources 
                (id, user_id, title, authors_json, year, source_type, journal, 
                 publisher, url, doi, isbn, custom_citation, tags_json, created_at, last_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                source_data['id'],
                source_data['user_id'],
                source_data['title'],
                json.dumps(source_data.get('authors', [])),
                source_data.get('year'),
                source_data.get('source_type', SourceType.OTHER.value),
                source_data.get('journal'),
                source_data.get('publisher'),
                source_data.get('url'),
                source_data.get('doi'),
                source_data.get('isbn'),
                source_data.get('custom_citation'),
                json.dumps(source_data.get('tags', [])),
                source_data['created_at'].isoformat(),
                source_data['last_used'].isoformat()
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error adding source: {e}")
            return False

    async def get_sources(self, page: int = 1, limit: int = 20) -> List[UserSource]:
        """Получение источников с пагинацией"""
        offset = (page - 1) * limit
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM sources 
            WHERE user_id = ? 
            ORDER BY last_used DESC 
            LIMIT ? OFFSET ?
        ''', (self.user_id, limit, offset))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_source(row) for row in rows]

    async def delete_source(self, source_id: str) -> bool:
        """Удаление источника"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sources WHERE id = ? AND user_id = ?',
                           (source_id, self.user_id))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting source: {e}")
            return False