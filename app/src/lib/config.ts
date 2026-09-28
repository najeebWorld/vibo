import Constants from 'expo-constants';

/**
 * API base URL.
 *  - Store / EAS builds: set EXPO_PUBLIC_API_URL (https) in eas.json or .env.
 *  - Expo Go on the LAN: derived from the dev server host, port EXPO_PUBLIC_API_PORT (default 8000).
 */
const port = process.env.EXPO_PUBLIC_API_PORT ?? '8000';

function guessDevUrl(): string {
  const host = Constants.expoConfig?.hostUri?.split(':')[0];
  return `http://${host ?? 'localhost'}:${port}`;
}

export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? guessDevUrl()).replace(/\/$/, '');
export const IS_DEV = __DEV__;
