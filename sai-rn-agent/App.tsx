import React, { useState, useEffect, useRef } from 'react';
import {
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  Image,
  NativeModules,
  TextInput,
  Animated,
  Easing,
  Dimensions,
} from 'react-native';

const { SaiDeviceControl } = NativeModules;
const { width: SCREEN_W } = Dimensions.get('window');

// ── Animated pulse ring for status indicators ──
const PulseRing = ({ color, active }: { color: string; active: boolean }) => {
  const scale = useRef(new Animated.Value(1)).current;
  const opacity = useRef(new Animated.Value(0.6)).current;

  useEffect(() => {
    if (!active) { scale.setValue(1); opacity.setValue(0); return; }
    const loop = Animated.loop(
      Animated.parallel([
        Animated.timing(scale, { toValue: 2.4, duration: 1400, easing: Easing.out(Easing.ease), useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0, duration: 1400, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [active]);

  return (
    <Animated.View style={[styles.pulseRing, { borderColor: color, transform: [{ scale }], opacity }]} />
  );
};

// ── Status Badge ──
const StatusBadge = ({ label, value, color }: { label: string; value: string; color: string }) => (
  <View style={styles.badgeContainer}>
    <View style={styles.badgeRow}>
      <View style={[styles.badgeDot, { backgroundColor: color }]} />
      <Text style={styles.badgeLabel}>{label}</Text>
    </View>
    <Text style={[styles.badgeValue, { color }]}>{value}</Text>
  </View>
);

// ── Metric Card ──
const MetricCard = ({ icon, label, value }: { icon: string; label: string; value: string }) => (
  <View style={styles.metricCard}>
    <Text style={styles.metricIcon}>{icon}</Text>
    <Text style={styles.metricValue}>{value}</Text>
    <Text style={styles.metricLabel}>{label}</Text>
  </View>
);

function App(): React.JSX.Element {
  const [activeTab, setActiveTab] = useState('Control');
  const [serverStatus, setServerStatus] = useState<'stopped' | 'running' | 'error'>('stopped');
  const [hasAccessibility, setHasAccessibility] = useState(false);
  const [commandLog, setCommandLog] = useState<string[]>([]);
  const [visionStatus, setVisionStatus] = useState('Idle');
  const [visionImageBase64, setVisionImageBase64] = useState('');
  const [visionElements, setVisionElements] = useState<any[]>([]);
  const [visionPackage, setVisionPackage] = useState('—');

  const [token, setToken] = useState('jarvis_network_key');
  const [whitelist, setWhitelist] = useState('');
  const [port, setPort] = useState('8080');

  const [fadeAnim] = useState(new Animated.Value(1));
  const slideAnim = useRef(new Animated.Value(0)).current;
  const headerGlow = useRef(new Animated.Value(0)).current;

  // Header glow animation
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(headerGlow, { toValue: 1, duration: 3000, easing: Easing.inOut(Easing.ease), useNativeDriver: false }),
        Animated.timing(headerGlow, { toValue: 0, duration: 3000, easing: Easing.inOut(Easing.ease), useNativeDriver: false }),
      ])
    ).start();
  }, []);

  useEffect(() => {
    SaiDeviceControl.checkAccessibilityPermission()
      .then((enabled: boolean) => setHasAccessibility(enabled));
  }, []);

  const addLog = (msg: string) => {
    const ts = new Date().toLocaleTimeString('en-US', { hour12: false });
    setCommandLog(prev => [`[${ts}] ${msg}`, ...prev].slice(0, 50));
  };

  const switchTab = (tab: string) => {
    Animated.sequence([
      Animated.timing(fadeAnim, { toValue: 0, duration: 120, useNativeDriver: true }),
      Animated.timing(fadeAnim, { toValue: 1, duration: 120, useNativeDriver: true })
    ]).start();
    setTimeout(() => setActiveTab(tab), 120);
  };

  const handleStartServer = async () => {
    try {
      const msg = await SaiDeviceControl.startLocalServer(parseInt(port), token, whitelist);
      setServerStatus('running');
      addLog(`API server started on port ${port}`);
    } catch (e: any) {
      setServerStatus('error');
      addLog(`Server error: ${e.message}`);
    }
  };

  const handleStopServer = async () => {
    try {
      await SaiDeviceControl.stopLocalServer();
      setServerStatus('stopped');
      addLog('API server stopped');
    } catch (e: any) {
      addLog(`Stop error: ${e.message}`);
    }
  };

  const handleCaptureVision = async () => {
    setVisionStatus('Capturing...');
    addLog('Vision capture initiated');
    try {
      const res = await fetch(`http://127.0.0.1:${port}/state/screenshot`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const payload = await res.json();
      if (payload.status === 'success') {
        setVisionImageBase64(payload.image_base64 || '');
        setVisionElements(Array.isArray(payload?.screen_data?.elements) ? payload.screen_data.elements : []);
        setVisionPackage(payload?.screen_data?.package || '—');
        const count = payload.screen_data.elements?.length || 0;
        setVisionStatus(`${count} elements detected`);
        addLog(`Vision: ${count} UI elements found in ${visionPackage}`);
      } else {
        setVisionStatus(payload.message || 'Capture failed');
        addLog(`Vision failed: ${payload.message}`);
      }
    } catch (err: any) {
      setVisionStatus(err?.message || 'Server error');
      addLog(`Vision error: ${err?.message}`);
    }
  };

  const statusColor = serverStatus === 'running' ? '#00e5ff' : serverStatus === 'error' ? '#ff3d71' : '#576574';
  const statusText = serverStatus === 'running' ? 'ONLINE' : serverStatus === 'error' ? 'ERROR' : 'OFFLINE';

  const glowColor = headerGlow.interpolate({
    inputRange: [0, 1],
    outputRange: ['rgba(0, 229, 255, 0.0)', 'rgba(0, 229, 255, 0.12)'],
  });

  // ── CONTROL TAB ──
  const renderControl = () => (
    <View style={styles.tabContent}>
      {/* Main Status Orb */}
      <View style={styles.orbContainer}>
        <PulseRing color={statusColor} active={serverStatus === 'running'} />
        <View style={[styles.orb, { borderColor: statusColor, shadowColor: statusColor }]}>
          <Text style={styles.orbIcon}>{serverStatus === 'running' ? '⚡' : '○'}</Text>
        </View>
        <Text style={[styles.orbLabel, { color: statusColor }]}>{statusText}</Text>
        <Text style={styles.orbSub}>API Server · Port {port}</Text>
      </View>

      {/* Action Buttons */}
      <View style={styles.actionRow}>
        <TouchableOpacity
          style={[styles.actionBtn, serverStatus === 'running' && styles.actionBtnDisabled]}
          onPress={handleStartServer}
          disabled={serverStatus === 'running'}
        >
          <Text style={styles.actionBtnIcon}>▶</Text>
          <Text style={styles.actionBtnText}>START</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.actionBtn, styles.actionBtnDanger, serverStatus !== 'running' && styles.actionBtnDisabled]}
          onPress={handleStopServer}
          disabled={serverStatus !== 'running'}
        >
          <Text style={styles.actionBtnIcon}>■</Text>
          <Text style={styles.actionBtnText}>STOP</Text>
        </TouchableOpacity>
      </View>

      {/* Status Grid */}
      <View style={styles.metricsRow}>
        <MetricCard icon="🛡️" label="Accessibility" value={hasAccessibility ? 'ON' : 'OFF'} />
        <MetricCard icon="📡" label="Server" value={serverStatus === 'running' ? 'Active' : '—'} />
        <MetricCard icon="👁️" label="Vision" value={visionStatus === 'Idle' ? '—' : '✓'} />
      </View>

      {/* Accessibility Card */}
      {!hasAccessibility && (
        <TouchableOpacity style={styles.warningCard} onPress={() => SaiDeviceControl.openAccessibilitySettings()}>
          <Text style={styles.warningIcon}>⚠️</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.warningTitle}>Accessibility Required</Text>
            <Text style={styles.warningDesc}>Tap to enable SAI Accessibility Service for screen reading, gestures, and screenshots.</Text>
          </View>
          <Text style={styles.chevron}>›</Text>
        </TouchableOpacity>
      )}

      {/* Command Log */}
      <View style={styles.glassCard}>
        <Text style={styles.sectionLabel}>ACTIVITY LOG</Text>
        {commandLog.length === 0 ? (
          <Text style={styles.logEmpty}>No activity yet. Start the server to begin.</Text>
        ) : (
          commandLog.slice(0, 8).map((entry, idx) => (
            <Text key={idx} style={[styles.logEntry, idx === 0 && styles.logEntryLatest]}>{entry}</Text>
          ))
        )}
      </View>
    </View>
  );

  // ── VISION TAB ──
  const renderVision = () => {
    const maxBounds = visionElements.reduce((acc, el) => {
      const b = el?.bounds || [0, 0, 0, 0];
      return { w: Math.max(acc.w, Number(b[2]) || 0), h: Math.max(acc.h, Number(b[3]) || 0) };
    }, { w: 1080, h: 1920 });

    return (
      <View style={styles.tabContent}>
        <View style={styles.glassCard}>
          <View style={styles.rowBetween}>
            <View>
              <Text style={styles.sectionLabel}>VISION INTELLIGENCE</Text>
              <Text style={styles.sectionSub}>{visionPackage}</Text>
            </View>
            <View style={[styles.statusChip, { backgroundColor: visionStatus.includes('element') ? 'rgba(0,229,255,0.15)' : 'rgba(255,255,255,0.05)' }]}>
              <Text style={[styles.statusChipText, { color: visionStatus.includes('element') ? '#00e5ff' : '#576574' }]}>{visionStatus}</Text>
            </View>
          </View>

          <TouchableOpacity style={styles.captureBtn} onPress={handleCaptureVision}>
            <Text style={styles.captureBtnIcon}>📸</Text>
            <Text style={styles.captureBtnText}>CAPTURE SCREEN</Text>
          </TouchableOpacity>
        </View>

        {visionImageBase64 ? (
          <View style={styles.glassCard}>
            <View style={styles.visionFrame}>
              <Image source={{ uri: `data:image/jpeg;base64,${visionImageBase64}` }} style={styles.visionImg} resizeMode="contain" />
              <View style={styles.overlayLayer} pointerEvents="none">
                {visionElements.slice(0, 30).map((el, idx) => {
                  const b = el?.bounds || [0, 0, 0, 0];
                  return (
                    <View key={idx} style={[styles.overlayBox, {
                      left: `${(Number(b[0]) / maxBounds.w) * 100}%`,
                      top: `${(Number(b[1]) / maxBounds.h) * 100}%`,
                      width: `${Math.max(((Number(b[2]) - Number(b[0])) / maxBounds.w) * 100, 2)}%`,
                      height: `${Math.max(((Number(b[3]) - Number(b[1])) / maxBounds.h) * 100, 2)}%`,
                    }]} />
                  );
                })}
              </View>
            </View>
            <Text style={styles.visionCount}>{visionElements.length} elements detected</Text>
          </View>
        ) : (
          <View style={[styles.glassCard, styles.emptyVision]}>
            <Text style={styles.emptyIcon}>🔍</Text>
            <Text style={styles.emptyText}>No capture yet</Text>
            <Text style={styles.emptySub}>Tap "Capture Screen" to analyze UI elements</Text>
          </View>
        )}
      </View>
    );
  };

  // ── SETTINGS TAB ──
  const renderSettings = () => (
    <View style={styles.tabContent}>
      <View style={styles.glassCard}>
        <Text style={styles.sectionLabel}>NETWORK</Text>

        <Text style={styles.inputLabel}>PORT</Text>
        <TextInput style={styles.input} value={port} onChangeText={setPort} keyboardType="number-pad" placeholderTextColor="#576574" />

        <Text style={styles.inputLabel}>AUTH TOKEN</Text>
        <TextInput style={styles.input} value={token} onChangeText={setToken} secureTextEntry placeholderTextColor="#576574" />

        <Text style={styles.inputLabel}>IP WHITELIST</Text>
        <TextInput style={styles.input} value={whitelist} onChangeText={setWhitelist} placeholder="Empty = allow all LAN" placeholderTextColor="#3d4f5f" />
        <Text style={styles.inputHint}>Leave empty to allow connections from any device on your network.</Text>
      </View>

      <View style={styles.glassCard}>
        <Text style={styles.sectionLabel}>SYSTEM</Text>

        <TouchableOpacity style={styles.settingsRow} onPress={() => SaiDeviceControl.openAccessibilitySettings()}>
          <Text style={styles.settingsIcon}>🛡️</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.settingsTitle}>Accessibility Service</Text>
            <Text style={styles.settingsSub}>{hasAccessibility ? 'Enabled' : 'Disabled'}</Text>
          </View>
          <Text style={styles.chevron}>›</Text>
        </TouchableOpacity>

        <View style={styles.divider} />

        <View style={styles.settingsRow}>
          <Text style={styles.settingsIcon}>🤖</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.settingsTitle}>Model Pipeline</Text>
            <Text style={styles.settingsSub}>Vision: local-ocr · Command: gpt-4o</Text>
          </View>
        </View>

        <View style={styles.divider} />

        <View style={styles.settingsRow}>
          <Text style={styles.settingsIcon}>📱</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.settingsTitle}>App Version</Text>
            <Text style={styles.settingsSub}>S.A.I. Companion v2.0.0</Text>
          </View>
        </View>
      </View>
    </View>
  );

  const tabs = [
    { id: 'Control', icon: '⚡', label: 'Control' },
    { id: 'Vision', icon: '👁️', label: 'Vision' },
    { id: 'Settings', icon: '⚙️', label: 'Settings' },
  ];

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#060e18" />

      {/* Header */}
      <Animated.View style={[styles.header, { backgroundColor: glowColor }]}>
        <View style={styles.headerInner}>
          <View style={styles.headerLeft}>
            <View style={[styles.headerDot, { backgroundColor: statusColor }]} />
            <View>
              <Text style={styles.headerTitle}>S.A.I.</Text>
              <Text style={styles.headerSub}>COMPANION NODE</Text>
            </View>
          </View>
          <View style={[styles.connChip, { borderColor: statusColor }]}>
            <Text style={[styles.connText, { color: statusColor }]}>{statusText}</Text>
          </View>
        </View>
      </Animated.View>

      {/* Content */}
      <Animated.ScrollView
        style={[styles.scroll, { opacity: fadeAnim }]}
        contentContainerStyle={{ paddingBottom: 100 }}
        showsVerticalScrollIndicator={false}
      >
        {activeTab === 'Control' && renderControl()}
        {activeTab === 'Vision' && renderVision()}
        {activeTab === 'Settings' && renderSettings()}
      </Animated.ScrollView>

      {/* Bottom Nav */}
      <View style={styles.bottomNav}>
        {tabs.map(tab => (
          <TouchableOpacity
            key={tab.id}
            style={[styles.navItem, activeTab === tab.id && styles.navItemActive]}
            onPress={() => switchTab(tab.id)}
          >
            <Text style={styles.navIcon}>{tab.icon}</Text>
            <Text style={[styles.navLabel, activeTab === tab.id && styles.navLabelActive]}>{tab.label}</Text>
            {activeTab === tab.id && <View style={styles.navIndicator} />}
          </TouchableOpacity>
        ))}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#060e18' },

  // Header
  header: { paddingTop: 16, paddingBottom: 16, paddingHorizontal: 20, borderBottomWidth: 1, borderColor: 'rgba(0,229,255,0.08)' },
  headerInner: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  headerDot: { width: 10, height: 10, borderRadius: 5 },
  headerTitle: { color: '#fff', fontSize: 22, fontWeight: '800', letterSpacing: 4 },
  headerSub: { color: '#3d6b7f', fontSize: 9, letterSpacing: 3, marginTop: 1 },
  connChip: { borderWidth: 1, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 5 },
  connText: { fontSize: 10, fontWeight: '700', letterSpacing: 2 },

  scroll: { flex: 1, paddingHorizontal: 16 },
  tabContent: { paddingTop: 20, paddingBottom: 20 },

  // Status Orb
  orbContainer: { alignItems: 'center', paddingVertical: 30 },
  orb: { width: 90, height: 90, borderRadius: 45, borderWidth: 2, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(0,229,255,0.04)', shadowOffset: { width: 0, height: 0 }, shadowOpacity: 0.5, shadowRadius: 20, elevation: 10 },
  orbIcon: { fontSize: 32 },
  orbLabel: { fontSize: 16, fontWeight: '800', letterSpacing: 4, marginTop: 16 },
  orbSub: { color: '#3d6b7f', fontSize: 11, marginTop: 4, letterSpacing: 1 },
  pulseRing: { position: 'absolute', width: 90, height: 90, borderRadius: 45, borderWidth: 2 },

  // Action Buttons
  actionRow: { flexDirection: 'row', gap: 12, marginBottom: 24 },
  actionBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, paddingVertical: 16, borderRadius: 14, backgroundColor: 'rgba(0,229,255,0.08)', borderWidth: 1, borderColor: 'rgba(0,229,255,0.25)' },
  actionBtnDanger: { backgroundColor: 'rgba(255,61,113,0.08)', borderColor: 'rgba(255,61,113,0.25)' },
  actionBtnDisabled: { opacity: 0.35 },
  actionBtnIcon: { fontSize: 14, color: '#00e5ff' },
  actionBtnText: { color: '#fff', fontSize: 13, fontWeight: '700', letterSpacing: 2 },

  // Metrics
  metricsRow: { flexDirection: 'row', gap: 10, marginBottom: 20 },
  metricCard: { flex: 1, backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: 14, padding: 16, alignItems: 'center', borderWidth: 1, borderColor: 'rgba(255,255,255,0.04)' },
  metricIcon: { fontSize: 22, marginBottom: 8 },
  metricValue: { color: '#fff', fontSize: 14, fontWeight: '700' },
  metricLabel: { color: '#3d6b7f', fontSize: 10, marginTop: 4, letterSpacing: 1 },

  // Warning Card
  warningCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(255,170,0,0.06)', borderRadius: 14, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: 'rgba(255,170,0,0.15)', gap: 14 },
  warningIcon: { fontSize: 24 },
  warningTitle: { color: '#ffaa00', fontSize: 14, fontWeight: '700' },
  warningDesc: { color: '#7a6a3d', fontSize: 11, marginTop: 3, lineHeight: 16 },

  // Glass Card
  glassCard: { backgroundColor: 'rgba(255,255,255,0.025)', borderRadius: 16, padding: 20, marginBottom: 16, borderWidth: 1, borderColor: 'rgba(255,255,255,0.04)' },
  sectionLabel: { color: '#3d6b7f', fontSize: 11, fontWeight: '700', letterSpacing: 2.5, marginBottom: 14 },
  sectionSub: { color: '#576574', fontSize: 11, marginTop: 2 },

  // Badges
  badgeContainer: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 8 },
  badgeRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  badgeDot: { width: 8, height: 8, borderRadius: 4 },
  badgeLabel: { color: '#8899a6', fontSize: 13 },
  badgeValue: { fontSize: 13, fontWeight: '700' },

  // Log
  logEmpty: { color: '#2a3f4f', fontSize: 12, fontStyle: 'italic' },
  logEntry: { color: '#4a6a7f', fontSize: 11, fontFamily: 'monospace', paddingVertical: 3, borderBottomWidth: 1, borderColor: 'rgba(255,255,255,0.02)' },
  logEntryLatest: { color: '#00e5ff' },

  // Row helpers
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },

  // Status Chip
  statusChip: { borderRadius: 20, paddingHorizontal: 12, paddingVertical: 5 },
  statusChipText: { fontSize: 10, fontWeight: '700', letterSpacing: 1 },

  // Vision Capture
  captureBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, marginTop: 18, paddingVertical: 14, borderRadius: 12, backgroundColor: 'rgba(0,229,255,0.08)', borderWidth: 1, borderColor: 'rgba(0,229,255,0.2)' },
  captureBtnIcon: { fontSize: 18 },
  captureBtnText: { color: '#00e5ff', fontSize: 12, fontWeight: '700', letterSpacing: 2 },

  visionFrame: { width: '100%', height: 380, backgroundColor: '#000', borderRadius: 12, overflow: 'hidden', marginBottom: 10 },
  visionImg: { width: '100%', height: '100%' },
  overlayLayer: { ...StyleSheet.absoluteFillObject },
  overlayBox: { position: 'absolute', borderWidth: 1.5, borderColor: 'rgba(0,229,255,0.7)', backgroundColor: 'rgba(0,229,255,0.08)', borderRadius: 3 },
  visionCount: { color: '#3d6b7f', fontSize: 11, textAlign: 'center', letterSpacing: 1 },

  emptyVision: { alignItems: 'center', paddingVertical: 50 },
  emptyIcon: { fontSize: 40, marginBottom: 16 },
  emptyText: { color: '#576574', fontSize: 16, fontWeight: '600' },
  emptySub: { color: '#2a3f4f', fontSize: 12, marginTop: 6 },

  // Settings
  inputLabel: { color: '#00e5ff', fontSize: 10, fontWeight: '700', letterSpacing: 2, marginTop: 16, marginBottom: 6 },
  input: { backgroundColor: 'rgba(255,255,255,0.04)', color: '#fff', borderRadius: 10, paddingHorizontal: 16, paddingVertical: 13, fontSize: 14, borderWidth: 1, borderColor: 'rgba(255,255,255,0.06)' },
  inputHint: { color: '#2a3f4f', fontSize: 10, marginTop: 6, lineHeight: 15 },

  settingsRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 14, gap: 14 },
  settingsIcon: { fontSize: 22 },
  settingsTitle: { color: '#c8d6df', fontSize: 14, fontWeight: '600' },
  settingsSub: { color: '#576574', fontSize: 11, marginTop: 2 },
  divider: { height: 1, backgroundColor: 'rgba(255,255,255,0.04)' },
  chevron: { color: '#3d6b7f', fontSize: 22, fontWeight: '300' },

  // Bottom Nav
  bottomNav: { flexDirection: 'row', backgroundColor: '#060e18', paddingBottom: 28, paddingTop: 10, borderTopWidth: 1, borderColor: 'rgba(0,229,255,0.06)', position: 'absolute', bottom: 0, left: 0, right: 0 },
  navItem: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 6, position: 'relative' },
  navItemActive: {},
  navIcon: { fontSize: 20, marginBottom: 4 },
  navLabel: { color: '#2a3f4f', fontSize: 9, fontWeight: '700', letterSpacing: 1.5 },
  navLabelActive: { color: '#00e5ff' },
  navIndicator: { position: 'absolute', bottom: -2, width: 20, height: 2, borderRadius: 1, backgroundColor: '#00e5ff' },
});

export default App;
