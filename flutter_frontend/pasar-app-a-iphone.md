# Probar la app desde el iPhone

Guía para usar la app desde tu iPhone y que hable con el backend de tu PC.

> **Realidad importante (estás en Windows):** no se puede **compilar ni firmar una
> app nativa de iOS sin un Mac con Xcode**. iOS no usa APK (usa `.ipa`) y Apple
> exige macOS para construir y firmar. Por eso, la forma práctica de probar desde
> tu iPhone **sin Mac** es abrir la app como **página web en Safari**, servida
> desde tu PC. Tu proyecto Flutter ya soporta web (el script
> `scripts/30_frontend_run.sh` arranca por defecto en Chrome). Las alternativas
> para tener la app **nativa** en el iPhone (que sí necesitan un Mac o un servicio
> en la nube) están al final.

---

## Opción recomendada: la app web en Safari (sin Mac)

La idea: el PC sirve la app web y el iPhone la abre por la red local. Así pruebas
el servidor desde el iPhone sin nada de Apple.

### 1. Apuntar la app a la IP de tu PC (no a localhost)

La URL está fija en `lib/src/config/app_config.dart`:

```dart
class AppConfig {
  static const String baseUrl = 'http://localhost:8000';
}
```

En el iPhone, `localhost` es el **propio teléfono**, no tu PC. Pon la **IP local
del PC** (sácala con `ipconfig` en Windows, por ejemplo `192.168.1.50`).

**Opción A (rápida):** edita el fichero:

```dart
class AppConfig {
  static const String baseUrl = 'http://192.168.1.50:8000'; // IP de tu PC
}
```

**Opción B (recomendada, sin tocar el código en cada arranque):**

```dart
class AppConfig {
  static const String baseUrl = String.fromEnvironment(
    'BASE_URL',
    defaultValue: 'http://localhost:8000',
  );
}
```

y pasa la IP al arrancar con `--dart-define=BASE_URL=http://192.168.1.50:8000`.

### 2. Servir la web escuchando en toda la red

Desde `flutter_frontend/`, dos formas:

**Rápida (modo desarrollo):**

```bash
flutter run -d web-server --web-hostname 0.0.0.0 --web-port 8080 \
  --dart-define=BASE_URL=http://192.168.1.50:8000
```

**Compilada (más estable):**

```bash
flutter build web --dart-define=BASE_URL=http://192.168.1.50:8000
# luego sirve la carpeta build/web (tienes Python):
python -m http.server 8080 --directory build/web --bind 0.0.0.0
```

### 3. Abrir desde el iPhone

1. iPhone y PC en la **misma red WiFi**.
2. En **Safari** del iPhone, abre `http://IP_PC:8080` (la app web).
3. La app llamará al backend en `http://IP_PC:8000`.

### 4. Que el iPhone alcance PC y backend

- **Cortafuegos de Windows:** permite los puertos entrantes **8080** (la web) y
  **8000** (el backend). Para el panel de Grafana y el vídeo, también **3000** y
  **9000**.
- Sirve la web por **HTTP** (no HTTPS), igual que el backend. Si la web fuese
  HTTPS y el backend HTTP, Safari bloquearía la llamada por contenido mixto.
- CORS ya está abierto en el backend (`allow_origins=["*"]`), así que el navegador
  no bloqueará las peticiones.
- Prueba primero en Safari: abre `http://IP_PC:8000/docs`. Si ves la documentación
  de la API, la app web también llegará.

> Limitación: una web no se "instala" como app; la abres desde Safari cada vez
> (puedes usar "Añadir a pantalla de inicio" para un acceso directo). Para
> pruebas del servidor es más que suficiente.

---

## Lo que seguirá fallando si solo cambias la baseUrl

Dos endpoints devuelven URLs con `localhost` dentro y fallarán en el iPhone aunque
el login funcione:

- **Panel de Grafana** (`/user/{robot_id}/dashboard-url`): usa `GRAFANA_URL` del
  `.env` del backend. Ponlo a `http://IP_PC:3000`.
- **Vídeo de incidencias** (`/user/incidents/{id}/show-video`): genera una URL
  prefirmada de MinIO con `MINIO_ENDPOINT`. Ponlo a `http://IP_PC:9000`.

Es decir, en el **`.env` del backend** cambia `GRAFANA_URL` y `MINIO_ENDPOINT` a
`IP_PC` para una experiencia completa desde el iPhone.

---

## Alternativas para la app nativa en iOS (requieren Mac o nube)

Si de verdad quieres el `.ipa` instalado como app en el iPhone:

- **Mac con Xcode (lo más directo):** abre el proyecto, conecta el iPhone y
  `flutter run`. Con un **Apple ID gratuito** puedes instalarla en tu propio
  dispositivo, pero caduca a los 7 días (hay que reinstalar). Sin Mac físico,
  puedes alquilar uno en la nube (MacinCloud, MacStadium), aunque instalar en un
  iPhone físico desde un Mac remoto es incómodo.
- **CI en la nube (sin Mac propio):** servicios como **Codemagic** o **GitHub
  Actions** (runner de macOS) compilan el `.ipa`. Para instalarlo en el iPhone
  necesitas **firma de código** (cuenta de Apple Developer, 99 USD al año) y
  distribución por **TestFlight**, o *ad-hoc* registrando el UDID del dispositivo.
- **Transporte seguro (ATS):** iOS bloquea HTTP en claro por defecto. Para una app
  nativa contra un backend HTTP habría que permitirlo en `Info.plist`
  (`NSAppTransportSecurity` con `NSAllowsArbitraryLoads`), o servir el backend por
  HTTPS.

En resumen: para **probar el servidor desde tu iPhone ya**, usa la **web en
Safari**. La app nativa de iOS queda para cuando dispongas de un Mac o montes la
firma y TestFlight.

---

## Resumen de qué tocar (vía web en Safari)

| Dónde | Qué | Valor |
|---|---|---|
| `lib/src/config/app_config.dart` | `baseUrl` | `http://IP_PC:8000` |
| Arranque web | escuchar en la red | `--web-hostname 0.0.0.0` (o `http.server --bind 0.0.0.0`) |
| `backend/.env` | `GRAFANA_URL` | `http://IP_PC:3000` (para el panel) |
| `backend/.env` | `MINIO_ENDPOINT` | `http://IP_PC:9000` (para el vídeo) |
| Windows | cortafuegos | abrir `8080` y `8000` (y `3000`, `9000`) |
