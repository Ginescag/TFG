enum AuthStatus { unknown, unauthenticated, authenticated }

class AuthState {
  final AuthStatus status;
  final String? token;
  final String? role;
  final int? userId;

  const AuthState({required this.status, this.token, this.role, this.userId});

  const AuthState.unknown() : this(status: AuthStatus.unknown);

  const AuthState.unauthenticated() : this(status: AuthStatus.unauthenticated);

  const AuthState.authenticated({
    required String token,
    required String role,
    required int userId,
  }) : this(
         status: AuthStatus.authenticated,
         token: token,
         role: role,
         userId: userId,
       );
}
