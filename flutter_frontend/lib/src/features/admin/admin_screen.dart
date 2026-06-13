import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shadcn_ui/shadcn_ui.dart';

import '../../data/api_exception.dart';
import '../../models/incident.dart';
import '../../models/robot.dart';
import '../../models/user.dart';
import '../../providers.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/error_view.dart';
import '../../widgets/loading_view.dart';

final adminUsersProvider = FutureProvider<List<User>>((ref) {
  return ref.read(adminRepositoryProvider).listUsers();
});

final adminRobotsProvider = FutureProvider<List<Robot>>((ref) {
  return ref.read(adminRepositoryProvider).listRobots();
});

class AdminScreen extends ConsumerStatefulWidget {
  const AdminScreen({super.key});

  @override
  ConsumerState<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends ConsumerState<AdminScreen> {
  final _robotIdController = TextEditingController();
  List<Incident> _robotIncidents = [];
  bool _loadingIncidents = false;
  String _activeTab = 'users';

  @override
  @override
  void dispose() {
    _robotIdController.dispose();
    super.dispose();
  }

  Future<void> _loadIncidents() async {
    setState(() => _loadingIncidents = true);
    try {
      final data = await ref
          .read(adminRepositoryProvider)
          .listRobotIncidents(_robotIdController.text.trim());
      setState(() => _robotIncidents = data);
    } on ApiException catch (e) {
      _showMessage(e.message);
    } catch (_) {
      _showMessage('No se pudieron cargar incidencias.');
    } finally {
      setState(() => _loadingIncidents = false);
    }
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final titleStyle = Theme.of(context).textTheme.titleSmall;

    return Scaffold(
      drawer: const AppDrawer(),
      appBar: AppBar(title: const Text('Admin')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: ShadTabs<String>(
          value: _activeTab,
          onChanged: (value) => setState(() => _activeTab = value),
          tabBarAlignment: Alignment.center,
          tabBarConstraints: const BoxConstraints(maxWidth: 520),
          tabs: [
            ShadTab(
              value: 'users',
              content: _UsersTab(),
              child: Text('Usuarios', style: titleStyle),
            ),
            ShadTab(
              value: 'robots',
              content: _RobotsTab(),
              child: Text('Robots', style: titleStyle),
            ),
            ShadTab(
              value: 'incidents',
              content: _IncidentsTab(
                controller: _robotIdController,
                incidents: _robotIncidents,
                loading: _loadingIncidents,
                onLoad: _loadIncidents,
              ),
              child: Text('Incidencias', style: titleStyle),
            ),
          ],
        ),
      ),
    );
  }
}

class _UsersTab extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final usersAsync = ref.watch(adminUsersProvider);

    return usersAsync.when(
      data: (users) => ListView.separated(
        padding: const EdgeInsets.all(16),
        itemCount: users.length,
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (context, index) {
          final user = users[index];
          return ShadCard(
            title: Text(user.nombre),
            description: Text(user.email),
            footer: Row(
              children: [
                ShadButton.outline(
                  onPressed: () async {
                    await ref.read(adminRepositoryProvider).grantAdmin(user.id);
                    ref.refresh(adminUsersProvider);
                  },
                  child: const Text('Grant admin'),
                ),
                const SizedBox(width: 8),
                ShadButton.outline(
                  onPressed: () async {
                    await ref.read(adminRepositoryProvider).revokeAdmin(user.id);
                    ref.refresh(adminUsersProvider);
                  },
                  child: const Text('Revoke admin'),
                ),
                const Spacer(),
                ShadButton.destructive(
                  onPressed: () async {
                    await ref.read(adminRepositoryProvider).deleteUser(user.id);
                    ref.refresh(adminUsersProvider);
                  },
                  child: const Text('Eliminar'),
                ),
              ],
            ),
          );
        },
      ),
      loading: () => const LoadingView(),
      error: (error, _) => ErrorView(
        message: error is ApiException ? error.message : 'Error al cargar usuarios.',
        onRetry: () => ref.refresh(adminUsersProvider),
      ),
    );
  }
}

class _RobotsTab extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final robotsAsync = ref.watch(adminRobotsProvider);

    return robotsAsync.when(
      data: (robots) => ListView.separated(
        padding: const EdgeInsets.all(16),
        itemCount: robots.length,
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (context, index) {
          final robot = robots[index];
          return ShadCard(
            title: Text(robot.alias),
            description: Text('ID: ${robot.id}'),
            footer: Align(
              alignment: Alignment.centerRight,
              child: ShadButton.destructive(
                onPressed: () async {
                  await ref
                      .read(adminRepositoryProvider)
                      .deleteRobot(robot.id);
                  ref.refresh(adminRobotsProvider);
                },
                child: const Text('Eliminar'),
              ),
            ),
          );
        },
      ),
      loading: () => const LoadingView(),
      error: (error, _) => ErrorView(
        message: error is ApiException ? error.message : 'Error al cargar robots.',
        onRetry: () => ref.refresh(adminRobotsProvider),
      ),
    );
  }
}

class _IncidentsTab extends StatelessWidget {
  final TextEditingController controller;
  final List<Incident> incidents;
  final bool loading;
  final VoidCallback onLoad;

  const _IncidentsTab({
    required this.controller,
    required this.incidents,
    required this.loading,
    required this.onLoad,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          ShadInput(
            controller: controller,
            placeholder: const Text('Robot ID'),
            onSubmitted: (_) => onLoad(),
          ),
          const SizedBox(height: 12),
          ShadButton(
            onPressed: loading ? null : onLoad,
            child: Text(loading ? 'Cargando...' : 'Buscar incidencias'),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: incidents.isEmpty
                ? const Center(child: Text('Sin incidencias'))
                : ListView.separated(
                    itemCount: incidents.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 12),
                    itemBuilder: (context, index) {
                      final incident = incidents[index];
                      return ShadCard(
                        title: Text('Incidencia ${incident.id.substring(0, 8)}'),
                        description: Text('Robot: ${incident.robotId}'),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
