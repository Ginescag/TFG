import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../repositories/auth_repository.dart';
import '../storage/session_storage.dart';
import 'auth_state.dart';

class AuthController extends StateNotifier<AuthState> {
  AuthController(this._repository, this._storage)
    : super(const AuthState.unknown()) {
    _restoreSession();
  }

  final AuthRepository _repository;
  final SessionStorage _storage;

  Future<void> _restoreSession() async {
    final session = await _storage.readSession();
    if (session == null) {
      state = const AuthState.unauthenticated();
      return;
    }
    state = AuthState.authenticated(
      token: session.token,
      role: session.role,
      userId: session.userId,
    );
  }

  Future<void> login({required String email, required String password}) async {
    final session = await _repository.login(email: email, password: password);
    await _storage.saveSession(
      SessionData(
        token: session.token,
        role: session.role,
        userId: session.userId,
      ),
    );
    state = AuthState.authenticated(
      token: session.token,
      role: session.role,
      userId: session.userId,
    );
  }

  Future<void> registerAndLogin({
    required String nombre,
    required String email,
    required String password,
    String? tlf,
  }) async {
    await _repository.register(
      nombre: nombre,
      email: email,
      password: password,
      tlf: tlf,
    );
    await login(email: email, password: password);
  }

  Future<void> logout() async {
    await _storage.clear();
    state = const AuthState.unauthenticated();
  }
}
