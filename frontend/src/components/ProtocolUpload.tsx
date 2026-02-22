/**
 * ProtocolUpload Component — Drag-and-drop file upload zone.
 *
 * === WHAT THIS DOES ===
 * Provides a dropzone where the moderator can drag a JSON file
 * (or click to browse) to upload a new protocol.
 *
 * === KEY CONCEPTS ===
 * - useRef: Creates a reference to a DOM element (like document.getElementById).
 *   We use it to programmatically click the hidden file input.
 * - Drag events: HTML supports drag-and-drop natively. We listen for
 *   onDragOver (file is hovering), onDrop (file is dropped), etc.
 * - FormData: The browser's way to package file uploads for sending to a server.
 *   Similar to how you'd use `requests.post(files=...)` in Python.
 * - async/await: JavaScript's way of waiting for asynchronous operations
 *   (like API calls). Similar to Python's async/await.
 */

import { useState, useRef } from 'react';
import { api } from '../api/client';

// Props: callback when a protocol is successfully uploaded
interface Props {
  onUploadSuccess: () => void;  // Called after successful upload to refresh the list
}

export default function ProtocolUpload({ onUploadSuccess }: Props) {
  // ─── STATE ─────────────────────────────────────────────────────────────
  const [isDragging, setIsDragging] = useState(false);     // Is a file being dragged over?
  const [uploading, setUploading] = useState(false);       // Is upload in progress?
  const [message, setMessage] = useState<string | null>(null);  // Success/error message
  const [isError, setIsError] = useState(false);           // Is the message an error?

  // useRef creates a reference to the hidden <input type="file"> element.
  // We need this to programmatically trigger the file browser when clicking the dropzone.
  const fileInputRef = useRef<HTMLInputElement>(null);


  // ─── UPLOAD HANDLER ────────────────────────────────────────────────────
  async function handleUpload(file: File) {
    // Validate file type
    if (!file.name.endsWith('.json')) {
      setMessage('Please upload a .json file');
      setIsError(true);
      return;
    }

    setUploading(true);
    setMessage(null);

    try {
      // Create FormData — the standard way to upload files via HTTP
      // This is like Python's: requests.post(url, files={'file': open('protocol.json', 'rb')})
      const formData = new FormData();
      formData.append('file', file);  // 'file' matches the parameter name in FastAPI

      // Send POST request with the file
      // Note: We override Content-Type to let the browser set it correctly for file uploads
      const response = await api.post('/protocols/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      setMessage(`✓ Protocol "${response.data.name}" uploaded successfully`);
      setIsError(false);
      onUploadSuccess();  // Notify parent to refresh the protocol list

    } catch (err: unknown) {
      // Extract error message from the API response
      const errorDetail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Upload failed';
      setMessage(errorDetail);
      setIsError(true);
    } finally {
      setUploading(false);
    }
  }


  // ─── DRAG & DROP HANDLERS ──────────────────────────────────────────────
  // These functions handle the HTML5 drag-and-drop events

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();         // Required to allow dropping
    setIsDragging(true);
  }

  function handleDragLeave() {
    setIsDragging(false);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);

    // Get the dropped file(s)
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleUpload(files[0]);  // Upload the first file
    }
  }

  // Handle click-to-browse (when user clicks the dropzone)
  function handleClick() {
    fileInputRef.current?.click();  // Trigger the hidden file input
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleUpload(files[0]);
    }
  }


  // ─── RENDER ────────────────────────────────────────────────────────────
  return (
    <div>
      <h3 className="text-lg font-semibold text-text-primary mb-3">
        Import
      </h3>

      {/* Upload label */}
      <p className="text-sm text-text-secondary mb-2">Upload protocol JSON:</p>

      {/* Dropzone area */}
      {/* The border changes style when dragging (dashed → solid, color change) */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
          transition-colors duration-200
          ${isDragging
            ? 'border-primary bg-primary/5'           // Highlighted when dragging over
            : 'border-border hover:border-primary/50'  // Default + hover state
          }
          ${uploading ? 'opacity-50 pointer-events-none' : ''}
        `}
      >
        {/* Upload icon */}
        <div className="text-3xl mb-2">📁</div>

        {uploading ? (
          <p className="text-sm text-text-secondary">Uploading...</p>
        ) : (
          <>
            <p className="text-sm text-text-primary font-medium">
              Drag & drop a JSON file here
            </p>
            <p className="text-xs text-text-secondary mt-1">
              or click to browse
            </p>
          </>
        )}
      </div>

      {/* Hidden file input — triggered by clicking the dropzone */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".json"
        onChange={handleFileSelect}
        className="hidden"  // Tailwind: display none
      />

      {/* Status message (success or error) */}
      {message && (
        <div className={`mt-3 p-3 rounded-lg text-sm ${
          isError
            ? 'bg-red-50 text-red-700 border border-red-200'
            : 'bg-green-50 text-green-700 border border-green-200'
        }`}>
          {message}
        </div>
      )}
    </div>
  );
}
