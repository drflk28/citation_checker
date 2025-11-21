import React, { useState, useEffect } from 'react';
import axios from 'axios';

const DocumentList = ({ onDocumentSelect, refreshTrigger }) => {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState({});

  useEffect(() => {
    fetchDocuments();
  }, [refreshTrigger]);

  const fetchDocuments = async () => {
    try {
      const response = await axios.get('http://localhost:8001/documents');
      setDocuments(response.data);
    } catch (error) {
      console.error('Error fetching documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async (docId, e) => {
    e.stopPropagation(); // Предотвращаем всплытие события
    setAnalyzing(prev => ({ ...prev, [docId]: true }));

    try {
      await axios.post(`http://localhost:8001/documents/${docId}/analyze`);
      alert('Анализ запущен! Результаты будут доступны через несколько секунд.');

      // Автоматически обновляем список через 3 секунды
      setTimeout(() => {
        fetchDocuments();
      }, 3000);
    } catch (error) {
      console.error('Error starting analysis:', error);
      alert('Ошибка запуска анализа. Пожалуйста, попробуйте снова.');
    } finally {
      setAnalyzing(prev => ({ ...prev, [docId]: false }));
    }
  };

  const handleViewResults = (doc, e) => {
    e.stopPropagation(); // Предотвращаем всплытие события
    onDocumentSelect(doc);
  };

  if (loading) {
    return (
      <div className="card">
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Загрузка документов...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title">Документы</h2>
        <p className="card-subtitle">Управление и анализ загруженных документов</p>
      </div>

      <div className="card-content">
        {documents.length === 0 ? (
          <div className="empty-state">
            <svg
              className="empty-icon"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 48 48"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M9 12h6m-6 6h6m-6 6h6M6 6v.01M6 12v.01M6 18v.01M6 24v.01M6 30v.01M6 36v.01"
              />
            </svg>
            <p className="empty-title">Нет загруженных документов</p>
            <p className="empty-subtitle">Загрузите первый документ для начала работы</p>
          </div>
        ) : (
          <div className="documents-list">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="document-item"
                onClick={() => onDocumentSelect(doc)}
              >
                <div className="document-info">
                  <h3 className="document-name">{doc.filename}</h3>
                  <p className="document-meta">
                    Загружен: {new Date(doc.upload_date).toLocaleDateString('ru-RU')} •
                    Размер: {(doc.file_size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
                <div className="document-actions" onClick={e => e.stopPropagation()}>
                  <button
                    onClick={(e) => handleAnalyze(doc.id, e)}
                    disabled={analyzing[doc.id]}
                    className={`action-btn analyze-btn ${analyzing[doc.id] ? 'analyze-btn-disabled' : 'analyze-btn-active'}`}
                  >
                    {analyzing[doc.id] ? 'Анализ...' : 'Анализировать'}
                  </button>
                  <button
                    onClick={(e) => handleViewResults(doc, e)}
                    className="action-btn view-btn"
                  >
                    Просмотреть результаты
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentList;