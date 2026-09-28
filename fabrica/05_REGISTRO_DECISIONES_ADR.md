# 05 — Registro de Decisiones de Arquitectura (ADR)

- **Documento:** Architecture Decision Records (ADRs) de la Fábrica
- **Estado:** `APROBADO`
- **Fecha:** 2026-09-26

---

## 📑 Índice de Decisiones (ADRs)

- [ADR-001: Tiny-Steward como Motor Central vs Frameworks Externos (LangGraph / CrewAI)](#adr-001-tiny-steward-como-motor-central-vs-frameworks-externos)
- [ADR-002: Topología Asimétrica de 2 GPUs (GPU 0 Maestro Caliente, GPU 1 Pool Multiplexado)](#adr-002-topología-asimétrica-de-2-gpus)
- [ADR-003: Persistencia en Disco (Maildir Atómico + SQLite WAL) sin Message Brokers Externos](#adr-003-persistencia-en-disco-maildir-atómico--sqlite-wal)
- [ADR-004: Modelo Híbrido On-Premise + Cloud Gateway con Techo de Gasto](#adr-004-modelo-híbrido-on-premise--cloud-gateway)
- [ADR-005: Fronteras Estrictas de Human-in-the-Loop (HITL) para Operaciones Financieras y Comerciales](#adr-005-fronteras-estrictas-de-human-in-the-loop-hitl)

---

### ADR-001: Tiny-Steward como Motor Central vs Frameworks Externos

- **Estado:** Aceptado
- **Contexto:**
  Para orquestar múltiples agentes autónomos existen alternativas populares en la comunidad de código abierto como LangGraph, CrewAI o AutoGen.
- **Decisión:**
  Se decide construir la fábrica multiagente utilizando **directamente el core nativo de Tiny-Steward** (`core/mailbox.py`, `core/runtime_delegate.py`, `core/task_contract.py`, `core/service_kernel.py`).
- **Justificación:**
  1. *Compatibilidad y Estabilidad Windows:* Los frameworks de terceros a menudo asumen entornos Linux/macOS y presentan comportamientos impredecibles con sockets, multiprocessing o dependencias complejas en Windows.
  2. *Cero Overhead:* Tiny-Steward es extremadamente ligero, rápido de iniciar y libre de abstracciones innecesarias.
  3. *Control Total:* Ya cuenta con un sistema de reflexión (`/dream`), contratos formales de tarea y control de shell (`shell_guard.py`).
- **Consecuencias:**
  - Positivas: Máxima velocidad, estabilidad en Windows/PowerShell, trazabilidad completa sin dependencias ocultas.
  - Negativas: Requiere mantener nuestro propio código de enrutamiento y contratos en lugar de usar componentes prediseñados.

---

### ADR-002: Topología Asimétrica de 2 GPUs

- **Estado:** Aceptado
- **Contexto:**
  El sistema dispone de 2 GPUs en local. Se debe decidir si agruparlas en un clúster unificado (Tensor Parallelism TP=2) o desacoplarlas por funciones.
- **Decisión:**
  Se adopta una **arquitectura asimétrica desacoplada**:
  - **GPU 0:** Asignada exclusivamente al Agente Maestro (Orchestrator) 24/7 en memoria caliente.
  - **GPU 1:** Asignada al pool dinámico de workers con inferencia multi-slot paralela.
- **Justificación:**
  Si se utilizara TP=2 para correr un único modelo grande, cualquier ráfaga de trabajo de un worker congelaría la capacidad de respuesta del Maestro. Con la división asimétrica, el Maestro **nunca pierde el control ni sufre latencia**, pudiendo supervisar, cancelar o reasignar tareas en tiempo real mientras la GPU 1 está al 100% de carga.
- **Consecuencias:**
  - Positivas: Aislamiento total de fallos; el supervisor nunca se cuelga por culpa de un worker.
  - Negativas: El tamaño máximo de modelo en cada GPU está limitado a la VRAM individual de cada tarjeta.

---

### ADR-003: Persistencia en Disco (Maildir Atómico + SQLite WAL)

- **Estado:** Aceptado
- **Contexto:**
  La comunicación inter-agente requiere un bus de mensajes fiable y persistente ante caídas del sistema o cortes de energía.
- **Decisión:**
  Utilizar la estructura **Maildir atómica** ya implementada en `core/mailbox.py` (archivos JSON individuales creados vía `.tmp` y renombrado atómico) respaldada por una base de datos **SQLite en modo Write-Ahead Logging (WAL)** para indexación rápida. Rechazar Redis, RabbitMQ o Kafka.
- **Justificación:**
  1. No requiere levantar ni mantener servicios o contenedores adicionales en segundo plano.
  2. Cero corrupción de mensajes: el sistema de archivos del sistema operativo garantiza la atomicidad de `rename()`.
  3. Inspección humana inmediata: el usuario puede abrir la carpeta `sessions/.mailbox/` con el explorador de Windows o VS Code y leer los mensajes directamente en JSON.
- **Consecuencias:**
  - Positivas: Simplicidad radical, tolerancia absoluta a cortes eléctricos, inspeccionable a simple vista.
  - Negativas: Rendimiento de miles de mensajes por segundo inferior a Redis en memoria, lo cual es irrelevante para una fábrica de decenas o cientos de tareas diarias.

---

### ADR-004: Modelo Híbrido On-Premise + Cloud Gateway

- **Estado:** Aceptado
- **Contexto:**
  Los modelos locales en GPU de 7B a 14B son excelentes para tareas estructuradas, parsing y extracción de datos, pero insuficientes para ciertas tareas de generación visual fotorrealista (imágenes de catálogo) o razonamiento de nivel frontera.
- **Decisión:**
  Implementar un **Cloud Hybrid Gateway** con límite de presupuesto mensual estricto. Las tareas locales son el estándar por defecto (coste cero). Las llamadas a APIs externas requieren aprobación de presupuesto automática o manual.
- **Justificación:**
  Permite una rentabilidad económica óptima: operar 24/7 en local consumiendo únicamente electricidad, y activar la potencia de modelos como Claude 3.5 Sonnet o Flux solo cuando una ficha de producto o una oportunidad tiene un valor potencial comprobado.
- **Consecuencias:**
  - Positivas: Calidad comercial impecable sin facturas inesperadas de API.
  - Negativas: Requiere mantener conectores y claves API actualizadas.

---

### ADR-005: Fronteras Estrictas de Human-in-the-Loop (HITL)

- **Estado:** Aceptado
- **Contexto:**
  El sistema interactúa con plataformas comerciales con políticas de uso estrictas (Etsy no tolera spam de listings automatizados de baja calidad) y maneja análisis de activos financieros.
- **Decisión:**
  Fijar una **frontera de contención infranqueable**:
  - Ningún listing se publica en vivo sin un clic de aprobación humana en el Dashboard.
  - Ninguna transacción económica o movimiento de dinero se ejecuta de forma autónoma.
- **Justificación:**
  Prevenir bloqueos de cuentas en marketplaces, pérdidas patrimoniales por errores de inferencia (alucinaciones) y mantener la supervisión humana en la toma de decisiones finales.
- **Consecuencias:**
  - Positivas: Riesgo de veto o pérdida económica reducido a cero.
  - Negativas: Requiere un par de minutos al día por parte del usuario para revisar la bandeja de aprobaciones pendientes.

---

### ADR-006: El Ágora Web, Time-Slicing Awakening y Dominios de Skills Pre-Asignados

- **Estado:** Aceptado
- **Contexto:**
  Los agentes necesitan coordinarse, deliberar sobre nuevas ideas comerciales y evolucionar sus identidades sin saturar las 3 GPUs ni consumir tiempo y tokens en búsquedas semánticas RAG repetitivas de herramientas básicas.
- **Decisión:**
  1. **El Ágora Web:** Implementar un foro persistente en JSONL + Markdown con interfaz web en tiempo real dentro de `core/web_server.py` y `dashboard.html`.
  2. **Time-Slicing Awakening:** Los agentes rotan para despertar secuencialmente (lee contexto ➡️ reflexiona ➡️ publica ➡️ registra en diario ➡️ duerme) protegiendo la VRAM.
  3. **Dominios de Skills Pre-Asignados (`assigned_skill_domains`):** Cada persona tiene cargados de forma nativa los playbooks de su especialidad (cero latencia RAG en operaciones recurrentes).
  4. **Reclutamiento Autónomo:** Los trabajadores y el Maestro proponen nuevas personas en el Ágora y el Maestro (Tiny-Steward) las aprueba y provisiona de forma autónoma.
- **Justificación:**
  Crea una red social interna viva, orgánica y colaborativa con un consumo de hardware predecible y una especialización profesional auténtica para cada agente.
- **Consecuencias:**
  - Positivas: Cero contención en GPU, alta cohesión de equipo, inspección humana en tiempo real y velocidad máxima de ejecución de herramientas.
  - Negativas: Requiere mantener las fichas de personas sincronizadas en `agora/personas/`.
