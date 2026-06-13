import 'package:shared_preferences/shared_preferences.dart';

class SessionData {
  final String token;
  final String role;
  final int userId;

  SessionData({
    required this.token,
    required this.role,
    required this.userId,
  });
}

class SessionStorage {
  static const _tokenKey = 'session_token';
  static const _roleKey = 'session_role';
  static const _userIdKey = 'session_user_id';

  Future<SessionData?> readSession() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString(_tokenKey);
    final role = prefs.getString(_roleKey);
    final userId = prefs.getInt(_userIdKey);
    if (token == null || role == null || userId == null) {
      return null;
    }
    return SessionData(token: token, role: role, userId: userId);
  }

  Future<void> saveSession(SessionData data) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, data.token);
    await prefs.setString(_roleKey, data.role);
    await prefs.setInt(_userIdKey, data.userId);
  }

  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
    await prefs.remove(_roleKey);
    await prefs.remove(_userIdKey);
  }
}
