import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shadcn_ui/shadcn_ui.dart';

import '../providers.dart';
import '../state/auth_state.dart';

class AppDrawer extends ConsumerWidget {
  const AppDrawer({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authControllerProvider);
    final primary = Theme.of(context).colorScheme.primary;

    return Drawer(
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          DrawerHeader(
            decoration: BoxDecoration(color: primary.withOpacity(0.1)),
            child: Center(
              child: Text(
                'Menu',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: primary,
                ),
              ),
            ),
          ),
          _drawerItem(
            context,
            icon: Icons.home_outlined,
            label: 'Home',
            route: '/home',
          ),
          _drawerItem(
            context,
            icon: Icons.smart_toy_outlined,
            label: 'Robots',
            route: '/robots',
          ),
          _drawerItem(
            context,
            icon: Icons.report_problem_outlined,
            label: 'Incidents',
            route: '/incidents',
          ),
          _drawerItem(
            context,
            icon: Icons.person_outline,
            label: 'Profile',
            route: '/profile',
          ),
          if (auth.status == AuthStatus.authenticated && auth.role == 'admin')
            _drawerItem(
              context,
              icon: Icons.admin_panel_settings_outlined,
              label: 'Admin',
              route: '/admin',
            ),
          const ShadSeparator.horizontal(),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: ShadButton(
              onPressed: () async {
                await ref.read(authControllerProvider.notifier).logout();
                if (context.mounted) {
                  context.go('/auth');
                }
              },
              child: const Text('Close session'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _drawerItem(
    BuildContext context, {
    required IconData icon,
    required String label,
    required String route,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: ShadButton.ghost(
        leading: Icon(icon),
        onPressed: () {
          Navigator.pop(context);
          context.go(route);
        },
        child: Align(
          alignment: Alignment.centerLeft,
          child: Text(label),
        ),
      ),
    );
  }
}
