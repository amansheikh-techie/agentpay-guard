// components/RequestPanel.tsx — Natural-language shopping request form wired to POST /api/agent/propose
// Featuring Voice Assistant integration (Web Speech API Recognition & SpeechSynthesis)
import { useState, useEffect, useRef } from 'react';
import {
  Send,
  Sparkles,
  AlertCircle,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Square,
  Radio,
} from 'lucide-react';
import { propose } from '../api/client';
import type { Proposal } from '../types';

interface Props {
  onProposalCreated: (proposal: Proposal) => void;
}

const DEMO_SCENARIOS = [
  {
    chip: 'Allowed',
    chipClass: 'chip-allowed',
    text: 'Find a wireless mouse for work, under $35, from an approved merchant.',
    hint: 'Meets cap ($29.99 < $40), merchant TechCore is approved.',
  },
  {
    chip: 'Blocked: Cap',
    chipClass: 'chip-blocked',
    text: 'I need a high-end mechanical keyboard for typing.',
    hint: 'Product costs $79.99, exceeds $40 per-order limit.',
  },
  {
    chip: 'Blocked: Merchant',
    chipClass: 'chip-merchant',
    text: 'Find a shadowtech gadget for my desk.',
    hint: 'Merchant ShadowTech is NOT in approved list.',
  },
];

// Browser Web Speech API SpeechRecognition compatibility constructor
const getSpeechRecognitionClass = () => {
  if (typeof window === 'undefined') return null;
  const win = window as any;
  return win.SpeechRecognition || win.webkitSpeechRecognition || null;
};

export default function RequestPanel({ onProposalCreated }: Props) {
  const [requestText, setRequestText] = useState('');
  const [selectedScenarioIndex, setSelectedScenarioIndex] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Voice Assistant states
  const speechSupported = !!getSpeechRecognitionClass();
  const [speechLang, setSpeechLang] = useState<'en-IN' | 'en-US'>('en-IN');
  const [isListening, setIsListening] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState('');
  const [speechError, setSpeechError] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);

  const recognitionRef = useRef<any>(null);

  // Cleanup speech synthesis on unmount
  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // ignore
        }
      }
    };
  }, []);

  // Voice synthesizer helper preferring en-IN or en-US voices
  const speakVerdict = (text: string) => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window) || isMuted) {
      return;
    }
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();

    // Prefer selected English accent (en-IN or en-US)
    const preferredVoice =
      speechLang === 'en-IN'
        ? voices.find((v) => v.lang === 'en-IN' || v.lang === 'en_IN') ||
          voices.find((v) => v.lang.startsWith('en')) ||
          null
        : voices.find((v) => v.lang.startsWith('en-US')) ||
          voices.find((v) => v.lang.startsWith('en')) ||
          null;

    if (preferredVoice) {
      utterance.voice = preferredVoice;
    }
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.speak(utterance);
  };

  const handleStopSpeaking = () => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    }
  };

  const handleToggleMute = () => {
    if (!isMuted && isSpeaking) {
      handleStopSpeaking();
    }
    setIsMuted((prev) => !prev);
  };

  const submitProposal = async (textToSubmit: string, mode: 'text' | 'voice' = 'text') => {
    const clean = textToSubmit.trim();
    if (!clean || loading) return;

    setLoading(true);
    setError(null);
    setSpeechError(null);

    try {
      const proposal = await propose(clean, mode);
      onProposalCreated(proposal);

      // Speak the deterministic verdict aloud if voice synthesis is enabled
      if (proposal.spoken_response) {
        speakVerdict(proposal.spoken_response);
      }
    } catch (err: unknown) {
      const msg = (err as Error).message || 'Failed to submit shopping request.';
      setError(msg);
      if (mode === 'voice') {
        speakVerdict('Speech unclear. Please repeat your shopping request mentioning the item you want.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleStartListening = () => {
    const SpeechClass = getSpeechRecognitionClass();
    if (!SpeechClass || loading) return;

    setError(null);
    setSpeechError(null);
    handleStopSpeaking();

    try {
      const recognition = new (SpeechClass as any)();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = speechLang;

      recognition.onstart = () => {
        setIsListening(true);
        setLiveTranscript('');
      };

      recognition.onresult = (event: any) => {
        let interim = '';
        let final = '';

        for (let i = 0; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            final += event.results[i][0].transcript;
          } else {
            interim += event.results[i][0].transcript;
          }
        }

        const current = final || interim;
        setLiveTranscript(current);

        if (final && final.trim().length >= 3) {
          setRequestText(final.trim());
          setSelectedScenarioIndex(null);
          submitProposal(final.trim(), 'voice');
        }
      };

      recognition.onerror = (event: any) => {
        setIsListening(false);
        if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
          setSpeechError('Microphone permission denied. Please allow microphone access in your browser or type your request.');
        } else if (event.error === 'no-speech') {
          setSpeechError('No speech was detected. Please try clicking the mic again or type your request.');
        } else if (event.error === 'network') {
          setSpeechError('Speech recognition network error. Please check your connection or type your request.');
        } else {
          setSpeechError(`Voice input error (${event.error}). Please type your request below.`);
        }
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.error('Could not initialize speech recognition:', err);
      setIsListening(false);
      setSpeechError('Could not start microphone. Please type your shopping request.');
    }
  };

  const handleStopListening = () => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
    }
    setIsListening(false);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    submitProposal(requestText, 'text');
  };

  return (
    <div className="card">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div className="card-icon">
            <Sparkles size={18} />
          </div>
          <h2 style={{ margin: 0 }}>AI Shopping Agent</h2>
        </div>

        {/* Audio control actions */}
        <div className="voice-audio-controls">
          {isSpeaking && (
            <>
              <span className="speaking-indicator">
                <Radio size={12} /> Speaking
              </span>
              <button
                type="button"
                className="voice-ctrl-btn"
                onClick={handleStopSpeaking}
                title="Stop reading verdict aloud"
              >
                <Square size={12} /> Stop
              </button>
            </>
          )}

          <button
            type="button"
            className="voice-ctrl-btn"
            onClick={handleToggleMute}
            title={isMuted ? 'Unmute voice replies' : 'Mute voice replies'}
          >
            {isMuted ? <VolumeX size={14} color="var(--danger)" /> : <Volume2 size={14} color="var(--success)" />}
            <span>{isMuted ? 'Muted' : 'Voice Reply ON'}</span>
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem', width: '100%', minWidth: 0 }}>
        {error && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.625rem', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 'var(--radius-md)', color: 'var(--danger)', fontSize: '0.8rem' }}>
            <AlertCircle size={15} />
            <span>{error}</span>
          </div>
        )}

        {speechError && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.625rem', background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 'var(--radius-md)', color: '#fbbf24', fontSize: '0.8rem' }}>
            <AlertCircle size={15} />
            <span>{speechError}</span>
          </div>
        )}

        {/* Voice Assistant Interactive Bar (only when Web Speech API is supported) */}
        {speechSupported && (
          <div className="voice-toolbar">
            <div className="voice-toolbar-top">
              <div className="voice-status-group">
                <button
                  type="button"
                  className={`mic-btn ${isListening ? 'listening' : ''}`}
                  onClick={isListening ? handleStopListening : handleStartListening}
                  disabled={loading}
                  title={isListening ? 'Listening... click to stop' : 'Click to speak shopping request'}
                  aria-label={isListening ? 'Stop listening' : 'Start voice input'}
                >
                  {isListening ? <MicOff size={18} /> : <Mic size={18} />}
                </button>
                <span className="voice-status-text">
                  {isListening ? 'Listening… speak your shopping request now' : 'Voice Assistant Ready'}
                </span>
              </div>

              <div className="voice-accent-group">
                <label htmlFor="voice-lang-select" className="voice-accent-label">
                  Accent:
                </label>
                <select
                  id="voice-lang-select"
                  value={speechLang}
                  onChange={(e) => setSpeechLang(e.target.value as 'en-IN' | 'en-US')}
                  disabled={isListening || loading}
                  className="voice-accent-select"
                  title="Select language accent for speech recognition and spoken verdict"
                >
                  <option value="en-IN">en-IN (India)</option>
                  <option value="en-US">en-US (US)</option>
                </select>
              </div>
            </div>

            <div className="voice-status-subtext">
              {isListening
                ? 'Say an item and price (e.g. "Find a mouse under $35")'
                : 'Click microphone to speak or type in the box below'}
            </div>
          </div>
        )}

        {/* Live Speech Interim Transcript preview */}
        {isListening && liveTranscript && (
          <div className="voice-live-transcript">
            <Radio size={14} className="spin-anim" />
            <span>&ldquo;{liveTranscript}&rdquo;</span>
          </div>
        )}

        <div className="form-group" style={{ width: '100%', minWidth: 0 }}>
          <label className="form-label" htmlFor="shopping-request">
            Natural-Language Shopping Request
          </label>
          <textarea
            id="shopping-request"
            className="form-textarea"
            placeholder="e.g. Find a wireless mouse for work, under $35, from an approved merchant."
            value={requestText}
            onChange={(e) => {
              const val = e.target.value;
              setRequestText(val);
              if (selectedScenarioIndex !== null && val !== DEMO_SCENARIOS[selectedScenarioIndex]?.text) {
                setSelectedScenarioIndex(null);
              }
            }}
            rows={3}
            disabled={loading}
          />
        </div>

        {/* Demo Scenario Quick-Picks */}
        <div style={{ width: '100%', minWidth: 0 }}>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Test Hackathon Demo Scenarios:
          </p>
          <div className="scenario-list">
            {DEMO_SCENARIOS.map((s, idx) => {
              const isSelected = selectedScenarioIndex === idx && requestText === s.text;
              return (
                <button
                  key={idx}
                  type="button"
                  className={`scenario-btn ${isSelected ? 'selected' : ''}`}
                  onClick={() => {
                    setRequestText(s.text);
                    setSelectedScenarioIndex(idx);
                  }}
                  disabled={loading}
                  aria-pressed={isSelected}
                >
                  <span className={`scenario-chip ${s.chipClass}`}>{s.chip}</span>
                  <div className="scenario-text">{s.text}</div>
                  <div className="scenario-hint">{s.hint}</div>
                </button>
              );
            })}
          </div>
        </div>

        <button
          id="submit-request-btn"
          type="submit"
          className="btn btn-primary btn-full btn-lg"
          disabled={!requestText.trim() || loading}
        >
          {loading ? (
            <>
              <span className="spinner" />
              <span>Checking policy...</span>
            </>
          ) : (
            <>
              <Send size={16} />
              <span>Propose Purchase</span>
            </>
          )}
        </button>

        <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', textAlign: 'center', lineHeight: 1.45, margin: 0 }}>
          🎙️ <strong>Voice Boundary</strong>: Voice can propose products. Final payment approval stays an explicit human click in the Approvals tab.
        </p>
      </form>
    </div>
  );
}
