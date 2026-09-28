import { useEvent } from 'expo';
import { useVideoPlayer, VideoView } from 'expo-video';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, Share, StyleSheet, Text, View } from 'react-native';

import type { ClientEvent } from '../lib/events';
import type { FeedVideo } from '../lib/feed';
import { mainTopic, strings, whyLabel } from '../lib/labels';
import { localUri } from '../lib/prefetch';
import { WatchTracker } from '../lib/watch';

interface Props {
  video: FeedVideo;
  index: number;
  active: boolean; // the one on screen: plays with sound
  near: boolean; // within one swipe: keep a player ready
  height: number;
  onEvent: (event: ClientEvent) => void;
  onMore: (video: FeedVideo) => void;
}

export function VideoCard({ video, index, active, near, height, onEvent, onMore }: Props) {
  const source = useMemo(
    () => (near ? { uri: localUri(video.video_id) ?? video.url, useCaching: true } : null),
    [near, video.video_id, video.url],
  );
  const player = useVideoPlayer(source, (p) => {
    p.loop = true;
    p.muted = false;
  });
  const { isPlaying } = useEvent(player, 'playingChange', { isPlaying: player.playing });
  const tracker = useRef(new WatchTracker(video.duration_ms));
  const wasActive = useRef(false);
  const [saved, setSaved] = useState(false);
  const [paused, setPaused] = useState(false);

  useEffect(() => tracker.current.setPlaying(isPlaying), [isPlaying]);

  useEffect(() => {
    if (active) {
      tracker.current = new WatchTracker(video.duration_ms);
      onEvent({ video_id: video.video_id, kind: 'impression', position: index });
      setPaused(false);
      player.play();
    } else {
      player.pause();
      if (wasActive.current) onEvent({ video_id: video.video_id, ...tracker.current.leave(index) });
    }
    wasActive.current = active;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  useEffect(
    () => () => {
      if (wasActive.current) onEvent({ video_id: video.video_id, ...tracker.current.leave(index) });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const togglePause = () => {
    if (!active) return;
    if (isPlaying) {
      player.pause();
      setPaused(true);
      onEvent({ video_id: video.video_id, ...tracker.current.action('pause', index) });
    } else {
      player.play();
      setPaused(false);
    }
  };

  const save = () => {
    if (saved) return;
    setSaved(true);
    onEvent({ video_id: video.video_id, ...tracker.current.action('save', index) });
  };

  const share = async () => {
    try {
      const r = await Share.share({ message: video.url, url: video.url });
      if (r.action === Share.sharedAction) onEvent({ video_id: video.video_id, ...tracker.current.action('share', index) });
    } catch {
      /* user cancelled */
    }
  };

  return (
    <View style={[styles.page, { height }]}>
      <Pressable style={StyleSheet.absoluteFill} onPress={togglePause} accessibilityLabel="Play or pause">
        {near ? (
          <VideoView player={player} style={StyleSheet.absoluteFill} contentFit="cover" nativeControls={false} />
        ) : (
          <View style={[StyleSheet.absoluteFill, styles.placeholder]} />
        )}
        {paused && (
          <View style={styles.pausedBadge} pointerEvents="none">
            <Text style={styles.pausedText}>❚❚</Text>
          </View>
        )}
      </Pressable>

      <View style={styles.meta} pointerEvents="none">
        <Text style={styles.topic}>#{mainTopic(video)}</Text>
        <Text style={styles.why}>{whyLabel(video)}</Text>
      </View>

      <View style={styles.actions}>
        <Action label={saved ? strings.saved : strings.save} icon={saved ? '♥' : '♡'} onPress={save} />
        <Action label={strings.share} icon="↗" onPress={share} />
        <Action label={strings.more} icon="⋯" onPress={() => onMore(video)} />
      </View>
    </View>
  );
}

function Action({ label, icon, onPress }: { label: string; icon: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={styles.action} accessibilityRole="button" accessibilityLabel={label} hitSlop={12}>
      <Text style={styles.actionIcon}>{icon}</Text>
      <Text style={styles.actionLabel}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  page: { width: '100%', backgroundColor: '#000' },
  placeholder: { backgroundColor: '#111' },
  pausedBadge: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, alignItems: 'center', justifyContent: 'center' },
  pausedText: { color: 'rgba(255,255,255,0.7)', fontSize: 48 },
  meta: { position: 'absolute', left: 16, right: 96, bottom: 48 },
  topic: { color: '#fff', fontSize: 18, fontWeight: '700', textShadowColor: '#000', textShadowRadius: 6 },
  why: { color: 'rgba(255,255,255,0.85)', fontSize: 14, marginTop: 4, textShadowColor: '#000', textShadowRadius: 6 },
  actions: { position: 'absolute', right: 12, bottom: 48, alignItems: 'center', gap: 18 },
  action: { alignItems: 'center' },
  actionIcon: { color: '#fff', fontSize: 30, textShadowColor: '#000', textShadowRadius: 6 },
  actionLabel: { color: '#fff', fontSize: 11, marginTop: 2 },
});
