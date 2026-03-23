/**
 * InterviewAce — Prep Dashboard
 * Pre-interview setup: upload files, select model, configure audio, start session.
 *
 * Owner: Dev 3
 * Status: STUB — UI structure implemented, needs API integration
 */

import { useState, useEffect } from 'react';
import FileUploader from '../components/FileUploader';
import ModelSelector from '../components/ModelSelector';
import AudioDevicePicker from '../components/AudioDevicePicker';
import StatusIndicator from '../components/StatusIndicator';

export default function PrepDashboard() {
    // File state
    const [resumeFile, setResumeFile] = useState(null);
    const [jdText, setJdText] = useState('');
    const [contextFiles, setContextFiles] = useState([]);

    // Config state
    const [model, setModel] = useState('claude-sonnet-4-20250514');
    const [systemDevice, setSystemDevice] = useState('');
    const [micDevice, setMicDevice] = useState('');

    // Session state
    const [sessionStatus, setSessionStatus] = useState('idle'); // idle | preparing | ready | live
    const [prepProgress, setPrepProgress] = useState(0);
    const [prepStep, setPrepStep] = useState('');
    const [predictedQuestions, setPredictedQuestions] = useState([]);
    const [sessionId, setSessionId] = useState(null);
    const [error, setError] = useState('');

    // Fetch audio devices on mount
    const [devices, setDevices] = useState({ system_devices: [], mic_devices: [] });

    useEffect(() => {
        fetch('/api/devices')
            .then((res) => res.json())
            .then((data) => {
                setDevices(data);
                if (data.system_devices.length > 0) setSystemDevice(data.system_devices[0]);
                if (data.mic_devices.length > 0) setMicDevice(data.mic_devices[0]);
            })
            .catch((err) => console.error('Failed to fetch devices:', err));
    }, []);

    // ─── Start Session ──────────────────────────
    const handleStartPrep = async () => {
        if (!resumeFile) {
            setError('Please upload your resume');
            return;
        }
        if (!jdText.trim()) {
            setError('Please paste the job description');
            return;
        }

        setError('');
        setSessionStatus('preparing');
        setPrepProgress(0);

        try {
            const formData = new FormData();
            formData.append('resume', resumeFile);
            formData.append('jd_text', jdText);
            formData.append('model', model);
            formData.append('system_audio_device', systemDevice);
            formData.append('mic_device', micDevice);
            contextFiles.forEach((f) => formData.append('context_files', f));

            const res = await fetch('/api/session/create', {
                method: 'POST',
                body: formData,
            });

            const data = await res.json();
            setSessionId(data.session_id);

            // Connect to WebSocket for prep progress
            const ws = new WebSocket(
                `ws://localhost:8000/api/copilot/${data.session_id}`
            );

            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'prep_progress') {
                    setPrepStep(msg.step);
                    setPrepProgress(msg.percent);
                } else if (msg.type === 'prep_complete') {
                    setSessionStatus('ready');
                    setPredictedQuestions(msg.predicted_questions || []);
                } else if (msg.type === 'error') {
                    setError(msg.message);
                    setSessionStatus('idle');
                }
            };
        } catch (err) {
            setError(`Failed to start session: ${err.message}`);
            setSessionStatus('idle');
        }
    };

    // ─── Go Live ────────────────────────────────
    const handleGoLive = () => {
        setSessionStatus('live');
        // Tell Electron to show the stealth overlay
        if (window.electronAPI) {
            window.electronAPI.showOverlay();
        } else {
            // If not in Electron, open overlay in new tab
            window.open('/overlay', '_blank');
        }
    };

    return (
        <div className="min-h-screen bg-gray-950 text-white">
            {/* Header */}
            <header className="border-b border-gray-800 px-6 py-4">
                <div className="flex items-center justify-between max-w-4xl mx-auto">
                    <div className="flex items-center gap-3">
                        <span className="text-2xl">🎯</span>
                        <h1 className="text-xl font-semibold">InterviewAce</h1>
                    </div>
                    <StatusIndicator status={sessionStatus} />
                </div>
            </header>

            {/* Main Content */}
            <main className="max-w-4xl mx-auto px-6 py-8 space-y-8">

                {/* Error Banner */}
                {error && (
                    <div className="bg-red-900/30 border border-red-700 text-red-300 px-4 py-3 rounded-lg">
                        {error}
                        <button
                            className="ml-4 text-red-400 hover:text-red-200"
                            onClick={() => setError('')}
                        >
                            ✕
                        </button>
                    </div>
                )}

                {/* Step 1: Upload Resume */}
                <section>
                    <h2 className="text-lg font-medium mb-3 flex items-center gap-2">
                        <span className="bg-blue-600 text-white w-6 h-6 rounded-full flex items-center justify-center text-xs">1</span>
                        Upload Resume
                    </h2>
                    <FileUploader
                        accept=".pdf,.docx,.doc"
                        label="Drop your resume here (PDF or DOCX)"
                        onFile={setResumeFile}
                        file={resumeFile}
                    />
                </section>

                {/* Step 2: Job Description */}
                <section>
                    <h2 className="text-lg font-medium mb-3 flex items-center gap-2">
                        <span className="bg-blue-600 text-white w-6 h-6 rounded-full flex items-center justify-center text-xs">2</span>
                        Paste Job Description
                    </h2>
                    <textarea
                        className="w-full h-40 bg-gray-900 border border-gray-700 rounded-lg p-4 text-sm
                                   text-gray-200 placeholder-gray-500 resize-y
                                   focus:outline-none focus:border-blue-500 transition"
                        placeholder="Paste the full job description here..."
                        value={jdText}
                        onChange={(e) => setJdText(e.target.value)}
                    />
                </section>

                {/* Step 3: Context Files (Optional) */}
                <section>
                    <h2 className="text-lg font-medium mb-3 flex items-center gap-2">
                        <span className="bg-gray-600 text-white w-6 h-6 rounded-full flex items-center justify-center text-xs">3</span>
                        Context Files
                        <span className="text-xs text-gray-500 font-normal">(optional)</span>
                    </h2>
                    <FileUploader
                        accept=".pdf,.docx,.doc,.txt,.md"
                        label="Drop additional context files (notes, portfolio, STAR stories...)"
                        onFile={(f) => setContextFiles((prev) => [...prev, f])}
                        multiple
                    />
                    {contextFiles.length > 0 && (
                        <div className="mt-2 space-y-1">
                            {contextFiles.map((f, i) => (
                                <div key={i} className="flex items-center gap-2 text-sm text-gray-400">
                                    <span>📄 {f.name}</span>
                                    <button
                                        className="text-red-400 hover:text-red-300 text-xs"
                                        onClick={() =>
                                            setContextFiles((prev) => prev.filter((_, j) => j !== i))
                                        }
                                    >
                                        remove
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </section>

                {/* Step 4: Configuration */}
                <section>
                    <h2 className="text-lg font-medium mb-3 flex items-center gap-2">
                        <span className="bg-blue-600 text-white w-6 h-6 rounded-full flex items-center justify-center text-xs">4</span>
                        Configure
                    </h2>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <ModelSelector value={model} onChange={setModel} />
                        <AudioDevicePicker
                            label="System Audio (Interviewer)"
                            devices={devices.system_devices}
                            value={systemDevice}
                            onChange={setSystemDevice}
                        />
                        <AudioDevicePicker
                            label="Microphone (You)"
                            devices={devices.mic_devices}
                            value={micDevice}
                            onChange={setMicDevice}
                        />
                    </div>
                </section>

                {/* Prep Progress */}
                {sessionStatus === 'preparing' && (
                    <section className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                        <h3 className="text-sm font-medium text-gray-400 mb-3">Preparing your session...</h3>
                        <div className="w-full bg-gray-800 rounded-full h-2 mb-2">
                            <div
                                className="bg-blue-500 h-2 rounded-full transition-all duration-500"
                                style={{ width: `${prepProgress}%` }}
                            />
                        </div>
                        <p className="text-xs text-gray-500">{prepStep}</p>
                    </section>
                )}

                {/* Predicted Questions Preview */}
                {sessionStatus === 'ready' && predictedQuestions.length > 0 && (
                    <section className="bg-gray-900 border border-green-800 rounded-lg p-6">
                        <h3 className="text-sm font-medium text-green-400 mb-3">
                            ✅ Session Ready — {predictedQuestions.length} questions predicted
                        </h3>
                        <div className="space-y-2 max-h-48 overflow-y-auto">
                            {predictedQuestions.slice(0, 5).map((q, i) => (
                                <div key={i} className="text-sm text-gray-300 flex gap-2">
                                    <span className="text-gray-500 shrink-0">{i + 1}.</span>
                                    <span>{q.question || q}</span>
                                </div>
                            ))}
                            {predictedQuestions.length > 5 && (
                                <p className="text-xs text-gray-500">
                                    + {predictedQuestions.length - 5} more questions prepared
                                </p>
                            )}
                        </div>
                    </section>
                )}

                {/* Action Buttons */}
                <section className="flex gap-4">
                    {sessionStatus === 'idle' && (
                        <button
                            onClick={handleStartPrep}
                            className="px-6 py-3 bg-blue-600 hover:bg-blue-500 rounded-lg font-medium
                                       transition disabled:opacity-50 disabled:cursor-not-allowed"
                            disabled={!resumeFile || !jdText.trim()}
                        >
                            🧠 Prepare Session
                        </button>
                    )}

                    {sessionStatus === 'ready' && (
                        <button
                            onClick={handleGoLive}
                            className="px-6 py-3 bg-red-600 hover:bg-red-500 rounded-lg font-medium
                                       transition animate-pulse"
                        >
                            🔴 Go Live
                        </button>
                    )}

                    {sessionStatus === 'live' && (
                        <div className="flex items-center gap-3 text-green-400">
                            <span className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
                            <span className="font-medium">Interview in progress — overlay is active</span>
                        </div>
                    )}
                </section>
            </main>
        </div>
    );
}
