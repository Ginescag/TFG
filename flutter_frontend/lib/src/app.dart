import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shadcn_ui/shadcn_ui.dart';

import 'providers.dart';
import 'router.dart';
import 'theme/app_theme.dart';

class WardenApp extends ConsumerWidget {
  const WardenApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    final themeMode = ref.watch(themeControllerProvider);

    return MaterialApp.router(
      debugShowCheckedModeBanner: false,
      title: 'Warden',
      routerConfig: router,
      themeMode: themeMode,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      builder: (context, child) {
        final shadTheme = themeMode == ThemeMode.dark
            ? AppTheme.shadDark()
            : AppTheme.shadLight();
        return ShadTheme(
          data: shadTheme,
          child: child ?? const SizedBox.shrink(),
        );
      },
    );
  }
}
