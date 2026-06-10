import 'package:flutter/services.dart';

/// Thin wrapper over [HapticFeedback] so call sites read as intent
/// ("selection", "success") rather than impact strength.
class Haptics {
  Haptics._();

  /// Tab taps, segmented-control changes, picker ticks.
  static void selection() => HapticFeedback.selectionClick();

  /// Button presses and toggles.
  static void light() => HapticFeedback.lightImpact();

  /// A completed action: timer stopped, status changed, form saved.
  static void success() => HapticFeedback.mediumImpact();
}
