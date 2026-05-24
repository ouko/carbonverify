import React, { useEffect, useState } from 'react';
import { View, StyleSheet, ScrollView } from 'react-native';
import { Card, Title, Paragraph, Button, Badge, Divider } from 'react-native-paper';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getPendingSurveys, getPendingPhotos } from '../services/database';
import { isOnline, syncPendingData } from '../services/sync';

export function HomeScreen({ navigation }: any) {
  const [pendingSurveys, setPendingSurveys] = useState(0);
  const [pendingPhotos, setPendingPhotos] = useState(0);
  const [online, setOnline] = useState(false);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    loadStats();
    checkOnline();
    loadLastSync();
  }, []);

  const loadStats = async () => {
    const surveys = await getPendingSurveys();
    const photos = await getPendingPhotos();
    setPendingSurveys(surveys.length);
    setPendingPhotos(photos.length);
  };

  const checkOnline = async () => {
    setOnline(await isOnline());
  };

  const loadLastSync = async () => {
    const ts = await AsyncStorage.getItem('cv_last_sync');
    setLastSync(ts);
  };

  const handleSync = async () => {
    setSyncing(true);
    const result = await syncPendingData();
    setSyncing(false);
    await loadStats();
    await loadLastSync();
    // Show alert with result
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Title>Field Data Collection</Title>
        <Badge style={online ? styles.badgeOnline : styles.badgeOffline}>
          {online ? 'Online' : 'Offline'}
        </Badge>
      </View>

      <Card style={styles.card} onPress={() => navigation.navigate('Survey')}>
        <Card.Content>
          <Title>📝 Household Survey</Title>
          <Paragraph>Complete surveys for households in your assignment</Paragraph>
        </Card.Content>
      </Card>

      <Card style={styles.card} onPress={() => navigation.navigate('PhotoCapture')}>
        <Card.Content>
          <Title>📸 Photo Collection</Title>
          <Paragraph>Capture GPS-tagged photos of stoves and fuel</Paragraph>
        </Card.Content>
      </Card>

      <Card style={styles.card}>
        <Card.Content>
          <Title>☁️ Sync Status</Title>
          <Paragraph>Pending surveys: {pendingSurveys}</Paragraph>
          <Paragraph>Pending photos: {pendingPhotos}</Paragraph>
          <Paragraph>Last sync: {lastSync ? new Date(lastSync).toLocaleString() : 'Never'}</Paragraph>
          <Button mode="outlined" onPress={handleSync} loading={syncing} style={{ marginTop: 10 }}>
            Sync Now
          </Button>
        </Card.Content>
      </Card>

      <Divider style={styles.divider} />

      <Button mode="contained" onPress={() => navigation.navigate('Supervisor')} style={styles.button}>
        Supervisor Dashboard
      </Button>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#f5f5f5' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  card: { marginBottom: 12 },
  badgeOnline: { backgroundColor: '#4caf50' },
  badgeOffline: { backgroundColor: '#f44336' },
  divider: { marginVertical: 16 },
  button: { marginBottom: 20 },
});
