import '../data/api_client.dart';
import '../models/user.dart';

class UserRepository {
  UserRepository(this._api);

  final ApiClient _api;

  Future<User> getProfile() async {
    final data = await _api.get<Map<String, dynamic>>('/user/profile');
    return User.fromJson(data);
  }

  Future<User> updateInfo({
    required String nombre,
    required String email,
    required String password,
    String? tlf,
  }) async {
    final data = await _api.put<Map<String, dynamic>>(
      '/user/update-info',
      data: {
        'nombre': nombre,
        'email': email,
        'password': password,
        'tlf': tlf,
      },
    );
    return User.fromJson(data);
  }

  Future<User> updatePassword({
    required String oldPassword,
    required String newPassword,
  }) async {
    final data = await _api.put<Map<String, dynamic>>(
      '/user/update-password',
      data: {
        'oldPassword': oldPassword,
        'newPassword': newPassword,
      },
    );
    return User.fromJson(data);
  }
}
