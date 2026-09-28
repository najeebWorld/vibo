import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { strings } from '../lib/labels';

/** First-launch terms for user-generated content (App Store 1.2 asks for an explicit agreement). */
export function ConsentScreen({ onAgree }: { onAgree: () => void }) {
  return (
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={styles.body}>
        <Text style={styles.title}>{strings.consentTitle}</Text>
        <Text style={styles.text}>{strings.consentBody}</Text>
      </ScrollView>
      <Pressable style={styles.button} onPress={onAgree} accessibilityRole="button">
        <Text style={styles.buttonText}>{strings.consentAgree}</Text>
      </Pressable>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#000' },
  body: { padding: 24, gap: 16 },
  title: { color: '#fff', fontSize: 26, fontWeight: '800' },
  text: { color: '#d0d0dc', fontSize: 16, lineHeight: 24 },
  button: { margin: 24, backgroundColor: '#fff', paddingVertical: 16, borderRadius: 999, alignItems: 'center' },
  buttonText: { color: '#000', fontSize: 16, fontWeight: '700' },
});
