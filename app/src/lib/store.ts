/** What this session added to the trail (fed by POST /events responses). Drives the chapter-end card. */
import { useSyncExternalStore } from 'react';

import type { TrailItem } from './events';

interface State {
  trail: TrailItem[];
  shownIds: Set<number>; // ids already presented on a chapter card
}

let state: State = { trail: [], shownIds: new Set() };
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

export const trailStore = {
  get: () => state,
  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
  /** Merge by id: the streak row is updated in place on the server, so it replaces its older copy. */
  add(items: TrailItem[]) {
    const byId = new Map(state.trail.map((t) => [t.id, t]));
    items.forEach((t) => byId.set(t.id, t));
    state = { ...state, trail: [...byId.values()].sort((a, b) => a.id - b.id) };
    emit();
  },
  /** Items to show on the next chapter card: new since the last card, plus the live streak. */
  pending(): TrailItem[] {
    return state.trail.filter((t) => !state.shownIds.has(t.id) || t.kind === 'streak');
  },
  markShown() {
    state = { ...state, shownIds: new Set(state.trail.map((t) => t.id)) };
    emit();
  },
  reset() {
    state = { trail: [], shownIds: new Set() };
    emit();
  },
};

export function useSessionTrail(): TrailItem[] {
  return useSyncExternalStore(trailStore.subscribe, () => state.trail, () => state.trail);
}
