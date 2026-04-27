import 'package:flutter/material.dart';

const Color kBackground = Color(0xFF0F172A);
const Color kSurface = Color(0xFF1E293B);
const Color kBorder = Color(0xFF334155);
const Color kPrimary = Color(0xFF14B8A6);
const Color kText = Color(0xFFF1F5F9);
const Color kMuted = Color(0xFF94A3B8);

final ThemeData lumaTheme = ThemeData(
  brightness: Brightness.dark,
  scaffoldBackgroundColor: kBackground,
  primaryColor: kPrimary,
  colorScheme: const ColorScheme.dark(
    primary: kPrimary,
    secondary: kPrimary,
    surface: kSurface,
  ),
  appBarTheme: const AppBarTheme(
    backgroundColor: kSurface,
    foregroundColor: kText,
    elevation: 0,
  ),
  cardTheme: const CardTheme(
    color: kSurface,
    elevation: 0,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.all(Radius.circular(12)),
      side: BorderSide(color: kBorder),
    ),
  ),
  inputDecorationTheme: const InputDecorationTheme(
    filled: true,
    fillColor: kBackground,
    border: OutlineInputBorder(),
    labelStyle: TextStyle(color: kMuted),
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
