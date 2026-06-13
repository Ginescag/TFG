import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shadcn_ui/shadcn_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../data/api_exception.dart';
import '../../providers.dart';
import '../../widgets/error_view.dart';
import '../../widgets/loading_view.dart';

final incidentVideoUrlProvider = FutureProvider.family<String, String>((ref, id) {
  return ref.read(incidentsRepositoryProvider).getVideoUrl(id);
});

class IncidentDetailScreen extends ConsumerWidget {
  final String incidentId;

  const IncidentDetailScreen({super.key, required this.incidentId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final urlAsync = ref.watch(incidentVideoUrlProvider(incidentId));
    final titleStyle = Theme.of(context).textTheme.headlineSmall;

    return Scaffold(
      appBar: AppBar(
        centerTitle: true,
        title: Text('Incident Detail', style: titleStyle),
      ),
      body: urlAsync.when(
        data: (url) => _DetailBody(url: url),
        loading: () => const LoadingView(),
        error: (error, _) => ErrorView(
          message: _mapError(error),
          onRetry: () => ref.refresh(incidentVideoUrlProvider(incidentId)),
        ),
      ),
    );
  }

  String _mapError(Object error) {
    if (error is ApiException) return error.message;
    return 'Failed to load the video.';
  }
}

class _DetailBody extends StatelessWidget {
  final String url;

  const _DetailBody({required this.url});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: ShadCard(
        title: const Text('Video Clip'),
        description: const Text('Open the clip in an external window.'),
        footer: Row(
          children: [
            ShadButton(
              onPressed: () async {
                final uri = Uri.parse(url);
                if (await canLaunchUrl(uri)) {
                  await launchUrl(uri, mode: LaunchMode.externalApplication);
                } else {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Failed to open the video.'),
                    ),
                  );
                }
              },
              child: const Text('View video'),
            ),
            const SizedBox(width: 12),
            ShadButton.outline(
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Alert to the police pending'),
                  ),
                );
              },
              child: const Text('Notify the police'),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: SelectableText(url),
        ),
      ),
    );
  }
}
