class Incident {
  final String id;
  final String robotId;
  final String? robotAlias;
  final bool revisado;
  final String? createdAt;

  Incident({
    required this.id,
    required this.robotId,
    required this.robotAlias,
    required this.revisado,
    required this.createdAt,
  });

  factory Incident.fromJson(Map<String, dynamic> json) {
    return Incident(
      id: json['id'] as String,
      robotId: json['robot_id'] as String,
      robotAlias: json['robot_alias'] as String?,
      revisado: json['revisado'] as bool? ?? false,
      createdAt: json['created_at'] as String?,
    );
  }
}
