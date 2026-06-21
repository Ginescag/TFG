import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/robot.dart';
import '../core/providers.dart';

class RobotsController extends AsyncNotifier<List<Robot>> {
  @override
  Future<List<Robot>> build() async {
    final repo = ref.read(robotsRepositoryProvider);
    return repo.listRobots();
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      final repo = ref.read(robotsRepositoryProvider);
      return repo.listRobots();
    });
  }

  /// Recarga la lista sin mostrar el spinner de carga (para polling en segundo
  /// plano). Si falla, mantiene los datos actuales en vez de pasar a error.
  Future<void> silentRefresh() async {
    final repo = ref.read(robotsRepositoryProvider);
    try {
      final robots = await repo.listRobots();
      state = AsyncData(robots);
    } catch (_) {
      // Ignorar fallos transitorios del refresco en segundo plano.
    }
  }

  Future<void> addRobot({required String id, required String alias}) async {
    final repo = ref.read(robotsRepositoryProvider);
    await repo.addRobot(id: id, alias: alias);
    await refresh();
  }

  Future<void> deleteRobot(String robotId) async {
    final repo = ref.read(robotsRepositoryProvider);
    await repo.deleteRobot(robotId);
    await refresh();
  }

  Future<void> setPatrol({required String robotId, required bool enable}) async {
    final repo = ref.read(robotsRepositoryProvider);
    if (enable) {
      await repo.startPatrol(robotId);
    } else {
      await repo.stopPatrol(robotId);
    }
    await silentRefresh();
  }

  Future<void> reinstall(String robotId) async {
    final repo = ref.read(robotsRepositoryProvider);
    await repo.reinstall(robotId);
    await refresh();
  }

  Future<void> updateAlias({required String robotId, required String alias}) async {
    final repo = ref.read(robotsRepositoryProvider);
    await repo.updateAlias(robotId, alias);
    await refresh();
  }
}
