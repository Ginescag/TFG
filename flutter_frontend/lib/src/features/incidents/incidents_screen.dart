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
        child: Text(
          'No incidents registered.',
          textAlign: TextAlign.center,
        ),
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: incidents.length,
      separatorBuilder: (_, __) => const SizedBox(height: 16),
      itemBuilder: (context, index) {
        final incident = incidents[index];
        return ShadCard(
          title: Text('Incident ${incident.id.substring(0, 8)}'),
          description: Text('Robot: ${incident.robotId}'),
          footer: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              ShadBadge.outline(
                child: Text(_formatDate(incident.createdAt)),
              ),
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
