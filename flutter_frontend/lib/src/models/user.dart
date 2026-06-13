class User {
  final int id;
  final String nombre;
  final String email;
  final String? tlf;
  final String rol;

  User({
    required this.id,
    required this.nombre,
    required this.email,
    required this.tlf,
    required this.rol,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] as int,
      nombre: json['nombre'] as String,
      email: json['email'] as String,
      tlf: json['tlf'] as String?,
      rol: json['rol'] as String? ?? 'user',
    );
  }
}
