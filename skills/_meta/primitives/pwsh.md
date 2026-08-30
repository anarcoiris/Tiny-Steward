---
name: pwsh
type: skill
requires: []
provides: [shell, windows-commands, system-admin]
tags: [powershell, shell, windows, system]
related: [bash, python, grep, ls]
---

# PowerShell (pwsh)

Primary shell for Tiny Steward. Executes PowerShell commands natively on Windows.

## Usage

```xml
<tool_call>
<function=pwsh>
<parameter=command>
Get-ChildItem -Recurse -Filter *.py
</parameter>
</function>
</tool_call>
```

## Notes

- Use `-ErrorAction SilentlyContinue` to suppress non-critical errors
- Pipe to `Select-Object -First N` to limit output
- Prefer relative paths from the Tiny Steward workspace cwd
- Use `date` for time awareness, scheduling, planning timers... (be creative and resolutive)
- Use argument `-h` or `--help` to investigate problematic methods and calls

## Basic usage


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

## Full reference for methods and calls

- Methods appendix: **"C:\\Users\\soyko\\Documents\\tiny_steward\\skills\\_infra\\powershell\\SKILL.md"**
