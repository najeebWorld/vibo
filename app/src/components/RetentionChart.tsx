import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { pct, type RetentionCurve } from '../lib/creator';

/**
 * Two single-series bar charts, no chart library:
 *  - retention: share of viewers still watching at 0%, 10%, ... 100% of the video
 *  - histogram: how many views ended in each 10% bucket
 * Text stays in text colors; bars carry only magnitude. The drop segment is named in words, not only by color.
 */
export function RetentionChart({ curve }: { curve: RetentionCurve }) {
  const drop = curve.biggest_drop?.at_pct ?? -1;
  const maxHist = Math.max(1, ...curve.histogram);
  return (
    <View>
      <Text style={styles.caption}>Still watching at…</Text>
      <View style={styles.plot}>
        {curve.retention.map((share, k) => {
          const inDrop = k * 10 === drop || k * 10 === drop + 10;
          return (
            <View key={k} style={styles.col}>
              {(k === 0 || k === 10 || k * 10 === drop) && <Text style={styles.value}>{pct(share)}</Text>}
              <View style={styles.track}>
                <View style={[styles.bar, inDrop && styles.barDrop, { height: `${Math.max(2, share * 100)}%` }]} />
              </View>
              {k % 5 === 0 && <Text style={styles.tick}>{k * 10}%</Text>}
            </View>
          );
        })}
      </View>

      <Text style={styles.caption}>Where views ended</Text>
      <View style={[styles.plot, styles.plotShort]}>
        {curve.histogram.map((n, k) => (
          <View key={k} style={styles.col}>
            {n > 0 && n === maxHist && <Text style={styles.value}>{n}</Text>}
            <View style={styles.track}>
              <View style={[styles.bar, styles.barMuted, { height: `${Math.max(2, (n / maxHist) * 100)}%` }]} />
            </View>
            {(k === 0 || k === 5 || k === 9) && <Text style={styles.tick}>{k === 9 ? '90–100%' : `${k * 10}%`}</Text>}
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  caption: { color: '#9a9ab0', fontSize: 13, marginTop: 20, marginBottom: 8 },
  plot: { flexDirection: 'row', alignItems: 'flex-end', height: 160, gap: 3 },
  plotShort: { height: 110 },
  col: { flex: 1, alignItems: 'center', justifyContent: 'flex-end', height: '100%' },
  track: {
    flex: 1,
    width: '100%',
    justifyContent: 'flex-end',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#3a3a4a',
  },
  bar: { width: '100%', backgroundColor: '#6f8cff', borderTopLeftRadius: 4, borderTopRightRadius: 4 },
  barDrop: { backgroundColor: '#ffb257' },
  barMuted: { backgroundColor: '#4a4f66' },
  value: { color: '#fff', fontSize: 11, marginBottom: 2 },
  tick: { color: '#7a7a90', fontSize: 10, marginTop: 4 },
});
