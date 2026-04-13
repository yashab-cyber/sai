import React, { useEffect, useState, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Torus, Sphere, Icosahedron, Stars, MeshDistortMaterial } from '@react-three/drei';
import { io } from 'socket.io-client';
import { Terminal, Activity, Cpu, Network, Command, ShieldAlert, Zap, Target } from 'lucide-react';
import * as THREE from 'three';

const socket = io(window.location.host);

interface SaiState {
  thought: string;
  action: string;
  status: string;
  neural_load: string;
  cpu_load: string;
  latency: string;
  history: string[];
}

// J.A.R.V.I.S / F.R.I.D.A.Y 3D Core Component
const HolographicCore = ({ active }: { active: boolean }) => {
  const groupRef = useRef<THREE.Group>(null);
  const ring1Ref = useRef<THREE.Mesh>(null);
  const ring2Ref = useRef<THREE.Mesh>(null);
  const ring3Ref = useRef<THREE.Mesh>(null);
  
  const colorPrimary = "#00d8ff";
  const colorSecondary = "#0055ff";
  const colorActive = "#ffffff";

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const speed = active ? 2.5 : 0.5;
    
    if (groupRef.current) {
      groupRef.current.rotation.y = t * 0.1 * speed;
      groupRef.current.position.y = Math.sin(t * 1.5) * 0.1;
    }
    if (ring1Ref.current) {
      ring1Ref.current.rotation.x = t * 0.5 * speed;
      ring1Ref.current.rotation.y = t * 0.2 * speed;
    }
    if (ring2Ref.current) {
      ring2Ref.current.rotation.y = t * 0.4 * speed;
      ring2Ref.current.rotation.z = t * 0.3 * speed;
    }
    if (ring3Ref.current) {
      ring3Ref.current.rotation.x = t * 0.1 * speed;
      ring3Ref.current.rotation.z = t * 0.6 * speed;
    }
  });

  return (
    <group ref={groupRef}>
      {/* Inner Energy Core */}
      <Sphere args={[1.2, 64, 64]}>
        <MeshDistortMaterial
          color={active ? colorPrimary : "#051824"}
          emissive={active ? colorPrimary : "#051824"}
          emissiveIntensity={active ? 1.5 : 0.5}
          distort={active ? 0.5 : 0.1}
          speed={active ? 5 : 1}
          roughness={0.1}
          wireframe={false}
        />
      </Sphere>

      {/* Wireframe Shell */}
      <Icosahedron args={[1.7, 2]}>
        <meshBasicMaterial color={colorPrimary} wireframe transparent opacity={0.15} />
      </Icosahedron>

      {/* Holographic Rings */}
      <Torus ref={ring1Ref} args={[2.5, 0.015, 16, 100]} rotation={[Math.PI / 2, 0, 0]}>
        <meshBasicMaterial color={active ? colorActive : colorPrimary} transparent opacity={0.6} />
      </Torus>
      <Torus ref={ring2Ref} args={[2.8, 0.01, 16, 100]} rotation={[0, Math.PI / 3, 0]}>
        <meshBasicMaterial color={colorSecondary} transparent opacity={0.4} />
      </Torus>
      <Torus ref={ring3Ref} args={[3.2, 0.02, 16, 100, Math.PI * 1.7]} rotation={[0, 0, Math.PI / 4]}>
        <meshBasicMaterial color={colorPrimary} transparent opacity={0.8} />
      </Torus>
      
      {/* Target reticle elements on the Z axis */}
      <Torus args={[0.5, 0.02, 16, 32]} position={[0, 0, 3.5]}>
        <meshBasicMaterial color={colorPrimary} transparent opacity={0.3} />
      </Torus>
      <Torus args={[0.5, 0.02, 16, 32]} position={[0, 0, -3.5]}>
        <meshBasicMaterial color={colorPrimary} transparent opacity={0.3} />
      </Torus>
    </group>
  );
};

export default function App() {
  const [state, setState] = useState<SaiState>({
    thought: "AWAITING DIRECTIVE...",
    action: "SYSTEM_IDLE",
    status: "offline",
    neural_load: "0%",
    cpu_load: "0%",
    latency: "0ms",
    history: []
  });
  
  const [cmdInput, setCmdInput] = useState("");
  const historyEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    socket.on('connect', () => setState(s => ({ ...s, status: 'online' })));
    socket.on('state_update', (newState: SaiState) => setState(newState));
    socket.on('disconnect', () => setState(s => ({ ...s, status: 'offline' })));

    return () => {
      socket.off('connect');
      socket.off('state_update');
      socket.off('disconnect');
    };
  }, []);

  useEffect(() => {
    if (historyEndRef.current) {
      historyEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [state.history]);

  const sendCommand = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cmdInput.trim()) return;
    
    try {
      await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmdInput })
      });
      setCmdInput("");
    } catch (err) {
      console.error("Command Error", err);
    }
  };

  const isWorking = state.status === "online" && state.action !== "SYSTEM_IDLE" && state.action !== "IDLE";
  const glowColor = state.status === 'online' ? 'shadow-[0_0_15px_rgba(0,216,255,0.4)]' : 'shadow-[0_0_15px_rgba(239,68,68,0.4)]';
  const borderColor = state.status === 'online' ? 'border-[#00d8ff]' : 'border-red-500';

  return (
    <div className="relative w-screen h-screen bg-[#020608] text-[#00d8ff] font-mono overflow-hidden select-none">
      
      {/* 3D Core Canvas */}
      <div className="absolute inset-0 z-0">
        <Canvas camera={{ position: [0, 0, 7], fov: 60 }}>
          <ambientLight intensity={isWorking ? 1.5 : 0.5} />
          <directionalLight position={[10, 10, 5]} intensity={2} color="#00ffff" />
          <directionalLight position={[-10, -10, -5]} intensity={1} color="#0055ff" />
          <Stars radius={100} depth={50} count={3000} factor={3} saturation={1} fade speed={isWorking ? 2 : 0.2} />
          <HolographicCore active={isWorking} />
          <OrbitControls 
            enableZoom={false} 
            enablePan={false}
            autoRotate={true} 
            autoRotateSpeed={0.5} 
            maxPolarAngle={Math.PI/1.5}
            minPolarAngle={Math.PI/3}
          />
        </Canvas>
      </div>

      {/* Cyberpunk Vignette / Scanlines */}
      <div className="absolute inset-0 z-0 pointer-events-none bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-transparent via-[#020608]/50 to-[#020608] opacity-90"></div>
      <div className="absolute inset-0 z-0 pointer-events-none opacity-10 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0IiBoZWlnaHQ9IjQiPgo8cmVjdCB3aWR0aD0iNCIgaGVpZ2h0PSI0IiBmaWxsPSIjZmZmIiBmaWxsLW9wYWNpdHk9IjAuMSIvPgo8L3N2Zz4=')] mix-blend-overlay"></div>

      {/* HUD Corners (J.A.R.V.I.S Style Brackets) */}
      <div className={`absolute top-4 left-4 w-16 h-16 border-t-2 border-l-2 ${borderColor} opacity-60 z-10 pointer-events-none`}></div>
      <div className={`absolute top-4 right-4 w-16 h-16 border-t-2 border-r-2 ${borderColor} opacity-60 z-10 pointer-events-none`}></div>
      <div className={`absolute bottom-4 left-4 w-16 h-16 border-b-2 border-l-2 ${borderColor} opacity-60 z-10 pointer-events-none`}></div>
      <div className={`absolute bottom-4 right-4 w-16 h-16 border-b-2 border-r-2 ${borderColor} opacity-60 z-10 pointer-events-none`}></div>

      {/* Main UI Layout */}
      <div className="absolute inset-0 z-10 p-4 md:p-6 flex flex-col justify-between pointer-events-none overflow-hidden">
        
        {/* Top Header Row */}
        <div className="flex flex-col md:flex-row justify-between items-start gap-4 md:gap-0 pointer-events-auto">
          
          {/* Left: System Identification */}
          <div className={`backdrop-blur-md bg-black/40 border border-[#00d8ff]/30 p-4 w-full md:w-80 rounded-sm clip-beveled-tl ${glowColor}`}>
            <div className="flex items-center justify-between border-b border-[#00d8ff]/30 pb-2 mb-2">
              <h1 className="text-xl font-bold tracking-[0.2em] flex items-center gap-2">
                <Target className="text-[#00d8ff] w-5 h-5 animate-[spin_4s_linear_infinite]" />
                S.A.I. CORE
              </h1>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full animate-pulse ${state.status === 'online' ? 'bg-cyan-400 shadow-[0_0_8px_#00ffff]' : 'bg-red-500'}`}></span>
                <span className="text-xs uppercase tracking-widest text-cyan-200">{state.status}</span>
              </div>
            </div>
            <div className="space-y-1">
              <p className="text-[10px] tracking-widest text-[#00d8ff]/60">MODEL: ADVANCED NEURAL PROTOCOL</p>
              <p className="text-[10px] tracking-widest text-[#00d8ff]/60">UPTIME: CONTINUOUS</p>
              <p className="text-[10px] tracking-widest text-[#00d8ff]/60">SECURE LINK: ESTABLISHED</p>
            </div>
          </div>
          
          {/* Right: Telemetry Hub */}
          <div className={`backdrop-blur-md bg-black/40 border border-[#00d8ff]/30 p-4 w-full md:w-80 rounded-sm clip-beveled-tr ${glowColor}`}>
            <h2 className="text-[10px] uppercase tracking-widest text-[#00d8ff]/60 mb-3 border-b border-[#00d8ff]/30 pb-1">System Diagnostics</h2>
            
            <div className="space-y-4">
              <div className="flex justify-between items-center group">
                <div className="flex items-center gap-2"><Activity className="w-4 h-4 text-purple-400"/> <span className="text-xs tracking-wider">NEURAL LOAD</span></div>
                <div className="text-sm font-bold text-white shadow-[#00d8ff] drop-shadow-md bg-[#00d8ff]/10 px-2 py-0.5 rounded border border-[#00d8ff]/20">{state.neural_load}</div>
              </div>
              
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2"><Cpu className="w-4 h-4 text-blue-400"/> <span className="text-xs tracking-wider">CPU THREADS</span></div>
                <div className="text-sm font-bold text-white shadow-[#00d8ff] bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">{state.cpu_load}</div>
              </div>

              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2"><Network className="w-4 h-4 text-green-400"/> <span className="text-xs tracking-wider">SYS LATENCY</span></div>
                <div className="text-sm font-bold text-white shadow-[#00d8ff] bg-green-500/10 px-2 py-0.5 rounded border border-green-500/20">{state.latency}</div>
              </div>
            </div>
          </div>

        </div>

        {/* Center: Thought Tracker (The "Mind" of SAI) */}
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-[90%] md:w-[70%] max-w-4xl flex flex-col items-center justify-center pointer-events-none z-0">
          <div className={`relative backdrop-blur-sm bg-cyan-950/20 border-l-2 border-r-2 border-[#00d8ff]/50 px-4 md:px-12 py-4 md:py-6 w-full text-center shadow-[0_0_30px_rgba(0,216,255,0.1)] transition-all duration-300 ${isWorking ? 'scale-[1.02] md:scale-105' : 'scale-100'}`}>
            
            {/* Top and bottom decorative bracket lines */}
            <div className="absolute top-0 left-1/4 right-1/4 h-[1px] bg-gradient-to-r from-transparent via-[#00d8ff] to-transparent"></div>
            <div className="absolute bottom-0 left-1/4 right-1/4 h-[1px] bg-gradient-to-r from-transparent via-[#00d8ff] to-transparent"></div>

            <ShieldAlert className={`w-8 h-8 mx-auto mb-4 opacity-50 ${isWorking ? 'animate-bounce text-white' : 'text-[#00d8ff]'}`} />
            
            <p className="text-sm tracking-[0.3em] text-[#00d8ff]/70 mb-2 uppercase">Current Cognitive Vector</p>
            <h2 className="text-2xl sm:text-3xl font-light text-white drop-shadow-[0_0_10px_rgba(0,255,255,0.8)] leading-tight italic mb-6">
              "{state.thought}"
            </h2>
            
            <div className="inline-block bg-[#00d8ff]/10 border border-[#00d8ff]/40 rounded-full px-4 py-1 uppercase tracking-widest text-[#00d8ff] text-xs font-bold font-sans">
              <span className="opacity-50 mr-2">ACTION:</span> {state.action}
            </div>
          </div>
        </div>

        {/* Bottom Area: Console and Terminal */}
        <div className="flex flex-col md:flex-row gap-4 md:gap-6 items-stretch md:items-end justify-between pointer-events-auto z-10 w-full mb-0">
          
          {/* Left: Terminal History */}
          <div className="w-full md:w-1/3 min-h-32 h-40 md:h-56 bg-black/60 border border-[#00d8ff]/30 p-4 rounded-sm backdrop-blur-md font-mono text-[10px] leading-tight flex flex-col shadow-[0_0_15px_rgba(0,150,255,0.15)] clip-beveled-bl">
            <div className="text-[#00d8ff] mb-2 pb-1 border-b border-[#00d8ff]/30 uppercase tracking-widest flex items-center gap-2">
              <Terminal className="w-3 h-3" /> Event Log Stream
            </div>
            
            <div className="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-1 pr-2">
              {state.history.length === 0 ? (
                <div className="text-[#00d8ff]/40 italic">Awaiting system events...</div>
              ) : (
                state.history.map((log, i) => (
                  <div key={i} className="animate-fade-in text-gray-300">
                    <span className="text-[#00d8ff] opacity-60 mr-2">[{new Date().toISOString().substring(11,19)}]</span> {log}
                  </div>
                ))
              )}
              <div ref={historyEndRef} />
            </div>
          </div>

          {/* Right: Command Input */}
          <div className="w-full md:w-2/3 h-auto md:h-16 bg-black/60 border border-[#00d8ff]/50 backdrop-blur-md rounded-sm p-4 relative clip-beveled-br">
            {/* Corner decorations */}
            <div className="absolute top-0 left-0 w-2 h-2 border-t border-l border-[#00d8ff]"></div>
            <div className="absolute bottom-0 right-0 w-2 h-2 border-b border-r border-[#00d8ff]"></div>

            <form onSubmit={sendCommand} className="h-full flex flex-col md:flex-row gap-4 items-center justify-between">
              <div className="hidden md:flex bg-[#00d8ff]/20 p-2 rounded text-[#00d8ff] items-center justify-center shrink-0">
                <Command className="w-5 h-5" />
              </div>
              
              <input
                type="text"
                value={cmdInput}
                onChange={e => setCmdInput(e.target.value)}
                placeholder="INPUT OVERRIDE DIRECTIVE //"
                className="w-full relative flex-1 bg-[#00d8ff]/5 md:bg-transparent border md:border-none border-[#00d8ff]/30 p-3 md:p-0 outline-none text-base md:text-[1.1rem] text-white placeholder-[#00d8ff]/30 font-bold tracking-widest uppercase rounded md:rounded-none shrink"
                disabled={state.status !== 'online'}
                autoComplete="off"
                spellCheck="false"
              />
              
              <button 
                type="submit" 
                disabled={!cmdInput.trim() || state.status !== 'online'}
                className="w-full md:w-48 h-12 md:h-12 px-4 md:px-6 bg-[#00d8ff]/10 hover:bg-[#00d8ff]/30 text-[#00d8ff] hover:text-white border border-[#00d8ff]/40 hover:border-[#00d8ff] transition-all disabled:opacity-30 disabled:cursor-not-allowed group flex items-center justify-center gap-3 tracking-[0.2em] text-sm shrink-0 md:-my-1"
              >
                EXECUTE
                <Zap className="w-4 h-4 group-hover:animate-pulse group-hover:drop-shadow-[0_0_5px_#fff]" />
              </button>
            </form>
          </div>

        </div>
      </div>
    </div>
  );
}
