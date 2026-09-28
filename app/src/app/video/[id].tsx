import { useLocalSearchParams, useRouter } from 'expo-router';
import React, { useCallback, useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { RetentionChart } from '../../components/RetentionChart';
import { api } from '../../lib/api';
import { ageText, dropText, pct, type RetentionCurve } from '../../lib/creator';

const REFRESH_MS = 30_000;

/** Creator feedback: where people leave this video. Refreshes every 30 s while open. */
export default function VideoRetentionScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [curve, setCurve] = useState<RetentionCurve | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setCurve(await api.retention(Number(id)));
      setError(null);
    } catch {
      setError('Could not load stats.');
    }
  }, [id]);

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(t);
  }, [load]);

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.header}>
        <Text style={styles.title}>Video #{id}</Text>
        <Pressable onPress={() => router.back()} hitSlop={12} accessibilityRole="button" accessibilityLabel="Close">
          <Text style={styles.close}>✕</Text>
        </Pressable>
      </View>
      <ScrollView contentContainerStyle={styles.body}>
        {error && <Text style={styles.muted}>{error}</Text>}
        {curve && (
          <>
            <Text style={styles.muted}>{ageText(curve)} · updates every 30 s</Text>
            <View style={styles.tiles}>
              <Tile label="Views" value={String(curve.views)} />
              <Tile label="Finished" value={pct(curve.completion_rate)} />
              <Tile label="Avg watched" value={pct(curve.avg_watch_ratio)} />
            </View>
            <Text style={styles.insight}>{dropText(curve)}</Text>
            <RetentionChart curve={curve} />
            {curve.views === 0 && <Text style={styles.muted}>No views yet. The curve appears with the first swipe.</Text>}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.tile}>
      <Text style={styles.tileValue}>{value}</Text>
      <Text style={styles.tileLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#000' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 20 },
  title: { color: '#fff', fontSize: 24, fontWeight: '800' },
  close: { color: '#fff', fontSize: 22 },
  body: { paddingHorizontal: 20, paddingBottom: 40 },
  muted: { color: '#9a9ab0', fontSize: 13, marginBottom: 12 },
  tiles: { flexDirection: 'row', gap: 12, marginBottom: 16 },
  tile: { flex: 1, backgroundColor: '#15151f', borderRadius: 12, padding: 14 },
  tileValue: { color: '#fff', fontSize: 22, fontWeight: '800' },
  tileLabel: { color: '#9a9ab0', fontSize: 12, marginTop: 2 },
  insight: { color: '#fff', fontSize: 16, fontWeight: '600' },
});
