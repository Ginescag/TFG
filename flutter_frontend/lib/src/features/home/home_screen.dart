import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shadcn_ui/shadcn_ui.dart';

import '../../data/api_exception.dart';
import '../../models/robot.dart';
import '../../providers.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/connection_dot.dart';
import '../../widgets/error_view.dart';
import '../../widgets/loading_view.dart';

/// Estados en los que el robot está "activo" (el switch se muestra ON).
const _activeStates = {'exploring', 'saving_map', 'planning', 'patrolling'};

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
              themeMode == ThemeMode.dark ? Icons.dark_mode : Icons.light_mode,
            ),
            onPressed: () =>
                ref.read(themeControllerProvider.notifier).toggle(),
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
  Timer? _pollTimer;

  /// Robots con una llamada de patrulla en curso (muestran spinner).
  final Set<String> _pending = {};

  @override
  void initState() {
    super.initState();
    // Al montar ya tenemos datos frescos del robot.
    _lastUpdate = DateTime.now();
    // Refresco en segundo plano para reflejar el estado real (heartbeat) del robot.
    _pollTimer = Timer.periodic(const Duration(seconds: 5), (_) async {
      final ok = await ref
          .read(robotsControllerProvider.notifier)
          .silentRefresh();
      if (ok && mounted) {
        setState(() => _lastUpdate = DateTime.now());
      }
    });
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

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

    // Aviso cuando un robot pasa a 'patrolling': ya se puede detener.
    ref.listen<AsyncValue<List<Robot>>>(robotsControllerProvider, (prev, next) {
      final before = prev?.valueOrNull ?? const <Robot>[];
      final after = next.valueOrNull ?? const <Robot>[];
      for (final r in after) {
        Robot? old;
        for (final b in before) {
          if (b.id == r.id) {
            old = b;
            break;
          }
        }
        if (old != null &&
            old.estadoOperativo != 'patrolling' &&
            r.estadoOperativo == 'patrolling') {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                '${r.alias} ya está patrullando: ahora puedes detenerlo.',
              ),
            ),
          );
        }
      }
    });

    // Indicador de armado: todo / nada / parcial sobre los estados activos.
    final activeCount = robots
        .where((r) => _activeStates.contains(r.estadoOperativo))
        .length;
    final desarmadoActive = robots.isNotEmpty && activeCount == 0;
    final armadoActive = robots.isNotEmpty && activeCount == robots.length;
    // Estado parcial (0 < activeCount < total): ninguno encendido (ambos outline).

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 640),
        child: Padding(
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
                          final isActive = _activeStates.contains(
                            robot.estadoOperativo,
                          );
                          final isPatrolling =
                              robot.estadoOperativo == 'patrolling';
                          final hint = isPatrolling
                              ? 'Patrullando · puedes detenerlo'
                              : isActive
                              ? 'Preparando patrulla (mapeando) · no se puede detener todavía'
                              : 'En espera';
                          return ShadCard(
                            title: Row(
                              children: [
                                ConnectionDot(
                                  online: robot.estadoConexion == 'online',
                                ),
                                const SizedBox(width: 8),
                                Expanded(child: Text(robot.alias)),
                              ],
                            ),
                            description: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('Status: ${robot.estadoOperativo}'),
                                Text(
                                  hint,
                                  style: const TextStyle(fontSize: 12),
                                ),
                              ],
                            ),
                            footer: Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                ShadBadge(
                                  child: Text(
                                    isPatrolling
                                        ? 'PATROLLING'
                                        : isActive
                                        ? 'PREPARING'
                                        : 'ON HOLD',
                                  ),
                                ),
                                if (_pending.contains(robot.id))
                                  const SizedBox(
                                    width: 44,
                                    child: Center(
                                      child: SizedBox(
                                        width: 20,
                                        height: 20,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                        ),
                                      ),
                                    ),
                                  )
                                else
                                  ShadSwitch(
                                    value: isActive,
                                    onChanged: (value) async {
                                      setState(() => _pending.add(robot.id));
                                      try {
                                        await ref
                                            .read(
                                              robotsControllerProvider.notifier,
                                            )
                                            .setPatrol(
                                              robotId: robot.id,
                                              enable: value,
                                            );
                                        _registerToggle();
                                      } on ApiException catch (e) {
                                        if (!mounted) return;
                                        if (e.statusCode == 409) {
                                          showShadDialog(
                                            context: context,
                                            builder: (ctx) => ShadDialog.alert(
                                              title: const Text(
                                                'El robot aún no está listo',
                                              ),
                                              description: const Padding(
                                                padding: EdgeInsets.only(
                                                  bottom: 8,
                                                ),
                                                child: Text(
                                                  'El robot todavía está configurándose (mapeando). '
                                                  'No se puede detener hasta que esté patrullando.',
                                                ),
                                              ),
                                              actions: [
                                                ShadButton(
                                                  child: const Text(
                                                    'Entendido',
                                                  ),
                                                  onPressed: () =>
                                                      Navigator.of(ctx).pop(),
                                                ),
                                              ],
                                            ),
                                          );
                                        } else {
                                          ScaffoldMessenger.of(
                                            context,
                                          ).showSnackBar(
                                            SnackBar(content: Text(e.message)),
                                          );
                                        }
                                      } catch (e) {
                                        if (mounted) {
                                          ScaffoldMessenger.of(
                                            context,
                                          ).showSnackBar(
                                            SnackBar(
                                              content: Text('Error: $e'),
                                            ),
                                          );
                                        }
                                      } finally {
                                        if (mounted) {
                                          setState(
                                            () => _pending.remove(robot.id),
                                          );
                                        }
                                      }
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
        ),
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
