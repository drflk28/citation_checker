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
      alert('Please upload PDF or DOCX files only');
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
        alert('Document uploaded successfully!');
        onUploadSuccess();
      }
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Upload failed. Please try again.');
    } finally {
      setUploading(false);
      setProgress(0);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">
          Upload Document
        </h2>
        <p className="text-gray-600 mb-8">
          Upload your PDF or DOCX document to check citations and bibliography
        </p>

        <div
          className={`border-2 border-dashed rounded-lg p-12 mb-4 transition-colors ${
            isDragging
              ? 'border-blue-400 bg-blue-50'
              : 'border-gray-300 hover:border-gray-400'
          } ${uploading ? 'opacity-50' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {uploading ? (
            <div className="text-center">
              <div className="mb-4">
                <div className="w-full bg-gray-200 rounded-full h-2.5">
                  <div
                    className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  ></div>
                </div>
                <p className="text-sm text-gray-600 mt-2">
                  Uploading... {progress}%
                </p>
              </div>
            </div>
          ) : (
            <>
              <div className="flex justify-center mb-4">
                <svg
                  className="w-12 h-12 text-gray-400"
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
              <p className="text-gray-600 mb-2">
                <span className="font-medium text-blue-600">
                  Click to upload
                </span>{' '}
                or drag and drop
              </p>
              <p className="text-sm text-gray-500">
                PDF, DOCX up to 10MB
              </p>
            </>
          )}
        </div>

        <input
          type="file"
          id="file-upload"
          className="hidden"
          accept=".pdf,.docx,.doc"
          onChange={handleFileSelect}
          disabled={uploading}
        />
        <label
          htmlFor="file-upload"
          className={`inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 ${
            uploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
          }`}
        >
          Select File
        </label>
      </div>
    </div>
  );
};

export default DocumentUpload;