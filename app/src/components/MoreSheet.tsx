import React, { useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import type { ReportReason } from '../lib/api';
import type { FeedVideo } from '../lib/feed';
import { reportReasons, strings } from '../lib/labels';

interface Props {
  video: FeedVideo | null;
  onClose: () => void;
  onReport: (video: FeedVideo, reason: ReportReason) => void;
  onBlock: (video: FeedVideo) => void;
  isMine?: (video: FeedVideo) => boolean;
  onStats?: (video: FeedVideo) => void;
}

/** Report / block sheet. Required for user-generated content on both stores (Apple 1.2, Google UGC). */
export function MoreSheet({ video, onClose, onReport, onBlock, isMine, onStats }: Props) {
  const [reporting, setReporting] = useState(false);
  const close = () => {
    setReporting(false);
    onClose();
  };
  return (
    <Modal visible={video !== null} transparent animationType="slide" onRequestClose={close}>
      <Pressable style={styles.backdrop} onPress={close} />
      <View style={styles.sheet}>
        {video && !reporting && (
          <>
            {isMine?.(video) && onStats && <Row label={strings.stats} onPress={() => onStats(video)} />}
            <Row label={strings.report} onPress={() => setReporting(true)} />
            {video.creator_id !== null && <Row label={strings.blockCreator} onPress={() => onBlock(video)} destructive />}
            <Row label={strings.cancel} onPress={close} />
          </>
        )}
        {video && reporting && (
          <>
            <Text style={styles.title}>{strings.reportTitle}</Text>
            {reportReasons.map((r) => (
              <Row key={r.key} label={r.label} onPress={() => onReport(video, r.key)} />
            ))}
            <Row label={strings.cancel} onPress={close} />
          </>
        )}
      </View>
    </Modal>
  );
}

function Row({ label, onPress, destructive }: { label: string; onPress: () => void; destructive?: boolean }) {
  return (
    <Pressable style={styles.row} onPress={onPress} accessibilityRole="button">
      <Text style={[styles.rowText, destructive && styles.destructive]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)' },
  sheet: { backgroundColor: '#15151f', paddingBottom: 32, paddingTop: 8, borderTopLeftRadius: 16, borderTopRightRadius: 16 },
  title: { color: '#9a9ab0', fontSize: 13, paddingHorizontal: 20, paddingVertical: 10, textTransform: 'uppercase' },
  row: { paddingVertical: 16, paddingHorizontal: 20 },
  rowText: { color: '#fff', fontSize: 17 },
  destructive: { color: '#ff6b6b' },
});
