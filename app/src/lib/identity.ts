/**
 * Install id = user id (no login in phase 1).
 * A random UUID generated on first launch and kept in the keychain/keystore. Deliberately NOT a hardware
 * identifier: CLAUDE.md forbids device fingerprints, and app-generated ids need no ATT prompt on iOS.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';

const KEY = 'vibo.install_id';

export async function getInstallId(): Promise<string> {
  const existing = (await readSecure()) ?? (await AsyncStorage.getItem(KEY));
  if (existing) return existing;
  const id = Crypto.randomUUID();
  if (!(await writeSecure(id))) await AsyncStorage.setItem(KEY, id);
  return id;
}

async function readSecure(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(KEY);
  } catch {
    return null;
  }
}

async function writeSecure(id: string): Promise<boolean> {
  try {
    await SecureStore.setItemAsync(KEY, id);
    return true;
  } catch {
    return false;
  }
}

const CONSENT_KEY = 'vibo.consent.v1';

export async function hasConsented(): Promise<boolean> {
  return (await AsyncStorage.getItem(CONSENT_KEY)) === 'yes';
}

export async function setConsented(): Promise<void> {
  await AsyncStorage.setItem(CONSENT_KEY, 'yes');
}
