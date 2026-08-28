# Direct native store builds

The `mobile/` folder contains the full AiMarket native source, including generated `android/` and `ios/` platform projects. The **Native Mobile Release Builds** GitHub Actions workflow does not use Expo cloud services. It compiles Android directly with Gradle and iOS directly with Xcode on a GitHub-hosted macOS runner.

| Artifact | Workflow input | Native toolchain | Signing requirement |
|---|---|---|---|
| Installable Android APK | `apk` | Gradle `assembleDebug` | None; QA-only debug signature |
| Play Store Android App Bundle | `aab` | Gradle `bundleRelease` | Upload keystore and alias credentials |
| App Store/TestFlight iOS IPA | `ios` | Xcode archive/export | Apple distribution certificate and App Store provisioning profile |

## Protected repository secrets

Set only in **GitHub → Settings → Secrets and variables → Actions**. Never commit these values, their decoded files, or an Android `gradle.properties` containing them.

| Secret | Required for | Notes |
|---|---|---|
| `ANDROID_KEYSTORE_BASE64` | AAB | Base64 encoding of the Play upload `.jks`/`.keystore` file |
| `ANDROID_KEYSTORE_PASSWORD` | AAB | Keystore password |
| `ANDROID_KEY_ALIAS` | AAB | Upload-key alias |
| `ANDROID_KEY_PASSWORD` | AAB | Alias password |
| `IOS_DISTRIBUTION_CERTIFICATE_BASE64` | IPA | Base64 encoding of the Apple Distribution `.p12` certificate |
| `IOS_DISTRIBUTION_CERTIFICATE_PASSWORD` | IPA | `.p12` export password |
| `IOS_PROVISIONING_PROFILE_BASE64` | IPA | Base64 encoding of the App Store provisioning profile |
| `APPLE_TEAM_ID` | IPA | Ten-character Apple Developer Team ID |
| `IOS_PROVISIONING_PROFILE_NAME` | IPA | Exact provisioning-profile name for `com.expertaitutor.aimarket` |

The workflow uploads the generated files as GitHub Actions artifacts. Download the signed `.aab` for Google Play Console and the signed `.ipa` for Transporter or App Store Connect. A GitHub artifact expires after 14 days; retain the final store-upload file securely after downloading it.
