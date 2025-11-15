import React, { useState } from 'react';
import DocumentUpload from './components/DocumentUpload';
import DocumentList from './components/DocumentList';
import AnalysisResults from './components/AnalysisResults';
import './App.css';

function App() {
  const [currentView, setCurrentView] = useState('upload');
  const [selectedDoc, setSelectedDoc] = useState(null);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <h1 className="text-2xl font-bold text-gray-900">
              Citation Checker
            </h1>
            <nav className="flex space-x-4">
              <button
                onClick={() => setCurrentView('upload')}
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  currentView === 'upload'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Upload
              </button>
              <button
                onClick={() => setCurrentView('documents')}
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  currentView === 'documents'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Documents
              </button>
            </nav>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {currentView === 'upload' && (
          <DocumentUpload onUploadSuccess={() => setCurrentView('documents')} />
        )}
        {currentView === 'documents' && (
          <DocumentList
            onDocumentSelect={(doc) => {
              setSelectedDoc(doc);
              setCurrentView('analysis');
            }}
          />
        )}
        {currentView === 'analysis' && selectedDoc && (
          <AnalysisResults
            document={selectedDoc}
            onBack={() => setCurrentView('documents')}
          />
        )}
      </main>
    </div>
  );
}

export default App;