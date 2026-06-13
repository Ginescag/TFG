class Robot {
  final String id;
  final String alias;
  final String estadoConexion;
  final String estadoOperativo;

  Robot({
    required this.id,
    required this.alias,
    required this.estadoConexion,
    required this.estadoOperativo,
  });

  factory Robot.fromJson(Map<String, dynamic> json) {
    return Robot(
      id: json['id'] as String,
      alias: json['alias'] as String,
      estadoConexion: json['estado_conexion'] as String? ?? 'offline',
      estadoOperativo: json['estado_operativo'] as String? ?? 'idle',
    );
  }
}
