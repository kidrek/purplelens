/**
 * Mapping statique ATT&CK → D3FEND
 *
 * Chaque entrée contient :
 *   cat  : catégorie D3FEND (harden | detect | isolate | deceive | evict | restore)
 *   name : nom de la contre-mesure D3FEND
 *   d3f_id : identifiant D3FEND pour construire l'URL
 *
 * URL ATT&CK  : https://attack.mitre.org/techniques/{T_CODE}/
 *               (sous-technique : remplacer . par /)
 * URL D3FEND  : https://d3fend.mitre.org/technique/d3f:{d3f_id}/
 *
 * Source : https://d3fend.mitre.org (mapping officiel MITRE)
 * Ce fichier est le fallback offline. L'import via Paramètres
 * enrichira ces données avec le mapping complet.
 */

export const D3FEND_MAP = {
  // ── Initial Access ───────────────────────────────────────────────────────
  "T1566": [
    { cat: "harden",  name: "Multi-factor Authentication",     d3f_id: "Multi-factorAuthentication" },
    { cat: "harden",  name: "User Account Permissions Limiting", d3f_id: "UserAccountPermissionsLimiting" },
    { cat: "detect",  name: "Email Link Analysis",              d3f_id: "EmailLinkAnalysis" },
    { cat: "detect",  name: "User Behavior Analysis",           d3f_id: "UserBehaviorAnalysis" },
    { cat: "isolate", name: "Inbound Traffic Filtering",        d3f_id: "InboundTrafficFiltering" },
  ],
  "T1566.001": [
    { cat: "harden",  name: "Multi-factor Authentication",     d3f_id: "Multi-factorAuthentication" },
    { cat: "detect",  name: "Email Link Analysis",              d3f_id: "EmailLinkAnalysis" },
    { cat: "detect",  name: "Dynamic Analysis",                 d3f_id: "DynamicAnalysis" },
  ],
  "T1566.002": [
    { cat: "harden",  name: "Multi-factor Authentication",     d3f_id: "Multi-factorAuthentication" },
    { cat: "detect",  name: "URL Analysis",                     d3f_id: "URLAnalysis" },
    { cat: "isolate", name: "Inbound Traffic Filtering",        d3f_id: "InboundTrafficFiltering" },
  ],
  "T1190": [
    { cat: "harden",  name: "Application Hardening",            d3f_id: "ApplicationHardening" },
    { cat: "harden",  name: "Application Configuration Hardening", d3f_id: "ApplicationConfigurationHardening" },
    { cat: "detect",  name: "Dynamic Analysis",                 d3f_id: "DynamicAnalysis" },
    { cat: "isolate", name: "Inbound Traffic Filtering",        d3f_id: "InboundTrafficFiltering" },
  ],
  "T1078": [
    { cat: "harden",  name: "Multi-factor Authentication",     d3f_id: "Multi-factorAuthentication" },
    { cat: "harden",  name: "User Account Permissions Limiting", d3f_id: "UserAccountPermissionsLimiting" },
    { cat: "detect",  name: "Authentication Event Thresholding", d3f_id: "AuthenticationEventThresholding" },
    { cat: "detect",  name: "Resource Access Pattern Analysis", d3f_id: "ResourceAccessPatternAnalysis" },
    { cat: "evict",   name: "Account Locking",                  d3f_id: "AccountLocking" },
  ],
  "T1133": [
    { cat: "harden",  name: "Multi-factor Authentication",     d3f_id: "Multi-factorAuthentication" },
    { cat: "detect",  name: "Remote Terminal Session Detection", d3f_id: "RemoteTerminalSessionDetection" },
    { cat: "isolate", name: "Network Isolation",                d3f_id: "NetworkIsolation" },
  ],
  "T1195": [
    { cat: "harden",  name: "Application Hardening",            d3f_id: "ApplicationHardening" },
    { cat: "detect",  name: "File Hash Verification",           d3f_id: "FileHashVerification" },
    { cat: "detect",  name: "Signature Analysis",               d3f_id: "SignatureAnalysis" },
  ],

  // ── Execution ────────────────────────────────────────────────────────────
  "T1059": [
    { cat: "harden",  name: "Application Execution Policy",    d3f_id: "ApplicationExecutionPolicy" },
    { cat: "detect",  name: "Script Execution Analysis",        d3f_id: "ScriptExecutionAnalysis" },
    { cat: "detect",  name: "Process Lineage Analysis",         d3f_id: "ProcessLineageAnalysis" },
    { cat: "detect",  name: "System Call Analysis",             d3f_id: "SystemCallAnalysis" },
  ],
  "T1059.001": [
    { cat: "harden",  name: "Application Execution Policy",    d3f_id: "ApplicationExecutionPolicy" },
    { cat: "detect",  name: "Script Execution Analysis",        d3f_id: "ScriptExecutionAnalysis" },
    { cat: "isolate", name: "Kernel-based Process Isolation",   d3f_id: "KernelbasedProcessIsolation" },
  ],
  "T1059.003": [
    { cat: "harden",  name: "Application Execution Policy",    d3f_id: "ApplicationExecutionPolicy" },
    { cat: "detect",  name: "Process Lineage Analysis",         d3f_id: "ProcessLineageAnalysis" },
    { cat: "detect",  name: "System Call Analysis",             d3f_id: "SystemCallAnalysis" },
  ],
  "T1106": [
    { cat: "harden",  name: "Application Hardening",            d3f_id: "ApplicationHardening" },
    { cat: "detect",  name: "System Call Analysis",             d3f_id: "SystemCallAnalysis" },
    { cat: "isolate", name: "Kernel-based Process Isolation",   d3f_id: "KernelbasedProcessIsolation" },
  ],
  "T1204": [
    { cat: "harden",  name: "Application Execution Policy",    d3f_id: "ApplicationExecutionPolicy" },
    { cat: "detect",  name: "Dynamic Analysis",                 d3f_id: "DynamicAnalysis" },
    { cat: "detect",  name: "User Behavior Analysis",           d3f_id: "UserBehaviorAnalysis" },
  ],

  // ── Persistence ──────────────────────────────────────────────────────────
  "T1053": [
    { cat: "harden",  name: "Application Configuration Hardening", d3f_id: "ApplicationConfigurationHardening" },
    { cat: "detect",  name: "Process Lineage Analysis",         d3f_id: "ProcessLineageAnalysis" },
    { cat: "detect",  name: "Scheduled Job Analysis",           d3f_id: "ScheduledJobAnalysis" },
  ],
  "T1547": [
    { cat: "harden",  name: "Bootloader Authentication",        d3f_id: "BootloaderAuthentication" },
    { cat: "harden",  name: "System Configuration Permissions", d3f_id: "SystemConfigurationPermissions" },
    { cat: "detect",  name: "Process Lineage Analysis",         d3f_id: "ProcessLineageAnalysis" },
  ],
  "T1136": [
    { cat: "harden",  name: "User Account Permissions Limiting", d3f_id: "UserAccountPermissionsLimiting" },
    { cat: "detect",  name: "User Account Management",           d3f_id: "UserAccountManagement" },
    { cat: "detect",  name: "Authentication Event Thresholding", d3f_id: "AuthenticationEventThresholding" },
  ],

  // ── Privilege Escalation ──────────────────────────────────────────────────
  "T1068": [
    { cat: "harden",  name: "Application Hardening",            d3f_id: "ApplicationHardening" },
    { cat: "harden",  name: "Segment Address Offset Randomization", d3f_id: "SegmentAddressOffsetRandomization" },
    { cat: "detect",  name: "System Call Analysis",             d3f_id: "SystemCallAnalysis" },
    { cat: "isolate", name: "Kernel-based Process Isolation",   d3f_id: "KernelbasedProcessIsolation" },
  ],
  "T1055": [
    { cat: "harden",  name: "Segment Address Offset Randomization", d3f_id: "SegmentAddressOffsetRandomization" },
    { cat: "detect",  name: "Process Code Segment Verification", d3f_id: "ProcessCodeSegmentVerification" },
    { cat: "detect",  name: "System Call Analysis",             d3f_id: "SystemCallAnalysis" },
    { cat: "isolate", name: "Kernel-based Process Isolation",   d3f_id: "KernelbasedProcessIsolation" },
  ],

  // ── Defense Evasion ───────────────────────────────────────────────────────
  "T1036": [
    { cat: "detect",  name: "File Hash Verification",           d3f_id: "FileHashVerification" },
    { cat: "detect",  name: "Process Lineage Analysis",         d3f_id: "ProcessLineageAnalysis" },
    { cat: "detect",  name: "Signature Analysis",               d3f_id: "SignatureAnalysis" },
  ],
  "T1562": [
    { cat: "harden",  name: "System Configuration Permissions", d3f_id: "SystemConfigurationPermissions" },
    { cat: "detect",  name: "System Call Analysis",             d3f_id: "SystemCallAnalysis" },
    { cat: "detect",  name: "Process Lineage Analysis",         d3f_id: "ProcessLineageAnalysis" },
  ],
  "T1070": [
    { cat: "harden",  name: "System Configuration Permissions", d3f_id: "SystemConfigurationPermissions" },
    { cat: "detect",  name: "File Analysis",                    d3f_id: "FileAnalysis" },
    { cat: "detect",  name: "System Call Analysis",             d3f_id: "SystemCallAnalysis" },
  ],

  // ── Credential Access ─────────────────────────────────────────────────────
  "T1003": [
    { cat: "harden",  name: "Credential Hardening",             d3f_id: "CredentialHardening" },
    { cat: "harden",  name: "Biometric Authentication",         d3f_id: "BiometricAuthentication" },
    { cat: "detect",  name: "Process Code Segment Verification", d3f_id: "ProcessCodeSegmentVerification" },
    { cat: "isolate", name: "Kernel-based Process Isolation",   d3f_id: "KernelbasedProcessIsolation" },
  ],
  "T1003.001": [
    { cat: "harden",  name: "Credential Hardening",             d3f_id: "CredentialHardening" },
    { cat: "detect",  name: "Process Code Segment Verification", d3f_id: "ProcessCodeSegmentVerification" },
    { cat: "isolate", name: "Kernel-based Process Isolation",   d3f_id: "KernelbasedProcessIsolation" },
  ],
  "T1110": [
    { cat: "harden",  name: "Multi-factor Authentication",     d3f_id: "Multi-factorAuthentication" },
    { cat: "harden",  name: "Strong Password Policy",           d3f_id: "StrongPasswordPolicy" },
    { cat: "detect",  name: "Authentication Event Thresholding", d3f_id: "AuthenticationEventThresholding" },
    { cat: "evict",   name: "Account Locking",                  d3f_id: "AccountLocking" },
  ],
  "T1187": [
    { cat: "harden",  name: "Credential Hardening",             d3f_id: "CredentialHardening" },
    { cat: "isolate", name: "Network Isolation",                d3f_id: "NetworkIsolation" },
    { cat: "detect",  name: "Network Traffic Community Deviation", d3f_id: "NetworkTrafficCommunityDeviation" },
  ],

  // ── Discovery ─────────────────────────────────────────────────────────────
  "T1083": [
    { cat: "harden",  name: "Application Configuration Hardening", d3f_id: "ApplicationConfigurationHardening" },
    { cat: "detect",  name: "File Analysis",                    d3f_id: "FileAnalysis" },
    { cat: "detect",  name: "System Call Analysis",             d3f_id: "SystemCallAnalysis" },
  ],
  "T1082": [
    { cat: "harden",  name: "Application Configuration Hardening", d3f_id: "ApplicationConfigurationHardening" },
    { cat: "detect",  name: "System Call Analysis",             d3f_id: "SystemCallAnalysis" },
    { cat: "deceive", name: "Decoy Environment",                d3f_id: "DecoyEnvironment" },
  ],
  "T1046": [
    { cat: "isolate", name: "Network Isolation",                d3f_id: "NetworkIsolation" },
    { cat: "detect",  name: "Network Traffic Community Deviation", d3f_id: "NetworkTrafficCommunityDeviation" },
    { cat: "detect",  name: "Protocol Metadata Anomaly Detection", d3f_id: "ProtocolMetadataAnomalyDetection" },
  ],

  // ── Lateral Movement ──────────────────────────────────────────────────────
  "T1021": [
    { cat: "harden",  name: "Multi-factor Authentication",     d3f_id: "Multi-factorAuthentication" },
    { cat: "detect",  name: "Remote Terminal Session Detection", d3f_id: "RemoteTerminalSessionDetection" },
    { cat: "isolate", name: "Network Isolation",                d3f_id: "NetworkIsolation" },
  ],
  "T1021.001": [
    { cat: "harden",  name: "Credential Hardening",             d3f_id: "CredentialHardening" },
    { cat: "detect",  name: "Remote Terminal Session Detection", d3f_id: "RemoteTerminalSessionDetection" },
    { cat: "isolate", name: "Network Isolation",                d3f_id: "NetworkIsolation" },
  ],
  "T1021.002": [
    { cat: "harden",  name: "Credential Hardening",             d3f_id: "CredentialHardening" },
    { cat: "detect",  name: "Remote Terminal Session Detection", d3f_id: "RemoteTerminalSessionDetection" },
    { cat: "isolate", name: "Broadcast Domain Isolation",       d3f_id: "BroadcastDomainIsolation" },
  ],
  "T1534": [
    { cat: "detect",  name: "User Behavior Analysis",           d3f_id: "UserBehaviorAnalysis" },
    { cat: "detect",  name: "Authentication Event Thresholding", d3f_id: "AuthenticationEventThresholding" },
    { cat: "isolate", name: "Network Isolation",                d3f_id: "NetworkIsolation" },
  ],

  // ── Collection ────────────────────────────────────────────────────────────
  "T1560": [
    { cat: "detect",  name: "File Analysis",                    d3f_id: "FileAnalysis" },
    { cat: "detect",  name: "System Call Analysis",             d3f_id: "SystemCallAnalysis" },
    { cat: "isolate", name: "Outbound Traffic Filtering",       d3f_id: "OutboundTrafficFiltering" },
  ],
  "T1074": [
    { cat: "detect",  name: "File Analysis",                    d3f_id: "FileAnalysis" },
    { cat: "detect",  name: "User Data Transfer Analysis",      d3f_id: "UserDataTransferAnalysis" },
    { cat: "detect",  name: "System Call Analysis",             d3f_id: "SystemCallAnalysis" },
  ],

  // ── Command and Control ───────────────────────────────────────────────────
  "T1071": [
    { cat: "detect",  name: "DNS Traffic Analysis",             d3f_id: "DNSTrafficAnalysis" },
    { cat: "detect",  name: "Protocol Metadata Anomaly Detection", d3f_id: "ProtocolMetadataAnomalyDetection" },
    { cat: "isolate", name: "Forward Resolution Domain Denylisting", d3f_id: "ForwardResolutionDomainDenylisting" },
  ],
  "T1071.001": [
    { cat: "detect",  name: "Network Traffic Community Deviation", d3f_id: "NetworkTrafficCommunityDeviation" },
    { cat: "detect",  name: "Protocol Metadata Anomaly Detection", d3f_id: "ProtocolMetadataAnomalyDetection" },
    { cat: "isolate", name: "Outbound Traffic Filtering",       d3f_id: "OutboundTrafficFiltering" },
  ],
  "T1095": [
    { cat: "detect",  name: "Network Traffic Community Deviation", d3f_id: "NetworkTrafficCommunityDeviation" },
    { cat: "isolate", name: "Outbound Traffic Filtering",       d3f_id: "OutboundTrafficFiltering" },
    { cat: "detect",  name: "Protocol Metadata Anomaly Detection", d3f_id: "ProtocolMetadataAnomalyDetection" },
  ],
  "T1572": [
    { cat: "detect",  name: "Network Traffic Community Deviation", d3f_id: "NetworkTrafficCommunityDeviation" },
    { cat: "isolate", name: "Encrypted Tunnels",                d3f_id: "EncryptedTunnels" },
    { cat: "detect",  name: "Protocol Metadata Anomaly Detection", d3f_id: "ProtocolMetadataAnomalyDetection" },
  ],

  // ── Exfiltration ──────────────────────────────────────────────────────────
  "T1041": [
    { cat: "isolate", name: "Outbound Traffic Filtering",       d3f_id: "OutboundTrafficFiltering" },
    { cat: "detect",  name: "Network Traffic Community Deviation", d3f_id: "NetworkTrafficCommunityDeviation" },
    { cat: "detect",  name: "User Data Transfer Analysis",      d3f_id: "UserDataTransferAnalysis" },
  ],
  "T1048": [
    { cat: "isolate", name: "Outbound Traffic Filtering",       d3f_id: "OutboundTrafficFiltering" },
    { cat: "detect",  name: "Protocol Metadata Anomaly Detection", d3f_id: "ProtocolMetadataAnomalyDetection" },
    { cat: "detect",  name: "User Data Transfer Analysis",      d3f_id: "UserDataTransferAnalysis" },
  ],

  // ── Impact ────────────────────────────────────────────────────────────────
  "T1486": [
    { cat: "harden",  name: "Backup System",                    d3f_id: "BackupSystem" },
    { cat: "detect",  name: "File Analysis",                    d3f_id: "FileAnalysis" },
    { cat: "detect",  name: "System Call Analysis",             d3f_id: "SystemCallAnalysis" },
    { cat: "evict",   name: "File Removal",                     d3f_id: "FileRemoval" },
  ],
  "T1490": [
    { cat: "harden",  name: "Bootloader Authentication",        d3f_id: "BootloaderAuthentication" },
    { cat: "harden",  name: "Backup System",                    d3f_id: "BackupSystem" },
    { cat: "detect",  name: "System Call Analysis",             d3f_id: "SystemCallAnalysis" },
  ],
  "T1498": [
    { cat: "isolate", name: "Inbound Traffic Filtering",        d3f_id: "InboundTrafficFiltering" },
    { cat: "detect",  name: "Network Traffic Community Deviation", d3f_id: "NetworkTrafficCommunityDeviation" },
    { cat: "isolate", name: "Network Isolation",                d3f_id: "NetworkIsolation" },
  ],
  "T1489": [
    { cat: "harden",  name: "System Configuration Permissions", d3f_id: "SystemConfigurationPermissions" },
    { cat: "detect",  name: "Process Lineage Analysis",         d3f_id: "ProcessLineageAnalysis" },
    { cat: "evict",   name: "Process Termination",              d3f_id: "ProcessTermination" },
  ],
};

/**
 * Catégories D3FEND avec couleur CSS et libellé
 */
export const D3FEND_CATEGORIES = {
  harden:  { label: "Harden",  css: "d3cat-harden" },
  detect:  { label: "Detect",  css: "d3cat-detect" },
  isolate: { label: "Isolate", css: "d3cat-isolate" },
  deceive: { label: "Deceive", css: "d3cat-deceive" },
  evict:   { label: "Evict",   css: "d3cat-evict" },
  restore: { label: "Restore", css: "d3cat-restore" },
};

/**
 * Construit l'URL MITRE ATT&CK pour un T-code.
 * T1566     → https://attack.mitre.org/techniques/T1566/
 * T1566.001 → https://attack.mitre.org/techniques/T1566/001/
 */
export function attackUrl(mitre_id) {
  const parts = mitre_id.replace("T", "").split(".");
  if (parts.length === 2) {
    return `https://attack.mitre.org/techniques/T${parts[0]}/${parts[1]}/`;
  }
  return `https://attack.mitre.org/techniques/${mitre_id}/`;
}

/**
 * Construit l'URL D3FEND pour un identifiant de contre-mesure.
 * "MultiFactorAuthentication" → https://d3fend.mitre.org/technique/d3f:MultiFactorAuthentication/
 */
export function d3fendUrl(d3f_id) {
  return `https://d3fend.mitre.org/technique/d3f:${d3f_id}/`;
}

/**
 * Retourne les contre-mesures D3FEND pour un T-code donné.
 * Cherche d'abord la correspondance exacte, sinon le parent (T1566.001 → T1566).
 */
export function getD3fendMeasures(mitre_id) {
  if (D3FEND_MAP[mitre_id]) return D3FEND_MAP[mitre_id];
  // Fallback sur la technique parente pour les sous-techniques
  const parent = mitre_id.split(".")[0];
  return D3FEND_MAP[parent] || [];
}
