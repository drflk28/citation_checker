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
      alert('Analysis started! Check back in a moment for results.');

      // Автоматически обновляем список через 3 секунды
      setTimeout(() => {
        fetchDocuments();
      }, 3000);
    } catch (error) {
      console.error('Error starting analysis:', error);
      alert('Error starting analysis. Please try again.');
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
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading documents...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-xl font-semibold text-gray-900">Documents</h2>
        <p className="text-gray-600 mt-1">Manage and analyze your uploaded documents</p>
      </div>

      <div className="p-6">
        {documents.length === 0 ? (
          <div className="text-center py-12">
            <svg
              className="w-24 h-24 text-gray-300 mx-auto mb-4"
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
            <p className="text-gray-500 text-lg">No documents uploaded yet</p>
            <p className="text-gray-400 mt-2">Upload a document to get started</p>
          </div>
        ) : (
          <div className="space-y-4">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors cursor-pointer"
                onClick={() => onDocumentSelect(doc)} // Клик по всей карточке
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <h3 className="font-medium text-gray-900">{doc.filename}</h3>
                    <p className="text-sm text-gray-500 mt-1">
                      Uploaded: {new Date(doc.upload_date).toLocaleDateString()} •
                      Size: {(doc.file_size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                  <div className="flex space-x-2 ml-4" onClick={e => e.stopPropagation()}>
                    <button
                      onClick={(e) => handleAnalyze(doc.id, e)}
                      disabled={analyzing[doc.id]}
                      className={`px-4 py-2 rounded-md transition-colors text-sm font-medium ${
                        analyzing[doc.id] 
                          ? 'bg-blue-400 cursor-not-allowed' 
                          : 'bg-blue-600 hover:bg-blue-700'
                      } text-white`}
                    >
                      {analyzing[doc.id] ? 'Analyzing...' : 'Analyze'}
                    </button>
                    <button
                      onClick={(e) => handleViewResults(doc, e)}
                      className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors text-sm font-medium"
                    >
                      View Results
                    </button>
                  </div>
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