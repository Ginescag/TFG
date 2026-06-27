import 'package:flutter/material.dart';

/// Punto de color que refleja el estado de conexión real del robot
/// (verde = online, gris = offline). Es estado semántico, no decoración.
class ConnectionDot extends StatelessWidget {
  final bool online;
  final double size;

  const ConnectionDot({super.key, required this.online, this.size = 10});

  @override
  Widget build(BuildContext context) {
    final color = online ? const Color(0xFF22C55E) : Colors.grey;
    return Tooltip(
      message: online ? 'Online' : 'Offline',
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      ),
    );
  }
}
