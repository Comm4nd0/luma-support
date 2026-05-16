#!/bin/sh
# Xcode Cloud post-clone hook for the Luma Flutter app.
#
# Xcode Cloud's macOS images don't ship Flutter, and xcodebuild won't
# run `pod install` on its own. This script clones the Flutter SDK,
# runs pub-get / pod-install, and bakes the production API_BASE into
# Flutter/Generated.xcconfig so Xcode's subsequent build step sees the
# correct --dart-define.
#
# Apple's spec for these scripts:
#   https://developer.apple.com/documentation/xcode/writing-custom-build-scripts
# CI_PRIMARY_REPOSITORY_PATH points at the cloned repo root.

set -euo pipefail

echo "→ Xcode Cloud post-clone: setting up Flutter"

# The Flutter team asked Homebrew to drop the `flutter` cask, so we
# install the SDK by shallow-cloning it. Xcode Cloud builders are
# ephemeral, so this clone runs every build.
FLUTTER_HOME="$HOME/flutter"
FLUTTER_CHANNEL="${FLUTTER_CHANNEL:-stable}"

if [ ! -x "$FLUTTER_HOME/bin/flutter" ]; then
  echo "  Cloning Flutter SDK ($FLUTTER_CHANNEL)…"
  git clone --depth 1 -b "$FLUTTER_CHANNEL" \
    https://github.com/flutter/flutter.git "$FLUTTER_HOME"
fi

# Flutter first so its bundled dart wins; then Homebrew for pod/etc.;
# then pub-cache for anything dart-pub installs.
export PATH="$FLUTTER_HOME/bin:/opt/homebrew/bin:$HOME/.pub-cache/bin:$PATH"

cd "$CI_PRIMARY_REPOSITORY_PATH/mobile"

flutter --version
flutter precache --ios
flutter pub get

# Regenerate Flutter/Generated.xcconfig with the prod dart-defines.
# `--config-only` skips the compilation step — xcodebuild does that
# next.
flutter build ios --release --config-only \
  --dart-define=API_BASE=https://support.lumatechsolutions.co.uk/api/v1

# xcodebuild won't run `pod install` for us, so do it explicitly now
# that pub-get has materialised the plugin podspecs.
cd ios
pod install

echo "→ Flutter setup complete"
