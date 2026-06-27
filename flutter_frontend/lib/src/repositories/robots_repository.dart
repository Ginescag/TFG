import '../data/api_client.dart';
import '../models/robot.dart';

class RobotsRepository {
  RobotsRepository(this._api);

  final ApiClient _api;

  Future<List<Robot>> listRobots() async {
    final data = await _api.get<List<dynamic>>('/user/robots');
    return data
        .map((item) => Robot.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<Robot> addRobot({required String id, required String alias}) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/user/new-robot',
      data: {'id': id, 'alias': alias},
    );
    return Robot.fromJson(data);
  }

  Future<void> deleteRobot(String robotId) async {
    await _api.delete<Map<String, dynamic>>('/user/$robotId/delete');
  }

  Future<Robot> startPatrol(String robotId) async {
    final data = await _api.put<Map<String, dynamic>>(
      '/user/$robotId/start-patrol',
    );
    return Robot.fromJson(data);
  }

  Future<Robot> stopPatrol(String robotId) async {
    final data = await _api.put<Map<String, dynamic>>(
      '/user/$robotId/stop-patrol',
    );
    return Robot.fromJson(data);
  }

  Future<String> getDashboardUrl(String robotId) async {
    final data = await _api.get<Map<String, dynamic>>(
      '/user/$robotId/dashboard-url',
    );
    return data['url'] as String;
  }

  Future<Robot> reinstall(String robotId) async {
    final data = await _api.put<Map<String, dynamic>>(
      '/user/$robotId/reinstall',
    );
    return Robot.fromJson(data);
  }

  Future<Robot> updateAlias(String robotId, String alias) async {
    final data = await _api.put<Map<String, dynamic>>(
      '/user/$robotId/alias',
      data: {'alias': alias},
    );
    return Robot.fromJson(data);
  }
}
