#!/bin/sh
# Xcode Cloud post-clone hook for the Luma Flutter app.
#
# Xcode Cloud's macOS images don't ship Flutter, and xcodebuild won't
# run `pod install` on its own. This script handles both, then bakes
# the production API_BASE into Flutter/Generated.xcconfig so Xcode's
# subsequent build step sees the correct --dart-define.
#
# Apple's spec for these scripts:
#   https://developer.apple.com/documentation/xcode/writing-custom-build-scripts
# CI_PRIMARY_REPOSITORY_PATH points at the cloned repo root.

set -euo pipefail

echo "→ Xcode Cloud post-clone: setting up Flutter"

if ! command -v flutter >/dev/null 2>&1; then
  echo "  Installing Flutter via Homebrew (one-time per builder)…"
  brew install --cask flutter
fi

# Homebrew installs into /opt/homebrew on Apple silicon; make sure
# subsequent steps in this shell can find flutter and pub-installed
# binaries.
export PATH="/opt/homebrew/bin:$HOME/.pub-cache/bin:$PATH"

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
