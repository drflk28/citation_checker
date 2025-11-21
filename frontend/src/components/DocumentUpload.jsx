import React, { useState } from 'react';
import axios from 'axios';

const DocumentUpload = ({ onUploadSuccess }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    await handleFiles(files);
  };

  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files);
    await handleFiles(files);
  };

  const handleFiles = async (files) => {
    if (files.length === 0) return;

    const file = files[0];
    const allowedTypes = ['.pdf', '.docx', '.doc'];
    const fileExtension = file.name.toLowerCase().slice(
      (file.name.lastIndexOf(".") - 1 >>> 0) + 2
    );

    if (!allowedTypes.includes(`.${fileExtension}`)) {
      alert('Пожалуйста, загружайте только PDF или DOCX файлы');
      return;
    }

    setUploading(true);
    setProgress(0);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('http://localhost:8001/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          setProgress(percentCompleted);
        },
      });

      if (response.data) {
        alert('Документ успешно загружен!');
        onUploadSuccess();
      }
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Ошибка загрузки. Пожалуйста, попробуйте снова.');
    } finally {
      setUploading(false);
      setProgress(0);
    }
  };

  return (
    <div className="card">
      <div className="upload-container">
        <h2 className="upload-title">Загрузка документа</h2>
        <p className="upload-description">
          Загрузите ваш PDF или DOCX документ для проверки цитирования и библиографии
        </p>

        <div
          className={`upload-zone ${isDragging ? 'upload-zone-dragging' : ''} ${uploading ? 'upload-zone-disabled' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {uploading ? (
            <div className="upload-progress">
              <div className="progress-container">
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${progress}%` }}
                  ></div>
                </div>
                <p className="progress-text">
                  Загрузка... {progress}%
                </p>
              </div>
            </div>
          ) : (
            <>
              <div className="upload-icon">
                <svg
                  className="upload-svg"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 48 48"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                  />
                </svg>
              </div>
              <p className="upload-instruction">
                <span className="upload-highlight">
                  Нажмите для загрузки
                </span>{' '}
                или перетащите файл
              </p>
              <p className="upload-formats">
                PDF, DOCX до 10MB
              </p>
            </>
          )}
        </div>

        <input
          type="file"
          id="file-upload"
          className="file-input"
          accept=".pdf,.docx,.doc"
          onChange={handleFileSelect}
          disabled={uploading}
        />
        <label
          htmlFor="file-upload"
          className={`upload-button ${uploading ? 'upload-button-disabled' : ''}`}
        >
          Выбрать файл
        </label>
      </div>
    </div>
  );
};

export default DocumentUpload;