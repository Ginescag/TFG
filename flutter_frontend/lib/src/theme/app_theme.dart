import 'package:flutter/material.dart';
import 'package:shadcn_ui/shadcn_ui.dart';

const kAccentOrange = Color(0xFFEA580C);
const kAkiraFamily = 'AkiraExpanded';

TextStyle _titleStyle(TextStyle? base, {FontWeight weight = FontWeight.w700}) {
  final style = base ?? const TextStyle();
  return style.copyWith(
    fontFamily: kAkiraFamily,
    color: kAccentOrange,
    fontWeight: weight,
  );
}

TextTheme _applyTitleStyles(TextTheme base) {
  return base.copyWith(
    displayLarge: _titleStyle(base.displayLarge),
    displayMedium: _titleStyle(base.displayMedium),
    displaySmall: _titleStyle(base.displaySmall),
    headlineLarge: _titleStyle(base.headlineLarge),
    headlineMedium: _titleStyle(base.headlineMedium),
    headlineSmall: _titleStyle(base.headlineSmall),
    titleLarge: _titleStyle(base.titleLarge),
    titleMedium: _titleStyle(base.titleMedium),
    titleSmall: _titleStyle(base.titleSmall),
    labelLarge: _titleStyle(base.labelLarge, weight: FontWeight.w600),
  );
}

ShadTextTheme _applyShadTitleStyles(ShadTextTheme base) {
  return base.copyWith(
    h1Large: _titleStyle(base.h1Large),
    h1: _titleStyle(base.h1, weight: FontWeight.w700),
    h2: _titleStyle(base.h2, weight: FontWeight.w600),
    h3: _titleStyle(base.h3, weight: FontWeight.w600),
    h4: _titleStyle(base.h4, weight: FontWeight.w600),
  );
}

class AppTheme {
  static ThemeData light() {
    final base = ThemeData(
      brightness: Brightness.light,
      scaffoldBackgroundColor: Colors.white,
      colorScheme: ColorScheme.fromSeed(
        seedColor: kAccentOrange,
        brightness: Brightness.light,
      ),
    );
    return base.copyWith(
      textTheme: _applyTitleStyles(base.textTheme),
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.white,
        elevation: 2,
        titleTextStyle: _titleStyle(base.textTheme.titleLarge),
      ),
    );
  }

  static ThemeData dark() {
    final base = ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: const Color(0xFF0E0E0E),
      colorScheme: ColorScheme.fromSeed(
        seedColor: kAccentOrange,
        brightness: Brightness.dark,
      ),
    );
    return base.copyWith(
      textTheme: _applyTitleStyles(base.textTheme),
      appBarTheme: AppBarTheme(
        backgroundColor: const Color(0xFF141414),
        elevation: 2,
        titleTextStyle: _titleStyle(base.textTheme.titleLarge),
      ),
    );
  }

  static ShadThemeData shadLight() {
    final scheme = const ShadOrangeColorScheme.light().copyWith(
      primary: kAccentOrange,
      ring: kAccentOrange,
    );
    return ShadThemeData(
      brightness: Brightness.light,
      colorScheme: scheme,
      textTheme: _applyShadTitleStyles(
        ShadDefaultThemeVariant.defaultTextTheme,
      ),
    );
  }

  static ShadThemeData shadDark() {
    final scheme = const ShadOrangeColorScheme.dark().copyWith(
      primary: kAccentOrange,
      ring: kAccentOrange,
    );
    return ShadThemeData(
      brightness: Brightness.dark,
      colorScheme: scheme,
      textTheme: _applyShadTitleStyles(
        ShadDefaultThemeVariant.defaultTextTheme,
      ),
    );
  }
}
