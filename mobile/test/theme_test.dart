import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:luma_support_mobile/src/theme.dart';

void main() {
  test('Cupertino transitions (swipe-back) apply on every platform', () {
    for (final theme in [lumaTheme, lumaLightTheme]) {
      for (final platform in [TargetPlatform.android, TargetPlatform.iOS]) {
        expect(
          theme.pageTransitionsTheme.builders[platform],
          isA<CupertinoPageTransitionsBuilder>(),
          reason: 'expected Cupertino transition for $platform',
        );
      }
    }
  });

  test('brand teal is preserved', () {
    expect(lumaTheme.colorScheme.primary, const Color(0xFF14B8A6));
    expect(lumaLightTheme.colorScheme.primary, const Color(0xFF14B8A6));
  });

  test('tab bar is iOS-style: no Material indicator pill, no ripple', () {
    expect(lumaTheme.navigationBarTheme.indicatorColor, Colors.transparent);
    expect(lumaTheme.splashFactory, NoSplash.splashFactory);
  });

  test('nav titles are centered with SF metrics', () {
    expect(lumaTheme.appBarTheme.centerTitle, isTrue);
    expect(lumaTheme.appBarTheme.titleTextStyle?.fontSize, 17);
  });
}
