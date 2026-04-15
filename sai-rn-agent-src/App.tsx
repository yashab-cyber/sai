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
  NativeModules,
} from 'react-native';

const { SaiDeviceControl } = NativeModules;

function App(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const [serverStatus, setServerStatus] = useState('Stopped');
  const [hasAccessibilityMsg, setHasAccessibilityMsg] = useState('Unknown');

  useEffect(() => {
    // Check if the accessibility service is running
    SaiDeviceControl.checkAccessibilityPermission()
      .then((enabled: boolean) => {
        setHasAccessibilityMsg(enabled ? 'Enabled' : 'Disabled');
      });
  }, []);

  const handleStartServer = async () => {
    try {
      const msg = await SaiDeviceControl.startLocalServer(8080);
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
  }
});

export default App;
