import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shadcn_ui/shadcn_ui.dart';

import '../../data/api_exception.dart';
import '../../models/robot.dart';
import '../../providers.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/error_view.dart';
import '../../widgets/loading_view.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final robotsAsync = ref.watch(robotsControllerProvider);
    final themeMode = ref.watch(themeControllerProvider);
    final titleStyle = Theme.of(context).textTheme.headlineSmall;

    return Scaffold(
      drawer: const AppDrawer(),
      appBar: AppBar(
        centerTitle: true,
        title: Text('WARDEN', style: titleStyle),
        actions: [
          ShadIconButton.outline(
            icon: const Icon(Icons.help_outline),
            onPressed: () => _showHelpDialog(context),
          ),
          ShadIconButton.outline(
            icon: Icon(
              themeMode == ThemeMode.dark
                  ? Icons.dark_mode
                  : Icons.light_mode,
            ),
            onPressed: () => ref.read(themeControllerProvider.notifier).toggle(),
          ),
        ],
      ),
      body: robotsAsync.when(
        data: (robots) => _HomeBody(robots: robots),
        loading: () => const LoadingView(),
        error: (error, _) => ErrorView(
          message: _mapError(error),
          onRetry: () => ref.read(robotsControllerProvider.notifier).refresh(),
        ),
      ),
    );
  }

  String _mapError(Object error) {
    if (error is ApiException) {
      return error.message;
    }
    return 'Failed to load robots.';
  }

  void _showHelpDialog(BuildContext context) {
    showShadDialog(
      context: context,
      builder: (context) => ShadDialog.alert(
        title: const Text('How to use the app'),
        description: const Padding(
          padding: EdgeInsets.only(bottom: 8),
          child: Text(
            '• Use the switch of each robot to start or stop the patrol.\n'
            '• The sidebar gives you access to robots, incidents and profile.\n'
            '• The light/dark mode can be toggled from the top bar.',
          ),
        ),
        actions: [
          ShadButton.outline(
            child: const Text('Close'),
            onPressed: () => Navigator.of(context).pop(),
          ),
        ],
      ),
    );
  }
}

class _HomeBody extends ConsumerStatefulWidget {
  final List<Robot> robots;

  const _HomeBody({required this.robots});

  @override
  ConsumerState<_HomeBody> createState() => _HomeBodyState();
}

class _HomeBodyState extends ConsumerState<_HomeBody> {
  DateTime? _lastUpdate;

  void _registerToggle() {
    if (!mounted) return;
    setState(() {
      _lastUpdate = DateTime.now();
    });
  }

  String _lastUpdateText() {
    if (_lastUpdate == null) return 'Never updated';
    final diff = DateTime.now().difference(_lastUpdate!);
    final seconds = diff.inSeconds;
    if (seconds < 60) return 'updated $seconds seconds ago';
    final minutes = diff.inMinutes;
    return 'updated $minutes minutes ago';
  }

  @override
  Widget build(BuildContext context) {
    final robots = widget.robots;

    bool desarmadoActive;
    bool armadoActive;

    if (robots.isEmpty) {
      desarmadoActive = false;
      armadoActive = false;
    } else if (robots.length == 1) {
      final isOn = robots[0].estadoOperativo == 'patrolling';
      desarmadoActive = !isOn;
      armadoActive = isOn;
    } else {
      desarmadoActive = true;
      armadoActive = true;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      child: Column(
        children: [
          const SizedBox(height: 24),
          AlarmStatusRow(
            desarmadoActive: desarmadoActive,
            armadoActive: armadoActive,
          ),
          const SizedBox(height: 40),
          Expanded(
            child: robots.isEmpty
                ? const Center(
                    child: Text(
                      'No robots available for patrolling.\n'
                      'Go to the robots view to add one.',
                      textAlign: TextAlign.center,
                    ),
                  )
                : ListView.separated(
                    itemCount: robots.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 24),
                    itemBuilder: (context, index) {
                      final robot = robots[index];
                      final isPatrolling = robot.estadoOperativo == 'patrolling';
                      return ShadCard(
                        title: Text(robot.alias),
                        description: Text('Status: ${robot.estadoOperativo}'),
                        footer: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            ShadBadge(
                              child: Text(
                                isPatrolling ? 'PATROLING' : 'ON HOLD',
                              ),
                            ),
                            ShadSwitch(
                              value: isPatrolling,
                              onChanged: (value) async {
                                await ref
                                    .read(robotsControllerProvider.notifier)
                                    .setPatrol(
                                      robotId: robot.id,
                                      enable: value,
                                    );
                                _registerToggle();
                              },
                            ),
                          ],
                        ),
                      );
                    },
                  ),
          ),
          Align(
            alignment: Alignment.bottomLeft,
            child: Text(
              'Last status update: ${_lastUpdateText()}',
              style: const TextStyle(fontSize: 14),
            ),
          ),
        ],
      ),
    );
  }
}

class AlarmStatusRow extends StatelessWidget {
  final bool desarmadoActive;
  final bool armadoActive;

  const AlarmStatusRow({
    super.key,
    required this.desarmadoActive,
    required this.armadoActive,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: [
        AlarmStateItem(
          icon: Icons.lock_open,
          label: 'DISARMED',
          active: desarmadoActive,
        ),
        AlarmStateItem(
          icon: Icons.lock,
          label: 'SECURED',
          active: armadoActive,
        ),
      ],
    );
  }
}

class AlarmStateItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool active;

  const AlarmStateItem({
    super.key,
    required this.icon,
    required this.label,
    required this.active,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 40),
        const SizedBox(height: 8),
        active
            ? ShadBadge(child: Text(label))
            : ShadBadge.outline(child: Text(label)),
      ],
    );
  }
}
