import re
from typing import List, Dict, Any
from app.models.data_models import TextBlock


class CitationExtractor:
    def __init__(self):
        self.citation_patterns = [
            r'\[([^\]]+)\]',  # [1], [1,2,3]
        ]

    def extract_citations(self, text_blocks: List[TextBlock]) -> Dict[str, Any]:
        print("Ищем цитирования в тексте...")
        all_citations = []
        citation_details = []

        for block in text_blocks:
            if block.block_type.value in ['paragraph', 'heading']:
                citations_in_block = self._find_citations_in_text(block.text)

                for citation in citations_in_block:
                    all_citations.append(citation)
                    citation_details.append({
                        'citation': citation,
                        'page': block.page_num,
                        'context': self._get_citation_context(block.text, citation),
                        'text_preview': block.text[:100] + '...' if len(block.text) > 100 else block.text
                    })

        unique_citations = list(set(all_citations))

        # Разделяем числовые и авторские ссылки
        numeric_citations = [c for c in unique_citations if c.isdigit()]
        author_citations = [c for c in unique_citations if not c.isdigit()]

        result = {
            'citations': unique_citations,
            'numeric_citations': numeric_citations,
            'author_citations': author_citations,
            'total_count': len(unique_citations),
            'occurrence_count': len(all_citations),
            'details': citation_details
        }

        print(f"Найдено цитирований: {result['total_count']} уникальных")
        print(f"Числовые ссылки: {len(numeric_citations)}")
        print(f"Авторские ссылки: {len(author_citations)}")
        print(f"Примеры: {unique_citations[:5]}")

        return result

    def _find_citations_in_text(self, text: str) -> List[str]:
        citations = []

        for pattern in self.citation_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if pattern == r'\[[^\]]+\]':
                    # Обработка [1], [1,2,3], [1-3]
                    citations.extend(self._process_numeric_citations(match))
                else:
                    # Обработка (Иванов, 2020)
                    citations.append(match)

        return citations

    def _process_numeric_citations(self, citation_text: str) -> List[str]:
        citations = []

        # Разделяем по запятым
        parts = [p.strip() for p in citation_text.split(',')]

        for part in parts:
            # Обработка диапазонов типа 1-3
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    citations.extend(str(i) for i in range(start, end + 1))
                except ValueError:
                    citations.append(part)
            elif part.isdigit():
                citations.append(part)

        return citations

    def _get_citation_context(self, text: str, citation: str) -> str:
        try:
            # Экранируем специальные символы для регулярных выражений
            if citation.isdigit():
                pattern = f"\\[{citation}\\]"
            else:
                # Экранируем специальные символы в авторских ссылках
                escaped_citation = re.escape(citation)
                pattern = f"\\({escaped_citation}\\)"

            match = re.search(pattern, text)
            if match:
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                return text[start:end]

            return text[:100] + '...' if len(text) > 100 else text

        except re.error as e:
            print(f"!! Ошибка regex для цитирования '{citation}': {e}")
            return text[:100] + '...' if len(text) > 100 else text