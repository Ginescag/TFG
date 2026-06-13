import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shadcn_ui/shadcn_ui.dart';

import '../../data/api_exception.dart';
import '../../models/robot.dart';
import '../../providers.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/error_view.dart';
import '../../widgets/loading_view.dart';

class RobotsScreen extends ConsumerWidget {
  const RobotsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final robotsAsync = ref.watch(robotsControllerProvider);
    final titleStyle = Theme.of(context).textTheme.headlineSmall;

    return Scaffold(
      drawer: const AppDrawer(),
      appBar: AppBar(
        centerTitle: true,
        title: Text('Robots', style: titleStyle),
      ),
      body: robotsAsync.when(
        data: (robots) => _RobotsList(robots: robots),
        loading: () => const LoadingView(),
        error: (error, _) => ErrorView(
          message: _mapError(error),
          onRetry: () => ref.read(robotsControllerProvider.notifier).refresh(),
        ),
      ),
      bottomNavigationBar: Padding(
        padding: const EdgeInsets.all(16),
        child: ShadButton(
          onPressed: () => _showAddRobotDialog(context, ref),
          child: const Text('Add robot'),
        ),
      ),
    );
  }

  String _mapError(Object error) {
    if (error is ApiException) return error.message;
    return 'Failed to load the robots.';
  }

  Future<void> _showAddRobotDialog(BuildContext context, WidgetRef ref) async {
    final idController = TextEditingController();
    final aliasController = TextEditingController();

    await showShadDialog<void>(
      context: context,
      builder: (context) => ShadDialog(
        title: const Text('Nuevo robot'),
        description: const Text('Register the robot with its ID and an alias.'),
        actions: [
          ShadButton.outline(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ShadButton(
            onPressed: () async {
              final id = idController.text.trim();
              final alias = aliasController.text.trim();
              if (id.isEmpty || alias.isEmpty) return;
              await ref
                  .read(robotsControllerProvider.notifier)
                  .addRobot(id: id, alias: alias);
              if (context.mounted) Navigator.pop(context);
            },
            child: const Text('Save'),
          ),
        ],
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ShadInput(
                controller: idController,
                placeholder: const Text('Robot ID (QR)'),
              ),
              const SizedBox(height: 12),
              ShadInput(
                controller: aliasController,
                placeholder: const Text('Alias'),
              ),
              const SizedBox(height: 12),
              ShadButton.outline(
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('QR Scan pending')),
                  );
                },
                child: const Text('Scan QR'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RobotsList extends ConsumerWidget {
  final List<Robot> robots;

  const _RobotsList({required this.robots});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (robots.isEmpty) {
      return const Center(
        child: Text(
          'No robots registered.\nPress the + button to add one.',
          textAlign: TextAlign.center,
        ),
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: robots.length,
      separatorBuilder: (_, __) => const SizedBox(height: 16),
      itemBuilder: (context, index) {
        final robot = robots[index];
        return ShadCard(
          title: Text(robot.alias),
          description: Text('ID: ${robot.id}'),
          footer: Row(
            children: [
              ShadIconButton.outline(
                icon: const Icon(Icons.edit),
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Edit alias pending')),
                  );
                },
              ),
              const SizedBox(width: 8),
              ShadIconButton.outline(
                icon: const Icon(Icons.settings_backup_restore),
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Reinstall pending')),
                  );
                },
              ),
              const Spacer(),
              ShadIconButton.destructive(
                icon: const Icon(Icons.delete_outline),
                onPressed: () async {
                  await ref
                      .read(robotsControllerProvider.notifier)
                      .deleteRobot(robot.id);
                },
              ),
            ],
          ),
        );
      },
    );
  }
}
