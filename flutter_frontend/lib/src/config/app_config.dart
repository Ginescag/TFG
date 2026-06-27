import 'package:flutter/foundation.dart' show kIsWeb;

class AppConfig {
  // Override explicito: --dart-define=BASE_URL=http://IP_PC:8000
  static const String _override = String.fromEnvironment('BASE_URL');

  static String get baseUrl {
    if (_override.isNotEmpty) return _override;
    // En web: mismo host que sirvio la pagina, en el puerto del backend (8000).
    if (kIsWeb) return 'http://${Uri.base.host}:8000';
    return 'http://localhost:8000';
  }
}
