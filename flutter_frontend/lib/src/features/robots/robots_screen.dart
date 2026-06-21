import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shadcn_ui/shadcn_ui.dart';
import 'package:url_launcher/url_launcher.dart';

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
                onPressed: () => _showEditAliasDialog(context, ref, robot),
              ),
              const SizedBox(width: 8),
              ShadIconButton.outline(
                icon: const Icon(Icons.settings_backup_restore),
                onPressed: () => _showReinstallDialog(context, ref, robot),
              ),
              const SizedBox(width: 8),
              ShadIconButton.outline(
                icon: const Icon(Icons.insights),
                onPressed: () async {
                  try {
                    final url = await ref
                        .read(robotsRepositoryProvider)
                        .getDashboardUrl(robot.id);
                    final ok = await launchUrl(
                      Uri.parse(url),
                      mode: LaunchMode.externalApplication,
                    );
                    if (!ok && context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('No se pudo abrir Grafana')),
                      );
                    }
                  } catch (e) {
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text('Error abriendo stats: $e')),
                      );
                    }
                  }
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

Future<void> _showEditAliasDialog(
    BuildContext context, WidgetRef ref, Robot robot) async {
  final aliasController = TextEditingController(text: robot.alias);
  await showShadDialog<void>(
    context: context,
    builder: (context) => ShadDialog(
      title: const Text('Editar alias'),
      description: Text('Robot ${robot.id}'),
      actions: [
        ShadButton.outline(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ShadButton(
          onPressed: () async {
            final alias = aliasController.text.trim();
            if (alias.isEmpty) return;
            await ref
                .read(robotsControllerProvider.notifier)
                .updateAlias(robotId: robot.id, alias: alias);
            if (context.mounted) Navigator.pop(context);
          },
          child: const Text('Save'),
        ),
      ],
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 16),
        child: ShadInput(
          controller: aliasController,
          placeholder: const Text('Alias'),
        ),
      ),
    ),
  );
}

Future<void> _showReinstallDialog(
    BuildContext context, WidgetRef ref, Robot robot) async {
  await showShadDialog<void>(
    context: context,
    builder: (context) => ShadDialog.alert(
      title: const Text('Reinstalar robot'),
      description: const Padding(
        padding: EdgeInsets.only(bottom: 8),
        child: Text(
          'Esto borrará el mapa actual y reiniciará el ciclo: el robot volverá a '
          '"idle" y mapeará de nuevo. Úsalo si cambias el robot de sitio. ¿Continuar?',
        ),
      ),
      actions: [
        ShadButton.outline(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ShadButton.destructive(
          onPressed: () async {
            await ref
                .read(robotsControllerProvider.notifier)
                .reinstall(robot.id);
            if (context.mounted) Navigator.pop(context);
          },
          child: const Text('Reinstalar'),
        ),
      ],
    ),
  );
}
