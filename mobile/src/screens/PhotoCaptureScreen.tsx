import React, { useState, useRef, useEffect } from 'react';
import { View, StyleSheet, Image, Alert, ScrollView } from 'react-native';
import { Button, Title, Paragraph, Card, ProgressBar } from 'react-native-paper';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as Location from 'expo-location';
import { v4 as uuidv4 } from 'uuid';
import { savePhoto } from '../services/database';

const PHOTO_PROMPTS = [
  'Please take a photo of the stove with a pot on it',
  'Please take a photo of the fuel storage area',
  'Please take a photo of a household member using the stove',
];

export function PhotoCaptureScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [currentPhoto, setCurrentPhoto] = useState(0);
  const [photos, setPhotos] = useState<Array<{ uri: string; gps: any }>>([]);
  const [location, setLocation] = useState<Location.LocationObject | null>(null);
  const cameraRef = useRef<CameraView>(null);

  useEffect(() => {
    requestLocation();
  }, []);

  const requestLocation = async () => {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status === 'granted') {
      const loc = await Location.getCurrentPositionAsync({});
      setLocation(loc);
    }
  };

  const takePicture = async () => {
    if (!cameraRef.current) return;

    try {
      const photo = await cameraRef.current.takePictureAsync({ exif: true });
      if (photo) {
        const newPhotos = [...photos, { uri: photo.uri, gps: location }];
        setPhotos(newPhotos);

        await savePhoto({
          id: uuidv4(),
          survey_id: null,
          local_uri: photo.uri,
          gps_latitude: location?.coords.latitude,
          gps_longitude: location?.coords.longitude,
          timestamp: new Date().toISOString(),
          synced: 0,
        });

        if (currentPhoto < PHOTO_PROMPTS.length - 1) {
          setCurrentPhoto(currentPhoto + 1);
        } else {
          Alert.alert('Complete', 'All photos captured successfully!');
        }
      }
    } catch (err: any) {
      Alert.alert('Error', err.message);
    }
  };

  if (!permission?.granted) {
    return (
      <View style={styles.container}>
        <Title>Camera Permission Required</Title>
        <Button onPress={requestPermission}>Grant Permission</Button>
      </View>
    );
  }

  const progress = (currentPhoto) / PHOTO_PROMPTS.length;

  return (
    <ScrollView style={styles.container}>
      <Card style={styles.card}>
        <Card.Content>
          <Title>Photo Collection</Title>
          <Paragraph>{PHOTO_PROMPTS[currentPhoto]}</Paragraph>
          <ProgressBar progress={progress} style={styles.progress} />
          <Paragraph>Photo {currentPhoto + 1} of {PHOTO_PROMPTS.length}</Paragraph>
        </Card.Content>
      </Card>

      <View style={styles.cameraContainer}>
        <CameraView style={styles.camera} ref={cameraRef}>
          <View style={styles.buttonContainer}>
            <Button mode="contained" onPress={takePicture} style={styles.captureButton}>
              Capture
            </Button>
          </View>
        </CameraView>
      </View>

      {photos.length > 0 && (
        <Card style={styles.card}>
          <Card.Content>
            <Title>Captured Photos</Title>
            <ScrollView horizontal>
              {photos.map((p, i) => (
                <Image key={i} source={{ uri: p.uri }} style={styles.thumbnail} />
              ))}
            </ScrollView>
          </Card.Content>
        </Card>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  card: { margin: 16, marginBottom: 8 },
  progress: { marginVertical: 8, height: 8 },
  cameraContainer: { height: 400, margin: 16 },
  camera: { flex: 1 },
  buttonContainer: { flex: 1, justifyContent: 'flex-end', padding: 20 },
  captureButton: { marginBottom: 20 },
  thumbnail: { width: 80, height: 80, marginRight: 8, borderRadius: 4 },
});
