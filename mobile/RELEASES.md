# Mobile release automation

The native source is intentionally contained in [`mobile/`](.) within the `ekodecrux/AiMarket0808` repository. GitHub Actions validates mobile changes and provides the manual **Native Mobile Release Builds** workflow for direct, platform-native compilation.

The workflow does **not** use Expo-hosted builds or require an Expo token. It produces an installable debug APK with Gradle without signing secrets. Store-uploadable Android App Bundles and iOS IPAs remain protected-signing operations and are enabled only after the corresponding GitHub repository secrets are set.

See [NATIVE_BUILDS.md](./NATIVE_BUILDS.md) for the authoritative artifact matrix, protected-secret names, and manual upload guidance. The workflow only builds and retains artifacts; it never submits an app to Google Play or App Store Connect.
