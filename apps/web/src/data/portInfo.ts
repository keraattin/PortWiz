// Reference notes for well-known ports, shown on the port detail page so a
// non-expert can tell at a glance what a port is normally for and why it may
// matter. The service name is the canonical (nmap-style) label; descriptions are
// kept short and in English as technical reference. The surrounding page chrome
// is localised through i18n.

export interface PortInfo {
  service: string;
  description: string;
}

export const PORT_INFO: Record<number, PortInfo> = {
  20: { service: "FTP-data", description: "FTP data channel, paired with control port 21. Unencrypted." },
  21: { service: "FTP", description: "File Transfer Protocol. Moves files between hosts; credentials and data travel unencrypted." },
  22: { service: "SSH", description: "Secure Shell. Encrypted remote login and command execution." },
  23: { service: "Telnet", description: "Unencrypted remote login. Legacy and insecure; avoid exposing it." },
  25: { service: "SMTP", description: "Simple Mail Transfer Protocol. Server-to-server email delivery." },
  53: { service: "DNS", description: "Domain Name System. Resolves hostnames to IP addresses." },
  67: { service: "DHCP", description: "Hands out IP addresses to hosts on the network." },
  69: { service: "TFTP", description: "Trivial File Transfer Protocol. No authentication; often used for device firmware." },
  80: { service: "HTTP", description: "Web traffic in the clear. Usually redirects to HTTPS." },
  110: { service: "POP3", description: "Retrieves email from a mailbox; the plaintext variant." },
  123: { service: "NTP", description: "Network Time Protocol. Synchronises the clock over the network." },
  135: { service: "MSRPC", description: "Windows RPC endpoint mapper. Common on internal Windows networks." },
  139: { service: "NetBIOS", description: "Legacy Windows file sharing over NetBIOS." },
  143: { service: "IMAP", description: "Reads email on the server; the plaintext variant." },
  161: { service: "SNMP", description: "Network device monitoring and management. Weak community strings are a common risk." },
  389: { service: "LDAP", description: "Directory service for users and groups; the plaintext variant." },
  443: { service: "HTTPS", description: "Web traffic over TLS. The standard for secure websites." },
  445: { service: "SMB", description: "Windows file and printer sharing. A frequent malware and ransomware target." },
  465: { service: "SMTPS", description: "SMTP email submission over TLS." },
  514: { service: "Syslog", description: "Remote logging. Often unauthenticated over UDP." },
  587: { service: "SMTP submission", description: "Authenticated email submission from clients to a mail server." },
  636: { service: "LDAPS", description: "LDAP directory service over TLS." },
  993: { service: "IMAPS", description: "IMAP email access over TLS." },
  995: { service: "POP3S", description: "POP3 email retrieval over TLS." },
  1433: { service: "MSSQL", description: "Microsoft SQL Server database." },
  1521: { service: "Oracle", description: "Oracle database listener." },
  2049: { service: "NFS", description: "Network File System. Shared filesystems, often trusted by IP." },
  2375: { service: "Docker", description: "Docker daemon API. Unauthenticated exposure grants full host control." },
  3306: { service: "MySQL", description: "MySQL / MariaDB database." },
  3389: { service: "RDP", description: "Windows Remote Desktop. A common brute-force and ransomware target." },
  5432: { service: "PostgreSQL", description: "PostgreSQL database." },
  5900: { service: "VNC", description: "Remote desktop sharing. Often weakly authenticated." },
  6379: { service: "Redis", description: "Redis in-memory data store. Frequently exposed without a password." },
  8080: { service: "HTTP-alt", description: "Alternate HTTP port, often an application server or proxy." },
  8443: { service: "HTTPS-alt", description: "Alternate HTTPS port, often an admin console or proxy." },
  9200: { service: "Elasticsearch", description: "Elasticsearch search and analytics API. Exposed clusters leak data." },
  11211: { service: "Memcached", description: "Memcached cache. Exposed instances are abused for DDoS amplification." },
  27017: { service: "MongoDB", description: "MongoDB database. Historically exposed without authentication." },
};

export function portInfo(port: number): PortInfo | undefined {
  return PORT_INFO[port];
}
