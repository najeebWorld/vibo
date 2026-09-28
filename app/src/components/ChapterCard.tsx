import React, { useEffect, useMemo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { TrailItem } from '../lib/events';
import { strings, trailLabel } from '../lib/labels';
import { trailStore, useSessionTrail } from '../lib/store';

interface Props {
  chapter: number;
  active: boolean;
  height: number;
  onContinue: () => void;
  onSeeTrail: () => void;
}

/** A natural stopping point every 12 videos: what this chapter added to your trail, then a choice. */
export function ChapterCard({ chapter, active, height, onContinue, onSeeTrail }: Props) {
  useSessionTrail(); // re-render when the trail changes
  const items = useMemo<TrailItem[]>(() => trailStore.pending(), [active]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!active) return;
    const t = setTimeout(() => trailStore.markShown(), 1500); // once the card has actually been seen
    return () => clearTimeout(t);
  }, [active]);

  return (
    <View style={[styles.page, { height }]}>
      <Text style={styles.title}>{strings.chapterTitle(chapter)}</Text>
      <View style={styles.list}>
        {items.length === 0 ? (
          <Text style={styles.empty}>{strings.chapterEmpty}</Text>
        ) : (
          items.map((t) => (
            <Text key={t.id} style={styles.item}>
              • {trailLabel(t)}
            </Text>
          ))
        )}
      </View>
      <Pressable style={styles.primary} onPress={onContinue} accessibilityRole="button">
        <Text style={styles.primaryText}>{strings.keepGoing}</Text>
      </Pressable>
      <Pressable style={styles.secondary} onPress={onSeeTrail} accessibilityRole="button">
        <Text style={styles.secondaryText}>{strings.seeTrail}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { width: '100%', backgroundColor: '#0b0b12', alignItems: 'center', justifyContent: 'center', padding: 32 },
  title: { color: '#fff', fontSize: 28, fontWeight: '800', marginBottom: 24 },
  list: { alignSelf: 'stretch', marginBottom: 32, gap: 10 },
  item: { color: '#e6e6f0', fontSize: 17 },
  empty: { color: '#9a9ab0', fontSize: 16, textAlign: 'center' },
  primary: { backgroundColor: '#fff', paddingVertical: 14, paddingHorizontal: 32, borderRadius: 999, marginBottom: 12 },
  primaryText: { color: '#000', fontSize: 16, fontWeight: '700' },
  secondary: { paddingVertical: 12 },
  secondaryText: { color: '#c8c8dc', fontSize: 15 },
});
