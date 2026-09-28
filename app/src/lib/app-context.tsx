import * as Crypto from 'expo-crypto';
import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { AppState } from 'react-native';

import { api } from './api';
import { EventBatcher, type ClientEvent } from './events';
import { SessionManager } from './session';
import { trailStore } from './store';

export interface AppServices {
  userId: string;
  numericUserId: number | null;
  sessionId: string;
  track: (event: ClientEvent) => void;
  flush: () => Promise<void>;
}

const Ctx = createContext<AppServices | null>(null);

export function useApp(): AppServices {
  const v = useContext(Ctx);
  if (!v) throw new Error('useApp outside AppProvider');
  return v;
}

export function AppProvider({ userId, children }: { userId: string; children: React.ReactNode }) {
  const session = useMemo(() => new SessionManager({ newId: () => Crypto.randomUUID() }), []);
  const [sessionId, setSessionId] = useState(session.id);
  const [numericUserId, setNumericUserId] = useState<number | null>(null);

  useEffect(() => {
    api.register(userId).then((r) => setNumericUserId(r.user_id)).catch(() => undefined);
  }, [userId]);

  const batcher = useMemo(
    () =>
      new EventBatcher({
        send: (events) => api.events(userId, session.id, events),
        onTrail: (items) => trailStore.add(items),
      }),
    [userId, session],
  );

  useEffect(() => {
    batcher.start();
    const unsubSession = session.subscribe((id) => {
      trailStore.reset();
      setSessionId(id);
    });
    const sub = AppState.addEventListener('change', (state) => {
      if (state !== 'active') void batcher.flush(); // post what we have before iOS/Android suspend us
      session.onAppState(state);
    });
    return () => {
      batcher.stop();
      void batcher.flush();
      unsubSession();
      sub.remove();
    };
  }, [batcher, session]);

  const value = useMemo<AppServices>(
    () => ({ userId, numericUserId, sessionId, track: (e) => batcher.add(e), flush: () => batcher.flush() }),
    [userId, numericUserId, sessionId, batcher],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
