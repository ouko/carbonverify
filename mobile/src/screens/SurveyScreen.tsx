import React, { useState, useEffect } from 'react';
import { View, StyleSheet, ScrollView, Alert } from 'react-native';
import { TextInput, Button, Title, Paragraph, ProgressBar, Card, RadioButton } from 'react-native-paper';
import * as Location from 'expo-location';
import { v4 as uuidv4 } from 'uuid';
import { saveSurvey, addToSyncQueue } from '../services/database';
import { isOnline } from '../services/sync';

interface Question {
  id: string;
  text: string;
  type: 'text' | 'number' | 'choice' | 'image';
  options?: string[];
  validation?: { min: number; max: number };
}

const SURVEY_QUESTIONS: Question[] = [
  { id: 'people_cooked', text: 'How many people cooked in this household yesterday?', type: 'number', validation: { min: 1, max: 20 } },
  { id: 'fuel_type', text: 'What fuel did you primarily use?', type: 'choice', options: ['wood', 'charcoal', 'gas', 'electricity', 'other'] },
  { id: 'cooking_hours', text: 'How many hours did you spend cooking yesterday?', type: 'number', validation: { min: 0.5, max: 12 } },
  { id: 'fuel_amount', text: 'Approximately how many kg of fuel did you use?', type: 'number', validation: { min: 0.1, max: 50 } },
  { id: 'meals_cooked', text: 'How many meals did you cook yesterday?', type: 'number', validation: { min: 1, max: 10 } },
  { id: 'village_name', text: 'Village name:', type: 'text' },
];

export function SurveyScreen() {
  const [currentStep, setCurrentStep] = useState(0);
  const [responses, setResponses] = useState<Record<string, any>>({});
  const [currentValue, setCurrentValue] = useState('');
  const [location, setLocation] = useState<Location.LocationObject | null>(null);
  const [surveyId] = useState(() => uuidv4());

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

  const currentQuestion = SURVEY_QUESTIONS[currentStep];
  const progress = (currentStep) / SURVEY_QUESTIONS.length;

  const validateAndNext = () => {
    if (!currentValue.trim()) {
      Alert.alert('Required', 'Please provide an answer');
      return;
    }

    if (currentQuestion.type === 'number') {
      const num = parseFloat(currentValue);
      if (isNaN(num) || (currentQuestion.validation && (num < currentQuestion.validation.min || num > currentQuestion.validation.max))) {
        Alert.alert('Invalid', `Please enter a number between ${currentQuestion.validation?.min} and ${currentQuestion.validation?.max}`);
        return;
      }
    }

    const newResponses = { ...responses, [currentQuestion.id]: currentValue };
    setResponses(newResponses);
    setCurrentValue('');

    if (currentStep < SURVEY_QUESTIONS.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      completeSurvey(newResponses);
    }
  };

  const completeSurvey = async (finalResponses: Record<string, any>) => {
    const survey = {
      id: surveyId,
      project_id: 'demo-project',
      household_id: finalResponses.household_id || `HH-${Date.now()}`,
      responses: finalResponses,
      gps_latitude: location?.coords.latitude,
      gps_longitude: location?.coords.longitude,
      photos: [],
      status: 'pending',
      synced: 0,
    };

    await saveSurvey(survey);
    await addToSyncQueue('survey-responses', surveyId, survey);

    Alert.alert(
      'Survey Complete',
      `Thank you! Survey saved locally. Reference: ${surveyId.slice(0, 8)}`,
      [{ text: 'OK' }]
    );
    setCurrentStep(0);
    setResponses({});
  };

  const renderInput = () => {
    if (currentQuestion.type === 'choice') {
      return (
        <RadioButton.Group onValueChange={setCurrentValue} value={currentValue}>
          {currentQuestion.options?.map((opt) => (
            <RadioButton.Item key={opt} label={opt} value={opt} />
          ))}
        </RadioButton.Group>
      );
    }

    return (
      <TextInput
        label={currentQuestion.text}
        value={currentValue}
        onChangeText={setCurrentValue}
        keyboardType={currentQuestion.type === 'number' ? 'decimal-pad' : 'default'}
        style={styles.input}
      />
    );
  };

  return (
    <ScrollView style={styles.container}>
      <Card style={styles.card}>
        <Card.Content>
          <Title>Household Survey</Title>
          <Paragraph>Question {currentStep + 1} of {SURVEY_QUESTIONS.length}</Paragraph>
          <ProgressBar progress={progress} style={styles.progress} />

          {currentQuestion.type !== 'choice' && (
            <Paragraph style={styles.question}>{currentQuestion.text}</Paragraph>
          )}

          {renderInput()}

          <Button mode="contained" onPress={validateAndNext} style={styles.button}>
            {currentStep < SURVEY_QUESTIONS.length - 1 ? 'Next' : 'Complete'}
          </Button>
        </Card.Content>
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#f5f5f5' },
  card: { marginBottom: 16 },
  progress: { marginVertical: 12, height: 8 },
  question: { fontSize: 16, marginVertical: 12, fontWeight: '500' },
  input: { marginBottom: 12 },
  button: { marginTop: 12 },
});
