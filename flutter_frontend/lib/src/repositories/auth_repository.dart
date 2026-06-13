import '../data/api_client.dart';
import '../models/user.dart';

class AuthSession {
  final String token;
  final int userId;
  final String role;

  AuthSession({
    required this.token,
    required this.userId,
    required this.role,
  });
}

class AuthRepository {
  AuthRepository(this._api);

  final ApiClient _api;

  Future<User> register({
    required String nombre,
    required String email,
    required String password,
    String? tlf,
  }) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/user/register',
      data: {
        'nombre': nombre,
        'email': email,
        'password': password,
        'tlf': tlf,
      },
    );
    return User.fromJson(data);
  }

  Future<AuthSession> login({
    required String email,
    required String password,
  }) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/user/login',
      data: {
        'email': email,
        'password': password,
      },
    );
    return AuthSession(
      token: data['access_token'] as String,
      userId: data['user_id'] as int,
      role: data['rol'] as String? ?? 'user',
    );
  }
}
