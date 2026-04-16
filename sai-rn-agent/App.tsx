import React, { useState, useEffect } from 'react';
import {
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  useColorScheme,
  View,
  TouchableOpacity,
  Image,
  NativeModules,
  TextInput,
  Animated,
  ActivityIndicator
} from 'react-native';
import { Camera, Mic, Settings, Activity, Power, PowerOff, ShieldCheck, AlignLeft } from 'lucide-react-native';

const { SaiDeviceControl } = NativeModules;

function App(): React.JSX.Element {
  const [activeTab, setActiveTab] = useState('Dashboard');
  const [serverStatus, setServerStatus] = useState('Stopped');
  const [hasAccessibilityMsg, setHasAccessibilityMsg] = useState('Unknown');
  const [visionStatus, setVisionStatus] = useState('Idle');
  const [visionImageBase64, setVisionImageBase64] = useState('');
  const [visionElements, setVisionElements] = useState<any[]>([]);
  const [visionPackage, setVisionPackage] = useState('unknown');

  const [token, setToken] = useState('jarvis_network_key');
  const [whitelist, setWhitelist] = useState('127.0.0.1,::1');
  const [fadeAnim] = useState(new Animated.Value(1));

  useEffect(() => {
    SaiDeviceControl.checkAccessibilityPermission()
      .then((enabled: boolean) => {
        setHasAccessibilityMsg(enabled ? 'Enabled' : 'Disabled');
      });
  }, []);

  const switchTab = (tab: string) => {
    Animated.sequence([
      Animated.timing(fadeAnim, { toValue: 0, duration: 150, useNativeDriver: true }),
      Animated.timing(fadeAnim, { toValue: 1, duration: 150, useNativeDriver: true })
    ]).start();
    setTimeout(() => setActiveTab(tab), 150);
  };

  const handleStartServer = async () => {
    try {
      const msg = await SaiDeviceControl.startLocalServer(8080, token, whitelist);
      setServerStatus(msg);
    } catch (e) {
      setServerStatus('Error starting server');
    }
  };

  const handleStopServer = async () => {
    try {
      const msg = await SaiDeviceControl.stopLocalServer();
      setServerStatus(msg);
    } catch (e) {
      setServerStatus('Error stopping server');
    }
  };

  const handleCaptureVision = async () => {
    setVisionStatus('Capturing...');
    try {
      const res = await fetch('http://127.0.0.1:8080/state/screenshot', {
        headers: { Authorization: `Bearer ${token}` }
      });
      const payload = await res.json();
      if (payload.status === 'success') {
        setVisionImageBase64(payload.image_base64 || '');
        setVisionElements(Array.isArray(payload?.screen_data?.elements) ? payload.screen_data.elements : []);
        setVisionPackage(payload?.screen_data?.package || 'unknown');
        setVisionStatus(`Found ${payload.screen_data.elements?.length || 0} elements`);
      } else {
        setVisionStatus(payload.message || 'Capture failed');
      }
    } catch (err: any) {
      setVisionStatus(err?.message || 'Server error');
    }
  };

  const renderDashboard = () => (
    <View style={styles.tabContent}>
      <Text style={styles.sectionHeader}>System Status</Text>
      
      <View style={styles.glassCard}>
        <View style={styles.statusRow}>
          <Activity color="#00e5ff" size={24} />
          <View style={styles.statusTextContainer}>
            <Text style={styles.statusLabel}>API Server</Text>
            <Text style={[styles.statusValue, { color: serverStatus.includes('running') ? '#00e5ff' : '#e74c3c' }]}>
              {serverStatus}
            </Text>
          </View>
        </View>
        <View style={styles.buttonGroup}>
          <TouchableOpacity style={[styles.btn, styles.bgPrimary]} onPress={handleStartServer}>
            <Power color="#fff" size={18} /><Text style={styles.btnText}>START</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.btn, styles.bgDanger]} onPress={handleStopServer}>
            <PowerOff color="#fff" size={18} /><Text style={styles.btnText}>STOP</Text>
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.glassCard}>
        <View style={styles.statusRow}>
          <ShieldCheck color="#bdc3c7" size={24} />
          <View style={styles.statusTextContainer}>
            <Text style={styles.statusLabel}>Accessibility Module</Text>
            <Text style={[styles.statusValue, { color: hasAccessibilityMsg === 'Enabled' ? '#00e5ff' : '#f39c12' }]}>
              {hasAccessibilityMsg}
            </Text>
          </View>
        </View>
        <TouchableOpacity style={[styles.btn, styles.bgSecondary, { marginTop: 12 }]} onPress={() => SaiDeviceControl.openAccessibilitySettings()}>
          <Text style={styles.btnText}>CONFIGURE PERMISSION</Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderVision = () => {
    const maxBounds = visionElements.reduce((acc, el) => {
      const b = el?.bounds || [0, 0, 0, 0];
      return { w: Math.max(acc.w, Number(b[2]) || 0), h: Math.max(acc.h, Number(b[3]) || 0) };
    }, { w: 1080, h: 1920 });

    return (
      <View style={styles.tabContent}>
        <View style={styles.glassCard}>
          <View style={styles.flexRowBetween}>
            <Text style={styles.statusLabel}>Vision Intelligence</Text>
            <Text style={styles.statusValue}>{visionStatus}</Text>
          </View>
          <TouchableOpacity style={[styles.btn, styles.bgPrimary, { marginTop: 16 }]} onPress={handleCaptureVision}>
            <Camera color="#fff" size={18} /><Text style={styles.btnText}>RUN CAPTURE</Text>
          </TouchableOpacity>
        </View>

        {visionImageBase64 ? (
          <View style={styles.glassCardPadded}>
            <Text style={styles.caption}>Target: {visionPackage}</Text>
            <View style={styles.visionContainer}>
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
          </View>
        ) : null}
      </View>
    );
  };

  const renderVoice = () => (
    <View style={styles.tabContent}>
      <View style={styles.glassCardCentered}>
        <View style={styles.micCircleWrapper}>
          <View style={styles.micCircle}>
            <Mic color="#00e5ff" size={42} />
          </View>
        </View>
        <Text style={styles.statusLabel}>Voice Loop System</Text>
        <Text style={styles.caption}>Waiting for "Hey SAI" wake word...</Text>
      </View>
      <View style={styles.glassCard}>
        <Text style={styles.statusLabel}><AlignLeft size={16} color="#bdc3c7" /> Live Transcription</Text>
        <Text style={[styles.caption, { marginTop: 8 }]}>[System] Voice engine ready.</Text>
      </View>
    </View>
  );

  const renderSettings = () => (
    <View style={styles.tabContent}>
      <View style={styles.glassCard}>
        <Text style={styles.sectionHeader}>Security & Network</Text>
        <Text style={styles.inputLabel}>AUTH TOKEN</Text>
        <TextInput style={styles.input} value={token} onChangeText={setToken} secureTextEntry={true} />
        
        <Text style={styles.inputLabel}>IP WHITELIST</Text>
        <TextInput style={styles.input} value={whitelist} onChangeText={setWhitelist} />
        
        <Text style={styles.inputLabel}>MODEL</Text>
        <TextInput style={styles.input} value={"Vision: local-ocr, Command: gpt-4o"} editable={false} />
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#071420" />
      <View style={styles.header}>
        <Text style={styles.headerTitle}>S.A.I. MATRIX</Text>
        <Text style={styles.headerSubtitle}>COMPANION NODE</Text>
      </View>

      <Animated.ScrollView style={[styles.mainScroll, { opacity: fadeAnim }]} contentContainerStyle={{ paddingBottom: 100 }}>
        {activeTab === 'Dashboard' && renderDashboard()}
        {activeTab === 'Vision' && renderVision()}
        {activeTab === 'Voice' && renderVoice()}
        {activeTab === 'Settings' && renderSettings()}
      </Animated.ScrollView>

      {/* Bottom Navigation */}
      <View style={styles.bottomNav}>
        {[
          { id: 'Dashboard', icon: <Activity color={activeTab === 'Dashboard' ? '#00e5ff' : '#7f8c8d'} size={22} /> },
          { id: 'Vision', icon: <Camera color={activeTab === 'Vision' ? '#00e5ff' : '#7f8c8d'} size={22} /> },
          { id: 'Voice', icon: <Mic color={activeTab === 'Voice' ? '#00e5ff' : '#7f8c8d'} size={22} /> },
          { id: 'Settings', icon: <Settings color={activeTab === 'Settings' ? '#00e5ff' : '#7f8c8d'} size={22} /> },
        ].map(tab => (
          <TouchableOpacity key={tab.id} style={styles.navItem} onPress={() => switchTab(tab.id)}>
            {tab.icon}
            <Text style={[styles.navText, activeTab === tab.id && styles.navTextActive]}>{tab.id}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#071420' },
  header: { paddingTop: 30, paddingBottom: 20, alignItems: 'center', borderBottomWidth: 1, borderColor: '#132c40' },
  headerTitle: { color: '#ffffff', fontSize: 24, fontWeight: '800', letterSpacing: 3 },
  headerSubtitle: { color: '#00e5ff', fontSize: 10, letterSpacing: 2, marginTop: 4 },
  mainScroll: { flex: 1, padding: 16 },
  tabContent: { paddingBottom: 20 },
  sectionHeader: { color: '#bdc3c7', fontSize: 13, fontWeight: '600', letterSpacing: 1.5, marginBottom: 12, textTransform: 'uppercase' },
  glassCard: { backgroundColor: 'rgba(19, 44, 64, 0.6)', borderRadius: 16, padding: 20, marginBottom: 16, borderWidth: 1, borderColor: 'rgba(0, 229, 255, 0.15)' },
  glassCardCentered: { backgroundColor: 'rgba(19, 44, 64, 0.6)', borderRadius: 16, padding: 30, marginBottom: 16, alignItems: 'center', borderWidth: 1, borderColor: 'rgba(0, 229, 255, 0.15)' },
  glassCardPadded: { backgroundColor: 'rgba(19, 44, 64, 0.6)', borderRadius: 16, padding: 10, marginBottom: 16, borderWidth: 1, borderColor: 'rgba(0, 229, 255, 0.15)' },
  statusRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  statusTextContainer: { marginLeft: 16, flex: 1 },
  statusLabel: { color: '#bdc3c7', fontSize: 14, fontWeight: '500' },
  statusValue: { color: '#ffffff', fontSize: 16, fontWeight: '700', marginTop: 2 },
  caption: { color: '#7f8c8d', fontSize: 12, marginTop: 4 },
  buttonGroup: { flexDirection: 'row', gap: 12, marginTop: 8 },
  btn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 12, borderRadius: 8, gap: 8 },
  btnText: { color: '#fff', fontSize: 12, fontWeight: '700', letterSpacing: 1 },
  bgPrimary: { backgroundColor: 'rgba(0, 229, 255, 0.2)', borderWidth: 1, borderColor: '#00e5ff' },
  bgSecondary: { backgroundColor: 'rgba(127, 140, 141, 0.2)', borderWidth: 1, borderColor: '#7f8c8d' },
  bgDanger: { backgroundColor: 'rgba(231, 76, 60, 0.2)', borderWidth: 1, borderColor: '#e74c3c' },
  flexRowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  inputLabel: { color: '#00e5ff', fontSize: 11, fontWeight: '700', letterSpacing: 1, marginTop: 12, marginBottom: 6 },
  input: { backgroundColor: 'rgba(255,255,255,0.05)', color: '#fff', borderRadius: 8, paddingHorizontal: 16, paddingVertical: 12, fontSize: 14, borderBottomWidth: 1, borderColor: '#00e5ff' },
  bottomNav: { flexDirection: 'row', backgroundColor: '#071420', paddingBottom: 24, paddingTop: 12, borderTopWidth: 1, borderColor: '#132c40', position: 'absolute', bottom: 0, left: 0, right: 0 },
  navItem: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  navText: { color: '#7f8c8d', fontSize: 10, marginTop: 6, fontWeight: '600' },
  navTextActive: { color: '#00e5ff' },
  micCircleWrapper: { width: 120, height: 120, borderRadius: 60, backgroundColor: 'rgba(0, 229, 255, 0.05)', alignItems: 'center', justifyContent: 'center', marginBottom: 20 },
  micCircle: { width: 80, height: 80, borderRadius: 40, backgroundColor: 'rgba(0, 229, 255, 0.1)', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#00e5ff' },
  visionContainer: { width: '100%', height: 350, backgroundColor: '#000', borderRadius: 8, overflow: 'hidden', marginTop: 8 },
  visionImg: { width: '100%', height: '100%' },
  overlayLayer: { ...StyleSheet.absoluteFillObject },
  overlayBox: { position: 'absolute', borderWidth: 1, borderColor: '#00e5ff', backgroundColor: 'rgba(0,229,255,0.15)' }
});

export default App;
