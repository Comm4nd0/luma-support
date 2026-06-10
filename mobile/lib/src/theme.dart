import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

// ---- Dark (default) palette ----
const Color kBackground = Color(0xFF0F172A);
const Color kSurface = Color(0xFF1E293B);
const Color kBorder = Color(0xFF334155);
const Color kPrimary = Color(0xFF14B8A6);
const Color kText = Color(0xFFF1F5F9);
const Color kMuted = Color(0xFF94A3B8);

// ---- Light palette (mirrors the dark tokens; brand teal preserved) ----
const Color kLightBackground = Color(0xFFF8FAFC);
const Color kLightSurface = Color(0xFFFFFFFF);
const Color kLightBorder = Color(0xFFE2E8F0);
const Color kLightText = Color(0xFF0F172A);
const Color kLightMuted = Color(0xFF64748B);

/// iOS page transitions (slide-from-right + edge swipe-back) on every
/// platform — one Apple-feel design, not platform-adaptive.
const PageTransitionsTheme _cupertinoTransitions = PageTransitionsTheme(
  builders: {
    TargetPlatform.android: CupertinoPageTransitionsBuilder(),
    TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
    TargetPlatform.macOS: CupertinoPageTransitionsBuilder(),
    TargetPlatform.linux: CupertinoPageTransitionsBuilder(),
    TargetPlatform.windows: CupertinoPageTransitionsBuilder(),
    TargetPlatform.fuchsia: CupertinoPageTransitionsBuilder(),
  },
);

/// Text styles using SF Pro's metrics (sizes + tracking from Apple's HIG)
/// so Android — which renders Roboto — still carries the same rhythm.
TextTheme _sfTextTheme(Color text, Color muted) {
  return TextTheme(
    // iOS "Large Title".
    displaySmall: TextStyle(
      fontSize: 34, fontWeight: FontWeight.w700, letterSpacing: -0.37,
      color: text,
    ),
    headlineMedium: TextStyle(
      fontSize: 28, fontWeight: FontWeight.w700, letterSpacing: -0.36,
      color: text,
    ),
    // iOS nav-bar title.
    titleLarge: TextStyle(
      fontSize: 17, fontWeight: FontWeight.w600, letterSpacing: -0.41,
      color: text,
    ),
    titleMedium: TextStyle(
      fontSize: 16, fontWeight: FontWeight.w600, letterSpacing: -0.32,
      color: text,
    ),
    bodyLarge: TextStyle(
      fontSize: 17, letterSpacing: -0.41, color: text,
    ),
    bodyMedium: TextStyle(
      fontSize: 15, letterSpacing: -0.24, color: text,
    ),
    bodySmall: TextStyle(
      fontSize: 13, letterSpacing: -0.08, color: muted,
    ),
    labelLarge: TextStyle(
      fontSize: 17, fontWeight: FontWeight.w600, letterSpacing: -0.41,
      color: text,
    ),
    labelSmall: TextStyle(
      fontSize: 11, letterSpacing: 0.07, color: muted,
    ),
  );
}

ThemeData _build(Brightness brightness) {
  final isDark = brightness == Brightness.dark;
  final bg = isDark ? kBackground : kLightBackground;
  final surface = isDark ? kSurface : kLightSurface;
  final border = isDark ? kBorder : kLightBorder;
  final text = isDark ? kText : kLightText;
  final muted = isDark ? kMuted : kLightMuted;
  return ThemeData(
    brightness: brightness,
    scaffoldBackgroundColor: bg,
    primaryColor: kPrimary,
    colorScheme: ColorScheme(
      brightness: brightness,
      primary: kPrimary,
      onPrimary: const Color(0xFF042F2E),
      secondary: kPrimary,
      onSecondary: const Color(0xFF042F2E),
      error: const Color(0xFFEF4444),
      onError: Colors.white,
      surface: surface,
      onSurface: text,
    ),
    pageTransitionsTheme: _cupertinoTransitions,
    // Cupertino widgets (switches, dialogs, pickers) pick up the brand.
    cupertinoOverrideTheme: NoDefaultCupertinoThemeData(
      brightness: brightness,
      primaryColor: kPrimary,
      scaffoldBackgroundColor: bg,
      barBackgroundColor: surface.withOpacity(0.9),
    ),
    // iOS press feel: a quiet highlight instead of the Material ripple.
    splashFactory: NoSplash.splashFactory,
    highlightColor: text.withOpacity(0.04),
    textTheme: _sfTextTheme(text, muted),
    appBarTheme: AppBarTheme(
      backgroundColor: surface,
      foregroundColor: text,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: true,
      titleTextStyle: TextStyle(
        fontSize: 17,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.41,
        color: text,
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      height: 64,
      backgroundColor: surface.withOpacity(0.85),
      surfaceTintColor: Colors.transparent,
      indicatorColor: Colors.transparent,
      labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w500,
          letterSpacing: -0.08,
          color: states.contains(WidgetState.selected) ? kPrimary : muted,
        ),
      ),
      iconTheme: WidgetStateProperty.resolveWith(
        (states) => IconThemeData(
          color: states.contains(WidgetState.selected) ? kPrimary : muted,
        ),
      ),
    ),
    cardTheme: CardThemeData(
      color: surface,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: const BorderRadius.all(Radius.circular(12)),
        side: BorderSide(color: border),
      ),
    ),
    listTileTheme: ListTileThemeData(
      contentPadding: const EdgeInsets.symmetric(horizontal: 16),
      iconColor: muted,
    ),
    dividerTheme: DividerThemeData(
      color: border,
      thickness: 0.5,
      space: 0.5,
      indent: 16,
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: surface,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(14)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: bg,
      border: const OutlineInputBorder(),
      labelStyle: TextStyle(color: muted),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: kPrimary,
        foregroundColor: const Color(0xFF042F2E),
        minimumSize: const Size(0, 50),
        textStyle: const TextStyle(
          fontSize: 17,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.41,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: kPrimary,
        textStyle: const TextStyle(
          fontSize: 17,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.41,
        ),
      ),
    ),
  );
}

final ThemeData lumaTheme = _build(Brightness.dark);
final ThemeData lumaLightTheme = _build(Brightness.light);
