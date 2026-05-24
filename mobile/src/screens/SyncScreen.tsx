import React, { useState, useEffect } from 'react';
import { View, StyleSheet, ScrollView } from 'react-native';
import { Title, Paragraph, Button, Card, List, Badge } from 'react-native-paper';
import { getPendingSurveys, getPendingPhotos } from '../services/database';
import { isOnline, syncPendingData } from '../services/sync';

export function SyncScreen() {
  const [surveys, setSurveys] = useState<any[]>([]);
  const [photos, setPhotos] = useState<any[]>([]);
  const [online, setOnline] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    loadData();
    checkOnline();
  }, []);

  const loadData = async () => {
    const s = await getPendingSurveys();
    const p = await getPendingPhotos();
    setSurveys(s);
    setPhotos(p);
  };

  const checkOnline = async () => {
    setOnline(await isOnline());
  };

  const handleSync = async () => {
    setSyncing(true);
    const res = await syncPendingData();
    setResult(res);
    setSyncing(false);
    await loadData();
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Title>Sync Status</Title>
        <Badge style={online ? styles.online : styles.offline}>
          {online ? 'Online' : 'Offline'}
        </Badge>
      </View>

      <Card style={styles.card}>
        <Card.Content>
          <Paragraph>Pending Surveys: {surveys.length}</Paragraph>
          <Paragraph>Pending Photos: {photos.length}</Paragraph>
        </Card.Content>
      </Card>

      <Button
        mode="contained"
        onPress={handleSync}
        loading={syncing}
        disabled={!online || syncing}
        style={styles.button}
      >
        {syncing ? 'Syncing...' : 'Sync Now'}
      </Button>

      {result && (
        <Card style={styles.card}>
          <Card.Content>
            <Title>Sync Result</Title>
            <Paragraph>Surveys synced: {result.surveys}</Paragraph>
            <Paragraph>Photos synced: {result.photos}</Paragraph>
            {result.errors.length > 0 && (
              <>
                <Paragraph style={styles.errorTitle}>Errors:</Paragraph>
                {result.errors.map((e: string, i: number) => (
                  <Paragraph key={i} style={styles.error}>• {e}</Paragraph>
                ))}
              </>
            )}
          </Card.Content>
        </Card>
      )}

      <List.Section title="Pending Surveys">
        {surveys.map((s) => (
          <List.Item
            key={s.id}
            title={`Survey ${s.id.slice(0, 8)}`}
            description={`Household: ${s.household_id || 'N/A'} | ${new Date(s.created_at).toLocaleDateString()}`}
            left={(props) => <List.Icon {...props} icon="clipboard-text" />}
          />
        ))}
      </List.Section>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#f5f5f5' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  card: { marginBottom: 12 },
  button: { marginVertical: 12 },
  online: { backgroundColor: '#4caf50' },
  offline: { backgroundColor: '#f44336' },
  errorTitle: { marginTop: 8, fontWeight: 'bold', color: '#f44336' },
  error: { color: '#f44336' },
});
