/**
 * InterviewAce — File Uploader Component
 * Drag-and-drop file upload with visual feedback.
 *
 * Owner: Dev 3
 */

import { useState, useRef } from 'react';

export default function FileUploader({ accept, label, onFile, file, multiple = false }) {
    const [isDragging, setIsDragging] = useState(false);
    const inputRef = useRef(null);

    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragging(false);
        const dropped = e.dataTransfer.files;
        if (dropped.length > 0) {
            onFile(dropped[0]);
        }
    };

    const handleChange = (e) => {
        if (e.target.files.length > 0) {
            onFile(e.target.files[0]);
        }
    };

    return (
        <div
            className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition
                ${isDragging
                    ? 'border-blue-500 bg-blue-500/10'
                    : file
                    ? 'border-green-700 bg-green-900/10'
                    : 'border-gray-700 hover:border-gray-500 bg-gray-900/50'
                }`}
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
        >
            <input
                ref={inputRef}
                type="file"
                accept={accept}
                multiple={multiple}
                className="hidden"
                onChange={handleChange}
            />
            {file ? (
                <div className="text-green-400 text-sm">
                    ✅ {file.name}
                    <span className="text-gray-500 ml-2">
                        ({(file.size / 1024).toFixed(1)} KB)
                    </span>
                </div>
            ) : (
                <div className="text-gray-500 text-sm">{label}</div>
            )}
        </div>
    );
}
