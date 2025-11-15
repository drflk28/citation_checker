import React, { useState, useEffect } from 'react';
import axios from 'axios';

// Вспомогательная функция для безопасного преобразования в строку
const safeString = (value) => {
  if (!value) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return value.toString();
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value === 'object') {
    return value.value || value.id || value.title || value.name || '';
  }
  return String(value);
};

const AnalysisResults = ({ document, onBack }) => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedTab, setSelectedTab] = useState('summary');
  const [selectedEntry, setSelectedEntry] = useState(null); // Для модального окна

  useEffect(() => {
    if (!document) {
      console.error('Документ не предоставлен для AnalysisResults');
      return;
    }

    const fetchAnalysis = async () => {
      try {
        console.log('Получение анализа для документа:', document.id);
        const response = await axios.get(
          `http://localhost:8001/documents/${document.id}/analysis`
        );
        console.log('Ответ анализа:', response.data);
        setAnalysis(response.data);
        setLoading(false);
      } catch (error) {
        console.error('Ошибка при получении анализа:', error);
        setLoading(false);
      }
    };

    fetchAnalysis();

    const interval = setInterval(() => {
      if (analysis?.status === 'processing' || !analysis) {
        fetchAnalysis();
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [document?.id, analysis?.status]);

  if (!document) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
        <div className="text-center text-red-600">
          <h3 className="text-lg font-medium">Ошибка</h3>
          <p className="mt-2">Документ не выбран</p>
          <button
            onClick={onBack}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Назад к документам
          </button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Загрузка результатов анализа...</p>
          <p className="text-sm text-gray-500 mt-2">Документ: {document.filename}</p>
        </div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
        <div className="text-center text-red-600">
          <h3 className="text-lg font-medium">Ошибка</h3>
          <p className="mt-2">Не удалось загрузить результаты анализа</p>
          <button
            onClick={onBack}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Назад к документам
          </button>
        </div>
      </div>
    );
  }

  if (analysis.status === 'processing') {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Анализ документа...</p>
          <p className="text-sm text-gray-500 mt-2">Это может занять несколько минут</p>
          <p className="text-sm text-gray-400 mt-1">{document.filename}</p>
        </div>
      </div>
    );
  }

  if (analysis.status === 'error') {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
        <div className="text-center text-red-600">
          <h3 className="text-lg font-medium">Ошибка анализа</h3>
          <p className="mt-2">{analysis.error_message || 'Произошла неизвестная ошибка'}</p>
          <button
            onClick={onBack}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Назад к документам
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      {/* Заголовок */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={onBack}
              className="flex items-center text-gray-600 hover:text-gray-900 transition-colors font-medium"
            >
              ← Назад к документам
            </button>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">
                {document.filename}
              </h2>
              <p className="text-sm text-gray-500">
                Проанализирован {new Date().toLocaleDateString('ru-RU')}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <span
              className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                analysis.issues_found === 0
                  ? 'bg-green-100 text-green-800'
                  : 'bg-yellow-100 text-yellow-800'
              }`}
            >
              {analysis.issues_found === 0 ? 'Нет проблем' : `${analysis.issues_found} проблем`}
            </span>
          </div>
        </div>
      </div>

      {/* Вкладки */}
      <div className="border-b border-gray-200">
        <nav className="flex -mb-px">
          {[
            { key: 'summary', label: 'Обзор' },
            { key: 'citations', label: 'Цитаты' },
            { key: 'bibliography', label: 'Библиография' },
            { key: 'issues', label: 'Проблемы' }
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setSelectedTab(tab.key)}
              className={`py-4 px-6 text-sm font-medium border-b-2 transition-colors ${
                selectedTab === tab.key
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Контент */}
      <div className="p-6">
        {selectedTab === 'summary' && (
          <SummaryTab analysis={analysis} onTabChange={setSelectedTab} />
        )}
        {selectedTab === 'citations' && <CitationsTab analysis={analysis} />}
        {selectedTab === 'bibliography' && (
          <BibliographyTab
            analysis={analysis}
            onEntrySelect={setSelectedEntry}
          />
        )}
        {selectedTab === 'issues' && <IssuesTab analysis={analysis} />}
      </div>

      {/* Модальное окно с деталями источника */}
      {selectedEntry && (
        <SourceDetailsModal
          entry={selectedEntry}
          onClose={() => setSelectedEntry(null)}
        />
      )}
    </div>
  );
};

const SummaryTab = ({ analysis, onTabChange }) => {
  const entriesWithOnlineData = (analysis.bibliography_entries || [])
    .filter(entry => entry.online_metadata && Object.keys(entry.online_metadata).length > 0);

  // Подсчитываем верифицированные записи
  const verifiedEntries = (analysis.bibliography_entries || []).filter(
    entry => entry.online_metadata
  ).length;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-blue-50 rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-blue-600">
            {analysis.citations_found || 0}
          </div>
          <div className="text-sm text-blue-600">Всего цитат</div>
        </div>
        <div className="bg-red-50 rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-red-600">
            {analysis.issues_found || 0}
          </div>
          <div className="text-sm text-red-600">Найдено проблем</div>
        </div>
        <div className="bg-green-50 rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-green-600">
            {analysis.bibliography_entries_found || 0}
          </div>
          <div className="text-sm text-green-600">Записей библиографии</div>
        </div>
        <div className="bg-purple-50 rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-purple-600">
            {analysis.summary?.completeness_score ?
              `${(analysis.summary.completeness_score * 100).toFixed(0)}%` : 'Н/Д'
            }
          </div>
          <div className="text-sm text-purple-600">Полнота</div>
        </div>
      </div>

      <div className="bg-gray-50 rounded-lg p-4">
        <h3 className="font-medium text-gray-900 mb-2">Обзор анализа</h3>
        <p className="text-sm text-gray-600">
          Документ содержит {analysis.citations_found || 0} цитат с{' '}
          {analysis.issues_found || 0} проблемами, требующими внимания.
          {analysis.summary?.completeness_score && (
            <span> Оценка полноты: {(analysis.summary.completeness_score * 100).toFixed(1)}%</span>
          )}
          {verifiedEntries > 0 && (
            <span> {verifiedEntries} источников верифицировано онлайн.</span>
          )}
        </p>
      </div>

      {/* Быстрые ссылки на другие вкладки */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div
          className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors cursor-pointer"
          onClick={() => onTabChange('citations')}
        >
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
              </svg>
            </div>
            <div>
              <h4 className="font-medium text-gray-900 mb-1">Цитаты</h4>
              <p className="text-sm text-gray-600">
                Просмотр {analysis.citations_found || 0} цитат, найденных в документе
              </p>
            </div>
          </div>
        </div>
        <div
          className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors cursor-pointer"
          onClick={() => onTabChange('bibliography')}
        >
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <div>
              <h4 className="font-medium text-gray-900 mb-1">Библиография</h4>
              <p className="text-sm text-gray-600">
                Просмотр {analysis.bibliography_entries_found || 0} записей библиографии
                {verifiedEntries > 0 && ` (${verifiedEntries} с онлайн-данными)`}
              </p>
            </div>
          </div>
        </div>
        <div
          className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors cursor-pointer"
          onClick={() => onTabChange('issues')}
        >
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div>
              <h4 className="font-medium text-gray-900 mb-1">Проблемы</h4>
              <p className="text-sm text-gray-600">
                Просмотр {analysis.issues_found || 0} найденных проблем в цитатах
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const CitationsTab = ({ analysis }) => (
  <div className="space-y-4">
    <h3 className="font-medium text-gray-900">
      Найденные цитаты ({(analysis.citations || []).length})
    </h3>
    <div className="space-y-3">
      {(analysis.citations || []).map((citation, index) => (
        <div
          key={citation.id || index}
          className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <p className="text-sm text-gray-900 font-medium">{citation.text}</p>
              <p className="text-xs text-gray-500 mt-1">{citation.context}</p>
            </div>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 ml-4">
              {citation.style || 'Неизвестно'}
            </span>
          </div>
        </div>
      ))}
      {(analysis.citations || []).length === 0 && (
        <p className="text-gray-500 text-center py-4">Цитаты не найдены</p>
      )}
    </div>
  </div>
);

const BibliographyTab = ({ analysis }) => {
  const entries = analysis.bibliography_entries || [];
  const entriesWithOnlineData = entries.filter(entry => entry.online_metadata);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-gray-900">
          Записи библиографии ({entries.length})
        </h3>
        <div className="flex items-center space-x-4 text-sm text-gray-500">
          <div className="flex items-center">
            <div className="w-3 h-3 bg-green-500 rounded-full mr-1"></div>
            <span>Верифицировано ({entriesWithOnlineData.length})</span>
          </div>
          <div className="flex items-center">
            <div className="w-3 h-3 bg-gray-300 rounded-full mr-1"></div>
            <span>Не верифицировано ({entries.length - entriesWithOnlineData.length})</span>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {entries.map((entry, index) => (
          <BibliographyEntryCard key={entry.id || index} entry={entry} index={index} />
        ))}
        {entries.length === 0 && (
          <div className="text-center py-8">
            <svg
              className="w-16 h-16 text-gray-300 mx-auto mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
              />
            </svg>
            <p className="text-gray-500 text-lg">Записи библиографии не найдены</p>
            <p className="text-gray-400 mt-2">Документ не содержит раздела библиографии</p>
          </div>
        )}
      </div>
    </div>
  );
};

const BibliographyEntryCard = ({ entry, index }) => {
  const metadata = entry.online_metadata || {};

  // БЕЗОПАСНЫЕ функции для обработки данных
  const safeString = (value) => {
    if (!value) return '';
    if (typeof value === 'string') return value;
    if (typeof value === 'number') return value.toString();
    if (Array.isArray(value)) return value.join(', ');
    // Если это объект, пытаемся извлечь полезные данные
    if (typeof value === 'object') {
      return value.value || value.id || value.title || value.name || JSON.stringify(value);
    }
    return String(value);
  };

  const getIsbnSearchUrl = (isbn) => {
    const isbnString = safeString(isbn);
    if (!isbnString) return null;
    return `https://www.google.com/search?q=isbn+${isbnString}`;
  };

  const getGoogleSearchUrl = (title) => {
    const titleString = safeString(title);
    if (!titleString) return null;
    return `https://www.google.com/search?q=${encodeURIComponent(titleString)}`;
  };

  const getArxivUrl = (url) => {
    const urlString = safeString(url);
    if (urlString && urlString.includes('arxiv.org')) return urlString;
    return urlString;
  };

  // Безопасное получение массива авторов
  const getAuthors = (authors) => {
    if (!authors) return [];
    if (Array.isArray(authors)) {
      return authors.map(author => safeString(author));
    }
    return [safeString(authors)];
  };

  // Получаем основную ссылку для источника
  const getPrimaryUrl = () => {
    const url = getArxivUrl(metadata.url);
    if (url) return url;

    const isbnUrl = getIsbnSearchUrl(metadata.isbn);
    if (isbnUrl) return isbnUrl;

    if (metadata.title) return getGoogleSearchUrl(metadata.title);

    return null;
  };

  const primaryUrl = getPrimaryUrl();
  const authors = getAuthors(metadata.authors);

  const hasOnlineData = metadata && Object.keys(metadata).length > 0 &&
                       (safeString(metadata.title) || authors.length > 0 ||
                        safeString(metadata.url) || getIsbnSearchUrl(metadata.isbn));

  // Функция для получения порядкового номера (без bib_ префикса)
  const getDisplayIndex = () => {
    if (entry.id && typeof entry.id === 'string') {
      // Убираем префикс bib_ если он есть и преобразуем в число
      const cleanId = entry.id.replace(/^bib_/, '');
      const numId = parseInt(cleanId, 10);
      // Если получилось число, возвращаем его + 1 (чтобы начиналось с 1)
      if (!isNaN(numId)) {
        return numId + 1;
      }
      return cleanId;
    }
    // Если нет ID, используем индекс + 1
    return index + 1;
  };

  return (
    <div className={`border rounded-lg p-4 transition-colors ${
      hasOnlineData 
        ? 'border-green-200 bg-green-50 hover:bg-green-100' 
        : 'border-gray-200 bg-white hover:bg-gray-50'
    }`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-start space-x-3">
            <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium flex-shrink-0 mt-0.5 ${
              hasOnlineData 
                ? 'bg-green-100 text-green-600' 
                : 'bg-gray-100 text-gray-600'
            }`}>
              {getDisplayIndex()}
            </span>
            <div className="flex-1">
              <p className="text-sm text-gray-900">{safeString(entry.text)}</p>

              {/* БЛОК С ОНЛАЙН-ДАННЫМИ */}
              {hasOnlineData && (
                <div className="mt-3 p-3 bg-white rounded border border-green-200">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center">
                      <svg className="w-4 h-4 text-green-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                      </svg>
                      <span className="text-sm font-medium text-green-700">
                        Найдено в {safeString(metadata.source)}
                      </span>
                    </div>
                    {metadata.confidence && (
                      <span className="text-xs bg-blue-100 text-blue-600 px-2 py-1 rounded">
                        {(safeString(metadata.confidence) * 100).toFixed(0)}% уверенность
                      </span>
                    )}
                  </div>

                  {/* УЛУЧШЕННЫЕ ССЫЛКИ */}
                  <div className="flex flex-wrap gap-2">
                    {/* Основная ссылка */}
                    {primaryUrl && (
                      <a
                        href={primaryUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center px-3 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                      >
                        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                        Открыть источник
                      </a>
                    )}

                    {/* Резервный поиск в Google */}
                    {!primaryUrl && safeString(metadata.title) && (
                      <a
                        href={getGoogleSearchUrl(metadata.title)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center px-3 py-2 text-sm bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
                      >
                        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                        </svg>
                        Найти в Google
                      </a>
                    )}
                  </div>

                  {/* ИНФОРМАЦИЯ О МЕТАДАННЫХ */}
                  <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-gray-600">
                    {safeString(metadata.title) && (
                      <div><span className="font-medium">Название:</span> {safeString(metadata.title)}</div>
                    )}
                    {authors.length > 0 && (
                      <div><span className="font-medium">Авторы:</span> {authors.join(', ')}</div>
                    )}
                    {safeString(metadata.year) && (
                      <div><span className="font-medium">Год:</span> {safeString(metadata.year)}</div>
                    )}
                    {safeString(metadata.publisher) && (
                      <div><span className="font-medium">Издатель:</span> {safeString(metadata.publisher)}</div>
                    )}
                    {safeString(metadata.journal) && (
                      <div><span className="font-medium">Журнал:</span> {safeString(metadata.journal)}</div>
                    )}
                  </div>
                </div>
              )}

              <p className="text-xs text-gray-500 mt-2">
                {hasOnlineData ? 'Верифицированная запись' : 'Запись библиографии'}
                {entry.matched_citations && Array.isArray(entry.matched_citations) && entry.matched_citations.length > 0 && (
                  <span className="ml-2">
                    • Используется в цитатах: [{entry.matched_citations.join(', ')}]
                  </span>
                )}
              </p>
            </div>
          </div>
        </div>

        <div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ml-4 ${
          hasOnlineData 
            ? 'bg-green-100 text-green-800' 
            : 'bg-gray-100 text-gray-600'
        }`}>
          {hasOnlineData ? 'Верифицировано' : 'Ссылка'}
        </div>
      </div>
    </div>
  );
};

const IssuesTab = ({ analysis }) => (
  <div className="space-y-4">
    <h3 className="font-medium text-gray-900">
      Найденные проблемы ({(analysis.issues || []).length})
    </h3>
    <div className="space-y-3">
      {(analysis.issues || []).map((issue, index) => (
        <div
          key={index}
          className={`border-l-4 rounded-r-lg p-4 transition-colors ${
            issue.severity === 'high'
              ? 'border-red-400 bg-red-50'
              : issue.severity === 'medium'
              ? 'border-yellow-400 bg-yellow-50'
              : 'border-blue-400 bg-blue-50'
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <h4 className="text-sm font-medium text-gray-900 capitalize">
                {issue.type || 'Неизвестная'} проблема
              </h4>
              <p className="text-sm text-gray-600 mt-1">{issue.description}</p>
              {issue.suggestion && (
                <p className="text-sm text-gray-500 mt-2">
                  <strong>Рекомендация:</strong> {issue.suggestion}
                </p>
              )}
            </div>
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ml-4 ${
                issue.severity === 'high'
                  ? 'bg-red-100 text-red-800'
                  : issue.severity === 'medium'
                  ? 'bg-yellow-100 text-yellow-800'
                  : 'bg-blue-100 text-blue-800'
              }`}
            >
              {issue.severity || 'неизвестно'}
            </span>
          </div>
        </div>
      ))}
      {(analysis.issues || []).length === 0 && (
        <div className="text-center py-8">
          <div className="text-green-600 font-medium">Проблемы не найдены!</div>
          <p className="text-gray-500 text-sm mt-1">Все цитаты правильно оформлены.</p>
        </div>
      )}
    </div>
  </div>
);

// МОДАЛЬНОЕ ОКНО С ДЕТАЛЯМИ (опционально)
const SourceDetailsModal = ({ entry, onClose }) => {
  const metadata = entry.online_metadata || {};

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium">Детали источника</h3>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>

          <div className="space-y-4">
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnalysisResults;