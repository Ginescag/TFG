import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/providers.dart';
import 'models/robot.dart';
import 'state/auth_controller.dart';
import 'state/auth_state.dart';
import 'state/robots_controller.dart';
import 'state/theme_controller.dart';

export 'core/providers.dart';

final authControllerProvider = StateNotifierProvider<AuthController, AuthState>(
  (ref) {
    return AuthController(
      ref.read(authRepositoryProvider),
      ref.read(sessionStorageProvider),
    );
  },
);

final themeControllerProvider =
    StateNotifierProvider<ThemeController, ThemeMode>((ref) {
      return ThemeController();
    });

final robotsControllerProvider =
    AsyncNotifierProvider<RobotsController, List<Robot>>(RobotsController.new);
