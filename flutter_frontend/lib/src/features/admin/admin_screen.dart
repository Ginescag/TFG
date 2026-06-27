import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
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
      _showMessage('Could not load incidents.');
    } finally {
      setState(() => _loadingIncidents = false);
    }
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final baseTitle = Theme.of(context).textTheme.titleSmall;
    final titleStyle = baseTitle?.copyWith(
      fontSize: (baseTitle.fontSize ?? 14) - 1,
    );

    return Scaffold(
      drawer: const AppDrawer(),
      appBar: AppBar(
        centerTitle: true,
        title: Text(
          'Admin',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: ShadTabs<String>(
          value: _activeTab,
          onChanged: (value) => setState(() => _activeTab = value),
          tabBarAlignment: Alignment.center,
          tabBarConstraints: const BoxConstraints(maxWidth: 520),
          tabs: [
            ShadTab(
              value: 'users',
              mainAxisAlignment: MainAxisAlignment.center,
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
              content: _UsersTab(),
              child: Text('Users', style: titleStyle),
            ),
            ShadTab(
              value: 'robots',
              mainAxisAlignment: MainAxisAlignment.center,
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
              content: _RobotsTab(),
              child: Text('Robots', style: titleStyle),
            ),
            ShadTab(
              value: 'incidents',
              mainAxisAlignment: MainAxisAlignment.center,
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
              content: _IncidentsTab(
                controller: _robotIdController,
                incidents: _robotIncidents,
                loading: _loadingIncidents,
                onLoad: _loadIncidents,
              ),
              child: Text('Incidents', style: titleStyle),
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
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        itemCount: users.length,
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (context, index) {
          final user = users[index];
          return ShadCard(
            title: Text(user.nombre),
            description: Text(user.email),
            footer: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ShadButton.outline(
                  width: double.infinity,
                  onPressed: () async {
                    await ref.read(adminRepositoryProvider).grantAdmin(user.id);
                    ref.refresh(adminUsersProvider);
                  },
                  child: const Text('Grant admin'),
                ),
                const SizedBox(height: 8),
                ShadButton.outline(
                  width: double.infinity,
                  onPressed: () async {
                    await ref
                        .read(adminRepositoryProvider)
                        .revokeAdmin(user.id);
                    ref.refresh(adminUsersProvider);
                  },
                  child: const Text('Revoke admin'),
                ),
                const SizedBox(height: 8),
                ShadButton.destructive(
                  width: double.infinity,
                  onPressed: () async {
                    await ref.read(adminRepositoryProvider).deleteUser(user.id);
                    ref.refresh(adminUsersProvider);
                  },
                  child: const Text('Delete'),
                ),
              ],
            ),
          );
        },
      ),
      loading: () => const LoadingView(),
      error: (error, _) => ErrorView(
        message: error is ApiException
            ? error.message
            : 'Error al cargar usuarios.',
        onRetry: () => ref.refresh(adminUsersProvider),
      ),
    );
  }
}

class _RobotsTab extends ConsumerStatefulWidget {
  @override
  ConsumerState<_RobotsTab> createState() => _RobotsTabState();
}

class _RobotsTabState extends ConsumerState<_RobotsTab> {
  final _searchController = TextEditingController();
  String _query = '';

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final robotsAsync = ref.watch(adminRobotsProvider);

    return robotsAsync.when(
      data: (robots) {
        final q = _query.trim().toLowerCase();
        final filtered = q.isEmpty
            ? robots
            : robots
                  .where(
                    (r) =>
                        r.alias.toLowerCase().contains(q) ||
                        r.id.toLowerCase().contains(q),
                  )
                  .toList();

        return Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ShadInput(
                controller: _searchController,
                placeholder: const Text('Search robot...'),
                onChanged: (value) => setState(() => _query = value),
              ),
              const SizedBox(height: 12),
              if (filtered.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 24),
                  child: Center(child: Text('No robots found')),
                )
              else
                ListView.separated(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: filtered.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
                  itemBuilder: (context, index) {
                    final robot = filtered[index];
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
                          child: const Text('Delete'),
                        ),
                      ),
                    );
                  },
                ),
            ],
          ),
        );
      },
      loading: () => const LoadingView(),
      error: (error, _) => ErrorView(
        message: error is ApiException
            ? error.message
            : 'Error al cargar robots.',
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
        mainAxisSize: MainAxisSize.min,
        children: [
          ShadInput(
            controller: controller,
            placeholder: const Text('Robot ID'),
            onSubmitted: (_) => onLoad(),
          ),
          const SizedBox(height: 12),
          ShadButton(
            onPressed: loading ? null : onLoad,
            child: Text(loading ? 'Loading...' : 'Search incidents'),
          ),
          const SizedBox(height: 12),
          if (incidents.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: Center(child: Text('No incidents')),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: incidents.length,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final incident = incidents[index];
                final alias = incident.robotAlias;
                final robotLabel = (alias == null || alias.isEmpty)
                    ? incident.robotId
                    : '$alias (${incident.robotId})';
                return ShadCard(
                  title: Text(
                    'Incidencia ${incident.id.substring(0, 8)}',
                  ),
                  description: Text('Robot: $robotLabel'),
                  footer: Align(
                    alignment: Alignment.centerRight,
                    child: ShadButton.outline(
                      onPressed: () => context.go(
                        '/admin/incidents/${incident.id}',
                        extra: incident,
                      ),
                      child: const Text('View details'),
                    ),
                  ),
                );
              },
            ),
        ],
      ),
    );
  }
}
