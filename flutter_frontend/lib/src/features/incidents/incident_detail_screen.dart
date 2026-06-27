import 'package:chewie/chewie.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shadcn_ui/shadcn_ui.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:video_player/video_player.dart';

import '../../data/api_exception.dart';
import '../../models/incident.dart';
import '../../providers.dart';
import '../../widgets/error_view.dart';
import '../../widgets/loading_view.dart';
import 'incidents_screen.dart';

/// Número marcado por el botón "Notify the police" (emergencias, España/UE).
const String _policePhoneNumber = '112';

final incidentVideoUrlProvider = FutureProvider.family<String, String>((
  ref,
  id,
) {
  return ref.read(incidentsRepositoryProvider).getVideoUrl(id);
});

/// Versión admin: usa el endpoint admin del vídeo (sin filtro de propietario),
/// para que el admin pueda ver el clip de incidencias de cualquier robot.
final adminIncidentVideoUrlProvider = FutureProvider.family<String, String>((
  ref,
  id,
) {
  return ref.read(adminRepositoryProvider).getIncidentVideoUrl(id);
});

/// Trae los detalles frescos de una incidencia (incluido `revisado`) con un GET.
/// Usa el endpoint admin o el de usuario segun el flag `admin`.
final incidentDetailProvider =
    FutureProvider.family<Incident, ({String id, bool admin})>((ref, args) {
      if (args.admin) {
        return ref.read(adminRepositoryProvider).getIncident(args.id);
      }
      return ref.read(incidentsRepositoryProvider).getIncident(args.id);
    });

class IncidentDetailScreen extends ConsumerWidget {
  final String incidentId;

  /// Incidencia ya cargada (la pasa el admin vía `extra`). Si es null, se busca
  /// en la lista de incidencias del usuario (`incidentByIdProvider`).
  final Incident? incident;

  /// En modo admin se usa el endpoint admin del vídeo.
  final bool admin;

  const IncidentDetailScreen({
    super.key,
    required this.incidentId,
    this.incident,
    this.admin = false,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final videoProvider = admin
        ? adminIncidentVideoUrlProvider(incidentId)
        : incidentVideoUrlProvider(incidentId);
    final urlAsync = ref.watch(videoProvider);
    final detailAsync = ref.watch(
      incidentDetailProvider((id: incidentId, admin: admin)),
    );
    final resolvedIncident =
        detailAsync.valueOrNull ??
        incident ??
        ref.watch(incidentByIdProvider(incidentId));
    final titleStyle = Theme.of(context).textTheme.headlineSmall;

    return Scaffold(
      appBar: AppBar(
        centerTitle: true,
        title: Text('Incident details', style: titleStyle),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _MetadataCard(
              incidentId: incidentId,
              incident: resolvedIncident,
              admin: admin,
            ),
            const SizedBox(height: 16),
            _VideoCard(
              urlAsync: urlAsync,
              onRetry: () => ref.refresh(videoProvider),
            ),
          ],
        ),
      ),
    );
  }
}

class _MetadataCard extends ConsumerStatefulWidget {
  final String incidentId;
  final Incident? incident;
  final bool admin;

  const _MetadataCard({
    required this.incidentId,
    required this.incident,
    required this.admin,
  });

  @override
  ConsumerState<_MetadataCard> createState() => _MetadataCardState();
}

class _MetadataCardState extends ConsumerState<_MetadataCard> {
  bool _marking = false;

  Future<void> _markChecked() async {
    setState(() => _marking = true);
    try {
      if (widget.admin) {
        await ref.read(adminRepositoryProvider).markReviewed(widget.incidentId);
      } else {
        await ref
            .read(incidentsRepositoryProvider)
            .markReviewed(widget.incidentId);
      }
      ref.invalidate(
        incidentDetailProvider((id: widget.incidentId, admin: widget.admin)),
      );
      if (!widget.admin) ref.invalidate(incidentsProvider);
    } on ApiException catch (e) {
      _showMessage(e.message);
    } catch (_) {
      _showMessage('Could not update the incident.');
    } finally {
      if (mounted) setState(() => _marking = false);
    }
  }

  void _showMessage(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final incident = widget.incident;
    final reviewed = incident?.revisado ?? false;
    final accent = ShadTheme.of(context).colorScheme.primary;

    return ShadCard(
      title: const Text('Incident'),
      footer: (incident != null && !reviewed)
          ? ShadButton(
              onPressed: _marking ? null : _markChecked,
              child: Text(_marking ? 'Updating...' : 'Mark as checked'),
            )
          : null,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _MetaRow(label: 'ID', value: widget.incidentId, selectable: true),
            const SizedBox(height: 8),
            _MetaRow(label: 'Robot', value: incident?.robotAlias ?? '—'),
            const SizedBox(height: 8),
            _MetaRow(label: 'Robot ID', value: incident?.robotId ?? '—'),
            const SizedBox(height: 8),
            _MetaRow(label: 'Date', value: _formatDate(incident?.createdAt)),
            const SizedBox(height: 8),
            _MetaRow(
              label: 'Status',
              value: incident == null
                  ? '—'
                  : (reviewed ? 'Checked' : 'Pending'),
              valueColor: reviewed ? accent : null,
              bold: reviewed,
            ),
          ],
        ),
      ),
    );
  }
}

class _MetaRow extends StatelessWidget {
  final String label;
  final String value;
  final bool selectable;
  final Color? valueColor;
  final bool bold;

  const _MetaRow({
    required this.label,
    required this.value,
    this.selectable = false,
    this.valueColor,
    this.bold = false,
  });

  @override
  Widget build(BuildContext context) {
    final labelStyle = Theme.of(
      context,
    ).textTheme.bodySmall?.copyWith(fontWeight: FontWeight.bold);

    final valueStyle = (valueColor != null || bold)
        ? TextStyle(
            color: valueColor,
            fontWeight: bold ? FontWeight.bold : null,
          )
        : null;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(width: 64, child: Text(label, style: labelStyle)),
        const SizedBox(width: 12),
        Expanded(
          child: selectable
              ? SelectableText(value)
              : Text(value, style: valueStyle),
        ),
      ],
    );
  }
}

class _VideoCard extends StatelessWidget {
  final AsyncValue<String> urlAsync;
  final VoidCallback onRetry;

  const _VideoCard({required this.urlAsync, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    final url = urlAsync.valueOrNull;

    return ShadCard(
      title: const Text('Video clip'),
      footer: Row(
        children: [
          ShadButton(
            onPressed: () => _notifyPolice(context),
            child: const Text('Notify the police'),
          ),
          if (url != null) ...[
            const SizedBox(width: 12),
            ShadButton.outline(
              onPressed: () => _openExternal(context, url),
              child: const Text('Open in browser'),
            ),
          ],
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: urlAsync.when(
          data: (url) => _IncidentVideoPlayer(url: url),
          loading: () => const SizedBox(height: 180, child: LoadingView()),
          error: (error, _) =>
              ErrorView(message: _mapError(error), onRetry: onRetry),
        ),
      ),
    );
  }

  Future<void> _notifyPolice(BuildContext context) async {
    final messenger = ScaffoldMessenger.of(context);
    final uri = Uri(scheme: 'tel', path: _policePhoneNumber);
    try {
      final launched = await launchUrl(
        uri,
        mode: LaunchMode.externalApplication,
      );
      if (launched) return;
    } catch (_) {}
    messenger.showSnackBar(
      const SnackBar(
        content: Text('Could not open the phone dialer for $_policePhoneNumber.'),
      ),
    );
  }

  Future<void> _openExternal(BuildContext context, String url) async {
    final messenger = ScaffoldMessenger.of(context);
    final uri = Uri.parse(url);
    try {
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
        return;
      }
    } catch (_) {}
    messenger.showSnackBar(
      const SnackBar(content: Text('Failed to open the video.')),
    );
  }
}

/// Reproductor de vídeo incrustado (video_player + chewie). Carga la URL
/// prefirmada de MinIO y la reproduce dentro de la app, con un spinner
/// centrado mientras inicializa.
class _IncidentVideoPlayer extends StatefulWidget {
  final String url;

  const _IncidentVideoPlayer({required this.url});

  @override
  State<_IncidentVideoPlayer> createState() => _IncidentVideoPlayerState();
}

class _IncidentVideoPlayerState extends State<_IncidentVideoPlayer> {
  VideoPlayerController? _videoController;
  ChewieController? _chewieController;
  double _aspectRatio = 16 / 9;
  bool _initializing = true;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _setup();
  }

  Future<void> _setup() async {
    final videoController = VideoPlayerController.networkUrl(
      Uri.parse(widget.url),
    );
    _videoController = videoController;
    try {
      await videoController.initialize();
      if (!mounted) return;
      final ratio = videoController.value.aspectRatio;
      _aspectRatio = (ratio.isFinite && ratio > 0) ? ratio : 16 / 9;
      _chewieController = ChewieController(
        videoPlayerController: videoController,
        autoPlay: false,
        looping: false,
        aspectRatio: _aspectRatio,
        allowFullScreen: true,
        allowMuting: true,
      );
      setState(() => _initializing = false);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _failed = true;
        _initializing = false;
      });
    }
  }

  @override
  void didUpdateWidget(covariant _IncidentVideoPlayer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.url != widget.url) {
      _disposeControllers();
      setState(() {
        _initializing = true;
        _failed = false;
      });
      _setup();
    }
  }

  void _disposeControllers() {
    _chewieController?.dispose();
    _videoController?.dispose();
    _chewieController = null;
    _videoController = null;
  }

  @override
  void dispose() {
    _disposeControllers();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_initializing) {
      return const AspectRatio(
        aspectRatio: 16 / 9,
        child: Center(child: CircularProgressIndicator()),
      );
    }

    if (_failed || _chewieController == null) {
      return const AspectRatio(
        aspectRatio: 16 / 9,
        child: Center(
          child: Text(
            'Could not load the video preview.\nUse "Open in browser".',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    return AspectRatio(
      aspectRatio: _aspectRatio,
      child: Chewie(controller: _chewieController!),
    );
  }
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

String _mapError(Object error) {
  if (error is ApiException) return error.message;
  return 'Failed to load the video.';
}
