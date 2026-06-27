import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shadcn_ui/shadcn_ui.dart';

import '../../data/api_exception.dart';
import '../../models/incident.dart';
import '../../providers.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/error_view.dart';
import '../../widgets/loading_view.dart';

final incidentsProvider = FutureProvider<List<Incident>>((ref) {
  return ref.read(incidentsRepositoryProvider).listIncidents();
});

/// Localiza un incidente por id dentro de la lista ya cargada
/// (`incidentsProvider`), sin una llamada de red adicional. Devuelve `null`
/// si la lista aún no está disponible o el incidente no existe.
final incidentByIdProvider = Provider.family<Incident?, String>((ref, id) {
  final list = ref.watch(incidentsProvider).valueOrNull;
  if (list == null) return null;
  for (final incident in list) {
    if (incident.id == id) return incident;
  }
  return null;
});

class IncidentsScreen extends ConsumerWidget {
  const IncidentsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final incidentsAsync = ref.watch(incidentsProvider);
    final titleStyle = Theme.of(context).textTheme.headlineSmall;

    return Scaffold(
      drawer: const AppDrawer(),
      appBar: AppBar(
        centerTitle: true,
        title: Text('Incidents', style: titleStyle),
      ),
      body: incidentsAsync.when(
        data: (incidents) => _IncidentsList(incidents: incidents),
        loading: () => const LoadingView(),
        error: (error, _) => ErrorView(
          message: _mapError(error),
          onRetry: () => ref.refresh(incidentsProvider),
        ),
      ),
    );
  }

  String _mapError(Object error) {
    if (error is ApiException) return error.message;
    return 'Failed to load the incidents.';
  }
}

class _IncidentsList extends StatelessWidget {
  final List<Incident> incidents;

  const _IncidentsList({required this.incidents});

  @override
  Widget build(BuildContext context) {
    if (incidents.isEmpty) {
      return const Center(
        child: Text('No incidents registered.', textAlign: TextAlign.center),
      );
    }

    final accent = ShadTheme.of(context).colorScheme.primary;
    final muted = ShadTheme.of(context).colorScheme.mutedForeground;

    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: incidents.length,
      separatorBuilder: (_, _) => const SizedBox(height: 16),
      itemBuilder: (context, index) {
        final incident = incidents[index];
        return ShadCard(
          title: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Incident ${incident.id.substring(0, 8)}'),
              Text(
                incident.revisado ? 'CHECKED' : 'PENDING',
                style: TextStyle(
                  color: incident.revisado ? accent : muted,
                ),
              ),
            ],
          ),
          description: Text('Robot: ${_robotLabel(incident)}'),
          footer: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              ShadBadge.outline(child: Text(_formatDate(incident.createdAt))),
              ShadButton.outline(
                onPressed: () => context.go('/incidents/${incident.id}'),
                child: const Text('View details'),
              ),
            ],
          ),
        );
      },
    );
  }

  String _robotLabel(Incident incident) {
    final alias = incident.robotAlias;
    if (alias == null || alias.isEmpty) return incident.robotId;
    return '$alias (${incident.robotId})';
  }

  String _formatDate(String? raw) {
    if (raw == null) return 'Unknown date';
    try {
      final date = DateTime.parse(raw);
      return DateFormat('dd/MM/yyyy HH:mm').format(date.toLocal());
    } catch (_) {
      return raw;
    }
  }
}
