// frontend/src/App.jsx
import React, { useState } from 'react';
import DocumentUpload from './components/DocumentUpload';
import DocumentList from './components/DocumentList';
import AnalysisResults from './components/AnalysisResults';
import PersonalLibrary from './components/PersonalLibrary';
import './App.css';
import './css/components.css';

function App() {
  const [currentView, setCurrentView] = useState('library'); // По умолчанию открываем библиотеку
  const [selectedDoc, setSelectedDoc] = useState(null);

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <h1>📚 Citation Checker</h1>
          <nav className="nav">
            <button
              onClick={() => setCurrentView('upload')}
              className={`nav-button ${currentView === 'upload' ? 'active' : ''}`}
            >
              📤 Upload
            </button>
            <button
              onClick={() => setCurrentView('documents')}
              className={`nav-button ${currentView === 'documents' ? 'active' : ''}`}
            >
              📄 Documents
            </button>
            <button
              onClick={() => setCurrentView('library')}
              className={`nav-button ${currentView === 'library' ? 'active' : ''}`}
            >
              🏛️ Library
            </button>
          </nav>
        </div>
      </header>

      <main className="main">
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
        {currentView === 'library' && (
          <PersonalLibrary />
        )}
      </main>

      <footer className="footer">
        <p>Citation Checker • Общая библиотека источников</p>
      </footer>
    </div>
  );
}

export default App;