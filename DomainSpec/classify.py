"""
Classify skill slugs into DomainSpec topic buckets.

Topic buckets are catalog tags for organizing skills/ — they are NOT the same
as DomainSpec v2 `type: domain` nodes (git, docker, python). See classify.md.

Layout decision: topic-primary folders; verb prefix kept as metadata.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS_RAW = HERE / "skills_raw.txt"
OUT_CSV = HERE / "domainspec_mapping.csv"
GOLDEN_CSV = HERE / "golden_set.csv"

# --- 1. Explicit anchors ---
bare_domains = {"bash", "docker", "git", "linux", "powershell", "python_env"}
meta_or_uncertain = {
    "primitives",
    "pulse-routing",
    "nomic-local",
    "delegate-router",
    "delegation-gate",
    "troubleshooting",
    "paid-bash-security-v1-1",
}
policy_items = {"legal"}

# Keywords that must match as whole path segments (hyphen-delimited).
# Prevents `cape` matching landscape/escape, `c2-` matching soc2, etc.
BOUNDED_KEYWORDS = {
    "cape",
    "c2",
    "xss",
    "xxe",
    "csrf",
    "idor",
    "ssrf",
    "jwt",
    "npm",
    "pypi",
    "llm",
    "dast",
    "sast",
    "sbom",
    "slsa",
    "mtls",
    "ztna",
    "soc2",
    "yara",
    "k8s",
    "dnp3",
    "adcs",
    "esc1",
    "esc8",
    "mft",
    "ioc",
    "aws",
    "gcp",
    "azure",
    "s3",
    "ida",
    "cmmc",
}

# Synonym expansions applied before matching (slug substring → canonical keyword).
SYNONYMS = {
    "server-side-request-forgery": "ssrf",
    "canary-tokens": "canarytoken",
    "canary-token": "canarytoken",
    "json-web-token": "jwt",
    "open-policy-agent": "opa",
    "policy-as-code": "policy-as-code",
    "llms": "llm",
    "sboms": "sbom",
    "stix2": "stix",
    "guardrails": "llm-guardrails",
}


def slug_tokens(slug: str) -> list[str]:
    return [t for t in slug.split("-") if t]


def keyword_matches(slug: str, kw: str) -> bool:
    """True if keyword matches slug with safe boundaries for short tokens."""
    core = kw.rstrip("-")
    if core in BOUNDED_KEYWORDS or len(core) <= 4:
        tokens = slug_tokens(slug)
        # Multi-segment keywords like "cuckoo-sandbox"
        parts = [p for p in kw.split("-") if p]
        if len(parts) == 1:
            return parts[0] in tokens
        # Sliding window over tokens
        n = len(parts)
        for i in range(len(tokens) - n + 1):
            if tokens[i : i + n] == parts:
                return True
        return False
    return kw in slug


def normalize_for_match(slug: str) -> str:
    """Apply synonym rewrites so expanded forms hit short canonical keywords."""
    out = slug
    for src, dst in SYNONYMS.items():
        if src in out:
            out = out.replace(src, dst)
    return out


# --- 2. Domain rules (specific → general). First match = primary topic. ---
DOMAIN_RULES: list[tuple[str, list[str]]] = [
    (
        "ai_and_llm_security",
        [
            "llm",
            "prompt-injection",
            "garak",
            "promptfoo",
            "pyrit",
            "mcp-servers",
            "tool-poisoning",
            "agentic-ai-tool",
            "vector-and-embedding",
            "rag-pipelines",
            "system-prompt-leakage",
            "model-extraction",
            "data-and-model-poisoning",
            "orchestrating-llm",
            "ai-model-prompt-injection",
            "ai-driven-osint",
            "business-email-compromise-with-ai",
            "llm-guardrails",
        ],
    ),
    (
        "web3_and_smart_contract_security",
        ["smart-contract", "ethereum", "foundry-smart-contract"],
    ),
    (
        "ot_ics_scada_security",
        [
            "scada",
            "modbus",
            "dnp3",
            "plc-firmware",
            "historian",
            "purdue",
            "s7comm",
            "hmi-security",
            "power-grid",
            "oil-gas",
            "claroty",
            "nozomi",
            "dragos",
            "tofino",
            "industrial-control-systems",
            "ot-remote-access",
            "ot-network",
            "ot-incident",
            "ot-vulnerability",
            "ot-systems",
            "ot-environment",
            "conduit-security",
        ],
    ),
    (
        "deception_technology",
        [
            "honeytoken",
            "canarytoken",
            "honeypot",
            "decoy",
            "deception",
        ],
    ),
    (
        "detection_engineering_and_threat_hunting",
        [
            "siem",
            "sigma",
            "splunk",
            "qradar",
            "elastic-siem",
            "wazuh",
            "zeek",
            "sysmon",
            "ueba",
            "detection-rule",
            "detection-rules",
            "alert-fatigue",
            "alert-triage",
            "false-positive-reduction",
            "log-source-onboarding",
            "security-monitoring",
            "user-behavior-analytics",
            "dns-tunneling",
            "threat-hunting",
            "correlating-security-events",
            "correlating-threat-campaigns",
            "network-traffic-analysis",
            "network-packet-capture",
            "network-flow-data",
            "network-packets",
            "network-traffic-for-incidents",
            "dns-logs-for-exfiltration",
            "web-server-logs-for-intrusion",
            "powershell-script-block-logging",
            "windows-event-logs-in-splunk",
            "security-logs",
            "log-forwarding",
            "log-integrity",
            "syslog-centralization",
            "malicious-url",
            "urlscan",
            "arkime",
            "tshark",
            "scapy",
            "netflow",
            "fluentd",
            "rsyslog",
            "datadog",
        ],
    ),
    (
        "mobile_security",
        [
            "android",
            "ios-app",
            "mobsf",
            "objection",
            "jadx",
            "deeplink",
            "mobile-app",
            "mobile-device-forensics",
            "mobile-api",
            "mobile-malware",
            "mobile-application-management",
            "android-intents",
            "insecure-data-storage-in-mobile",
            "certificate-pinning-bypass",
        ],
    ),
    (
        "malware_analysis_and_reverse_engineering",
        [
            "malware",
            "ghidra",
            "ida",
            "dnspy",
            "frida",
            "apktool",
            "upx-unpacker",
            "peepdf",
            "pdfid",
            "cuckoo-sandbox",
            "any-run",
            "cape",
            "yara",
            "rootkit",
            "bootkit",
            "ransomware-encryption",
            "agent-tesla",
            "packed-",
            "deobfuscating",
            "reverse-engineering",
            "firmware-malware",
            "firmware-extraction",
            "binwalk",
            "static-malware",
            "automated-malware",
            "malware-triage",
            "malware-hash",
            "malware-ioc",
            "malware-persistence-investigation",
            "malware-behavior",
            "malware-submission",
            "binary-exploitation",
            "heap-spray",
            "steganography",
            "elf-malware",
            "kernel-rootkits",
            "covert-channels-in-malware",
            "uefi-firmware",
            "chipsec",
            "uefi-bootkit",
            "cobalt-strike-beacon",
            "malleable-c2",
            "command-and-control-communication",
        ],
    ),
    (
        "digital_forensics_and_incident_response",
        [
            "disk-image",
            "autopsy",
            "volatility",
            "memory-dump",
            "memory-forensics",
            "memory-artifacts",
            "mft",
            "prefetch",
            "shellbag",
            "amcache",
            "lnk-file",
            "lnk-files",
            "eric-zimmerman",
            "kape",
            "plaso",
            "timesketch",
            "chainsaw",
            "hayabusa",
            "foremost",
            "photorec",
            "sqlite-database-forensics",
            "browser-forensics",
            "browser-history",
            "outlook-pst",
            "rekall",
            "forensics",
            "forensic-",
            "slack-space",
            "usb-device-connection",
            "windows-registry-for-artifacts",
            "windows-amcache",
            "windows-shellbag",
            "collecting-volatile-evidence",
            "triaging-windows-with-kape",
            "super-timelines",
            "timeline-reconstruction",
            "file-carving",
            "ransomware-attack-artifacts",
            "ransomware-recovery-procedures",
            "persistence-mechanisms-in-linux",
            "linux-system-artifacts",
            "linux-audit-logs",
            "powershell-empire-artifacts",
            "velociraptor",
            "windows-event-logs-artifacts",
            "log-analysis-for-forensic",
        ],
    ),
    (
        "threat_intelligence",
        [
            "misp",
            "opencti",
            "stix",
            "taxii",
            "indicators-of-compromise",
            "ioc",
            "threat-actor",
            "threat-intelligence",
            "ttps-with-mitre",
            "osint",
            "spiderfoot",
            "shodan",
            "darkweb",
            "dark-web",
            "campaign-attribution",
            "threat-feed",
            "diamond-model",
            "cyber-kill-chain",
            "brand-monitoring",
            "paste-site-monitoring",
            "threat-landscape",
            "mitre-navigator",
            "mitre-engage",
            "threat-hunt-hypothesis",
            "attack-pattern-library-from-cti",
            "apt-group",
            "mitre-attack-coverage",
            "mitre-attack-techniques",
            "threat-modeling",
            "intelligence-lifecycle",
            "indicator-lifecycle-management",
            "open-source-intelligence",
            "ransomware-leak-site",
            "ransomware-network-indicators",
            "ransomware-payment-wallets",
        ],
    ),
    (
        "active_directory_and_identity_attacks",
        [
            "dpapi",
            "shadow-credentials",
            "active-directory",
            "kerberoast",
            "golden-ticket",
            "dcsync",
            "pass-the-ticket",
            "pass-the-hash",
            "ntlm-relay",
            "adcs",
            "esc1",
            "esc8",
            "bloodhound",
            "constrained-delegation-abuse",
            "nopac",
            "zerologon",
            "entra-id",
            "roadtools",
            "aadinternals",
            "forest-trust",
            "coercer-petitpotam",
            "netexec",
            "graphrunner",
            "mimikatz",
            "wmiexec",
            "lateral-movement",
            "wmi-persistence",
            "wmi-subscriptions",
            "dcom-lateral",
            "domain-persistence",
            "acl-abuse",
            "ldap-security",
            "tiered-model",
            "account-manipulation",
            "oauth-with-device-code-phishing",
            "entra-offensive-tools",
            "saas-sso-token-abuse",
            "credential-access-with-lazagne",
            "hash-cracking",
            "hashcat",
        ],
    ),
    (
        "cloud_security",
        [
            "aws",
            "gcp",
            "azure",
            "cloudtrail",
            "guardduty",
            "cloudfox",
            "scout-suite",
            "pacu",
            "stratus-red-team",
            "cloud-storage",
            "cloud-security",
            "cloud-workload",
            "cloud-native",
            "cloud-dlp",
            "cloud-waf",
            "cloud-vulnerability-posture",
            "cloud-log-forensics",
            "cloud-incident",
            "cloud-penetration",
            "cloud-forensics",
            "cloud-asset-inventory",
            "cloud-siem",
            "cloudflare",
            "cloud-trail",
            "cloud-with-cis-benchmarks",
            "serverless",
            "office365",
            "google-workspace",
            "s3",
            "iam-privilege-escalation",
            "iam-permission",
            "cis-benchmarks",
            "data-loss-prevention-with-microsoft-purview",
        ],
    ),
    (
        "container_and_kubernetes_security",
        [
            "docker",
            "kubernetes",
            "k8s",
            "trivy",
            "falco",
            "calico",
            "kube-bench",
            "kubesec",
            "opa-gatekeeper",
            "pod-security",
            "container",
            "container-escape",
            "distroless",
            "harbor",
            "grype",
            "helm-chart",
            "escaping-containers",
            "rbac-hardening-for-kubernetes",
            "etcd-security",
            "runtime-security-with-tetragon",
        ],
    ),
    (
        "application_and_api_security",
        [
            "sql-injection",
            "sqlmap",
            "xss",
            "xxe",
            "csrf",
            "idor",
            "ssrf",
            "jwt",
            "graphql",
            "oauth2",
            "oauth-misconfiguration",
            "oauth-scope-minimization",
            "api-security",
            "api-gateway",
            "api-key",
            "api-rate-limiting",
            "api-schema",
            "api-fuzzing",
            "api-inventory",
            "api-authentication",
            "api-injection",
            "api-abuse-detection",
            "api-threat-protection",
            "owasp-zap",
            "nikto",
            "websocket",
            "http-request-smuggling",
            "http-parameter-pollution",
            "prototype-pollution",
            "deserialization",
            "mass-assignment",
            "cors-misconfiguration",
            "clickjacking",
            "web-cache",
            "web-application",
            "directory-traversal",
            "open-redirect",
            "host-header-injection",
            "email-header-injection",
            "business-logic-vulnerabilities",
            "broken-access-control",
            "broken-object",
            "broken-function-level",
            "broken-link-hijacking",
            "content-security-policy",
            "security-headers-audit",
            "soap-web-service",
            "thick-client",
            "sensitive-data-exposure",
            "type-juggling",
            "race-condition",
            "template-injection",
            "nosql-injection",
            "second-order-sql-injection",
            "burpsuite",
            "api-security-testing-with-postman",
            "excessive-data-exposure",
            "xml-injection",
            "cryptographic-audit-of-application",
        ],
    ),
    (
        "network_security_and_perimeter",
        [
            "nmap",
            "wireshark",
            "pfsense",
            "snort",
            "suricata",
            "arp-poisoning",
            "arp-spoofing",
            "vlan-hopping",
            "bgp-hijacking",
            "bgp-security",
            "network-segmentation",
            "firewall",
            "next-generation-firewall",
            "network-access-control",
            "host-based-intrusion",
            "ids-signatures",
            "fail2ban",
            "port-scanning",
            "packet-injection",
            "ssl-stripping",
            "man-in-the-middle",
            "bandwidth-throttling",
            "wireless-network",
            "wifi-password",
            "aircrack",
            "kismet",
            "bluetooth",
            "ipv6-vulnerabilities",
            "subdomain-enumeration",
            "dns-enumeration",
            "certificate-transparency",
            "tls-1-3",
            "tls-inspection",
            "ssl-tls",
            "ssl-certificate",
            "forced-browsing",
            "network-traffic-baselining",
            "eternalblue",
        ],
    ),
    (
        "zero_trust_and_secure_access",
        [
            "zero-trust",
            "ztna",
            "beyondcorp",
            "zscaler",
            "tailscale",
            "hashicorp-boundary",
            "microsegmentation",
            "software-defined-perimeter",
            "mtls",
            "conditional-access",
            "identity-aware-proxy",
            "browser-isolation",
            "device-posture",
            "network-access-control-with-cisco-ise",
        ],
    ),
    (
        "identity_and_access_management",
        [
            "privileged-access",
            "pam-for",
            "cyberark",
            "delinea",
            "hashicorp-vault",
            "secrets-management",
            "sailpoint",
            "saviynt",
            "role-mining",
            "entitlement-review",
            "service-account",
            "multi-factor-authentication",
            "passwordless",
            "fido2",
            "hardware-security-key",
            "identity-governance",
            "identity-federation",
            "privileged-session",
            "privileged-account",
            "just-in-time-access",
            "scim-provisioning",
            "saml-sso",
            "okta",
            "access-recertification",
            "access-review-and-certification",
            "zero-standing-privilege",
            "managing-cloud-identity",
        ],
    ),
    (
        "cryptography_and_pki",
        [
            "openssl",
            "hsm-for",
            "rsa-key",
            "ed25519",
            "aes-encryption",
            "envelope-encryption",
            "post-quantum-cryptography",
            "digital-signatures",
            "jwt-signing",
            "zero-knowledge-proof",
            "disk-encryption",
            "end-to-end-encryption",
            "tpm-measured-boot",
            "certificate-authority",
            "certificate-lifecycle",
            "hardware-security-module",
        ],
    ),
    (
        "supply_chain_and_devsecops",
        [
            "sbom",
            "slsa",
            "sigstore",
            "in-toto",
            "dependency-confusion",
            "typosquatting",
            "npm",
            "pypi",
            "gitleaks",
            "secret-scanning",
            "secrets-scanning",
            "devsecops",
            "sast",
            "dast",
            "semgrep",
            "snyk",
            "github-advanced-security",
            "github-actions-workflows",
            "infrastructure-as-code-security",
            "code-signing",
            "image-provenance",
            "build-provenance",
            "fuzz-testing",
            "fuzzing",
            "terraform-infrastructure",
            "policy-as-code",
            "opa",
        ],
    ),
    (
        "email_and_social_engineering_security",
        [
            "phishing",
            "dmarc",
            "proofpoint",
            "mimecast",
            "spearphishing",
            "vishing",
            "social-engineering",
            "qr-code-phishing",
            "email-account-compromise",
            "email-forwarding-rules",
            "email-security",
            "deepfake-audio",
            "pretext-call",
        ],
    ),
    (
        "vulnerability_management",
        [
            "cvss",
            "epss",
            "kev-catalog",
            "nessus",
            "openvas",
            "greenbone",
            "rapid7-insightvm",
            "defectdojo",
            "vulnerability-scanning",
            "vulnerability-management",
            "vulnerability-remediation",
            "vulnerability-sla",
            "vulnerability-aging",
            "vulnerability-exception",
            "vulnerability-dashboard",
            "vulnerability-triage",
            "ssvc-framework",
            "asset-criticality-scoring",
            "authenticated-scan",
            "authenticated-vulnerability-scan",
            "agentless-vulnerability",
            "attack-surface-management",
            "attack-path-analysis",
            "continuous-security-validation",
            "security-chaos-engineering",
            "patch-management",
        ],
    ),
    (
        "endpoint_security_and_hardening",
        [
            "edr-agent",
            "windows-defender",
            "endpoint-dlp",
            "osquery",
            "file-integrity-monitoring",
            "memory-protection-with-dep-aslr",
            "application-whitelisting",
            "usb-device-control",
            "ebpf-security-monitoring",
            "runtime-application-self-protection",
            "privilege-escalation-assessment",
            "privilege-escalation-on-linux",
            "anti-ransomware-group-policy",
            "windows-event-logging-for-detection",
            "immutable-backup",
            "restic",
        ],
    ),
    (
        "offensive_security_and_red_teaming",
        [
            "metasploit",
            "c2",
            "sliver",
            "havoc",
            "covenant",
            "red-team",
            "red-teaming",
            "purple-team",
            "penetration-test",
            "pentest",
            "initial-access",
            "evilginx3",
            "gophish",
            "physical-intrusion",
            "adversary-infrastructure",
            "adversary-engagement",
            "attack-simulation",
            "iot-security-assessment",
            "bluetooth-security-assessment",
        ],
    ),
    (
        "incident_response_and_soc_operations",
        [
            "incident-response",
            "ir-playbook",
            "soc-escalation",
            "soc-metrics",
            "soc-playbook",
            "soc-tabletop",
            "tabletop-exercise",
            "containing-active-breach",
            "eradicating-malware",
            "recovering-from-ransomware",
            "ransomware-response",
            "ransomware-playbook",
            "ransomware-backup",
            "ransomware-kill-switch",
            "ransomware-tabletop",
            "ransomware-canary",
            "triaging-security",
            "ticketing-system-for-incidents",
            "post-incident-lessons-learned",
            "patch-tuesday-response",
            "malware-incident",
            "phishing-incident",
            "phishing-reporting-button",
            "backup-integrity",
            "validating-backup",
            "insider-threat-indicators",
            "insider-threat-investigation",
            "soar-automation",
            "soar-playbook",
            "endpoint-detection",
        ],
    ),
    (
        "compliance_and_grc",
        [
            "cmmc",
            "cis-benchmark",
            "nist-800-30",
            "nist-rmf",
            "nist-csf",
            "gdpr",
            "hipaa",
            "pci-dss",
            "iso-27001",
            "nerc-cip",
            "iec-62443",
            "soc2",
            "privacy-impact-assessment",
            "third-party-vendor-risk",
            "cyber-risk-assessment",
            "compliance",
        ],
    ),
]

FALLBACK_PREFIXES = ("detecting-", "hunting-", "triaging-")

VERB_PREFIX_RE = re.compile(
    r"^(abusing|achieving|acquiring|analyzing|auditing|automating|building|"
    r"bypassing|collecting|configuring|conducting|containing|correlating|"
    r"deobfuscating|deploying|detecting|defending|eradicating|enumerating|"
    r"executing|exploiting|extracting|fleeing|generating|hardening|hunting|"
    r"implementing|integrating|investigating|mapping|migrating|monitoring|"
    r"moving|orchestrating|performing|post-exploiting|prioritizing|processing|"
    r"profiling|recovering|remediating|reverse-engineering|scanning|securing|"
    r"testing|triaging|troubleshooting|validating)-"
)


def verb_prefix(slug: str) -> str | None:
    m = VERB_PREFIX_RE.match(slug)
    return m.group(1) if m else None


def find_all_topic_hits(slug: str) -> list[tuple[str, str]]:
    """Return all (domain, keyword) hits in rule order (for secondary topics)."""
    match_slug = normalize_for_match(slug)
    hits: list[tuple[str, str]] = []
    for domain_id, keywords in DOMAIN_RULES:
        for kw in keywords:
            if keyword_matches(match_slug, kw) or keyword_matches(slug, kw):
                hits.append((domain_id, kw))
                break  # one keyword per domain is enough
    return hits


def classify(slug: str) -> tuple[str, str | None, str | None, list[str], str | None]:
    """
    Returns:
      node_type, primary_domain, matched_keyword, secondary_domains, verb
    """
    verb = verb_prefix(slug)

    if slug in bare_domains:
        return ("domain", slug, None, [], verb)
    if slug in meta_or_uncertain:
        return ("infra_or_meta_needs_triage", None, None, [], verb)
    if slug in policy_items:
        return ("policy", "legal_and_rules_of_engagement", None, [], verb)

    hits = find_all_topic_hits(slug)
    if hits:
        primary_domain, matched_kw = hits[0]
        secondary = [d for d, _ in hits[1:] if d != primary_domain]
        return ("skill", primary_domain, matched_kw, secondary, verb)

    if any(slug.startswith(p) for p in FALLBACK_PREFIXES):
        return (
            "skill",
            "detection_engineering_and_threat_hunting",
            "fallback-verb",
            [],
            verb,
        )

    return ("skill", "unclassified", None, [], verb)


# --- Golden set: regressions that must stay correct ---
DEFAULT_GOLDEN = [
    # False-positive regressions
    ("analyzing-threat-landscape-with-misp", "threat_intelligence"),
    ("detecting-container-escape-attempts", "container_and_kubernetes_security"),
    ("detecting-container-escape-with-falco-rules", "container_and_kubernetes_security"),
    ("performing-soc2-type2-audit-preparation", "compliance_and_grc"),
    # Synonym / previously unclassified
    ("exploiting-server-side-request-forgery", "application_and_api_security"),
    ("implementing-canary-tokens-for-network-intrusion", "deception_technology"),
    ("implementing-immutable-backup-with-restic", "endpoint_security_and_hardening"),
    ("implementing-policy-as-code-with-open-policy-agent", "supply_chain_and_devsecops"),
    # Detection engineering coverage
    ("building-detection-rules-with-sigma", "detection_engineering_and_threat_hunting"),
    ("analyzing-security-logs-with-splunk", "detection_engineering_and_threat_hunting"),
    ("performing-threat-hunting-with-elastic-siem", "detection_engineering_and_threat_hunting"),
    ("implementing-siem-use-cases-for-detection", "detection_engineering_and_threat_hunting"),
    # Stable positives
    ("exploiting-jwt-algorithm-confusion-attack", "application_and_api_security"),
    ("analyzing-android-malware-with-apktool", "mobile_security"),
    ("abusing-dpapi-for-credential-access", "active_directory_and_identity_attacks"),
    ("achieving-cmmc-level-2-compliance", "compliance_and_grc"),
    ("analyzing-ethereum-smart-contract-vulnerabilities", "web3_and_smart_contract_security"),
    ("deploying-honeytokens-and-canarytokens", "deception_technology"),
    ("building-c2-infrastructure-with-sliver-framework", "offensive_security_and_red_teaming"),
    ("detecting-malicious-npm-packages", "supply_chain_and_devsecops"),
    ("defending-llms-with-guardrails", "ai_and_llm_security"),
    ("generating-and-analyzing-sboms", "supply_chain_and_devsecops"),
    ("implementing-security-information-sharing-with-stix2", "threat_intelligence"),
]


def load_golden() -> list[tuple[str, str]]:
    if GOLDEN_CSV.exists():
        rows = []
        with GOLDEN_CSV.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append((row["skill_id"], row["expected_domain"]))
        return rows
    return DEFAULT_GOLDEN


def write_golden_if_missing() -> None:
    if GOLDEN_CSV.exists():
        return
    with GOLDEN_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["skill_id", "expected_domain", "notes"])
        for skill_id, domain in DEFAULT_GOLDEN:
            w.writerow([skill_id, domain, ""])


def run_golden(verbose: bool = True) -> int:
    golden = load_golden()
    failures = []
    for skill_id, expected in golden:
        _, domain, kw, secondary, _ = classify(skill_id)
        if domain != expected:
            failures.append((skill_id, expected, domain, kw, secondary))
    if verbose:
        if failures:
            print(f"GOLDEN FAIL: {len(failures)}/{len(golden)}")
            for skill_id, expected, got, kw, secondary in failures:
                print(f"  {skill_id}: expected={expected} got={got} via={kw!r} secondary={secondary}")
        else:
            print(f"GOLDEN PASS: {len(golden)}/{len(golden)}")
    return len(failures)


def main() -> int:
    write_golden_if_missing()

    if not SKILLS_RAW.exists():
        print(f"Missing {SKILLS_RAW}", file=sys.stderr)
        return 1

    slugs = [l.strip() for l in SKILLS_RAW.read_text(encoding="utf-8").splitlines() if l.strip()]

    rows = []
    domain_counter: Counter[str] = Counter()
    type_counter: Counter[str] = Counter()
    unclassified: list[str] = []

    for slug in slugs:
        node_type, domain, matched_kw, secondary, verb = classify(slug)
        m = re.search(r"-with-([a-z0-9\-]+)$", slug)
        tool = m.group(1) if m else None

        rows.append(
            (
                slug,
                node_type,
                domain or "",
                tool or "",
                matched_kw or "",
                ";".join(secondary),
                verb or "",
            )
        )

        type_counter[node_type] += 1
        if node_type == "skill":
            domain_counter[domain or ""] += 1
            if domain == "unclassified":
                unclassified.append(slug)

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "skill_id",
                "node_type",
                "domain",
                "detected_tool",
                "matched_keyword",
                "secondary_domains",
                "verb_prefix",
            ]
        )
        writer.writerows(sorted(rows))

    print("TYPE COUNTS:", dict(type_counter))
    print("\nDOMAIN COUNTS (skills only), total skills:", sum(domain_counter.values()))
    for d, c in domain_counter.most_common():
        print(f"  {d}: {c}")
    print(f"\nTotal slugs: {len(slugs)}")
    print(f"\nUnclassified ({len(unclassified)}):")
    for u in unclassified:
        print(" ", u)

    print()
    fails = run_golden()
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
