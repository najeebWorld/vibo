import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import React, { useEffect, useState } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { ConsentScreen } from '../components/ConsentScreen';
import { AppProvider } from '../lib/app-context';
import { getInstallId, hasConsented, setConsented } from '../lib/identity';

void SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [userId, setUserId] = useState<string | null>(null);
  const [consented, setConsentedState] = useState<boolean | null>(null);

  useEffect(() => {
    (async () => {
      const [id, ok] = await Promise.all([getInstallId(), hasConsented()]);
      setUserId(id);
      setConsentedState(ok);
      await SplashScreen.hideAsync();
    })();
  }, []);

  if (userId === null || consented === null) return null;

  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      {consented ? (
        <AppProvider userId={userId}>
          <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#000' } }}>
            <Stack.Screen name="index" />
            <Stack.Screen name="trail" options={{ presentation: 'modal' }} />
            <Stack.Screen name="creator" options={{ presentation: 'modal' }} />
            <Stack.Screen name="video/[id]" options={{ presentation: 'modal' }} />
          </Stack>
        </AppProvider>
      ) : (
        <ConsentScreen
          onAgree={() => {
            void setConsented();
            setConsentedState(true);
          }}
        />
      )}
    </SafeAreaProvider>
  );
}
