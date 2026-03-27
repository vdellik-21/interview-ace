/**
 * InterviewAce — Session Store (Zustand)
 * Global state for the current interview session.
 *
 * Owner: Dev 3
 */

import { create } from 'zustand';

const useSessionStore = create((set) => ({
    // Session identity
    sessionId: null,
    status: 'idle', // idle | preparing | ready | live | ended

    // Files
    resumeFile: null,
    jdText: '',
    contextFiles: [],

    // Config
    model: 'gpt-5-mini',
    systemDevice: '',
    micDevice: '',

    // Prep results
    prepProgress: 0,
    prepStep: '',
    predictedQuestions: [],

    // Live interview
    transcript: [],
    currentQuestion: '',
    currentAnswer: '',
    isStreaming: false,

    // Actions
    setSessionId: (id) => set({ sessionId: id }),
    setStatus: (status) => set({ status }),
    setResumeFile: (file) => set({ resumeFile: file }),
    setJdText: (text) => set({ jdText: text }),
    addContextFile: (file) => set((s) => ({ contextFiles: [...s.contextFiles, file] })),
    removeContextFile: (i) => set((s) => ({ contextFiles: s.contextFiles.filter((_, j) => j !== i) })),
    setModel: (model) => set({ model }),
    setSystemDevice: (d) => set({ systemDevice: d }),
    setMicDevice: (d) => set({ micDevice: d }),
    setPrepProgress: (step, percent) => set({ prepStep: step, prepProgress: percent }),
    setPredictedQuestions: (qs) => set({ predictedQuestions: qs }),
    addTranscript: (entry) => set((s) => ({ transcript: [...s.transcript.slice(-50), entry] })),
    setCurrentQuestion: (q) => set({ currentQuestion: q, currentAnswer: '', isStreaming: true }),
    appendAnswer: (token) => set((s) => ({ currentAnswer: s.currentAnswer + token })),
    setStreamingDone: () => set({ isStreaming: false }),

    // Reset
    reset: () => set({
        sessionId: null, status: 'idle', prepProgress: 0, prepStep: '',
        predictedQuestions: [], transcript: [], currentQuestion: '',
        currentAnswer: '', isStreaming: false,
    }),
}));

export default useSessionStore;
