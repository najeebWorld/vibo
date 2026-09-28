import { useRouter } from 'expo-router';
import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api } from '../lib/api';
import { useApp } from '../lib/app-context';
import { pct, type MyVideo } from '../lib/creator';

/** The creator's videos with live view counts; tap one for its retention curve. */
export default function CreatorScreen() {
  const { userId } = useApp();
  const router = useRouter();
  const [items, setItems] = useState<MyVideo[] | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      setItems((await api.myVideos(userId)).items);
    } catch {
      setItems((prev) => prev ?? []);
    } finally {
      setRefreshing(false);
    }
  }, [userId]);

  useEffect(() => void load(), [load]);

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.header}>
        <Text style={styles.title}>My videos</Text>
        <Pressable onPress={() => router.back()} hitSlop={12} accessibilityRole="button" accessibilityLabel="Close">
          <Text style={styles.close}>✕</Text>
        </Pressable>
      </View>
      <FlatList
        data={items ?? []}
        keyExtractor={(v) => String(v.video_id)}
        onRefresh={load}
        refreshing={refreshing}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <Pressable style={styles.row} onPress={() => router.push(`/video/${item.video_id}`)} accessibilityRole="button">
            <View style={styles.rowBody}>
              <Text style={styles.label}>Video #{item.video_id}</Text>
              <Text style={styles.when}>{new Date(item.created_at * 1000).toLocaleString()}</Text>
            </View>
            <Text style={styles.stat}>
              {item.views} views · {pct(item.completion_rate)} finished
            </Text>
          </Pressable>
        )}
        ListEmptyComponent={
          items === null ? null : (
            <Text style={styles.empty}>
              No uploads yet. Uploading from the phone arrives in phase 2; the retention curve is ready for it.
            </Text>
          )
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#000' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 20 },
  title: { color: '#fff', fontSize: 26, fontWeight: '800' },
  close: { color: '#fff', fontSize: 22 },
  list: { paddingHorizontal: 20, paddingBottom: 40, gap: 12 },
  row: { backgroundColor: '#15151f', borderRadius: 12, padding: 14, gap: 6 },
  rowBody: { flexDirection: 'row', justifyContent: 'space-between' },
  label: { color: '#fff', fontSize: 16, fontWeight: '600' },
  when: { color: '#7a7a90', fontSize: 12 },
  stat: { color: '#c8c8dc', fontSize: 14 },
  empty: { color: '#9a9ab0', fontSize: 15, textAlign: 'center', marginTop: 40, lineHeight: 22 },
});
