import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/api_client.dart';
import '../repositories/admin_repository.dart';
import '../repositories/auth_repository.dart';
import '../repositories/incidents_repository.dart';
import '../repositories/robots_repository.dart';
import '../repositories/user_repository.dart';
import '../storage/session_storage.dart';

final sessionStorageProvider = Provider<SessionStorage>((ref) {
  return SessionStorage();
});

final apiClientProvider = Provider<ApiClient>((ref) {
  final storage = ref.read(sessionStorageProvider);
  return ApiClient(storage);
});

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(ref.read(apiClientProvider));
});

final robotsRepositoryProvider = Provider<RobotsRepository>((ref) {
  return RobotsRepository(ref.read(apiClientProvider));
});

final incidentsRepositoryProvider = Provider<IncidentsRepository>((ref) {
  return IncidentsRepository(ref.read(apiClientProvider));
});

final userRepositoryProvider = Provider<UserRepository>((ref) {
  return UserRepository(ref.read(apiClientProvider));
});

final adminRepositoryProvider = Provider<AdminRepository>((ref) {
  return AdminRepository(ref.read(apiClientProvider));
});
