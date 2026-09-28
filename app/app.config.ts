import type { ConfigContext, ExpoConfig } from 'expo/config';

/**
 * One config for Expo Go, EAS dev/preview builds and the stores.
 * APP_ENV=production (set in eas.json) turns off the dev-only cleartext/ATS exceptions.
 */
const IS_PROD = process.env.APP_ENV === 'production';

const BUNDLE_ID = 'com.vibo.app'; // change before the first store submission; must be unique on both stores

export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: 'VIBO',
  slug: 'vibo',
  scheme: 'vibo',
  version: '0.1.0',
  orientation: 'portrait',
  icon: './assets/icon.png',
  userInterfaceStyle: 'dark',
  backgroundColor: '#000000',
  ios: {
    bundleIdentifier: BUNDLE_ID,
    buildNumber: '1',
    supportsTablet: false,
    config: { usesNonExemptEncryption: false }, // no export-compliance prompt on every upload
    infoPlist: {
      // Dev only: Expo Go / dev builds talk to the LAN API over http. Production is https-only.
      ...(IS_PROD ? {} : { NSAppTransportSecurity: { NSAllowsArbitraryLoads: true } }),
    },
  },
  android: {
    package: BUNDLE_ID,
    versionCode: 1,
    adaptiveIcon: {
      backgroundColor: '#000000',
      foregroundImage: './assets/android-icon-foreground.png',
      backgroundImage: './assets/android-icon-background.png',
      monochromeImage: './assets/android-icon-monochrome.png',
    },
    predictiveBackGestureEnabled: false,
    permissions: [], // INTERNET is implicit; nothing else (no location, contacts, camera, storage)
  },
  web: { favicon: './assets/favicon.png' },
  plugins: [
    'expo-router',
    ['expo-video', { supportsBackgroundPlayback: false, supportsPictureInPicture: false }],
    'expo-secure-store',
    ['expo-splash-screen', { image: './assets/splash-icon.png', backgroundColor: '#000000', imageWidth: 160 }],
    // Dev only: Expo Go / dev builds talk to the LAN API over http. Production builds are https-only.
    ['expo-build-properties', { android: { usesCleartextTraffic: !IS_PROD } }],
  ],
  extra: {
    eas: { projectId: process.env.EAS_PROJECT_ID }, // filled by `eas init`
  },
});
