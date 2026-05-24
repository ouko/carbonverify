import React, { useState } from 'react';
import { View, StyleSheet, ScrollView } from 'react-native';
import { Title, Paragraph, Card, DataTable, Button, Badge, TextInput } from 'react-native-paper';

interface EnumeratorStats {
  id: string;
  name: string;
  surveys: number;
  photos: number;
  qualityScore: number;
  rejectionRate: number;
  lastSync: string;
}

const MOCK_ENUMERATORS: EnumeratorStats[] = [
  { id: '1', name: 'John Mwangi', surveys: 45, photos: 120, qualityScore: 96, rejectionRate: 2, lastSync: '2024-05-24 08:30' },
  { id: '2', name: 'Amina Ochieng', surveys: 38, photos: 95, qualityScore: 94, rejectionRate: 4, lastSync: '2024-05-24 09:15' },
  { id: '3', name: 'Peter Njoroge', surveys: 12, photos: 30, qualityScore: 78, rejectionRate: 18, lastSync: '2024-05-23 14:00' },
  { id: '4', name: 'Grace Wanjiku', surveys: 52, photos: 140, qualityScore: 98, rejectionRate: 1, lastSync: '2024-05-24 10:00' },
];

export function SupervisorScreen() {
  const [searchQuery, setSearchQuery] = useState('');

  const filtered = MOCK_ENUMERATORS.filter((e) =>
    e.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const alerts = filtered.filter((e) => e.rejectionRate > 15 || e.qualityScore < 80);

  return (
    <ScrollView style={styles.container}>
      <Title>Supervisor Dashboard</Title>

      {alerts.length > 0 && (
        <Card style={[styles.card, styles.alertCard]}>
          <Card.Content>
            <Title style={styles.alertTitle}>⚠️ Data Quality Alerts</Title>
            {alerts.map((e) => (
              <Paragraph key={e.id} style={styles.alertText}>
                {e.name}: {e.rejectionRate}% rejection rate — investigate
              </Paragraph>
            ))}
          </Card.Content>
        </Card>
      )}

      <Card style={styles.card}>
        <Card.Content>
          <Title>Team Overview</Title>
          <Paragraph>Total enumerators: {filtered.length}</Paragraph>
          <Paragraph>Total surveys today: {filtered.reduce((sum, e) => sum + e.surveys, 0)}</Paragraph>
          <Paragraph>Avg quality score: {(filtered.reduce((sum, e) => sum + e.qualityScore, 0) / filtered.length).toFixed(1)}%</Paragraph>
        </Card.Content>
      </Card>

      <TextInput
        label="Search enumerator"
        value={searchQuery}
        onChangeText={setSearchQuery}
        style={styles.search}
      />

      <Card style={styles.card}>
        <Card.Content>
          <Title>Enumerator Performance</Title>
          <DataTable>
            <DataTable.Header>
              <DataTable.Title>Name</DataTable.Title>
              <DataTable.Title numeric>Surveys</DataTable.Title>
              <DataTable.Title numeric>Quality</DataTable.Title>
              <DataTable.Title numeric>Reject%</DataTable.Title>
            </DataTable.Header>
            {filtered.map((e) => (
              <DataTable.Row key={e.id}>
                <DataTable.Cell>{e.name}</DataTable.Cell>
                <DataTable.Cell numeric>{e.surveys}</DataTable.Cell>
                <DataTable.Cell numeric>
                  <Badge style={e.qualityScore >= 90 ? styles.goodBadge : styles.badBadge}>
                    {e.qualityScore}
                  </Badge>
                </DataTable.Cell>
                <DataTable.Cell numeric>{e.rejectionRate}%</DataTable.Cell>
              </DataTable.Row>
            ))}
          </DataTable>
        </Card.Content>
      </Card>

      <Button mode="outlined" onPress={() => {}} style={styles.button}>
        Export Report
      </Button>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#f5f5f5' },
  card: { marginBottom: 12 },
  alertCard: { backgroundColor: '#fff3e0' },
  alertTitle: { color: '#e65100' },
  alertText: { color: '#bf360c', marginTop: 4 },
  search: { marginBottom: 12 },
  goodBadge: { backgroundColor: '#4caf50' },
  badBadge: { backgroundColor: '#f44336' },
  button: { marginVertical: 12 },
});
