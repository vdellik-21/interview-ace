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
import AppIcon from '../components/AppIcon';

async function parseJsonResponse(res, fallbackMessage) {
    const raw = await res.text();
    const data = raw ? JSON.parse(raw) : null;

    if (!res.ok) {
        throw new Error(data?.message || fallbackMessage);
    }

    if (!data) {
        throw new Error(fallbackMessage);
    }

    return data;
}

export default function PrepDashboard() {
    // File state
    const [resumeFile, setResumeFile] = useState(null);
    const [jdText, setJdText] = useState('');
    const [contextFiles, setContextFiles] = useState([]);

    // Config state
    const [model, setModel] = useState('gpt-5-mini');
    const [systemDevice, setSystemDevice] = useState('');
    const [speakerOutput, setSpeakerOutput] = useState('');
    const [micDevice, setMicDevice] = useState('');

    // Session state
    const [sessionStatus, setSessionStatus] = useState('idle'); // idle | preparing | ready | live
    const [prepProgress, setPrepProgress] = useState(0);
    const [prepStep, setPrepStep] = useState('');
    const [predictedQuestions, setPredictedQuestions] = useState([]);
    const [sessionId, setSessionId] = useState(null);
    const [error, setError] = useState('');

    // Fetch audio devices on mount
    const [devices, setDevices] = useState({
        system_devices: [],
        mic_devices: [],
        output_devices: [],
        default_output_device: '',
        warnings: [],
    });

    useEffect(() => {
        fetch('/api/devices')
            .then((res) => parseJsonResponse(res, 'Backend is unavailable. Please wait for the backend to finish starting.'))
            .then((data) => {
                setDevices(data);
                if (data.system_devices.length > 0) setSystemDevice(data.system_devices[0]);
                if (data.default_output_device) {
                    setSpeakerOutput(data.default_output_device);
                } else if (data.output_devices?.length > 0) {
                    setSpeakerOutput(data.output_devices[0]);
                }
                if (data.mic_devices.length > 0) setMicDevice(data.mic_devices[0]);
            })
            .catch((err) => {
                console.error('Failed to fetch devices:', err);
                setError(err.message || 'Failed to fetch audio devices');
            });
    }, []);

    useEffect(() => {
        if (!window.electronAPI?.onSessionStatusChanged) {
            return undefined;
        }

        const handler = (payload) => {
            if (!payload?.status) {
                return;
            }

            if (payload.status === 'ready') {
                setError('');
            }

            setSessionStatus(payload.status);
        };

        window.electronAPI.onSessionStatusChanged(handler);
        return undefined;
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
        if (!systemDevice) {
            setError('Select an interviewer capture device such as BlackHole 2ch before preparing the session. Your speakers are configured separately in Playback Output.');
            return;
        }
        if (!speakerOutput) {
            setError('Select your playback output (system speakers or headphones) before preparing the session.');
            return;
        }

        setError('');
        setSessionStatus('preparing');
        setPrepProgress(5);
        setPrepStep('Uploading files and queueing prep...');

        try {
            const formData = new FormData();
            formData.append('resume', resumeFile);
            formData.append('jd_text', jdText);
            formData.append('model', model);
            formData.append('system_audio_device', systemDevice);
            formData.append('speaker_output_device', speakerOutput);
            formData.append('mic_device', micDevice);
            contextFiles.forEach((f) => formData.append('context_files', f));

            const res = await fetch('/api/session/create', {
                method: 'POST',
                body: formData,
            });

            const data = await parseJsonResponse(
                res,
                'Backend did not return a valid session response.'
            );
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
                    setPrepStep('Ready!');
                    setPrepProgress(100);
                    setPredictedQuestions(msg.predicted_questions || []);
                    ws.close();
                } else if (msg.type === 'error') {
                    setError(msg.message);
                    setSessionStatus('idle');
                    ws.close();
                }
            };
        } catch (err) {
            setError(`Failed to start session: ${err.message}`);
            setSessionStatus('idle');
        }
    };

    // ─── Go Live ────────────────────────────────
    const handleGoLive = () => {
        if (!sessionId) {
            setError('Session is not ready yet.');
            return;
        }

        setSessionStatus('live');
        // Tell Electron to show the stealth overlay
        if (window.electronAPI) {
            if (window.electronAPI.goLive) {
                window.electronAPI.goLive(sessionId);
            } else {
                window.electronAPI.showOverlay(sessionId);
            }
        } else {
            // If not in Electron, open overlay in new tab
            window.open(`/overlay?session=${encodeURIComponent(sessionId)}`, '_blank');
        }
    };

    const pageBackground =
        'linear-gradient(180deg, rgba(3,7,18,0.08) 0%, rgba(2,6,23,0.06) 100%)';
    const pageTextClass = 'text-white';
    const headerCardClass = 'border-white/8';
    const shellClass = 'border-white/8 shadow-[0_24px_80px_rgba(0,0,0,0.35)]';
    const sectionClass = 'border-white/10 shadow-[0_18px_60px_rgba(0,0,0,0.28)]';
    const configSectionClass = 'border-white/10 shadow-[0_18px_60px_rgba(0,0,0,0.32)]';
    const textareaClass =
        'border-white/10 bg-slate-950/75 text-gray-200 placeholder-gray-500 focus:border-cyan-400/60';
    const mutedTextClass = 'text-gray-500';
    const bodyTextClass = 'text-gray-300';
    const panelClass = 'border-white/8 bg-black/20';

    return (
        <div
            className={`min-h-screen ${pageTextClass}`}
            style={{
                background: pageBackground,
                transition: 'background 200ms ease',
            }}
        >
            {/* Header */}
            <header className="px-6 py-5">
                <div
                    className={`mx-auto flex max-w-5xl items-center justify-between rounded-[24px] border px-5 py-4 backdrop-blur-xl ${headerCardClass}`}
                    style={{ backgroundColor: 'rgba(2,6,23,0.18)' }}
                >
                    <div className="flex items-center gap-3">
                        <AppIcon className="h-10 w-10" />
                        <div>
                            <div className={`text-[11px] uppercase tracking-[0.22em] ${mutedTextClass}`}>
                                Stealth Workspace
                            </div>
                            <h1 className="text-lg font-medium text-gray-100">InterviewAce</h1>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <StatusIndicator status={sessionStatus} />
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="mx-auto max-w-5xl px-6 pb-10">
                <div
                    className={`space-y-8 rounded-[32px] border p-6 backdrop-blur-xl ${shellClass}`}
                    style={{ backgroundColor: 'rgba(2,6,23,0.16)' }}
                >

                {/* Error Banner */}
                {error && (
                    <div className="rounded-2xl border border-red-500/25 bg-red-500/10 px-4 py-3 text-red-200">
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
                <section
                    className={`rounded-[28px] border px-5 py-5 ${sectionClass}`}
                    style={{ backgroundColor: 'rgba(255,255,255,0.12)' }}
                >
                    <h2 className="mb-3 flex items-center gap-2 text-lg font-medium">
                        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-sm text-white">1</span>
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
                <section
                    className={`rounded-[28px] border px-5 py-5 ${sectionClass}`}
                    style={{ backgroundColor: 'rgba(255,255,255,0.12)' }}
                >
                    <h2 className="mb-3 flex items-center gap-2 text-lg font-medium">
                        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-sm text-white">2</span>
                        Paste Job Description
                    </h2>
                    <textarea
                        className={`h-40 w-full resize-y rounded-2xl border p-4 text-sm transition focus:outline-none ${textareaClass}`}
                        placeholder="Paste the full job description here..."
                        value={jdText}
                        onChange={(e) => setJdText(e.target.value)}
                    />
                </section>

                {/* Step 3: Context Files (Optional) */}
                <section
                    className={`rounded-[28px] border px-5 py-5 ${sectionClass}`}
                    style={{ backgroundColor: 'rgba(255,255,255,0.12)' }}
                >
                    <div className="mb-4 flex items-center justify-between gap-3">
                        <h2 className="text-lg font-medium flex items-center gap-2">
                            <span className="w-8 h-8 rounded-full flex items-center justify-center bg-white/10 text-sm text-white">3</span>
                            Context Files
                            <span className={`text-xs font-normal ${mutedTextClass}`}>(optional)</span>
                        </h2>
                        <span className={`rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.22em] ${panelClass} ${mutedTextClass}`}>
                            Stealth Context
                        </span>
                    </div>
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
                                        className="text-xs text-red-400 hover:text-red-300"
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
                <section
                    className={`rounded-[28px] border px-5 py-5 ${configSectionClass}`}
                    style={{ background: 'linear-gradient(180deg, rgba(255,255,255,0.16) 0%, rgba(255,255,255,0.1) 100%)' }}
                >
                    <div className="mb-4 flex items-center justify-between gap-3">
                        <div>
                            <h2 className="text-lg font-medium flex items-center gap-2">
                                <span className="bg-cyan-500/20 text-cyan-200 w-8 h-8 rounded-full flex items-center justify-center text-sm">4</span>
                                Configure
                            </h2>
                            <p className={`mt-1 text-xs uppercase tracking-[0.18em] ${mutedTextClass}`}>
                                Low-visibility live setup
                            </p>
                        </div>
                        <span className="rounded-full border border-cyan-400/20 bg-cyan-500/8 px-3 py-1 text-[10px] uppercase tracking-[0.22em] text-cyan-200/80">
                            Stealth Mode
                        </span>
                    </div>
                    {devices.warnings?.length > 0 && (
                        <div className="mb-4 rounded-2xl border border-yellow-700/40 bg-yellow-900/15 px-4 py-3 text-sm text-yellow-200">
                            {devices.warnings.join(' ')}
                        </div>
                    )}
                    <div
                        className={`rounded-[24px] border p-4 ${panelClass}`}
                        style={{ backgroundColor: 'rgba(2,6,23,0.18)' }}
                    >
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <ModelSelector value={model} onChange={setModel} />
                            <AudioDevicePicker
                                label="Interviewer Capture"
                                devices={devices.system_devices}
                                value={systemDevice}
                                onChange={setSystemDevice}
                            />
                            <AudioDevicePicker
                                label="Playback Output"
                                devices={devices.output_devices}
                                value={speakerOutput}
                                onChange={setSpeakerOutput}
                            />
                            <AudioDevicePicker
                                label="Microphone (optional, not recorded)"
                                devices={devices.mic_devices}
                                value={micDevice}
                                onChange={setMicDevice}
                            />
                        </div>
                    </div>
                    <p className={`mt-4 text-xs leading-relaxed ${mutedTextClass}`}>
                        The selected interview model now powers both preparation and live answers, so the
                        same model builds the dossier and answers questions during the interview.
                    </p>
                    <p className={`mt-2 text-xs leading-relaxed ${mutedTextClass}`}>
                        `Interviewer Capture` should be a loopback input like `BlackHole 2ch`.
                        `Playback Output` is where you hear the call, such as your MacBook Air speakers,
                        headphones, or a Multi-Output Device that includes both your speakers and BlackHole.
                        Your microphone selection is kept for convenience, but the live transcript now listens only to interviewer audio.
                    </p>
                </section>

                {/* Prep Progress */}
                {sessionStatus === 'preparing' && (
                    <section
                        className={`rounded-[24px] border p-6 ${sectionClass}`}
                        style={{ backgroundColor: 'rgba(255,255,255,0.12)' }}
                    >
                        <h3 className={`mb-3 text-[11px] font-medium uppercase tracking-[0.2em] ${mutedTextClass}`}>
                            Preparing session
                        </h3>
                        <div className="mb-2 h-2 w-full rounded-full bg-gray-800">
                            <div
                                className="h-2 rounded-full bg-cyan-400 transition-all duration-500"
                                style={{ width: `${prepProgress}%` }}
                            />
                        </div>
                        <p className={`text-sm ${bodyTextClass}`}>{prepStep}</p>
                    </section>
                )}

                {/* Predicted Questions Preview */}
                {sessionStatus === 'ready' && predictedQuestions.length > 0 && (
                    <section className="rounded-[24px] border border-emerald-400/20 bg-emerald-500/[0.05] p-6">
                        <h3 className="mb-3 text-sm font-medium text-emerald-300">
                            ✅ Session Ready — {predictedQuestions.length} questions predicted
                        </h3>
                        <div className="max-h-48 space-y-2 overflow-y-auto">
                            {predictedQuestions.slice(0, 5).map((q, i) => (
                                <div key={i} className={`flex gap-2 text-sm ${bodyTextClass}`}>
                                    <span className={`${mutedTextClass} shrink-0`}>{i + 1}.</span>
                                    <span>{q.question || q}</span>
                                </div>
                            ))}
                            {predictedQuestions.length > 5 && (
                                <p className={`text-xs ${mutedTextClass}`}>
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
                            className="rounded-2xl border border-cyan-400/20 bg-cyan-500/10 px-6 py-3 font-medium text-cyan-100
                                       transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={!resumeFile || !jdText.trim()}
                        >
                            🧠 Prepare Session
                        </button>
                    )}

                    {sessionStatus === 'ready' && (
                        <button
                            onClick={handleGoLive}
                            className="rounded-2xl border border-red-400/25 bg-red-500/10 px-6 py-3 font-medium text-red-100
                                       transition hover:bg-red-500/20"
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
                </div>
            </main>
        </div>
    );
}
