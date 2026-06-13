import 'package:flutter/material.dart';
import 'package:shadcn_ui/shadcn_ui.dart';

class LoadingView extends StatelessWidget {
  final String message;

  const LoadingView({super.key, this.message = 'Cargando...'});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ShadCard(
        title: const Text('Cargando'),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            const CircularProgressIndicator(),
            const SizedBox(height: 12),
            Text(message),
          ],
        ),
      ),
    );
  }
}
