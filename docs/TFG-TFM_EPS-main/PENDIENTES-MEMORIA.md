# Material pendiente para la memoria

Lista de elementos de apoyo (esquemas, diagramas, tablas, capturas, código y
gráficas) recomendados para completar la memoria del TFG *Sistema robótico
inteligente para la patrulla y detección de incidencias en estancias cerradas*.
Está organizada por capítulo. No sustituye al texto ya redactado: indica qué
falta por crear e insertar, y dónde encaja.

Marca cada elemento conforme lo añadas.

---

## Recordatorio de convenciones (libro de estilo EPS)

Antes de insertar cualquier figura o tabla:

- Toda figura y tabla va **numerada**, con `\caption` autoexplicativo,
  **referenciada en el texto** (`Figura~\ref{...}`, `Tabla~\ref{...}`) y con
  **nota de fuente** dentro del `\caption`: `Fuente: elaboración propia.` o
  `Adaptado de \parencite{clave}.`.
- Las figuras se guardan en `recursos/figuras/`. Para diagramas, preferible
  **formato vectorial** (PDF o SVG exportado a PDF); para capturas, PNG nítido.
- El código va siempre con los entornos `*code` de la plantilla (`pythoncode`,
  `bashcode`, `sqlcode`, `jsoncode`, `yamlcode`...), nunca `verbatim`.
- Capturas de pantalla: recortadas, legibles y **sin datos personales reales**
  (usa usuarios y robots de prueba).
- Etiquetas con prefijo consistente: `fig:`, `tab:`, `lst:`, `eq:`.
- Añade el texto alternativo de accesibilidad: `\includegraphics[alt={...}]`.

Marcadores que ya existen en el documento y hay que sustituir:

- `\missingfigure` en `desarrollo.tex` (etiqueta `fig:arquitectura`): diagrama de
  arquitectura general.
- `\todo[inline]` en `resultados.tex`: escenario de pruebas, pruebas funcionales
  y tabla de métricas.

---

## Capítulo 1. Introducción

- [ ] (Opcional) Figura conceptual de alto nivel que ilustre la idea: robot que
  patrulla una planta, detecta a una persona y avisa al usuario en el móvil.
  Ayuda a enganchar, pero no es imprescindible.

## Capítulo 2. Marco teórico

- [ ] **Figura:** modelo de comunicación de ROS 2 (nodos, *topics*,
  publicación/suscripción, servicios y acciones sobre DDS).
- [ ] **Figura:** esquema de SLAM basado en grafo de poses (nodos de pose,
  restricciones, cierre de bucle).
- [ ] **Figura:** arquitectura de Nav2 (planificador global, controlador local,
  árbol de comportamiento, *costmaps*).
- [ ] **Figura:** detección de objetos de una sola etapa (rejilla, cajas y
  confianza) para situar YOLO.
- [ ] **Figura:** patrón de arquitectura orientada a eventos (productores, *broker*
  y consumidores desacoplados).
- [ ] **Tabla comparativa del estado del arte:** una fila por trabajo o sistema
  relacionado y columnas como navegación autónoma, percepción, integración web,
  carácter abierto/cerrado y cita. Refuerza la sección de trabajos relacionados.
- [ ] (Opcional) **Ecuación:** definición de IoU y de precisión/exhaustividad,
  si luego se usan como métricas en Resultados.

## Capítulo 3. Objetivos

- [ ] (Opcional) **Tabla de trazabilidad** que relacione cada objetivo específico
  (OE1...OE8) con el capítulo o subsistema donde se aborda. Útil también para
  enlazar con Conclusiones.

## Capítulo 4. Metodología

- [ ] **Figura:** diagrama del flujo de desarrollo iterativo e incremental
  (orden de construcción por capas).
- [ ] **Figura o foto:** plataforma de pruebas (TurtleBot 4) y, si procede, plano
  o croquis de la estancia donde se valida.
- [ ] **Tabla:** métricas de evaluación con su **definición y unidad** (amplía la
  enumeración actual: tasa de éxito de patrulla, confianza media, falsos
  positivos por hora, latencia evento a alerta).
- [ ] (Opcional) **Tabla:** versiones concretas de cada herramienta (ROS 2 Humble,
  versión de Nav2, YOLOv8n, Kafka, FastAPI, Flutter...), para reproducibilidad.

## Capítulo 5. Desarrollo

El capítulo central: es donde más material visual conviene.

- [ ] **Figura (prioritaria):** diagrama de **arquitectura general** del sistema,
  los cuatro bloques (capa robótica, infraestructura de datos, backend y
  aplicación) y los flujos de eventos. Sustituye al `\missingfigure`
  (`fig:arquitectura`).
- [ ] **Figura:** diagrama de la **máquina de estados** del orquestador
  (IDLE, EXPLORING, SAVING_MAP, PLANNING, PATROLLING, PATROL_STOPPED) con las
  transiciones y los comandos que las disparan.
- [ ] **Figura:** **diagrama de secuencia** del flujo de incidencia
  (cámara, nodo YOLO, MinIO, Kafka, consumidor del backend, base de datos y app).
- [ ] **Figura:** diagrama de secuencia de la **telemetría** (suscripciones,
  publicación a Kafka, consumidor, InfluxDB, Grafana).
- [ ] **Figura:** diagrama de secuencia de la **autenticación TOFU/JWT**
  (primer arranque, obtención del secreto, *login* y refresco del token).
- [ ] **Figura:** **modelo de datos** (entidad-relación: Usuario, Robot,
  Incidente) o diagrama de clases del backend.
- [ ] **Figura:** **mapa generado por SLAM** con la **ruta de patrulla** (rejilla
  de puntos en zig-zag) superpuesta. Captura de RViz o del propio `.pgm`.
- [ ] **Figura:** **diagrama de despliegue** (servicios en contenedores de
  Docker Compose y sus conexiones).
- [ ] **Tabla:** **endpoints de la API REST** (método, ruta, descripción y si
  requiere autenticación), más completa que el ejemplo actual.
- [ ] **Capturas de la aplicación Flutter:** *login*, lista de robots, pantalla de
  control de patrulla (iniciar/detener/reiniciar), detalle de incidencia con
  reproducción del vídeo, y panel con el *dashboard* de Grafana embebido.
- [ ] **Captura del backend:** interfaz Swagger UI de FastAPI (`/docs`) con los
  endpoints.
- [ ] (Opcional) **Más extractos de código** con `pythoncode`: el diccionario de
  la FSM y el manejo de comandos, el callback de detección de YOLO, o el envío de
  *heartbeat*. El de generación de la rejilla de *waypoints* ya está incluido.

## Capítulo 6. Resultados

- [ ] **Figura o foto:** el robot patrullando en el escenario real.
- [ ] **Captura:** detección de YOLO sobre una persona (caja delimitadora y
  confianza), y un fotograma del clip de incidencia generado.
- [ ] **Figura:** mapa final con la trayectoria realmente recorrida durante la
  patrulla.
- [ ] **Tabla:** rellenar la **plantilla de métricas** (`tab:resultados-pendientes`)
  con los valores medidos.
- [ ] **Tabla:** **pruebas funcionales** ejecutadas (flujo probado y resultado
  superado/no superado).
- [ ] **Gráfica:** latencia de extremo a extremo (detección a registro), por
  ejemplo un diagrama de cajas o de barras.
- [ ] **Gráfica:** evolución de la batería o de la posición a lo largo de la
  patrulla, exportada de InfluxDB/Grafana.
- [ ] (Si hay datos etiquetados) **Gráfica:** matriz de confusión o curva
  precisión/exhaustividad de la detección.

## Capítulo 7. Conclusiones

- [ ] (Opcional) **Tabla resumen** del grado de consecución de cada objetivo
  específico (cumplido, parcial, pendiente), enlazada con la trazabilidad del
  Capítulo 3.

## Anexos

- [x] Manual de despliegue (`anexo-despliegue.tex`, ya creado).
- [ ] **Especificación completa de la API REST** (tabla larga con todos los
  endpoints, o exportación de la documentación OpenAPI).
- [ ] **Esquema de la base de datos** (`init.sql`) como bloque `sqlcode`.
- [ ] (Opcional) **Planificación temporal** del proyecto (diagrama de Gantt).
- [ ] (Opcional) **Manual de usuario** de la aplicación con capturas paso a paso.

---

## Herramientas sugeridas para generarlo

| Elemento | Herramienta recomendada |
| --- | --- |
| Diagramas de arquitectura, despliegue y secuencia | diagrams.net (draw.io), exportar a PDF |
| Diagramas UML (secuencia, clases, estados, ER) | PlantUML o Mermaid |
| Grafo de nodos y *topics* de ROS 2 | `rqt_graph` |
| Mapa y trayectoria del robot | RViz2 (captura) o el propio `.pgm` |
| Diagramas y gráficas dentro de LaTeX | TikZ y PGFPlots (ya disponibles en la plantilla) |
| Gráficas a partir de datos | matplotlib (con datos exportados de InfluxDB) |
| Paneles de telemetría | capturas de Grafana |
| Documentación de la API | Swagger UI de FastAPI (`/docs`) |

## Prioridad sugerida

1. Diagrama de **arquitectura general** (sustituye al `\missingfigure`).
2. Diagrama de la **máquina de estados** y **mapa con la ruta** de patrulla.
3. **Capturas** de la app Flutter y del *dashboard* de Grafana.
4. **Diagramas de secuencia** (incidencia, telemetría, autenticación).
5. Datos y gráficas de **Resultados** cuando se valide el sistema.
