Aquí tienes una lista completa de comandos PowerShell organizados por categorías y ordenados por utilidad dentro de cada una:

---

## 📁 Gestión de Archivos y Directorios

| Comando | Descripción |
|---------|-------------|
| `Get-ChildItem` (alias: `ls`, `dir`) | Lista archivos y carpetas del directorio actual |
| `Set-Location` (alias: `cd`) | Cambia de directorio |
| `Copy-Item` (alias: `cp`, `copy`) | Copia archivos o carpetas |
| `Move-Item` (alias: `mv`, `move`) | Mueve o renombra archivos/carpetas |
| `Remove-Item` (alias: `rm`, `del`) | Elimina archivos o carpetas |
| `New-Item` (alias: `ni`) | Crea nuevos archivos o carpetas |
| `Test-Path` | Verifica si existe un archivo o ruta |
| `Get-Content` (alias: `cat`, `type`) | Muestra el contenido de un archivo |
| `Set-Content` | Escribe contenido en un archivo (sobrescribe) |
| `Add-Content` | Añade contenido al final de un archivo |
| `Clear-Content` | Vacía el contenido de un archivo sin borrarlo |
| `Join-Path` | Combina rutas de forma segura |

---

## 🔍 Búsqueda y Filtrado

| Comando | Descripción |
|---------|-------------|
| `Where-Object` (alias: `?` o `where`) | Filtra objetos según condiciones |
| `Select-Object` (alias: `select`) | Selecciona propiedades específicas de objetos |
| `Sort-Object` (alias: `sort`) | Ordena objetos por propiedades |
| `Group-Object` | Agrupa objetos por propiedades |
| `Measure-Object` | Calcula estadísticas (conteo, suma, promedio, etc.) |
| `Find-Module` / `Find-Package` | Busca módulos o paquetes en repositorios |
| `Select-String` (similar a `grep`) | Busca texto dentro de archivos |

---

## 💻 Gestión de Procesos y Servicios

| Comando | Descripción |
|---------|-------------|
| `Get-Process` (alias: `ps`) | Muestra procesos en ejecución |
| `Stop-Process` (alias: `kill`) | Termina procesos por ID o nombre |
| `Start-Process` | Inicia un nuevo proceso |
| `Get-Service` | Lista servicios del sistema |
| `Start-Service` / `Stop-Service` / `Restart-Service` | Controla servicios |
| `Set-Service` | Modifica configuración de servicios |

---

## 🌐 Red y Conectividad

| Comando | Descripción |
|---------|-------------|
| `Test-Connection` (similar a `ping`) | Verifica conectividad de red |
| `Test-NetConnection` | Diagnóstico avanzado de red (puertos, traceroute) |
| `Get-NetIPAddress` / `Get-NetIPConfiguration` | Muestra configuración IP |
| `Invoke-WebRequest` (alias: `iwr`, `curl`, `wget`) | Realiza peticiones HTTP/HTTPS |
| `Invoke-RestMethod` | Consume APIs REST |
| `Resolve-DnsName` (similar a `nslookup`) | Resuelve nombres DNS |

---

## 👤 Usuarios y Permisos

| Comando | Descripción |
|---------|-------------|
| `Get-LocalUser` | Lista usuarios locales |
| `New-LocalUser` / `Remove-LocalUser` | Crea o elimina usuarios |
| `Get-LocalGroup` | Lista grupos locales |
| `Add-LocalGroupMember` | Añade usuarios a grupos |
| `Get-Acl` / `Set-Acl` | Obtiene o modifica permisos de archivos |
| `Get-ExecutionPolicy` / `Set-ExecutionPolicy` | Controla políticas de ejecución de scripts |

---

## 🔧 Sistema y Hardware

| Comando | Descripción |
|---------|-------------|
| `Get-ComputerInfo` | Información detallada del sistema |
| `Get-WmiObject` / `Get-CimInstance` | Acceso a WMI para hardware y sistema |
| `Get-EventLog` / `Get-WinEvent` | Consulta logs del sistema |
| `Clear-EventLog` | Limpia logs de eventos |
| `Restart-Computer` / `Stop-Computer` | Reinicia o apaga el equipo |
| `Get-HotFix` | Lista actualizaciones instaladas |
| `Get-Disk` / `Get-Partition` / `Get-Volume` | Gestión de discos y volúmenes |

---

## 📦 Módulos y Paquetes

| Comando | Descripción |
|---------|-------------|
| `Get-Module` | Lista módulos cargados o disponibles |
| `Import-Module` | Carga un módulo en la sesión |
| `Install-Module` | Instala módulos desde la PowerShell Gallery |
| `Update-Module` / `Uninstall-Module` | Actualiza o elimina módulos |
| `Get-Command` (alias: `gcm`) | Busca comandos disponibles |
| `Get-Help` | Muestra ayuda de cualquier comando |
| `Get-Alias` | Lista alias disponibles |

---

## 📝 Variables y Entorno

| Comando | Descripción |
|---------|-------------|
| `Get-Variable` / `Set-Variable` / `Remove-Variable` | Gestión de variables |
| `Get-ChildItem Env:` | Muestra variables de entorno |
| `$env:NOMBRE` | Acceso directo a variables de entorno |
| `Get-Date` | Obtiene fecha y hora actual |
| `Start-Sleep` | Pausa la ejecución |

---

## 🔄 Control de Flujo y Pipeline

| Comando | Descripción |
|---------|-------------|
| `ForEach-Object` (alias: `%`) | Itera sobre cada objeto del pipeline |
| `If` / `ElseIf` / `Else` | Condicionales |
| `For` / `While` / `Do-While` / `Do-Until` | Bucles |
| `Switch` | Estructura switch multi-valor |
| `Try` / `Catch` / `Finally` | Manejo de errores |
| `Throw` | Lanza excepciones |
| `Trap` | Captura errores a nivel de script |

---

## 📤 Exportación y Conversión

| Comando | Descripción |
|---------|-------------|
| `Export-Csv` / `Import-Csv` | Exporta/Importa datos en formato CSV |
| `Export-Clixml` / `Import-Clixml` | Serializa objetos a XML |
| `ConvertTo-Json` / `ConvertFrom-Json` | Convierte a/desde JSON |
| `ConvertTo-Html` | Genera reportes en HTML |
| `Out-File` / `Out-GridView` / `Out-Printer` | Redirige salida a archivo, ventana gráfica o impresora |
| `Tee-Object` | Guarda salida y la muestra en pantalla simultáneamente |
| `Format-Table` / `Format-List` | Formatea salida como tabla o lista |

---

## 💡 Consejos Rápidos

| Atajo | Descripción |
|-------|-------------|
| `Get-Help <comando> -Examples` | Muestra ejemplos prácticos |
| `Get-Help <comando> -Full` | Ayuda completa del comando |
| `Get-Command *palabra*` | Busca comandos que contengan "palabra" |
| `Get-Member` (alias: `gm`) | Muestra propiedades y métodos de objetos |
| `Ctrl+C` | Cancela ejecución actual |
| `Tab` / `Shift+Tab` | Autocompletado de comandos y parámetros |
| `Get-History` / `Invoke-History` | Historial de comandos ejecutados |

---

Estos son los comandos más utilizados en PowerShell. La clave es combinarlos con el **pipeline** (`|`) para crear operaciones potentes. Por ejemplo:

```powershell
Get-Process | Where-Object {$_.CPU -gt 100} | Sort-Object CPU -Descending | Select-Object -First 5
```

Este comando muestra los 5 procesos que más CPU consumen.