import re
from typing import List, Dict, Any, Tuple
from app.models.data_models import TextBlock


class CitationExtractor:
    def __init__(self):
        self.citation_patterns = [
            r'\[([^\]]+)\]',  # [1], [1,2,3]
        ]
        # Паттерны, которые НЕ являются цитатами
        self.non_citation_patterns = [
            r'\[Электронный ресурс\]',
            r'\[Электрон\. ресурс\]',
            r'\[Эл\. ресурс\]',
            r'\[Режим доступа\]',
            r'\[Рис\. \d+\]',
            r'\[Табл\. \d+\]',
        ]

    def _is_valid_citation(self, citation: str) -> bool:
        """Проверяет, является ли текст валидной цитатой"""
        # Игнорируем известные не-цитаты
        for pattern in self.non_citation_patterns:
            if re.fullmatch(pattern, f"[{citation}]", re.IGNORECASE):
                return False

        # Цитата должна быть числовой или числовым диапазоном
        if re.match(r'^\d+$', citation):  # 1, 2, 3
            return True
        if re.match(r'^\d+-\d+$', citation):  # 1-3, 10-15
            return True
        if re.match(r'^\d+(,\s*\d+)+$', citation):  # 1,2,3 или 1, 2, 3
            return True

        return False

    def extract_citations_with_full_context(self, text_blocks: List[TextBlock]) -> Dict[str, Any]:
        """Извлекает цитаты с полными абзацами контекста"""
        print("Ищем цитирования в тексте с полным контекстом...")

        # Сначала объединяем абзацы для лучшего анализа контекста
        merged_texts = self._merge_paragraphs(text_blocks)

        citation_details = []

        for i, (text, page_num) in enumerate(merged_texts):
            citations_in_text = self._find_citations_in_text(text)

            for citation in citations_in_text:
                # Извлекаем полный абзац с цитатой
                full_paragraph = self._get_full_paragraph_with_citation(text, citation)

                # Очищаем для лучшего отображения
                clean_paragraph = self._clean_paragraph_for_display(full_paragraph)

                citation_details.append({
                    'citation': citation,
                    'page': page_num,
                    'full_paragraph': clean_paragraph,
                    'context': self._get_extended_context(text, citation),
                    'text_preview': self._extract_meaningful_part(full_paragraph),
                    'block_index': i,
                    'paragraph_length': len(full_paragraph)
                })

        # Группируем по цитатам и объединяем абзацы
        grouped_citations = self._group_and_merge_citations(citation_details)

        result = {
            'citations': list(grouped_citations.keys()),
            'total_unique': len(grouped_citations),
            'total_occurrences': len(citation_details),
            'details': list(grouped_citations.values())
        }

        print(f"Найдено цитирований: {result['total_unique']} уникальных")
        print(f"Примеры цитат с полным контекстом:")
        for citation_num in result['citations'][:3]:
            if citation_num in grouped_citations:
                detail = grouped_citations[citation_num]
                print(f"  [{citation_num}]: {detail['merged_paragraph'][:100]}...")

        print(f"🔍 DEBUG CITATION EXTRACTOR:")
        print(f"   citations list: {result['citations']}")
        print(f"   details type: {type(result['details'])}")

        if isinstance(result['details'], dict):
            print(f"   details keys: {list(result['details'].keys())}")
            for key in list(result['details'].keys())[:3]:
                print(
                    f"   key '{key}': {result['details'][key].keys() if isinstance(result['details'][key], dict) else 'not dict'}")
        elif isinstance(result['details'], list):
            print(f"   details length: {len(result['details'])}")
            if result['details']:
                print(
                    f"   first item keys: {result['details'][0].keys() if isinstance(result['details'][0], dict) else 'not dict'}")

        return result

    def _merge_paragraphs(self, text_blocks: List[TextBlock]) -> List[Tuple[str, int]]:
        """Объединяет короткие абзацы для получения полного контекста"""
        merged_texts = []
        current_paragraph = ""
        current_page = 1

        for block in text_blocks:
            if block.block_type.value in ['paragraph', 'list_item']:
                text = block.text.strip()

                # Если абзац очень короткий, объединяем его с предыдущим
                if len(text) < 50 and current_paragraph:
                    current_paragraph += " " + text
                else:
                    # Сохраняем предыдущий объединенный абзац
                    if current_paragraph:
                        merged_texts.append((current_paragraph, current_page))

                    # Начинаем новый абзац
                    current_paragraph = text
                    current_page = block.page_num
            else:
                # Сохраняем текущий абзац перед другим типом блока
                if current_paragraph:
                    merged_texts.append((current_paragraph, current_page))
                    current_paragraph = ""

                # Добавляем текущий блок как отдельный элемент
                merged_texts.append((block.text.strip(), block.page_num))

        # Добавляем последний абзац
        if current_paragraph:
            merged_texts.append((current_paragraph, current_page))

        return merged_texts

    def _get_full_paragraph_with_citation(self, text: str, citation: str) -> str:
        """Получает полный абзац, содержащий цитату"""
        # Находим позицию цитаты
        if citation.isdigit():
            pattern = f"\\[{citation}\\]"
        else:
            pattern = f"\\({citation}\\)"

        match = re.search(pattern, text)
        if not match:
            return text  # Возвращаем весь текст если не нашли цитату

        start_pos = match.start()
        end_pos = match.end()

        # Определяем границы предложения
        sentence_start = self._find_sentence_start(text, start_pos)
        sentence_end = self._find_sentence_end(text, end_pos)

        # Извлекаем полное предложение
        full_sentence = text[sentence_start:sentence_end]

        # Если предложение короткое, берем больше контекста
        if len(full_sentence) < 100:
            # Берем +/- 200 символов вокруг цитаты
            context_start = max(0, start_pos - 200)
            context_end = min(len(text), end_pos + 200)
            full_context = text[context_start:context_end]

            # Добавляем многоточие если обрезали
            if context_start > 0:
                full_context = "..." + full_context
            if context_end < len(text):
                full_context = full_context + "..."

            return full_context

        return full_sentence

    def _find_sentence_start(self, text: str, position: int) -> int:
        """Находит начало предложения перед указанной позицией"""
        # Ищем конец предыдущего предложения
        for i in range(position - 1, max(-1, position - 300), -1):
            if i < 0:
                return 0
            if text[i] in '.!?':
                # Пропускаем возможные кавычки или пробелы
                j = i + 1
                while j < len(text) and text[j] in ' \t\n"\'«»':
                    j += 1
                return j
        return max(0, position - 300)

    def _find_sentence_end(self, text: str, position: int) -> int:
        """Находит конец предложения после указанной позиции"""
        # Ищем конец текущего предложения
        for i in range(position, min(len(text), position + 300)):
            if text[i] in '.!?':
                # Включаем возможные закрывающие кавычки
                j = i + 1
                while j < len(text) and text[j] in '"\'\u201d»':
                    j += 1
                return j
        return min(len(text), position + 300)

    def _clean_paragraph_for_display(self, paragraph: str) -> str:
        """Очищает абзац для отображения"""
        # Убираем лишние пробелы
        paragraph = re.sub(r'\s+', ' ', paragraph.strip())

        # Убираем разрывы строк внутри абзаца
        paragraph = paragraph.replace('\n', ' ')

        return paragraph

    def _extract_meaningful_part(self, paragraph: str, max_length: int = 150) -> str:
        """Извлекает наиболее значимую часть абзаца"""
        # Ищем первое предложение с цитатой
        sentences = re.split(r'(?<=[.!?])\s+', paragraph)

        for sentence in sentences:
            if '[' in sentence or '(' in sentence:
                # Обрезаем если слишком длинное
                if len(sentence) > max_length:
                    return sentence[:max_length] + "..."
                return sentence

        # Если не нашли предложение с цитатой, берем начало абзаца
        if len(paragraph) > max_length:
            return paragraph[:max_length] + "..."
        return paragraph

    def _group_and_merge_citations(self, citation_details: List[Dict]) -> Dict[str, Any]:
        """Группирует цитаты и объединяет их абзацы"""
        grouped = {}

        for detail in citation_details:
            citation = detail['citation']

            if citation not in grouped:
                grouped[citation] = {
                    'citation': citation,
                    'occurrences': [],
                    'paragraphs': [],
                    'contexts': [],
                    'merged_paragraph': ''
                }

            grouped[citation]['occurrences'].append({
                'page': detail['page'],
                'text_preview': detail['text_preview'],
                'paragraph_length': detail['paragraph_length'],
                'block_index': detail['block_index']
            })

            grouped[citation]['paragraphs'].append(detail['full_paragraph'])
            grouped[citation]['contexts'].append(detail['context'])

        # Объединяем абзацы для каждой цитаты
        for citation, data in grouped.items():
            paragraphs = data['paragraphs']

            if len(paragraphs) == 1:
                # Один абзац - используем как есть
                data['merged_paragraph'] = paragraphs[0]
            else:
                # Объединяем абзацы, убирая дубликаты
                unique_paragraphs = []
                seen = set()

                for para in paragraphs:
                    # Берем первые 100 символов как ключ уникальности
                    para_key = para[:100]
                    if para_key not in seen:
                        seen.add(para_key)
                        unique_paragraphs.append(para)

                # Объединяем уникальные абзацы
                if unique_paragraphs:
                    separator = " [...] "
                    combined = separator.join(unique_paragraphs)

                    # Ограничиваем длину
                    if len(combined) > 800:
                        # Оставляем первые 400 и последние 400 символов
                        data['merged_paragraph'] = combined[:400] + separator + "..." + separator + combined[-400:]
                    else:
                        data['merged_paragraph'] = combined
                else:
                    data['merged_paragraph'] = paragraphs[0]

        return grouped

    def _find_citations_in_text(self, text: str) -> List[str]:
        """Находит все цитаты в тексте"""
        citations = []

        for pattern in self.citation_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if pattern == r'\[[^\]]+\]':
                    # Проверяем, является ли это валидной цитатой
                    if self._is_valid_citation(match):
                        citations.extend(self._process_numeric_citations(match))
                else:
                    # Обработка (Иванов, 2020)
                    citations.append(match)

        return citations

    def _process_numeric_citations(self, citation_text: str) -> List[str]:
        """Обрабатывает числовые цитаты"""
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
        """Получает текст перед цитатой"""
        if citation.isdigit():
            pattern = f"\\[{citation}\\]"
        else:
            pattern = f"\\[{citation}\\]"

        match = re.search(pattern, text)
        if not match:
            return ""

        # Находим начало предложения
        start_pos = match.start()

        # Ищем начало предложения (первый символ после точки, восклицательного или вопросительного знака)
        sentence_start = start_pos
        for i in range(start_pos - 1, max(-1, start_pos - 200), -1):
            if i < 0:
                sentence_start = 0
                break
            if text[i] in '.!?':
                sentence_start = i + 1
                # Пропускаем пробелы
                while sentence_start < len(text) and text[sentence_start] in ' \t\n':
                    sentence_start += 1
                break

        # Берем текст от начала предложения до цитаты
        context = text[sentence_start:start_pos].strip()

        # Если контекст очень короткий, берем больше
        if len(context) < 20:
            context_start = max(0, start_pos - 100)
            context = text[context_start:start_pos].strip()
            if context_start > 0:
                context = "..." + context

        return context

    def _get_extended_context(self, text: str, citation: str, char_count: int = 300) -> str:
        """Получает расширенный контекст вокруг цитаты"""
        try:
            if citation.isdigit():
                pattern = f"\\[{citation}\\]"
            else:
                escaped_citation = re.escape(citation)
                pattern = f"\\({escaped_citation}\\)"

            match = re.search(pattern, text)
            if match:
                start = max(0, match.start() - char_count)
                end = min(len(text), match.end() + char_count)
                context = text[start:end]

                # Добавляем маркеры для цитаты
                quote_start = match.start() - start
                quote_end = match.end() - start

                # Оборачиваем цитату в маркеры для отображения
                marked_context = (
                        context[:quote_start] +
                        "【ЦИТАТА】" +
                        context[quote_start:quote_end] +
                        "【/ЦИТАТА】" +
                        context[quote_end:]
                )
                return marked_context

            return text[:char_count] + '...' if len(text) > char_count else text

        except Exception as e:
            print(f"Ошибка при извлечении контекста для '{citation}': {e}")
            return text[:char_count] + '...' if len(text) > char_count else text

    def extract_citations(self, text_blocks: List[TextBlock]) -> Dict[str, Any]:
        """Старый метод для обратной совместимости - использует полный контекст"""
        return self.extract_citations_with_full_context(text_blocks)