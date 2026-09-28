import { useRouter } from 'expo-router';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Alert, FlatList, Pressable, StyleSheet, Text, View, ViewToken, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ChapterCard } from '../components/ChapterCard';
import { MoreSheet } from '../components/MoreSheet';
import { VideoCard } from '../components/VideoCard';
import { api, type ReportReason } from '../lib/api';
import { useApp } from '../lib/app-context';
import { interleaveChapters, mergeVideos, needsMore, PAGE_SIZE, upcomingVideos, type FeedEntry, type FeedVideo } from '../lib/feed';
import { strings } from '../lib/labels';
import { prefetch, trimCache } from '../lib/prefetch';

export default function FeedScreen() {
  const { userId, numericUserId, sessionId, track } = useApp();
  const router = useRouter();
  const { height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const list = useRef<FlatList<FeedEntry>>(null);

  const [videos, setVideos] = useState<FeedVideo[]>([]);
  const [active, setActive] = useState(0);
  const [exhausted, setExhausted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [more, setMore] = useState<FeedVideo | null>(null);
  const loading = useRef(false);

  const entries = useMemo(() => interleaveChapters(videos), [videos]);

  const loadMore = useCallback(async () => {
    if (loading.current || exhausted) return;
    loading.current = true;
    try {
      const { items } = await api.feed(userId, sessionId, PAGE_SIZE);
      if (items.length === 0) setExhausted(true);
      setVideos((prev) => mergeVideos(prev, items));
      setError(null);
    } catch (e) {
      setError(strings.feedError);
    } finally {
      loading.current = false;
    }
  }, [userId, sessionId, exhausted]);

  // new session (30 min away) => fresh feed
  useEffect(() => {
    setVideos([]);
    setActive(0);
    setExhausted(false);
    void loadMore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  useEffect(() => {
    if (needsMore(entries, active)) void loadMore();
    const next = upcomingVideos(entries, active, 3);
    prefetch(next);
    trimCache(new Set([...next.map((v) => v.video_id), ...videos.slice(Math.max(0, active - 2), active + 4).map((v) => v.video_id)]));
  }, [active, entries, loadMore, videos]);

  const onViewableItemsChanged = useRef(({ viewableItems }: { viewableItems: ViewToken<FeedEntry>[] }) => {
    const first = viewableItems.find((v) => v.isViewable);
    if (first && typeof first.index === 'number') setActive(first.index);
  }).current;

  const scrollTo = (index: number) => list.current?.scrollToIndex({ index: Math.min(index, entries.length - 1), animated: true });

  const report = async (video: FeedVideo, reason: ReportReason) => {
    setMore(null);
    try {
      await api.report(video.video_id, userId, reason);
      setVideos((prev) => prev.filter((v) => v.video_id !== video.video_id));
      Alert.alert(strings.report, strings.reportDone);
    } catch {
      Alert.alert(strings.report, strings.feedError);
    }
  };

  const block = async (video: FeedVideo) => {
    setMore(null);
    if (video.creator_id === null) return;
    try {
      await api.block(userId, video.creator_id);
      setVideos((prev) => prev.filter((v) => v.creator_id !== video.creator_id));
      Alert.alert(strings.blockCreator, strings.blockDone);
    } catch {
      Alert.alert(strings.blockCreator, strings.feedError);
    }
  };

  const renderItem = ({ item, index }: { item: FeedEntry; index: number }) =>
    item.type === 'video' ? (
      <VideoCard
        video={item.video}
        index={index}
        active={index === active}
        near={Math.abs(index - active) <= 1}
        height={height}
        onEvent={track}
        onMore={setMore}
      />
    ) : (
      <ChapterCard
        chapter={item.chapter}
        active={index === active}
        height={height}
        onContinue={() => scrollTo(index + 1)}
        onSeeTrail={() => router.push('/trail')}
      />
    );

  return (
    <View style={styles.root}>
      <FlatList
        ref={list}
        data={entries}
        keyExtractor={(e) => e.key}
        renderItem={renderItem}
        pagingEnabled
        showsVerticalScrollIndicator={false}
        snapToInterval={height}
        decelerationRate="fast"
        getItemLayout={(_, index) => ({ length: height, offset: height * index, index })}
        onViewableItemsChanged={onViewableItemsChanged}
        viewabilityConfig={{ itemVisiblePercentThreshold: 60 }}
        windowSize={3}
        initialNumToRender={2}
        maxToRenderPerBatch={2}
        removeClippedSubviews
        onRefresh={() => {
          setExhausted(false);
          void loadMore();
        }}
        refreshing={false}
        ListEmptyComponent={
          <View style={[styles.empty, { height }]}>
            <Text style={styles.emptyText}>{error ?? (exhausted ? strings.feedEmpty : '…')}</Text>
          </View>
        }
      />
      <View style={[styles.header, { top: insets.top + 8 }]} pointerEvents="box-none">
        <Text style={styles.brand}>{strings.appName}</Text>
        <Pressable onPress={() => router.push('/trail')} hitSlop={12} accessibilityRole="button" accessibilityLabel={strings.trail}>
          <Text style={styles.trailLink}>{strings.trail} →</Text>
        </Pressable>
      </View>
      <MoreSheet
        video={more}
        onClose={() => setMore(null)}
        onReport={report}
        onBlock={block}
        isMine={(v) => numericUserId !== null && v.creator_id === numericUserId}
        onStats={(v) => {
          setMore(null);
          router.push(`/video/${v.video_id}`);
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#000' },
  header: { position: 'absolute', left: 16, right: 16, flexDirection: 'row', justifyContent: 'space-between' },
  brand: { color: '#fff', fontSize: 18, fontWeight: '900', letterSpacing: 2, textShadowColor: '#000', textShadowRadius: 6 },
  trailLink: { color: '#fff', fontSize: 15, fontWeight: '600', textShadowColor: '#000', textShadowRadius: 6 },
  empty: { alignItems: 'center', justifyContent: 'center', padding: 32 },
  emptyText: { color: '#9a9ab0', fontSize: 16, textAlign: 'center' },
});
