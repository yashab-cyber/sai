import React, { useState, useEffect } from 'react';
import {
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  useColorScheme,
  View,
  Button,
  Image,
  NativeModules,
} from 'react-native';

const { SaiDeviceControl } = NativeModules;

function App(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const [serverStatus, setServerStatus] = useState('Stopped');
  const [hasAccessibilityMsg, setHasAccessibilityMsg] = useState('Unknown');
  const [visionStatus, setVisionStatus] = useState('Idle');
  const [visionImageBase64, setVisionImageBase64] = useState('');
  const [visionElements, setVisionElements] = useState<any[]>([]);
  const [visionPackage, setVisionPackage] = useState('unknown');
  const [visionActivity, setVisionActivity] = useState('unknown');

  useEffect(() => {
    // Check if the accessibility service is running
    SaiDeviceControl.checkAccessibilityPermission()
      .then((enabled: boolean) => {
        setHasAccessibilityMsg(enabled ? 'Enabled' : 'Disabled');
      });
  }, []);

  const handleStartServer = async () => {
    try {
      const msg = await SaiDeviceControl.startLocalServer(
        8080,
        'jarvis_network_key',
        '127.0.0.1,::1'
      );
      setServerStatus(msg);
    } catch (e) {
      console.error(e);
      setServerStatus('Error starting server');
    }
  };

  const handleStopServer = async () => {
    try {
      const msg = await SaiDeviceControl.stopLocalServer();
      setServerStatus(msg);
    } catch (e) {
      console.error(e);
      setServerStatus('Error stopping server');
    }
  };

  const handleOpenAccessibility = () => {
    SaiDeviceControl.openAccessibilitySettings();
  };

  const handleCaptureVision = async () => {
    setVisionStatus('Capturing...');
    try {
      const res = await fetch('http://127.0.0.1:8080/state/screenshot', {
        method: 'GET',
        headers: {
          Authorization: 'Bearer jarvis_network_key',
        },
      });
      const payload = await res.json();
      if (payload.status === 'success') {
        setVisionImageBase64(payload.image_base64 || '');
        const elements = payload?.screen_data?.elements || [];
        setVisionElements(Array.isArray(elements) ? elements : []);
        setVisionPackage(payload?.screen_data?.package || 'unknown');
        setVisionActivity(payload?.screen_data?.activity || 'unknown');
        setVisionStatus(`Detected ${Array.isArray(elements) ? elements.length : 0} elements`);
      } else {
        setVisionStatus(payload.message || 'Capture failed');
      }
    } catch (err: any) {
      setVisionStatus(err?.message || 'Capture error');
    }
  };

  const maxBounds = visionElements.reduce(
    (acc, el) => {
      const b = el?.bounds || [0, 0, 0, 0];
      return {
        w: Math.max(acc.w, Number(b[2]) || 0),
        h: Math.max(acc.h, Number(b[3]) || 0),
      };
    },
    { w: 1080, h: 1920 }
  );

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle={isDarkMode ? 'light-content' : 'dark-content'} />
      <ScrollView contentInsetAdjustmentBehavior="automatic">
        <View style={styles.header}>
          <Text style={styles.title}>SAI Companion Agent</Text>
          <Text style={styles.subtitle}>React Native Controller</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>1. Accessibility Setup</Text>
          <Text style={styles.status}>Status: {hasAccessibilityMsg}</Text>
          <Text style={styles.description}>
            The Accessibility Service is required for reading screen text, clicking coordinates, and auto-typing without Root.
          </Text>
          <Button title="Enable Accessibility Service" onPress={handleOpenAccessibility} />
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>2. Local API Server</Text>
          <Text style={styles.status}>Server: {serverStatus}</Text>
          <Text style={styles.description}>
            Starts a local NanoHTTPD server on port 8080. The Python backend of SAI communicates directly with this address to trigger Android actions.
          </Text>
          <View style={styles.buttonRow}>
            <Button title="Start API" onPress={handleStartServer} color="#1abc9c" />
            <View style={{ width: 10 }} />
            <Button title="Stop API" onPress={handleStopServer} color="#e74c3c" />
          </View>
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>3. Advanced Control</Text>
          <Text style={styles.description}>
            Shizuku grants higher-level system privileges allowing adb-level operations continuously without root.
          </Text>
          <Button title="Pair Shizuku (Coming Soon)" onPress={() => {}} disabled={true} />
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>4. Vision Debug</Text>
          <Text style={styles.status}>{visionStatus}</Text>
          <Text style={styles.description}>Package: {visionPackage} | Activity: {visionActivity}</Text>
          <Button title="Capture Vision Frame" onPress={handleCaptureVision} color="#3498db" />

          {visionImageBase64 ? (
            <View style={styles.visionContainer}>
              <Image
                style={styles.visionImage}
                source={{ uri: `data:image/jpeg;base64,${visionImageBase64}` }}
                resizeMode="contain"
              />
              <View style={styles.overlayLayer} pointerEvents="none">
                {visionElements.slice(0, 25).map((el, idx) => {
                  const b = el?.bounds || [0, 0, 0, 0];
                  const left = (Number(b[0]) / (maxBounds.w || 1)) * 100;
                  const top = (Number(b[1]) / (maxBounds.h || 1)) * 100;
                  const width = ((Number(b[2]) - Number(b[0])) / (maxBounds.w || 1)) * 100;
                  const height = ((Number(b[3]) - Number(b[1])) / (maxBounds.h || 1)) * 100;
                  return (
                    <View
                      key={`${idx}-${el?.text || 'el'}`}
                      style={[
                        styles.overlayBox,
                        {
                          left: `${left}%`,
                          top: `${top}%`,
                          width: `${Math.max(width, 3)}%`,
                          height: `${Math.max(height, 2)}%`,
                        },
                      ]}
                    />
                  );
                })}
              </View>
            </View>
          ) : null}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#ecf0f1',
  },
  header: {
    padding: 24,
    alignItems: 'center',
    backgroundColor: '#34495e',
  },
  title: {
    fontSize: 26,
    fontWeight: 'bold',
    color: '#ffffff',
  },
  subtitle: {
    fontSize: 16,
    marginTop: 4,
    color: '#bdc3c7',
  },
  card: {
    backgroundColor: '#ffffff',
    margin: 16,
    padding: 20,
    borderRadius: 8,
    elevation: 3, 
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#2c3e50',
    marginBottom: 8,
  },
  description: {
    fontSize: 14,
    color: '#7f8c8d',
    marginBottom: 16,
    lineHeight: 20,
  },
  status: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#2980b9',
    marginBottom: 12,
  },
  buttonRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  visionContainer: {
    marginTop: 16,
    width: '100%',
    height: 260,
    borderRadius: 8,
    overflow: 'hidden',
    backgroundColor: '#1f1f1f',
    position: 'relative',
  },
  visionImage: {
    width: '100%',
    height: '100%',
  },
  overlayLayer: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: 0,
    bottom: 0,
  },
  overlayBox: {
    position: 'absolute',
    borderWidth: 1,
    borderColor: '#00e5ff',
    backgroundColor: 'rgba(0,229,255,0.08)',
  },
});

export default App;
