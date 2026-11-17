# MangaReader Android v1.1.2

This folder contains the Android project source snapshot in Base64 archive parts under `source-b64/`.

The GitHub Actions workflow `.github/workflows/build-android-apk.yml` restores the source archive, installs JDK 17, Gradle 8.7, and Android SDK 35, then builds an installable debug APK.

When the workflow succeeds, open the repository's Actions tab, select **Build MangaReader Android APK**, and download the artifact named **MangaReader-v1.1.2-APK**.

The generated APK is debug-signed for direct testing on Android devices. It is not a Play Store release build.

Build source snapshot committed for cloud APK build.
