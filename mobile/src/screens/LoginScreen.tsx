import React, { useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { TextInput, Button, Text, Card } from 'react-native-paper';
import AsyncStorage from '@react-native-async-storage/async-storage';

export function LoginScreen({ navigation }: any) {
  const [phone, setPhone] = useState('');
  const [pin, setPin] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setLoading(true);
    // In production, authenticate against backend
    await AsyncStorage.setItem('cv_auth_token', 'demo_token');
    await AsyncStorage.setItem('cv_enumerator_phone', phone);
    setLoading(false);
    navigation.replace('Home');
  };

  return (
    <View style={styles.container}>
      <Card style={styles.card}>
        <Card.Title title="CarbonVerify Field" subtitle="Enumerator Login" />
        <Card.Content>
          <TextInput
            label="Phone Number"
            value={phone}
            onChangeText={setPhone}
            keyboardType="phone-pad"
            style={styles.input}
          />
          <TextInput
            label="PIN"
            value={pin}
            onChangeText={setPin}
            secureTextEntry
            keyboardType="number-pad"
            style={styles.input}
          />
          <Button mode="contained" onPress={handleLogin} loading={loading} style={styles.button}>
            Login
          </Button>
          <Text style={styles.hint}>Enter your registered phone and PIN</Text>
        </Card.Content>
      </Card>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 20, backgroundColor: '#f5f5f5' },
  card: { padding: 10 },
  input: { marginBottom: 12 },
  button: { marginTop: 10 },
  hint: { marginTop: 12, textAlign: 'center', color: '#666' },
});
