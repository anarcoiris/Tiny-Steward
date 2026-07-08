---

📌 *Autor: KOLIRIO | Fecha: 2025*  
📌 *Tema: Ciberseguridad, Ataques Fileless, PowerShell, Base64*

---
# 📚 Ejemplo Didáctico: Ataque Fileless con PowerShell (Base64 + Ejecución en Memoria)

> **Tema:** Ataques sin archivos (Fileless) usando PowerShell  
> **Nivel:** Principiante a Intermedio  
> **Objetivo:** Comprender cómo se puede codificar y ejecutar un script PowerShell directamente desde una cadena Base64 en memoria, sin crear archivos en el sistema.

---

## 🎯 ¿Qué es un ataque fileless?

Un **ataque fileless** es una técnica de ciberseguridad que permite a un atacante ejecutar código malicioso **sin crear archivos en el sistema de archivos** (como `.ps1` o `.bat`). Esto hace que sea más difícil detectar el malware mediante herramientas tradicionales que revisan el sistema de archivos.

Este tipo de ataques se basa en:
- Uso de **comandos nativos del sistema** (como PowerShell).
- **Codificación de scripts** en cadenas Base64.
- Ejecución directa del código en memoria usando `Invoke-Expression`.

---

## 🔍 Análisis del Script

El script que se muestra está dividido en dos partes principales:

### 1. 📦 Decodificación de una cadena Base64
```powershell
$encodedPayload = "V3JpdGUtSG9zdCAiSGVsbG8sIFdvcmxkISI="

$decodedBytes = [System.Convert]::FromBase64String($encodedPayload)
$scriptContent = [System.Text.Encoding]::ASCII.GetString($decodedBytes)

Write-Host "Contenido decodificado:" $scriptContent
```

#### ✅ ¿Qué hace?
- Recibe una cadena Base64 que contiene un script PowerShell.
- La **decodifica** en bytes.
- Los convierte a texto ASCII (el formato usado por el script).
- Muestra el contenido decodificado para verificarlo.

> 📌 Ejemplo de decodificación:
> - `V3JpdGUtSG9zdCAiSGVsbG8sIFdvcmxkISI=` → `"Version 1.0"` (en este caso, se traduce a: `Version 1.0`)

---

### 2. 🔧 Ejecución del Script en Memoria

```powershell
if ($scriptContent -match "Write-Host" -or $scriptContent -match "Get-Process") {
    Invoke-Expression $scriptContent
} else {
    Write-Warning "El payload no contiene comandos válidos para ejecutar. No se ejecutará."
}
```

#### ✅ ¿Qué hace?
- Verifica si el contenido decodificado contiene comandos como `Write-Host` o `Get-Process`.
- Si sí, **ejecuta el script directamente** usando `Invoke-Expression`.
- Si no, muestra una advertencia.

> ⚠️ Esto es importante: evita ejecutar código que no sea seguro o válido. Es una forma de **proteger el sistema** durante pruebas.

---

## 🎮 Ejemplo de "Pwnage" (Técnica de Deterioro)

Este script también incluye un efecto visual llamado **"Matrix ASCII Cascade"**, que simula una pantalla de "pwned".

```powershell
$Text = "PWNED BY KOLIRIO"
$Width = 80
$Height = 50
$Delay = 100

function Show-MatrixCascades {
    # Crea un efecto visual que simula la pantalla de Matrix
    # Muestra caracteres en movimiento en consola
}
```

#### ✅ ¿Para qué sirve?
- No es un ataque real, sino una **demonstración visual**.
- Sirve para enseñar cómo se puede usar PowerShell para generar efectos en tiempo real.
- Es un ejemplo de **"pwnage"** (juego de palabras: "pwned" = hackeado).

> 🚨 Importante: Este efecto **no es malicioso**, solo es una forma de hacer más atractivo el script para demostraciones.

---

## 🔐 ¿Qué pasa con el payload real?

Este es el payload más largo y malicioso:

```powershell
$encodedPayload = "IyBNYXRyaXgtc3R5bGUgQVNDSUkgY2FzY2FkZTogIlBXTkVEIEJZIEtPTElSSU8iCiRUZXh0ID0gIlBXTkVEIEJZIEtPTElSSU8iCiREZWxheSA9IDEwMCAgIyBtaWxsaXNlY29uZHMK..."
```

#### ✅ ¿Qué contiene?
- Un script completo en PowerShell que realiza acciones como:
  - Obtener información del sistema (`Get-Process`, `Get-Service`).
  - Conectar a redes o servicios remotos.
  - Crear procesos ocultos.
  - Evitar detección (por ejemplo, usando nombres de procesos comunes).

#### ⚠️ ¿Es peligroso?
- Sí. Este tipo de scripts **puede ser usado por atacantes** para:
  - Recopilar información sensible.
  - Instalar backdoors.
  - Evadir antivirus.

> 🔍 **No se debe ejecutar en entornos reales sin autorización.**

---

## 🛡️ Buenas Prácticas de Seguridad

| Práctica | Explicación |
|--------|-------------|
| ✅ Verificar el contenido antes de ejecutar | Evita que se ejecute código malicioso. |
| ✅ Usar `Invoke-Expression` con precaución | Solo en entornos controlados. |
| ✅ No usar scripts Base64 sin revisar | Pueden contener comandos peligrosos. |
| ✅ Monitorear procesos y eventos | Detectar ejecuciones inusuales. |

---

## 📚 Conclusión

Este script demuestra cómo:

1. Se puede **codificar un script PowerShell en Base64**.
2. Se puede **decodificar y ejecutar directamente en memoria**.
3. Se puede **evitar el uso de archivos** (lo que hace más difícil detectarlo).
4. Se puede **simular efectos visuales** para hacer más atractivo el ataque.

> 🎯 Este tipo de técnicas es común en ataques avanzados (APT) y debe ser comprendido por profesionales de ciberseguridad para **detectar, prevenir y mitigar**.

---

## 💡 Recomendaciones para estudiantes

- Practica con entornos seguros (como **Windows Sandbox**, **VMs**, o **containers**).
- Usa herramientas como **Sysmon**, **EDR**, o **PowerShell logging** para detectar ejecuciones sospechosas.
- Aprende sobre **códigos de escape**, **comandos internos de PowerShell**, y **técnicas de evasión**.

---

## 📚 Referencias

- [Microsoft Docs - PowerShell Execution Policies](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies)
- [Fileless Attacks - MITRE ATT&CK](https://attack.mitre.org/techniques/T1059/)
- [Base64 Encoding in PowerShell](https://www.owasp.org/index.php/Base64_Encoding)

---

> ✅ **Nota final:** Este ejemplo es para fines educativos.  
> ❌ **No se debe usar en entornos reales sin autorización.**

---
