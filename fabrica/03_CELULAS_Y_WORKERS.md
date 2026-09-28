# 03 — Células de Trabajo y Especialización de Workers

- **Documento:** Catálogo Operativo de Agentes Trabajadores
- **Estado:** `APROBADO`
- **Fecha:** 2026-09-26
- **Contexto:** Definición de inputs, herramientas, contratos y entregables por célula

---

## 🏭 Matriz General de Células de Trabajo

| Célula / Worker | Enfoque de Dominio | Herramientas Principales | Entregable Clave | Nivel HITL |
| :--- | :--- | :--- | :--- | :--- |
| **Worker A: Scout & Radar** | Inteligencia de Mercado | Playwright, Google Trends, Reddit API, RSS | `reporte_oportunidades.json` | 0 (Autónomo) |
| **Worker B: E-Commerce (Etsy)** | Generación de Listings | Etsy API v3, Pillow, Cloud Image Gate | `draft_listing.json` + Mockups | 1 (Aprobación de publicación) |
| **Worker C: Smart Money & Insider** | Flujos de Capital y Datos | SEC EDGAR Form 4, Whale APIs, Polymarket | `alerta_smart_money.json` | 2 (Estrictamente analítico) |
| **Worker D: Diseño 3D & Assets** | Fabricación Digital | Blender Headless (Python), OpenSCAD | Archivos `.stl`, `.step` y Renders | 0 (Autónomo) |
| **Worker E: Web & Growth** | Distribución Digital | Astro / HTML generator, Social API, Mailer | Landings desplegadas y Campañas | 1 (Revisión de copy) |

---

## 🔍 Célula A: Worker Scout (Radar de Tendencias)

### 1. Misión Operativa
Monitorear la web 24/7 en busca de nichos emergentes, micro-tendencias de consumo, productos virales y necesidades no satisfechas en comunidades de usuarios.

### 2. Fuentes de Datos y Estrategia
- **Reddit:** Subreddits de nicho (`r/EtsySellers`, `r/3Dprinting`, `r/functionalprint`, `r/BuyItForLife`, `r/organization`). Detección de hilos con quejas recurrentes o solicitudes de "dónde puedo comprar esto".
- **Google Trends / Pinterest:** Palabras clave con crecimiento vertical (> 100% en 30 días).
- **TikTok Creative Center:** Hashtags de productos y sonidos virales asociados a manualidades o tecnología para el hogar.

### 3. Esquema del Entregable (`reporte_oportunidades.json`)
```json
{
  "timestamp": 1727362800,
  "oportunidades": [
    {
      "nicho": "Accesorios ergonómicos de escritorio",
      "concepto": "Soporte modular para estación de soldadura con organizador de puntas",
      "volumen_estimado": "Medio-Alto",
      "competencia": "Baja en Etsy",
      "margen_potencial_porcentaje": 75,
      "tipo_producto": "Imprimible 3D / Físico",
      "score_viabilidad": 8.7,
      "fuentes": ["https://reddit.com/r/functionalprint/..."]
    }
  ]
}
```

---

## 🛍️ Célula B: Worker E-Commerce (Etsy / Shopify)

### 1. Misión Operativa
Recibir una oportunidad validada por el Maestro y transformarla en una ficha de producto lista para vender, con optimización algorítmica para maximizar conversiones y visibilidad.

### 2. Tareas Específicas
- **Ingeniería de Título:** Estructura de alta conversión respetando el límite de 140 caracteres y colocando las palabras clave más potentes en los primeros 40 caracteres.
- **Optimización de Tags:** Selección de las 13 etiquetas permitidas por Etsy, priorizando frases de cola larga (long-tail keywords) con baja saturación.
- **Copywriting Persuasivo:** Estructuración de la descripción con:
  - Gancho inicial emocional.
  - Especificaciones técnicas y dimensiones exactas.
  - ¿Qué incluye el paquete?
  - Preguntas frecuentes (FAQ) para reducir fricción de compra.
- **Generación de Mockups:** Integración de imágenes del producto en entornos reales (ej. sobre un escritorio de trabajo o en un salón iluminado).

### 3. Esquema del Entregable (`draft_listing.json`)
```json
{
  "plataforma": "etsy",
  "estado": "draft",
  "titulo": "Soporte Ergonómico para Soldador Modular | Organizador 3D con Soporte para Bobina",
  "tags": ["soporte soldador", "organizador 3d", "taller electronica", "estacion soldadura"],
  "precio_sugerido": 24.95,
  "moneda": "EUR",
  "sku": "SOLD-MOD-01",
  "descripcion_markdown": "...",
  "mockup_images": [
    "storage/renders/sold_mod_mockup_01.png",
    "storage/renders/sold_mod_mockup_02.png"
  ]
}
```

---

## 📈 Célula C: Worker Smart Money & Insider Flow

### 1. Misión Operativa
Monitorear las huellas del gran capital y los movimientos de directivos con información privilegiada legal para detectar flujos de liquidez tempranos.

### 2. Fuentes de Datos
- **SEC EDGAR (Form 4):** Filtrado de adquisiciones de directores generales (CEO) y financieros (CFO) con capital propio (código de transacción `P` - Purchase en mercado abierto, descartando opciones sobre acciones `M` o compensaciones ejecutivas).
- **Tracking On-Chain de Ballenas:** Detección de grandes transferencias de stablecoins hacia exchanges o compras masivas de activos por billeteras históricamente rentables.
- **Mercados de Predicción (Polymarket):** Variaciones bruscas de volumen y probabilidades en eventos geopolíticos o económicos.

### 3. Regla Estricta de Gobernanza
- **Modo Exclusivo de Vigilancia:** Este worker genera **únicamente reportes analíticos y alertas de convicción**. No tiene acceso a claves privadas, cuentas de brokers ni APIs con permisos de trading.

---

## 📐 Célula D: Worker Diseño 3D & Procedural Assets

### 1. Misión Operativa
Automatizar la ingeniería y el renderizado visual de productos tridimensionales mediante programación y scripts sin necesidad de modelado manual interactivo.

### 2. Pipeline de Producción
1. **Generación Geométrica:**
   - Para piezas mecánicas y funcionales: Generación de código **OpenSCAD** (`.scad`) compilado directamente a `.stl`.
   - Para geometrías orgánicas o decorativas: Scripts Python ejecutados dentro de **Blender** en modo headless (`blender -b -P script.py`).
2. **Control de Calidad de Malla (Mesh Quality):**
   - Comprobación de que el modelo sea hermético (manifold), sin caras invertidas ni espesores de pared inferiores a 1.2 mm para garantizar imprimibilidad FDM/SLA.
3. **Estudio Fotográfico Virtual (Virtual Photo Studio):**
   - Escena base en Blender con iluminación de 3 puntos (Key light, Fill light, Rim light) y materiales PBR realistas.
   - Generación automática de 4 vistas canónicas: isométrica, frontal, detalle y render transparente para mockup.

---

## 🌐 Célula E: Worker Web & Growth

### 1. Misión Operativa
Construir y desplegar páginas de aterrizaje (landings) satélite para captar tráfico orgánico de Google, generar listas de correo electrónico y distribuir contenido automatizado en redes sociales.

### 2. Capacidades Técnicas
- **Generación Estática:** Sitios ultraligeros basados en HTML semántico o Astro, con puntuación de rendimiento 100/100 en Lighthouse.
- **SEO Programático:** Generación de páginas de aterrizaje específicas para cada variante de producto o nicho detectado.
- **Social Distribution:** Preparación de carruseles de imágenes, fichas técnicas y textos promocionales para plataformas sociales (Pinterest, Instagram, Twitter/X).
