import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Torus, Sphere, Icosahedron, Stars, MeshDistortMaterial } from '@react-three/drei';
import { io, Socket } from 'socket.io-client';
import {
  Terminal, Activity, Cpu, HardDrive, Thermometer,
  Zap, Eye, Globe, Mic, Brain, Shield, Code, FolderOpen,
  BarChart3, Settings, Wifi, Clock, Play, AlertTriangle,
  CheckCircle, XCircle, Package, GitBranch, DollarSign,
  Briefcase, TrendingUp, FileText, ClipboardList
} from 'lucide-react';
import * as THREE from 'three';
import './App.css';

// ════════════════════════════════════════════════════════
// Types
// ════════════════════════════════════════════════════════

interface SaiState {
  thought: string;
  action: string;
  status: string;
  neural_load: string;
  cpu_load: string;
  latency: string;
  net_speed: string;
  core_temp: string;
  screenshot: string;
  history: Array<{ action: string; observation?: string } | string>;
}

interface VoiceTranscriptItem {
  event: string;
  text: string;
  timestamp: number;
}

interface IdleLogEntry {
  type: string;
  timestamp: number;
  action?: string;
  phase?: string;
  status?: string;
  error?: string;
  message?: string;
  seconds?: number;
  rounds?: number;
  detail?: string;
  files?: number;
  project?: string;
  reason?: string;
  total?: number;
  result_summary?: string;
}

interface SettingsData {
  idle_enabled: boolean;
  idle_min_cooldown: number;
  idle_max_cooldown: number;
  email_enabled: boolean;
  voice_enabled: boolean;
  brain_provider: string;
  brain_model: string;
  safety_level: string;
}

interface BusinessAnalytics {
  generated_at?: string;
  revenue?: {
    total_earned_usd?: number;
    pending_usd?: number;
    overdue_invoices?: number;
    total_invoices?: number;
    collection_rate_pct?: number;
  };
  pipeline?: {
    total_jobs_discovered?: number;
    avg_fit_score?: number;
  };
  proposals?: {
    total_proposals?: number;
    submitted?: number;
    won?: number;
    win_rate_pct?: number;
    today_proposals?: number;
    daily_limit?: number;
  };
  projects?: {
    total_projects?: number;
    active?: number;
    delivered?: number;
    total_revenue_usd?: number;
  };
  engine_status?: {
    actions_executed?: number;
    last_action_time?: string;
  };
}

// ════════════════════════════════════════════════════════
// 3D Holographic Core
// ════════════════════════════════════════════════════════

const HolographicCore = ({ active, cpuPercent }: { active: boolean; cpuPercent: number }) => {
  const groupRef = useRef<THREE.Group>(null);
  const ring1Ref = useRef<THREE.Mesh>(null);
  const ring2Ref = useRef<THREE.Mesh>(null);
  const ring3Ref = useRef<THREE.Mesh>(null);

  const colorPrimary = "#00e5ff";
  const colorSecondary = "#7c4dff";

  useFrame((frameState) => {
    const t = frameState.clock.elapsedTime;
    const speed = active ? 2.0 : 0.4;
    const intensity = 0.5 + (cpuPercent / 100) * 1.5;

    if (groupRef.current) {
      groupRef.current.rotation.y = t * 0.08 * speed;
      groupRef.current.position.y = Math.sin(t * 1.2) * 0.08;
    }
    if (ring1Ref.current) {
      ring1Ref.current.rotation.x = t * 0.4 * speed;
      ring1Ref.current.rotation.y = t * 0.15 * speed;
      (ring1Ref.current.material as THREE.MeshBasicMaterial).opacity = 0.3 + Math.sin(t * 2) * 0.15;
    }
    if (ring2Ref.current) {
      ring2Ref.current.rotation.y = t * 0.3 * speed;
      ring2Ref.current.rotation.z = t * 0.25 * speed;
    }
    if (ring3Ref.current) {
      ring3Ref.current.rotation.x = t * 0.08 * speed;
      ring3Ref.current.rotation.z = t * 0.5 * speed;
      const s = 1 + Math.sin(t * 1.5) * 0.03 * intensity;
      ring3Ref.current.scale.set(s, s, s);
    }
  });

  return (
    <group ref={groupRef}>
      <Sphere args={[1.1, 64, 64]}>
        <MeshDistortMaterial
          color={active ? colorPrimary : "#071420"}
          emissive={active ? colorPrimary : "#071420"}
          emissiveIntensity={active ? 1.2 + cpuPercent / 100 : 0.3}
          distort={active ? 0.35 + cpuPercent / 300 : 0.08}
          speed={active ? 4 : 0.8}
          roughness={0.15}
        />
      </Sphere>

      <Icosahedron args={[1.6, 2]}>
        <meshBasicMaterial color={colorPrimary} wireframe transparent opacity={0.1} />
      </Icosahedron>

      <Torus ref={ring1Ref} args={[2.3, 0.012, 16, 100]} rotation={[Math.PI / 2, 0, 0]}>
        <meshBasicMaterial color={colorPrimary} transparent opacity={0.5} />
      </Torus>
      <Torus ref={ring2Ref} args={[2.6, 0.008, 16, 100]} rotation={[0, Math.PI / 3, 0]}>
        <meshBasicMaterial color={colorSecondary} transparent opacity={0.35} />
      </Torus>
      <Torus ref={ring3Ref} args={[3.0, 0.015, 16, 100, Math.PI * 1.6]} rotation={[0, 0, Math.PI / 4]}>
        <meshBasicMaterial color={colorPrimary} transparent opacity={0.6} />
      </Torus>

      <Torus args={[0.4, 0.015, 16, 32]} position={[0, 0, 3.2]}>
        <meshBasicMaterial color={colorPrimary} transparent opacity={0.2} />
      </Torus>
      <Torus args={[0.4, 0.015, 16, 32]} position={[0, 0, -3.2]}>
        <meshBasicMaterial color={colorSecondary} transparent opacity={0.2} />
      </Torus>
    </group>
  );
};

// ════════════════════════════════════════════════════════
// Gauge Ring Component
// ════════════════════════════════════════════════════════

interface GaugeRingProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  color: string;
  colorClass: string;
  size?: number;
}

const GaugeRing = ({ label, value, icon, color, colorClass, size = 72 }: GaugeRingProps) => {
  const numericValue = parseFloat(value) || 0;
  const clampedValue = Math.min(Math.max(numericValue, 0), 100);
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clampedValue / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2 opacity-0 animate-fade-in-up" style={{ animationFillMode: 'forwards' }}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="transform -rotate-90">
          <circle
            className="gauge-ring-track"
            cx={size / 2}
            cy={size / 2}
            r={radius}
          />
          <circle
            className={`gauge-ring-fill ${colorClass}`}
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={color}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xs font-bold" style={{ color, fontFamily: 'var(--font-mono)' }}>
            {value || '0%'}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-1.5">
        <span style={{ color }} className="opacity-70">{icon}</span>
        <span className="text-[9px] font-semibold tracking-wider uppercase" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}>
          {label}
        </span>
      </div>
    </div>
  );
};

// ════════════════════════════════════════════════════════
// Module Status Component
// ════════════════════════════════════════════════════════

interface ModuleInfo {
  name: string;
  icon: React.ReactNode;
  status: 'active' | 'idle' | 'offline';
}

const ModuleStatus = ({ modules }: { modules: ModuleInfo[] }) => (
  <div className="flex flex-col gap-1.5">
    {modules.map((mod, i) => (
      <div
        key={mod.name}
        className="module-indicator opacity-0 animate-fade-in-up"
        style={{ animationDelay: `${i * 0.05}s`, animationFillMode: 'forwards' }}
      >
        <div className={`module-dot ${mod.status}`} />
        <span className="opacity-60">{mod.icon}</span>
        <span style={{ color: 'var(--text-secondary)' }}>{mod.name}</span>
      </div>
    ))}
  </div>
);

// ════════════════════════════════════════════════════════
// Main App
// ════════════════════════════════════════════════════════

export default function App() {
  const [state, setState] = useState<SaiState>({
    thought: "Systems nominal, sir. All modules operational and standing by for your directive.",
    action: "STANDBY",
    status: "offline",
    neural_load: "0%",
    cpu_load: "0%",
    latency: "0%",
    net_speed: "0 KB/s",
    core_temp: "N/A",
    screenshot: "logs/hud.png",
    history: []
  });

  const [cmdInput, setCmdInput] = useState("");
  const [currentTime, setCurrentTime] = useState(new Date());
  const [uptime, setUptime] = useState(0);
  const [micState, setMicState] = useState<'idle' | 'active' | 'error'>('idle');
  const [devices, setDevices] = useState<{device_id: string, device_type: string, status: string}[]>([]);
  const [voiceTranscripts, setVoiceTranscripts] = useState<VoiceTranscriptItem[]>([]);
  const [idleLogs, setIdleLogs] = useState<IdleLogEntry[]>([]);
  const [showSettings, setShowSettings] = useState(false);
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [idleStatus, setIdleStatus] = useState<any>(null);
  const [showBusiness, setShowBusiness] = useState(false);
  const [bizData, setBizData] = useState<BusinessAnalytics | null>(null);

  const historyEndRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const fetchDevices = () => {
      fetch('/api/devices')
        .then(res => res.json())
        .then(data => {
          if (data.status === 'success') {
            setDevices(data.devices || []);
          }
        }).catch(err => console.error(err));
    };
    fetchDevices();
    const interval = setInterval(fetchDevices, 5000);
    return () => clearInterval(interval);
  }, []);

  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    fetch('/api/voice/transcripts?limit=20')
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success' && Array.isArray(data.items)) {
          setVoiceTranscripts(data.items);
        }
      })
      .catch(() => null);
  }, []);

  // Fetch idle logs + settings on mount
  useEffect(() => {
    fetch('/api/idle/logs?limit=50').then(r => r.json()).then(d => { if (d.status === 'success') setIdleLogs(d.items || []); }).catch(() => null);
    fetch('/api/settings').then(r => r.json()).then(d => { if (d.status === 'success') setSettings(d.settings); }).catch(() => null);
    const pollIdle = setInterval(() => {
      fetch('/api/idle/status').then(r => r.json()).then(d => { if (d.status === 'success') setIdleStatus(d); }).catch(() => null);
    }, 5000);
    // Poll business analytics every 15 seconds
    const fetchBiz = () =>
      fetch('/api/business/analytics').then(r => r.json()).then(d => { if (d.status === 'success') setBizData(d.analytics); }).catch(() => null);
    fetchBiz();
    const pollBiz = setInterval(fetchBiz, 15000);
    return () => { clearInterval(pollIdle); clearInterval(pollBiz); };
  }, []);

  // Voice trigger (Web Speech API)
  useEffect(() => {
    let recognition: any = null;
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition && state.status === 'online') {
      try {
        // First try to explicitly ask for microphone permissions if not in secure context this might fail,
        // but it will trigger the browser prompt
        navigator.mediaDevices.getUserMedia({ audio: true })
          .then(() => {
            console.log("Microphone access granted.");
            recognition = new SpeechRecognition();
            recognition.continuous = true;
            recognition.interimResults = false;
            recognition.lang = 'en-US';

            recognition.onstart = () => setMicState('active');
            
            recognition.onerror = (event: any) => {
              if (event.error === 'not-allowed') setMicState('error');
              console.warn("Speech recognition error:", event.error);
            };

            recognition.onend = () => {
              if (state.status === 'online') {
                try { recognition.start(); } catch(e) {}
              } else {
                setMicState('idle');
              }
            };

            recognition.onresult = (event: any) => {
              const current = event.resultIndex;
              const transcript = event.results[current][0].transcript.toLowerCase().trim();
              console.log("[S.A.I. Ears] Heard:", transcript);

              if (transcript.includes("hi sai") || transcript.includes("hi sy") || transcript.includes("hi sy") || transcript.includes("hey sai")) {
                const match = transcript.match(/(?:hi sai|hi sy|hey sai|hi sci)\s+(.*)/i);
                const command = match ? match[1].trim() : "GUI User hailed you via Voice.";
                if (command) {
                  fetch('/api/command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: command })
                  });
                }
              }
            };
            
            try { recognition.start(); } catch(e) {}
          })
          .catch((err) => {
            console.error("Microphone access denied:", err);
            setMicState('error');
          });
      } catch (e) {
        console.warn("Media devices API not supported.");
        setMicState('error');
      }
    }

    return () => {
      if (recognition) {
        recognition.onend = null;
        recognition.stop();
      }
    };
  }, [state.status]);

  // Clock & uptime
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
      setUptime(prev => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Socket connection
  useEffect(() => {
    const socket = io(window.location.host);
    socketRef.current = socket;

    socket.on('connect', () => setState(s => ({ ...s, status: 'online' })));
    socket.on('state_update', (newState: Partial<SaiState>) => {
      setState(prev => ({ ...prev, ...newState }));
    });
    socket.on('voice_transcript_update', (entry: VoiceTranscriptItem) => {
      setVoiceTranscripts(prev => [...prev.slice(-39), entry]);
    });
    socket.on('disconnect', () => setState(s => ({ ...s, status: 'offline' })));
    socket.on('idle_log_update', (entry: IdleLogEntry) => {
      setIdleLogs(prev => [...prev.slice(-99), entry]);
    });

    return () => {
      socket.off('connect');
      socket.off('state_update');
      socket.off('voice_transcript_update');
      socket.off('disconnect');
      socket.off('idle_log_update');
      socket.disconnect();
    };
  }, []);

  // Auto-scroll event log
  useEffect(() => {
    if (historyEndRef.current) {
      historyEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [state.history]);

  const sendCommand = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cmdInput.trim() || state.status !== 'online') return;

    try {
      await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmdInput })
      });
      setCmdInput("");
    } catch (err) {
      console.error("Command dispatch failed:", err);
    }
  }, [cmdInput, state.status]);

  // Derived state
  const isWorking = state.status === "online" && state.action !== "SYSTEM_IDLE" && state.action !== "IDLE";
  const cpuPercent = parseFloat(state.cpu_load) || 0;

  const formatUptime = (secs: number) => {
    const h = String(Math.floor(secs / 3600)).padStart(2, '0');
    const m = String(Math.floor((secs % 3600) / 60)).padStart(2, '0');
    const s = String(secs % 60).padStart(2, '0');
    return `${h}:${m}:${s}`;
  };

  const formatTime = (d: Date) =>
    d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

  const formatTranscriptTs = (ts: number) => {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  // Module list
  const modules: ModuleInfo[] = [
    { name: 'BRAIN', icon: <Brain size={12} />, status: state.status === 'online' ? 'active' : 'offline' },
    { name: 'VISION', icon: <Eye size={12} />, status: state.status === 'online' ? 'active' : 'offline' },
    { name: 'BROWSER', icon: <Globe size={12} />, status: state.status === 'online' ? 'idle' : 'offline' },
    { name: 'VOICE', icon: <Mic size={12} />, status: state.status === 'online' ? (micState === 'idle' ? 'idle' : (micState === 'error' ? 'offline' : 'active')) : 'offline' },
    { name: 'CODER', icon: <Code size={12} />, status: state.status === 'online' ? 'idle' : 'offline' },
    { name: 'SAFETY', icon: <Shield size={12} />, status: state.status === 'online' ? 'active' : 'offline' },
    { name: 'FILES', icon: <FolderOpen size={12} />, status: state.status === 'online' ? 'active' : 'offline' },
    { name: 'SYSTEM', icon: <BarChart3 size={12} />, status: state.status === 'online' ? 'active' : 'offline' },
  ];

  // Extract event log text
  const getLogText = (entry: { action: string; observation?: string } | string): string => {
    if (typeof entry === 'string') return entry;
    return entry.action || 'Unknown event';
  };

  const getIdleLogDisplay = (entry: IdleLogEntry) => {
    const icons: Record<string, React.ReactNode> = {
      'action_start':          <Play size={10} style={{ color: 'var(--cyan)' }} />,
      'action_complete':       <CheckCircle size={10} style={{ color: 'var(--green)' }} />,
      'action_error':          <XCircle size={10} style={{ color: 'var(--red)' }} />,
      'plan_start':            <Brain size={10} style={{ color: 'var(--purple)' }} />,
      'plan_complete':         <ClipboardList size={10} style={{ color: 'var(--cyan)' }} />,
      'review_start':          <FileText size={10} style={{ color: 'var(--amber)' }} />,
      'review_complete':       <CheckCircle size={10} style={{ color: 'var(--green)' }} />,
      'pipeline_start':        <GitBranch size={10} style={{ color: 'var(--cyan)' }} />,
      'pipeline_end':          <CheckCircle size={10} style={{ color: 'var(--green)' }} />,
      'pipeline_error':        <XCircle size={10} style={{ color: 'var(--red)' }} />,
      'phase':                 <Package size={10} style={{ color: 'var(--purple)' }} />,
      'phase_complete':        <CheckCircle size={10} style={{ color: 'var(--green)' }} />,
      'phase_error':           <AlertTriangle size={10} style={{ color: 'var(--red)' }} />,
      'quality_gate_failed':   <XCircle size={10} style={{ color: 'var(--red)' }} />,
      'next_cooldown':         <Clock size={10} style={{ color: 'var(--text-muted)' }} />,
    };
    const e = entry as any;
    const msgs: Record<string, string> = {
      'action_start':         entry.message || 'Starting action...',
      'action_complete':      `${entry.action} [${entry.status}] #${entry.total}`,
      'action_error':         `Error: ${entry.error?.substring(0, 80)}`,
      'plan_start':           `Planning ${e.domain || ''} action...`,
      'plan_complete':        `Plan: ${entry.action} — ${String(e.reasoning || '').substring(0, 60)}`,
      'review_start':         `Reviewing: ${entry.action}`,
      'review_complete':      `Review done — ${String(e.lessons || '').substring(0, 70)}`,
      'pipeline_start':       `Pipeline: ${entry.action}`,
      'pipeline_end':         `Pipeline done: ${entry.action} [${entry.status}]`,
      'pipeline_error':       `Pipeline error: ${entry.error?.substring(0, 80)}`,
      'phase':                `▸ ${(entry.phase || '').toUpperCase()}${entry.files ? ` (${entry.files} files)` : ''}`,
      'phase_complete':       `✓ ${(entry.phase || '').toUpperCase()} done${entry.rounds ? ` (${entry.rounds} rounds)` : ''}`,
      'phase_error':          `✗ ${entry.phase} failed: ${entry.error}`,
      'quality_gate_failed':  `Quality gate: ${entry.rounds} rounds exhausted`,
      'next_cooldown':        `Next action in ${entry.seconds}s`,
    };
    return { icon: icons[entry.type] || <Zap size={10} />, text: msgs[entry.type] || entry.type };
  };

  const saveSettings = (key: string, value: any) => {
    fetch('/api/settings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [key]: value })
    }).then(r => r.json()).then(() => {
      setSettings(prev => prev ? { ...prev, [key]: value } : prev);
    }).catch(() => null);
  };

  return (
    <div className="relative w-screen h-screen overflow-hidden select-none" style={{ background: 'var(--bg-deep)' }}>

      {/* ── Background Layers ── */}
      <div className="grid-bg" />
      <div className="scanline animate-scan" />

      {/* ── HUD Corner Brackets (hidden on very small screens) ── */}
      <div className="hud-corner tl hidden sm:block" />
      <div className="hud-corner tr hidden sm:block" />
      <div className="hud-corner bl hidden sm:block" />
      <div className="hud-corner br hidden sm:block" />

      {/* ════════════════════════════════════════════════
          MAIN UI
          ════════════════════════════════════════════════ */}
      <div className="absolute inset-0 z-10 flex flex-col p-2 sm:p-3 md:p-4 gap-2 sm:gap-3 overflow-y-auto overflow-x-hidden">

        {/* ── TOP ROW ── */}
        <div className="flex flex-wrap lg:flex-nowrap justify-between items-start gap-2 sm:gap-3 flex-shrink-0">

          {/* System ID Panel */}
          <div className="glass-panel p-3 sm:p-4 w-full sm:w-auto sm:min-w-[260px] lg:w-72 opacity-0 animate-fade-in-up stagger-1 order-1" style={{ animationFillMode: 'forwards' }}>
            <div className="flex items-center justify-between mb-2 sm:mb-3 pb-2" style={{ borderBottom: '1px solid var(--border)' }}>
              <h1 className="flex items-center gap-2" style={{ fontFamily: 'var(--font-display)', fontSize: '14px', fontWeight: 700, letterSpacing: '0.15em' }}>
                <Zap size={14} style={{ color: 'var(--cyan)' }} className="animate-pulse" />
                <span className="glow-text" style={{ color: 'var(--cyan)' }}>S.A.I.</span>
                <span style={{ color: 'var(--text-muted)', fontWeight: 400, fontSize: '10px' }}>CORE</span>
              </h1>
              <div className={`status-badge ${state.status}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${state.status === 'online' ? 'animate-pulse' : ''}`}
                  style={{ background: state.status === 'online' ? 'var(--green)' : 'var(--red)', boxShadow: state.status === 'online' ? '0 0 6px var(--green)' : '0 0 6px var(--red)' }}
                />
                {state.status}
              </div>
            </div>

            <div className="flex flex-col gap-1">
              {[
                ['MODEL', 'ADVANCED NEURAL PROTO'],
                ['UPTIME', formatUptime(uptime)],
                ['SECURE LINK', 'ESTABLISHED'],
                ['NODES LINKED', String(devices.length)],
              ].map(([label, val]) => (
                <div key={label} className="flex justify-between items-center" style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', letterSpacing: '0.08em' }}>
                  <span style={{ color: 'var(--text-muted)' }}>{label}</span>
                  <span style={{ color: 'var(--text-secondary)' }}>{val}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Center: Clock & Net Speed */}
          <div className="hidden lg:flex items-center gap-6 opacity-0 animate-fade-in-up stagger-3 order-3 lg:order-2" style={{ animationFillMode: 'forwards' }}>
            {devices.length > 0 && (
              <div className="flex items-center gap-2 px-3 py-1 rounded-md" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}>
                {devices.map(d => (
                  <div key={d.device_id} className="flex gap-1 items-center" style={{ fontFamily: 'var(--font-mono)', fontSize: '10px' }} title={d.device_id}>
                    <Zap size={10} style={{ color: d.status === 'online' ? 'var(--cyan)' : 'var(--text-muted)' }} />
                    <span style={{ color: 'var(--text-secondary)' }}>{d.device_type.substring(0,3).toUpperCase()}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="flex items-center gap-2" style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)' }}>
              <Clock size={13} style={{ color: 'var(--cyan)', opacity: 0.6 }} />
              <span>{formatTime(currentTime)}</span>
            </div>
            <div className="flex items-center gap-2" style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)' }}>
              <Wifi size={13} style={{ color: 'var(--green)', opacity: 0.6 }} />
              <span>{state.net_speed || '0 KB/s'}</span>
            </div>
          </div>

          {/* Telemetry Gauges */}
          <div className="glass-panel p-3 sm:p-4 w-full sm:w-auto opacity-0 animate-fade-in-up stagger-2 order-2 lg:order-3" style={{ animationFillMode: 'forwards' }}>
            <div className="section-label flex items-center gap-2">
              <Activity size={10} style={{ color: 'var(--cyan)' }} />
              SYSTEM DIAGNOSTICS
            </div>
            <div className="flex gap-3 sm:gap-5 items-start justify-center sm:justify-start flex-wrap sm:flex-nowrap">
              <GaugeRing label="CPU" value={state.cpu_load} icon={<Cpu size={10} />} color="var(--cyan)" colorClass="" size={56} />
              <GaugeRing label="RAM" value={state.neural_load} icon={<Activity size={10} />} color="var(--purple)" colorClass="purple" size={56} />
              <GaugeRing label="DISK" value={state.latency} icon={<HardDrive size={10} />} color="var(--green)" colorClass="green" size={56} />
              <GaugeRing label="TEMP" value={state.core_temp?.replace('°C', '%') || 'N/A'} icon={<Thermometer size={10} />} color="var(--amber)" colorClass="amber" size={56} />
            </div>
          </div>
        </div>

        {/* ── MIDDLE ROW (flexible) ── */}
        <div className="flex-1 flex flex-col md:flex-row gap-2 sm:gap-3 min-h-0">

          {/* Left Column: Module Status + Vision Feed — Desktop only */}
          <div className="w-full md:w-48 lg:w-56 flex-shrink-0 flex flex-col gap-2 sm:gap-3 hidden lg:flex">
            {/* Modules */}
            <div className="glass-panel p-3 opacity-0 animate-fade-in-up stagger-3" style={{ animationFillMode: 'forwards' }}>
              <div className="section-label flex items-center gap-2">
                <Settings size={10} style={{ color: 'var(--cyan)' }} />
                MODULE STATUS
              </div>
              <ModuleStatus modules={modules} />
            </div>

            {/* Vision Feed */}
            <div className="glass-panel p-3 flex-1 flex flex-col opacity-0 animate-fade-in-up stagger-5" style={{ animationFillMode: 'forwards' }}>
              <div className="section-label flex items-center gap-2">
                <Eye size={10} style={{ color: 'var(--cyan)' }} />
                <span>VISION FEED</span>
                <span className="ml-auto flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                  <span style={{ fontSize: '8px', color: 'var(--red)', fontFamily: 'var(--font-mono)' }}>LIVE</span>
                </span>
              </div>
              <div className="vision-feed flex-1">
                <img
                  src={`/${state.screenshot}?t=${Date.now()}`}
                  alt="SAI Vision Feed"
                  onError={(e) => { (e.target as HTMLImageElement).style.opacity = '0.2'; }}
                />
              </div>
            </div>
          </div>

          {/* ═══ CENTER COLUMN: 3D Core Box + Thought Panel ═══ */}
          <div className="flex-1 flex flex-col gap-2 sm:gap-3 min-h-0 min-w-0">

            {/* 3D Holographic Core — Dedicated Box */}
            <div className="flex-1 glass-panel relative overflow-hidden opacity-0 animate-fade-in-up stagger-3"
              style={{
                animationFillMode: 'forwards',
                minHeight: '200px',
                borderColor: isWorking ? 'rgba(0, 229, 255, 0.35)' : 'var(--border)',
                boxShadow: isWorking ? '0 0 30px rgba(0, 229, 255, 0.08), inset 0 0 40px rgba(0, 229, 255, 0.03)' : 'none',
                transition: 'border-color 0.5s ease, box-shadow 0.5s ease',
              }}
            >
              {/* HUD brackets inside the 3D box */}
              <div className="absolute top-2 left-2 sm:top-3 sm:left-3 w-3 h-3 sm:w-4 sm:h-4 border-t border-l pointer-events-none z-20" style={{ borderColor: 'rgba(0,229,255,0.3)' }} />
              <div className="absolute top-2 right-2 sm:top-3 sm:right-3 w-3 h-3 sm:w-4 sm:h-4 border-t border-r pointer-events-none z-20" style={{ borderColor: 'rgba(0,229,255,0.3)' }} />
              <div className="absolute bottom-2 left-2 sm:bottom-3 sm:left-3 w-3 h-3 sm:w-4 sm:h-4 border-b border-l pointer-events-none z-20" style={{ borderColor: 'rgba(0,229,255,0.3)' }} />
              <div className="absolute bottom-2 right-2 sm:bottom-3 sm:right-3 w-3 h-3 sm:w-4 sm:h-4 border-b border-r pointer-events-none z-20" style={{ borderColor: 'rgba(0,229,255,0.3)' }} />

              {/* Label */}
              <div className="absolute top-2 sm:top-3 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 pointer-events-none"
                style={{ fontFamily: 'var(--font-display)', fontSize: '7px', letterSpacing: '0.25em', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: isWorking ? 'var(--cyan)' : 'var(--text-muted)', boxShadow: isWorking ? '0 0 6px var(--cyan)' : 'none' }} />
                NEURAL CORE {isWorking ? '• ACTIVE' : '• STANDBY'}
              </div>

              {/* The 3D Canvas */}
              <Canvas camera={{ position: [0, 0, 7], fov: 55 }} style={{ position: 'absolute', inset: 0 }}>
                <ambientLight intensity={isWorking ? 1.2 : 0.4} />
                <directionalLight position={[10, 10, 5]} intensity={1.5} color="#00e5ff" />
                <directionalLight position={[-10, -10, -5]} intensity={0.8} color="#7c4dff" />
                <Stars radius={80} depth={60} count={2000} factor={3} saturation={0.8} fade speed={isWorking ? 1.5 : 0.15} />
                <HolographicCore active={isWorking} cpuPercent={cpuPercent} />
                <OrbitControls
                  enableZoom={false}
                  enablePan={false}
                  autoRotate
                  autoRotateSpeed={0.3}
                  maxPolarAngle={Math.PI / 1.5}
                  minPolarAngle={Math.PI / 3}
                />
              </Canvas>
            </div>

            {/* Thought / Cognitive Vector — Separate Panel Below */}
            <div className="flex-shrink-0 glass-panel px-3 py-2 sm:px-5 sm:py-3 opacity-0 animate-fade-in-up stagger-5 relative"
              style={{
                animationFillMode: 'forwards',
                borderColor: isWorking ? 'rgba(0, 229, 255, 0.3)' : 'var(--border)',
                transition: 'border-color 0.3s ease',
              }}
            >
              {/* Gradient accent lines */}
              <div className="absolute top-0 left-[15%] right-[15%] h-px" style={{ background: 'linear-gradient(to right, transparent, var(--cyan), transparent)' }} />

              <div className="flex flex-col sm:flex-row items-start gap-2 sm:gap-4">
                {/* Left: label + action badge */}
                <div className="flex flex-col sm:flex-col gap-1.5 flex-shrink-0 items-start sm:pt-0.5 max-w-full sm:max-w-[40%]">
                  <p style={{ fontFamily: 'var(--font-display)', fontSize: '8px', letterSpacing: '0.25em', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                    COGNITIVE VECTOR
                  </p>
                  <div className="inline-flex items-start gap-1.5 px-2 sm:px-3 py-1.5 rounded-md w-fit max-w-full"
                    style={{
                      background: isWorking ? 'var(--cyan-dim)' : 'rgba(255,255,255,0.03)',
                      border: `1px solid ${isWorking ? 'rgba(0,229,255,0.25)' : 'rgba(255,255,255,0.06)'}`,
                      fontFamily: 'var(--font-mono)',
                      fontSize: '8px',
                      letterSpacing: '0.08em',
                      color: isWorking ? 'var(--cyan)' : 'var(--text-muted)',
                      transition: 'all 0.3s ease',
                      wordBreak: 'break-word',
                    }}
                  >
                    <span style={{ opacity: 0.5, flexShrink: 0, marginTop: '2px' }}>ACTION:</span>
                    <span style={{ 
                      fontWeight: 600, 
                      whiteSpace: 'normal',
                      display: '-webkit-box',
                      WebkitLineClamp: 4,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden'
                    }} title={state.action}>
                      {state.action}
                    </span>
                    {isWorking && <Zap size={10} className="animate-pulse flex-shrink-0 mt-[2px]" />}
                  </div>
                </div>

                {/* Right: thought text */}
                <div className="flex-1 min-w-0 w-full sm:w-auto">
                  <p className="thought-display"
                    style={{
                      fontFamily: 'var(--font-body)',
                      fontSize: 'clamp(12px, 1.8vw, 18px)',
                      fontWeight: 300,
                      fontStyle: 'italic',
                      color: '#fff',
                      textShadow: '0 0 10px rgba(0, 229, 255, 0.3)',
                      lineHeight: 1.5,
                      overflow: 'hidden',
                      display: '-webkit-box',
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: 'vertical',
                    }}
                  >
                    "{state.thought}"
                    {isWorking && <span className="thought-cursor" />}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Event Log — hidden on small, shown md+ */}
          <div className="w-full md:w-56 lg:w-72 flex-shrink-0 glass-panel p-3 flex flex-col opacity-0 animate-fade-in-up stagger-4 hidden md:flex"
            style={{ animationFillMode: 'forwards' }}
          >
            <div className="section-label flex items-center gap-2">
              <Terminal size={10} style={{ color: 'var(--cyan)' }} />
              EVENT LOG STREAM
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-0.5 min-h-0">
              {(!state.history || state.history.length === 0) ? (
                <div className="event-entry" style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  Awaiting system events...
                </div>
              ) : (
                state.history.slice(-50).map((entry, i) => (
                  <div key={i} className="event-entry animate-fade-in flex items-start">
                    <span className="timestamp">[{formatTime(currentTime)}]</span>
                    <span className="event-text">{getLogText(entry)}</span>
                  </div>
                ))
              )}
              <div ref={historyEndRef} />
            </div>

            <div className="section-label flex items-center gap-2 mt-3">
              <Mic size={10} style={{ color: 'var(--cyan)' }} />
              VOICE TRANSCRIPT
            </div>
            <div className="max-h-28 overflow-y-auto custom-scrollbar flex flex-col gap-0.5">
              {voiceTranscripts.length === 0 ? (
                <div className="event-entry" style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  No transcript yet...
                </div>
              ) : (
                voiceTranscripts.slice(-8).map((entry, i) => (
                  <div key={i} className="event-entry animate-fade-in flex items-start">
                    <span className="timestamp">[{formatTranscriptTs(entry.timestamp)}]</span>
                    <span className="event-text">{entry.event.toUpperCase()}: {entry.text}</span>
                  </div>
                ))
              )}
            </div>

            {/* ── IDLE ENGINE MONITOR ── */}
            <div className="section-label flex items-center gap-2 mt-3">
              <Activity size={10} style={{ color: idleStatus?.action_in_progress ? 'var(--green)' : 'var(--cyan)' }} className={idleStatus?.action_in_progress ? 'animate-pulse' : ''} />
              IDLE ENGINE
              {idleStatus && (
                <span className="ml-auto" style={{ fontFamily: 'var(--font-mono)', fontSize: '8px', color: idleStatus.action_in_progress ? 'var(--green)' : 'var(--text-muted)' }}>
                  {idleStatus.action_in_progress ? '● WORKING' : idleStatus.paused ? '● PAUSED' : '● IDLE'} | #{idleStatus.actions_executed || 0}
                </span>
              )}
            </div>
            <div className="max-h-36 overflow-y-auto custom-scrollbar flex flex-col gap-0.5">
              {idleLogs.length === 0 ? (
                <div className="event-entry" style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  Waiting for idle activity...
                </div>
              ) : (
                idleLogs.slice(-20).map((entry, i) => {
                  const display = getIdleLogDisplay(entry);
                  const isError = entry.type.includes('error') || entry.type.includes('failed');
                  return (
                    <div key={i} className="event-entry animate-fade-in flex items-start gap-1.5">
                      <span className="flex-shrink-0 mt-[2px]">{display.icon}</span>
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontSize: '9px',
                        color: isError ? 'var(--red)' : entry.type === 'action_complete' || entry.type === 'pipeline_end' ? 'var(--green)' : 'var(--text-secondary)',
                      }}>{display.text}</span>
                    </div>
                  );
                })
              )}
            </div>

            {/* ── BUSINESS DASHBOARD TOGGLE ── */}
            <div className="mt-3">
              <button onClick={() => setShowBusiness(!showBusiness)}
                className="w-full flex items-center justify-center gap-2 px-3 py-1.5 rounded-md"
                style={{ background: bizData ? 'rgba(0,200,100,0.06)' : 'rgba(255,255,255,0.03)', border: `1px solid ${bizData ? 'rgba(0,200,100,0.25)' : 'var(--border)'}`, fontFamily: 'var(--font-display)', fontSize: '9px', letterSpacing: '0.15em', color: bizData ? 'var(--green)' : 'var(--text-muted)', cursor: 'pointer' }}
              >
                <Briefcase size={10} />
                {showBusiness ? 'HIDE BUSINESS' : 'BUSINESS DASH'}
                {bizData?.revenue?.total_earned_usd !== undefined && (
                  <span style={{ marginLeft: 'auto', color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>
                    ${bizData.revenue.total_earned_usd.toFixed(0)}
                  </span>
                )}
              </button>
            </div>

            {showBusiness && (
              <div className="flex flex-col gap-1.5 mt-2 p-2 rounded-md" style={{ background: 'rgba(0,200,100,0.03)', border: '1px solid rgba(0,200,100,0.15)' }}>
                {!bizData ? (
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-muted)', fontStyle: 'italic', textAlign: 'center', padding: '8px 0' }}>
                    Business engine offline
                  </div>
                ) : (
                  <>
                    {/* Revenue */}
                    <div style={{ fontFamily: 'var(--font-display)', fontSize: '8px', letterSpacing: '0.12em', color: 'var(--green)', opacity: 0.7, display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <DollarSign size={8} /> REVENUE
                    </div>
                    {[
                      ['EARNED', `$${(bizData.revenue?.total_earned_usd ?? 0).toFixed(2)}`],
                      ['PENDING', `$${(bizData.revenue?.pending_usd ?? 0).toFixed(2)}`],
                      ['OVERDUE INV', String(bizData.revenue?.overdue_invoices ?? 0)],
                    ].map(([k, v]) => (
                      <div key={k} className="flex justify-between" style={{ fontFamily: 'var(--font-mono)', fontSize: '9px' }}>
                        <span style={{ color: 'var(--text-muted)' }}>{k}</span>
                        <span style={{ color: 'var(--text-secondary)' }}>{v}</span>
                      </div>
                    ))}

                    {/* Proposals */}
                    <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', marginTop: '4px', paddingTop: '4px', fontFamily: 'var(--font-display)', fontSize: '8px', letterSpacing: '0.12em', color: 'var(--cyan)', opacity: 0.7, display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <TrendingUp size={8} /> PROPOSALS
                    </div>
                    {[
                      ['TOTAL', String(bizData.proposals?.total_proposals ?? 0)],
                      ['WON', String(bizData.proposals?.won ?? 0)],
                      ['WIN RATE', `${(bizData.proposals?.win_rate_pct ?? 0).toFixed(1)}%`],
                      ['TODAY', `${bizData.proposals?.today_proposals ?? 0} / ${bizData.proposals?.daily_limit ?? 10}`],
                    ].map(([k, v]) => (
                      <div key={k} className="flex justify-between" style={{ fontFamily: 'var(--font-mono)', fontSize: '9px' }}>
                        <span style={{ color: 'var(--text-muted)' }}>{k}</span>
                        <span style={{ color: 'var(--text-secondary)' }}>{v}</span>
                      </div>
                    ))}

                    {/* Projects */}
                    <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', marginTop: '4px', paddingTop: '4px', fontFamily: 'var(--font-display)', fontSize: '8px', letterSpacing: '0.12em', color: 'var(--purple)', opacity: 0.7, display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Briefcase size={8} /> PROJECTS
                    </div>
                    {[
                      ['ACTIVE', String(bizData.projects?.active ?? 0)],
                      ['DELIVERED', String(bizData.projects?.delivered ?? 0)],
                      ['TOTAL', String(bizData.projects?.total_projects ?? 0)],
                    ].map(([k, v]) => (
                      <div key={k} className="flex justify-between" style={{ fontFamily: 'var(--font-mono)', fontSize: '9px' }}>
                        <span style={{ color: 'var(--text-muted)' }}>{k}</span>
                        <span style={{ color: 'var(--text-secondary)' }}>{v}</span>
                      </div>
                    ))}

                    {/* Pipeline */}
                    <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', marginTop: '4px', paddingTop: '4px', fontFamily: 'var(--font-display)', fontSize: '8px', letterSpacing: '0.12em', color: 'var(--amber)', opacity: 0.7, display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <BarChart3 size={8} /> JOB PIPELINE
                    </div>
                    {[
                      ['DISCOVERED', String(bizData.pipeline?.total_jobs_discovered ?? 0)],
                      ['AVG SCORE', `${(bizData.pipeline?.avg_fit_score ?? 0).toFixed(0)}/100`],
                      ['ACTIONS', String(bizData.engine_status?.actions_executed ?? 0)],
                    ].map(([k, v]) => (
                      <div key={k} className="flex justify-between" style={{ fontFamily: 'var(--font-mono)', fontSize: '9px' }}>
                        <span style={{ color: 'var(--text-muted)' }}>{k}</span>
                        <span style={{ color: 'var(--text-secondary)' }}>{v}</span>
                      </div>
                    ))}
                  </>
                )}
              </div>
            )}

            {/* ── SETTINGS TOGGLE ── */}
            <div className="mt-3">
              <button onClick={() => setShowSettings(!showSettings)}
                className="w-full flex items-center justify-center gap-2 px-3 py-1.5 rounded-md"
                style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', fontFamily: 'var(--font-display)', fontSize: '9px', letterSpacing: '0.15em', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <Settings size={10} style={{ color: 'var(--cyan)' }} />
                {showSettings ? 'HIDE SETTINGS' : 'SETTINGS'}
              </button>
            </div>

            {showSettings && settings && (
              <div className="flex flex-col gap-2 mt-2 p-2 rounded-md" style={{ background: 'rgba(0,229,255,0.02)', border: '1px solid var(--border)' }}>
                {[
                  ['BRAIN', `${settings.brain_provider} / ${settings.brain_model}`],
                  ['SAFETY', settings.safety_level],
                  ['EMAIL', settings.email_enabled ? 'ENABLED' : 'DISABLED'],
                  ['VOICE', settings.voice_enabled ? 'ENABLED' : 'DISABLED'],
                ].map(([label, val]) => (
                  <div key={label} className="flex justify-between" style={{ fontFamily: 'var(--font-mono)', fontSize: '9px' }}>
                    <span style={{ color: 'var(--text-muted)' }}>{label}</span>
                    <span style={{ color: 'var(--text-secondary)' }}>{val}</span>
                  </div>
                ))}

                <div style={{ borderTop: '1px solid var(--border)', paddingTop: '6px', marginTop: '4px' }}>
                  <div className="flex justify-between items-center mb-1" style={{ fontFamily: 'var(--font-mono)', fontSize: '9px' }}>
                    <span style={{ color: 'var(--text-muted)' }}>IDLE ENGINE</span>
                    <button onClick={() => saveSettings('idle_enabled', !settings.idle_enabled)}
                      style={{ background: settings.idle_enabled ? 'rgba(0,200,100,0.2)' : 'rgba(255,50,50,0.2)', border: 'none', borderRadius: '4px', padding: '2px 8px', color: settings.idle_enabled ? 'var(--green)' : 'var(--red)', fontFamily: 'var(--font-mono)', fontSize: '8px', cursor: 'pointer' }}
                    >
                      {settings.idle_enabled ? 'ON' : 'OFF'}
                    </button>
                  </div>
                  <div className="flex justify-between items-center mb-1" style={{ fontFamily: 'var(--font-mono)', fontSize: '9px' }}>
                    <span style={{ color: 'var(--text-muted)' }}>MIN COOLDOWN</span>
                    <input type="number" value={settings.idle_min_cooldown} min={30} max={600} style={{ width: '50px', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', borderRadius: '3px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: '9px', textAlign: 'right', padding: '1px 4px' }}
                      onChange={e => saveSettings('idle_min_cooldown', parseInt(e.target.value) || 120)} />
                  </div>
                  <div className="flex justify-between items-center" style={{ fontFamily: 'var(--font-mono)', fontSize: '9px' }}>
                    <span style={{ color: 'var(--text-muted)' }}>MAX COOLDOWN</span>
                    <input type="number" value={settings.idle_max_cooldown} min={60} max={900} style={{ width: '50px', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', borderRadius: '3px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: '9px', textAlign: 'right', padding: '1px 4px' }}
                      onChange={e => saveSettings('idle_max_cooldown', parseInt(e.target.value) || 300)} />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Mobile-only: Compact Event Log (shown below 3D on small screens) ── */}
        <div className="flex-shrink-0 md:hidden glass-panel p-3 opacity-0 animate-fade-in-up stagger-5" style={{ animationFillMode: 'forwards', maxHeight: '120px' }}>
          <div className="section-label flex items-center gap-2">
            <Terminal size={10} style={{ color: 'var(--cyan)' }} />
            EVENT LOG
          </div>
          <div className="overflow-y-auto custom-scrollbar flex flex-col gap-0.5" style={{ maxHeight: '80px' }}>
            {(!state.history || state.history.length === 0) ? (
              <div className="event-entry" style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                Awaiting system events...
              </div>
            ) : (
              state.history.slice(-10).map((entry, i) => (
                <div key={i} className="event-entry animate-fade-in flex items-start">
                  <span className="event-text">{getLogText(entry)}</span>
                </div>
              ))
            )}
            <div ref={!state.history?.length ? undefined : historyEndRef} />
          </div>
        </div>

        {/* ── BOTTOM: Command Bar ── */}
        <div className="flex-shrink-0 opacity-0 animate-fade-in-up stagger-6" style={{ animationFillMode: 'forwards' }}>
          <form onSubmit={sendCommand} className="command-bar flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-4 px-3 sm:px-5 py-2 sm:py-3">
            <div className="flex items-center gap-3 sm:gap-4 flex-1 min-w-0">
              <div className="flex items-center justify-center p-1.5 sm:p-2 rounded flex-shrink-0" style={{ background: 'var(--cyan-dim)' }}>
                <Terminal size={16} style={{ color: 'var(--cyan)' }} />
              </div>

              <input
                type="text"
                id="command-input"
                value={cmdInput}
                onChange={e => setCmdInput(e.target.value)}
                placeholder="ENTER COMMAND //"
                disabled={state.status !== 'online'}
                autoComplete="off"
                spellCheck={false}
                style={{ fontSize: '12px' }}
              />
            </div>

            <button
              type="submit"
              id="execute-btn"
              disabled={!cmdInput.trim() || state.status !== 'online'}
              className="command-btn flex items-center justify-center gap-2 w-full sm:w-auto"
            >
              EXECUTE
              <Zap size={14} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
