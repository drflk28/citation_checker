// frontend/src/components/SourceList.jsx
import React from 'react';

const SourceList = ({ sources, onDelete, onExportAsDocument }) => {
    if (!sources || sources.length === 0) {
        return (
            <div className="empty-state">
                <p>Источники не найдены</p>
            </div>
        );
    }

    return (
        <div className="source-list">
            {sources.map(source => (
                <div key={source.id} className="source-card">
                    <div className="source-content">
                        <h3 className="source-title">{source.title}</h3>
                        <div className="source-meta">
                            <p className="source-authors">
                                <strong>Авторы:</strong> {source.authors?.join(', ') || 'Не указаны'}
                            </p>
                            {source.year && (
                                <p className="source-year">
                                    <strong>Год:</strong> {source.year}
                                </p>
                            )}
                            {source.publisher && (
                                <p className="source-publisher">
                                    <strong>Издательство:</strong> {source.publisher}
                                </p>
                            )}
                            {source.journal && (
                                <p className="source-journal">
                                    <strong>Журнал:</strong> {source.journal}
                                </p>
                            )}
                            {source.doi && (
                                <p className="source-doi">
                                    <strong>DOI:</strong> {source.doi}
                                </p>
                            )}
                            {source.isbn && (
                                <p className="source-isbn">
                                    <strong>ISBN:</strong> {source.isbn}
                                </p>
                            )}
                        </div>
                    </div>
                    <div className="source-actions">
                        <button
                            onClick={() => onExportAsDocument(source.id)}
                            className="btn-export"
                            title="Сохранить как документ для анализа"
                        >
                            📄 Экспорт
                        </button>
                        <button
                            onClick={() => onDelete(source.id)}
                            className="btn-delete"
                            title="Удалить источник"
                        >
                            🗑️ Удалить
                        </button>
                    </div>
                </div>
            ))}
        </div>
    );
};

export default SourceList;