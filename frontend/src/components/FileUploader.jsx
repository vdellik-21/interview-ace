/**
 * InterviewAce — File Uploader Component
 * Drag-and-drop file upload with visual feedback.
 *
 * Owner: Dev 3
 */

import { useState, useRef } from 'react';

export default function FileUploader({ accept, label, onFile, file, multiple = false, theme = 'dark' }) {
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

    const idleClasses =
        theme === 'light'
            ? 'border-slate-300 hover:border-slate-400 bg-white/75'
            : 'border-white/10 hover:border-white/20 bg-black/20';
    const successClasses =
        theme === 'light'
            ? 'border-emerald-500/40 bg-emerald-500/10'
            : 'border-emerald-500/40 bg-emerald-500/8';
    const draggingClasses =
        theme === 'light'
            ? 'border-cyan-500/70 bg-cyan-500/12 shadow-[0_0_0_1px_rgba(6,182,212,0.12)]'
            : 'border-cyan-400/70 bg-cyan-500/10 shadow-[0_0_0_1px_rgba(34,211,238,0.15)]';
    const textClasses = theme === 'light' ? 'text-slate-600' : 'text-gray-400';
    const fileTextClasses = theme === 'light' ? 'text-emerald-700' : 'text-emerald-300';
    const metaTextClasses = theme === 'light' ? 'text-slate-500' : 'text-gray-500';

    return (
        <div
            className={`rounded-2xl border border-dashed p-6 text-center cursor-pointer transition
                ${isDragging
                    ? draggingClasses
                    : file
                    ? successClasses
                    : idleClasses
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
                <div className={`${fileTextClasses} text-sm`}>
                    ✅ {file.name}
                    <span className={`${metaTextClasses} ml-2`}>
                        ({(file.size / 1024).toFixed(1)} KB)
                    </span>
                </div>
            ) : (
                <div className={`${textClasses} text-sm`}>{label}</div>
            )}
        </div>
    );
}
