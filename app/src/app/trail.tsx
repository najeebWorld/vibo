import { useRouter } from 'expo-router';
import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api } from '../lib/api';
import { useApp } from '../lib/app-context';
import type { TrailItem } from '../lib/events';
import { strings, trailLabel } from '../lib/labels';

/** Everything your sessions left behind (the anti-emptiness screen). */
export default function TrailScreen() {
  const { userId, flush } = useApp();
  const router = useRouter();
  const [items, setItems] = useState<TrailItem[] | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      await flush(); // make sure the last swipes are counted before we read
      setItems((await api.trail(userId)).items);
    } catch {
      setItems((prev) => prev ?? []);
    } finally {
      setRefreshing(false);
    }
  }, [userId, flush]);

  useEffect(() => void load(), [load]);

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.header}>
        <Text style={styles.title}>{strings.trail}</Text>
        <View style={styles.headerRight}>
          <Pressable onPress={() => router.push('/creator')} hitSlop={12} accessibilityRole="button">
            <Text style={styles.link}>{strings.myVideos} →</Text>
          </Pressable>
          <Pressable onPress={() => router.back()} hitSlop={12} accessibilityRole="button" accessibilityLabel="Close">
            <Text style={styles.close}>✕</Text>
          </Pressable>
        </View>
      </View>
      <FlatList
        data={items ?? []}
        keyExtractor={(t) => String(t.id)}
        onRefresh={load}
        refreshing={refreshing}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <Text style={styles.kind}>{kindIcon(item.kind)}</Text>
            <View style={styles.rowBody}>
              <Text style={styles.label}>{trailLabel(item)}</Text>
              <Text style={styles.when}>{new Date(item.ts * 1000).toLocaleString()}</Text>
            </View>
          </View>
        )}
        ListEmptyComponent={items === null ? null : <Text style={styles.empty}>{strings.trailEmpty}</Text>}
      />
    </SafeAreaView>
  );
}

function kindIcon(kind: string): string {
  return { saved: '♥', series_progress: '▶', topic_unlocked: '✦', streak: '⚡' }[kind] ?? '•';
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#000' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 20 },
  title: { color: '#fff', fontSize: 26, fontWeight: '800' },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 20 },
  link: { color: '#c8c8dc', fontSize: 15, fontWeight: '600' },
  close: { color: '#fff', fontSize: 22 },
  list: { paddingHorizontal: 20, paddingBottom: 40, gap: 14 },
  row: { flexDirection: 'row', gap: 14, alignItems: 'center' },
  kind: { color: '#fff', fontSize: 22, width: 28, textAlign: 'center' },
  rowBody: { flex: 1 },
  label: { color: '#fff', fontSize: 16 },
  when: { color: '#7a7a90', fontSize: 12, marginTop: 2 },
  empty: { color: '#9a9ab0', fontSize: 16, textAlign: 'center', marginTop: 40 },
});
