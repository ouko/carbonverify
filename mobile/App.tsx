import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { Provider as PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { LoginScreen } from './src/screens/LoginScreen';
import { HomeScreen } from './src/screens/HomeScreen';
import { SurveyScreen } from './src/screens/SurveyScreen';
import { PhotoCaptureScreen } from './src/screens/PhotoCaptureScreen';
import { SyncScreen } from './src/screens/SyncScreen';
import { SupervisorScreen } from './src/screens/SupervisorScreen';

const Stack = createStackNavigator();

export default function App() {
  return (
    <SafeAreaProvider>
      <PaperProvider>
        <NavigationContainer>
          <Stack.Navigator initialRouteName="Login">
            <Stack.Screen name="Login" component={LoginScreen} options={{ headerShown: false }} />
            <Stack.Screen name="Home" component={HomeScreen} options={{ title: 'CarbonVerify Field' }} />
            <Stack.Screen name="Survey" component={SurveyScreen} options={{ title: 'Household Survey' }} />
            <Stack.Screen name="PhotoCapture" component={PhotoCaptureScreen} options={{ title: 'Photo Collection' }} />
            <Stack.Screen name="Sync" component={SyncScreen} options={{ title: 'Sync Status' }} />
            <Stack.Screen name="Supervisor" component={SupervisorScreen} options={{ title: 'Supervisor Dashboard' }} />
          </Stack.Navigator>
        </NavigationContainer>
      </PaperProvider>
    </SafeAreaProvider>
  );
}
