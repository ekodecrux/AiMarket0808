# Mobile release automation

The native source is intentionally contained in [`mobile/`](.) within the `ekodecrux/AiMarket0808` repository. GitHub Actions validates every mobile change and provides a manual **Mobile Release Builds** workflow for release candidates.

| Requested artifact | Workflow choice | Build profile | Intended use |
|---|---|---|---|
| Android APK | `apk` | `preview` | Internal device QA and direct distribution |
| Android AAB | `aab` | `production` | Google Play Console upload |
| iOS IPA | `ios` | `production` | TestFlight / App Store Connect upload |

## Protected configuration

Create the GitHub Actions secret `EXPO_TOKEN` from the Expo account that owns the `AiMarketMobile` project. The first successful workflow links the EAS project and stores the project ID in the application configuration. Configure Android upload/signing credentials and Apple Developer credentials in the Expo/EAS credentials service for the same account. Do not commit keystores, Apple API keys, provisioning profiles, payment secrets, SMTP credentials, or provider tokens.

The workflows **build only**. They do not submit an app to Google Play or App Store Connect, and a manual dispatch is required for every release. Each run uploads JSON build receipts containing EAS build URLs. Download the final binary from the EAS build page once the cloud build completes.

## Same-day release sequence

1. Add `EXPO_TOKEN` in **GitHub → Settings → Secrets and variables → Actions**.
2. In Expo/EAS, ensure the Android package `com.expertaitutor.aimarket` and iOS bundle identifier use the intended store accounts and credentials.
3. Run **Actions → Mobile Release Builds → Run workflow → all**.
4. Open the artifact receipt, wait for the EAS build to finish, download the APK/AAB/IPA, and upload the AAB to Google Play and IPA through TestFlight/App Store Connect.
