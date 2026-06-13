import '../data/api_client.dart';
import '../models/incident.dart';
import '../models/robot.dart';
import '../models/user.dart';

class AdminRepository {
  AdminRepository(this._api);

  final ApiClient _api;

  Future<List<User>> listUsers() async {
    final data = await _api.get<List<dynamic>>('/admin/users');
    return data.map((item) => User.fromJson(item as Map<String, dynamic>)).toList();
  }

  Future<List<Robot>> listRobots() async {
    final data = await _api.get<List<dynamic>>('/admin/robots');
    return data.map((item) => Robot.fromJson(item as Map<String, dynamic>)).toList();
  }

  Future<List<Incident>> listRobotIncidents(String robotId) async {
    final data = await _api.get<List<dynamic>>('/admin/robots/$robotId/incidents');
    return data.map((item) => Incident.fromJson(item as Map<String, dynamic>)).toList();
  }

  Future<User> grantAdmin(int userId) async {
    final data = await _api.put<Map<String, dynamic>>('/admin/users/$userId/grant');
    return User.fromJson(data);
  }

  Future<User> revokeAdmin(int userId) async {
    final data = await _api.put<Map<String, dynamic>>('/admin/users/$userId/revoke');
    return User.fromJson(data);
  }

  Future<void> deleteUser(int userId) async {
    await _api.delete<Map<String, dynamic>>('/admin/users/$userId/delete');
  }

  Future<void> deleteRobot(String robotId) async {
    await _api.delete<Map<String, dynamic>>('/admin/robots/$robotId/delete');
  }
}
