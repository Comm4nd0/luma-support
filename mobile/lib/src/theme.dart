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
    appBarTheme: AppBarTheme(
      backgroundColor: surface,
      foregroundColor: text,
      elevation: 0,
    ),
    cardTheme: CardThemeData(
      color: surface,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: const BorderRadius.all(Radius.circular(12)),
        side: BorderSide(color: border),
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
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
    ),
  );
}

final ThemeData lumaTheme = _build(Brightness.dark);
final ThemeData lumaLightTheme = _build(Brightness.light);
