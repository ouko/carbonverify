import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Network from 'expo-network';
import { getPendingSurveys, markSurveySynced, getPendingPhotos, getSyncQueue, removeFromSyncQueue } from './database';

const API_BASE_URL = 'https://api.carbonverify.example.com'; // Configure per environment
const AUTH_TOKEN_KEY = 'cv_auth_token';

export async function getAuthToken(): Promise<string | null> {
  return await AsyncStorage.getItem(AUTH_TOKEN_KEY);
}

export async function isOnline(): Promise<boolean> {
  const networkState = await Network.getNetworkStateAsync();
  return networkState.isConnected === true && networkState.isInternetReachable === true;
}

export async function syncPendingData(): Promise<{ surveys: number; photos: number; errors: string[] }> {
  const errors: string[] = [];
  let surveysSynced = 0;
  let photosSynced = 0;

  if (!(await isOnline())) {
    return { surveys: 0, photos: 0, errors: ['No internet connection'] };
  }

  const token = await getAuthToken();
  if (!token) {
    return { surveys: 0, photos: 0, errors: ['Not authenticated'] };
  }

  // Sync surveys
  const pendingSurveys = await getPendingSurveys();
  for (const survey of pendingSurveys) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/survey-responses`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          ...survey,
          responses: JSON.parse(survey.responses),
          photos: JSON.parse(survey.photos || '[]'),
        }),
      });

      if (response.ok) {
        await markSurveySynced(survey.id);
        surveysSynced++;
      } else {
        errors.push(`Survey ${survey.id}: ${response.status}`);
      }
    } catch (err: any) {
      errors.push(`Survey ${survey.id}: ${err.message}`);
    }
  }

  // Sync photos
  const pendingPhotos = await getPendingPhotos();
  for (const photo of pendingPhotos) {
    try {
      const formData = new FormData();
      formData.append('file', {
        uri: photo.local_uri,
        name: `${photo.id}.jpg`,
        type: 'image/jpeg',
      } as any);
      formData.append('gps_latitude', photo.gps_latitude);
      formData.append('gps_longitude', photo.gps_longitude);

      const response = await fetch(`${API_BASE_URL}/api/v1/projects/${photo.project_id}/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (response.ok) {
        photosSynced++;
      } else {
        errors.push(`Photo ${photo.id}: ${response.status}`);
      }
    } catch (err: any) {
      errors.push(`Photo ${photo.id}: ${err.message}`);
    }
  }

  // Process sync queue
  const queue = await getSyncQueue();
  for (const item of queue) {
    try {
      const payload = JSON.parse(item.payload);
      const response = await fetch(`${API_BASE_URL}/api/v1/${item.entity_type}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        await removeFromSyncQueue(item.id);
      }
    } catch (err: any) {
      errors.push(`Queue item ${item.id}: ${err.message}`);
    }
  }

  // Update last sync timestamp
  await AsyncStorage.setItem('cv_last_sync', new Date().toISOString());

  return { surveys: surveysSynced, photos: photosSynced, errors };
}
