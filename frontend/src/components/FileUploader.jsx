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
            className={`rounded-2xl border border-dashed p-6 text-center cursor-pointer transition
                ${isDragging
                    ? 'border-cyan-400/70 bg-cyan-500/10 shadow-[0_0_0_1px_rgba(34,211,238,0.15)]'
                    : file
                    ? 'border-emerald-500/40 bg-emerald-500/8'
                    : 'border-white/10 hover:border-white/20 bg-black/20'
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
                <div className="text-emerald-300 text-sm">
                    ✅ {file.name}
                    <span className="text-gray-500 ml-2">
                        ({(file.size / 1024).toFixed(1)} KB)
                    </span>
                </div>
            ) : (
                <div className="text-gray-400 text-sm">{label}</div>
            )}
        </div>
    );
}
