import '../data/api_client.dart';
import '../models/incident.dart';

class IncidentsRepository {
  IncidentsRepository(this._api);

  final ApiClient _api;

  Future<List<Incident>> listIncidents() async {
    final data = await _api.get<List<dynamic>>('/user/incidents');
    return data.map((item) => Incident.fromJson(item as Map<String, dynamic>)).toList();
  }

  Future<List<Incident>> listByRobot(String robotId) async {
    final data = await _api.get<List<dynamic>>('/user/$robotId/incidents');
    return data.map((item) => Incident.fromJson(item as Map<String, dynamic>)).toList();
  }

  Future<String> getVideoUrl(String incidentId) async {
    final data = await _api.get<Map<String, dynamic>>('/user/incidents/$incidentId/show-video');
    return data['video_url'] as String;
  }
}
