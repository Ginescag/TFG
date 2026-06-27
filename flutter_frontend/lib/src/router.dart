import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'features/admin/admin_screen.dart';
import 'features/auth/auth_screen.dart';
import 'features/home/home_screen.dart';
import 'features/incidents/incident_detail_screen.dart';
import 'features/incidents/incidents_screen.dart';
import 'features/profile/profile_screen.dart';
import 'features/robots/robots_screen.dart';
import 'models/incident.dart';
import 'providers.dart';
import 'state/auth_state.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final auth = ref.watch(authControllerProvider);

  return GoRouter(
    initialLocation: '/auth',
    redirect: (context, state) {
      final isAuthRoute = state.matchedLocation == '/auth';

      if (auth.status == AuthStatus.unknown) {
        return isAuthRoute ? null : '/auth';
      }

      if (auth.status == AuthStatus.unauthenticated) {
        return isAuthRoute ? null : '/auth';
      }

      if (auth.status == AuthStatus.authenticated && isAuthRoute) {
        return '/home';
      }

      if (state.matchedLocation.startsWith('/admin') && auth.role != 'admin') {
        return '/home';
      }

      return null;
    },
    routes: [
      GoRoute(path: '/auth', builder: (context, state) => const AuthScreen()),
      GoRoute(path: '/home', builder: (context, state) => const HomeScreen()),
      GoRoute(
        path: '/robots',
        builder: (context, state) => const RobotsScreen(),
      ),
      GoRoute(
        path: '/incidents',
        builder: (context, state) => const IncidentsScreen(),
      ),
      GoRoute(
        path: '/incidents/:id',
        builder: (context, state) =>
            IncidentDetailScreen(incidentId: state.pathParameters['id'] ?? ''),
      ),
      GoRoute(
        path: '/profile',
        builder: (context, state) => const ProfileScreen(),
      ),
      GoRoute(path: '/admin', builder: (context, state) => const AdminScreen()),
      GoRoute(
        path: '/admin/incidents/:id',
        builder: (context, state) => IncidentDetailScreen(
          incidentId: state.pathParameters['id'] ?? '',
          incident: state.extra is Incident ? state.extra as Incident : null,
          admin: true,
        ),
      ),
    ],
  );
});
