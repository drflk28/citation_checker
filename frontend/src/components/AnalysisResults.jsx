import React, { useState, useEffect } from 'react';
import axios from 'axios';

const AnalysisResults = ({ document, onBack }) => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedTab, setSelectedTab] = useState('summary');
  const [selectedEntry, setSelectedEntry] = useState(null);

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
      <div className="card">
        <div className="error-state">
          <h3>Ошибка</h3>
          <p>Документ не выбран</p>
          <button className="btn btn-primary" onClick={onBack}>
            Назад к документам
          </button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="card">
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Загрузка результатов анализа...</p>
          <p className="document-info">Документ: {document.filename}</p>
        </div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="card">
        <div className="error-state">
          <h3>Ошибка</h3>
          <p>Не удалось загрузить результаты анализа</p>
          <button className="btn btn-primary" onClick={onBack}>
            Назад к документам
          </button>
        </div>
      </div>
    );
  }

  if (analysis.status === 'processing') {
    return (
      <div className="card">
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Анализ документа...</p>
          <p className="document-info">Это может занять несколько минут</p>
          <p className="document-name">{document.filename}</p>
        </div>
      </div>
    );
  }

  if (analysis.status === 'error') {
    return (
      <div className="card">
        <div className="error-state">
          <h3>Ошибка анализа</h3>
          <p>{analysis.error_message || 'Произошла неизвестная ошибка'}</p>
          <button className="btn btn-primary" onClick={onBack}>
            Назад к документам
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      {/* Заголовок */}
      <div className="card-header analysis-header">
        <div className="analysis-title">
          <button className="back-button" onClick={onBack}>
            ← Назад к документам
          </button>
          <div>
            <h2>{document.filename}</h2>
            <p className="analysis-date">
              Проанализирован {new Date().toLocaleDateString('ru-RU')}
            </p>
          </div>
        </div>
        <div className="analysis-status">
          <span className={`status-badge ${
            analysis.issues_found === 0 ? 'status-success' : 'status-warning'
          }`}>
            {analysis.issues_found === 0 ? 'Нет проблем' : `${analysis.issues_found} проблем`}
          </span>
        </div>
      </div>

      {/* Вкладки */}
      <div className="tabs-container">
        <nav className="tabs-nav">
          {[
            { key: 'summary', label: 'Обзор' },
            { key: 'citations', label: 'Цитаты' },
            { key: 'bibliography', label: 'Библиография' },
            { key: 'issues', label: 'Проблемы' }
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setSelectedTab(tab.key)}
              className={`tab-button ${selectedTab === tab.key ? 'tab-active' : 'tab-inactive'}`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Контент */}
      <div className="tab-content">
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

  const verifiedEntries = (analysis.bibliography_entries || []).filter(
    entry => entry.online_metadata
  ).length;

  return (
    <div className="summary-tab">
      <div className="stats-grid">
        <div className="stat-card stat-blue">
          <div className="stat-number">{analysis.citations_found || 0}</div>
          <div className="stat-label">Всего цитат</div>
        </div>
        <div className="stat-card stat-red">
          <div className="stat-number">{analysis.issues_found || 0}</div>
          <div className="stat-label">Найдено проблем</div>
        </div>
        <div className="stat-card stat-green">
          <div className="stat-number">{analysis.bibliography_entries_found || 0}</div>
          <div className="stat-label">Записей библиографии</div>
        </div>
        <div className="stat-card stat-purple">
          <div className="stat-number">
            {analysis.summary?.completeness_score ?
              `${(analysis.summary.completeness_score * 100).toFixed(0)}%` : 'Н/Д'
            }
          </div>
          <div className="stat-label">Полнота</div>
        </div>
      </div>

      <div className="analysis-overview">
        <h3>Обзор анализа</h3>
        <p>
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
      <div className="quick-links">
        <div className="quick-link" onClick={() => onTabChange('citations')}>
          <div className="link-icon">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
            </svg>
          </div>
          <div>
            <h4>Цитаты</h4>
            <p>Просмотр {analysis.citations_found || 0} цитат, найденных в документе</p>
          </div>
        </div>
        <div className="quick-link" onClick={() => onTabChange('bibliography')}>
          <div className="link-icon">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          </div>
          <div>
            <h4>Библиография</h4>
            <p>Просмотр {analysis.bibliography_entries_found || 0} записей библиографии
              {verifiedEntries > 0 && ` (${verifiedEntries} с онлайн-данными)`}</p>
          </div>
        </div>
        <div className="quick-link" onClick={() => onTabChange('issues')}>
          <div className="link-icon">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div>
            <h4>Проблемы</h4>
            <p>Просмотр {analysis.issues_found || 0} найденных проблем в цитатах</p>
          </div>
        </div>
      </div>
    </div>
  );
};

const CitationsTab = ({ analysis }) => (
  <div className="citations-tab">
    <h3 className="tab-title">
      Найденные цитаты ({(analysis.citations || []).length})
    </h3>
    <div className="citations-list">
      {(analysis.citations || []).map((citation, index) => (
        <div
          key={citation.id || index}
          className="citation-item"
        >
          <div className="citation-content">
            <div className="citation-main">
              <p className="citation-text">{citation.text}</p>
              <p className="citation-context">{citation.context}</p>
            </div>
            <span className="citation-style">
              {citation.style || 'Неизвестно'}
            </span>
          </div>
        </div>
      ))}
      {(analysis.citations || []).length === 0 && (
        <p className="empty-message">Цитаты не найдены</p>
      )}
    </div>
  </div>
);

const BibliographyTab = ({ analysis }) => {
  const entries = analysis.bibliography_entries || [];
  const entriesWithOnlineData = entries.filter(entry => entry.online_metadata);

  return (
    <div className="bibliography-tab">
      <div className="bibliography-header">
        <h3 className="tab-title">
          Записи библиографии ({entries.length})
        </h3>
        <div className="verification-stats">
          <div className="stat-item">
            <div className="stat-indicator verified"></div>
            <span>Верифицировано ({entriesWithOnlineData.length})</span>
          </div>
          <div className="stat-item">
            <div className="stat-indicator not-verified"></div>
            <span>Не верифицировано ({entries.length - entriesWithOnlineData.length})</span>
          </div>
        </div>
      </div>

      <div className="bibliography-list">
        {entries.map((entry, index) => (
          <BibliographyEntryCard key={entry.id || index} entry={entry} index={index} />
        ))}
        {entries.length === 0 && (
          <div className="empty-state">
            <svg
              className="empty-icon"
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
            <p className="empty-title">Записи библиографии не найдены</p>
            <p className="empty-subtitle">Документ не содержит раздела библиографии</p>
          </div>
        )}
      </div>
    </div>
  );
};

const BibliographyEntryCard = ({ entry, index }) => {
  const metadata = entry.online_metadata || {};

  const safeString = (value) => {
    if (!value) return '';
    if (typeof value === 'string') return value;
    if (typeof value === 'number') return value.toString();
    if (Array.isArray(value)) return value.join(', ');
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

  const getAuthors = (authors) => {
    if (!authors) return [];
    if (Array.isArray(authors)) {
      return authors.map(author => safeString(author));
    }
    return [safeString(authors)];
  };

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

  const getDisplayIndex = () => {
    if (entry.id && typeof entry.id === 'string') {
      const cleanId = entry.id.replace(/^bib_/, '');
      const numId = parseInt(cleanId, 10);
      if (!isNaN(numId)) {
        return numId + 1;
      }
      return cleanId;
    }
    return index + 1;
  };

  return (
    <div className={`bibliography-entry ${hasOnlineData ? 'entry-verified' : 'entry-normal'}`}>
      <div className="entry-content">
        <div className="entry-header">
          <span className={`entry-index ${hasOnlineData ? 'index-verified' : 'index-normal'}`}>
            {getDisplayIndex()}
          </span>
          <div className="entry-main">
            <p className="entry-text">{safeString(entry.text)}</p>

            {hasOnlineData && (
              <div className="online-data">
                <div className="data-header">
                  <div className="source-info">
                    <svg className="verified-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                    <span className="source-name">
                      Найдено в {safeString(metadata.source)}
                    </span>
                  </div>
                  {metadata.confidence && (
                    <span className="confidence-badge">
                      {(safeString(metadata.confidence) * 100).toFixed(0)}% уверенность
                    </span>
                  )}
                </div>

                <div className="action-links">
                  {primaryUrl && (
                    <a
                      href={primaryUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="action-btn primary-action"
                    >
                      <svg className="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                      Открыть источник
                    </a>
                  )}

                  {!primaryUrl && safeString(metadata.title) && (
                    <a
                      href={getGoogleSearchUrl(metadata.title)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="action-btn secondary-action"
                    >
                      <svg className="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                      Найти в Google
                    </a>
                  )}
                </div>

                <div className="metadata-grid">
                  {safeString(metadata.title) && (
                    <div className="metadata-item">
                      <span className="metadata-label">Название:</span>
                      <span className="metadata-value">{safeString(metadata.title)}</span>
                    </div>
                  )}
                  {authors.length > 0 && (
                    <div className="metadata-item">
                      <span className="metadata-label">Авторы:</span>
                      <span className="metadata-value">{authors.join(', ')}</span>
                    </div>
                  )}
                  {safeString(metadata.year) && (
                    <div className="metadata-item">
                      <span className="metadata-label">Год:</span>
                      <span className="metadata-value">{safeString(metadata.year)}</span>
                    </div>
                  )}
                  {safeString(metadata.publisher) && (
                    <div className="metadata-item">
                      <span className="metadata-label">Издатель:</span>
                      <span className="metadata-value">{safeString(metadata.publisher)}</span>
                    </div>
                  )}
                  {safeString(metadata.journal) && (
                    <div className="metadata-item">
                      <span className="metadata-label">Журнал:</span>
                      <span className="metadata-value">{safeString(metadata.journal)}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            <p className="entry-footer">
              {hasOnlineData ? 'Верифицированная запись' : 'Запись библиографии'}
              {entry.matched_citations && Array.isArray(entry.matched_citations) && entry.matched_citations.length > 0 && (
                <span className="citations-used">
                  • Используется в цитатах: [{entry.matched_citations.join(', ')}]
                </span>
              )}
            </p>
          </div>
        </div>
        <div className={`entry-status ${hasOnlineData ? 'status-verified' : 'status-normal'}`}>
          {hasOnlineData ? 'Верифицировано' : 'Ссылка'}
        </div>
      </div>
    </div>
  );
};

const IssuesTab = ({ analysis }) => (
  <div className="issues-tab">
    <h3 className="tab-title">
      Найденные проблемы ({(analysis.issues || []).length})
    </h3>
    <div className="issues-list">
      {(analysis.issues || []).map((issue, index) => (
        <div
          key={index}
          className={`issue-item issue-${issue.severity || 'medium'}`}
        >
          <div className="issue-content">
            <div className="issue-main">
              <h4 className="issue-type">
                {issue.type || 'Неизвестная'} проблема
              </h4>
              <p className="issue-description">{issue.description}</p>
              {issue.suggestion && (
                <p className="issue-suggestion">
                  <strong>Рекомендация:</strong> {issue.suggestion}
                </p>
              )}
            </div>
            <span className={`issue-severity severity-${issue.severity || 'medium'}`}>
              {issue.severity || 'неизвестно'}
            </span>
          </div>
        </div>
      ))}
      {(analysis.issues || []).length === 0 && (
        <div className="success-state">
          <div className="success-message">Проблемы не найдены!</div>
          <p className="success-subtitle">Все цитаты правильно оформлены.</p>
        </div>
      )}
    </div>
  </div>
);

// МОДАЛЬНОЕ ОКНО С ДЕТАЛЯМИ (опционально)
const SourceDetailsModal = ({ entry, onClose }) => {
  const metadata = entry.online_metadata || {};

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="modal-header">
          <h3 className="modal-title">Детали источника</h3>
          <button
            onClick={onClose}
            className="modal-close"
          >
            ✕
          </button>
        </div>
        <div className="modal-body">
          {/* Контент модального окна */}
        </div>
      </div>
    </div>
  );
};

export default AnalysisResults;
export { SummaryTab, CitationsTab, BibliographyTab, IssuesTab, BibliographyEntryCard, SourceDetailsModal };