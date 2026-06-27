import 'package:flutter/material.dart';
import 'package:shadcn_ui/shadcn_ui.dart';

class ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;

  const ErrorView({super.key, required this.message, this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ShadCard(
        title: const Text('Error'),
        description: Text(message, textAlign: TextAlign.center),
        footer: onRetry == null
            ? null
            : ShadButton(onPressed: onRetry, child: const Text('Reintentar')),
      ),
    );
  }
}
