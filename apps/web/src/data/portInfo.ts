import { type TKey } from "../i18n/locales/en";

// Reference notes for well-known ports, shown on the port detail page so a
// non-expert can tell at a glance what a port is normally for and why it may
// matter. The service name is the canonical (nmap-style) label; the description
// is an i18n key (`portinfo.<port>`) so it renders in the viewer's language.

export interface PortInfo {
  service: string;
  descKey: TKey;
}

export const PORT_INFO: Record<number, PortInfo> = {
  20: { service: "FTP-data", descKey: "portinfo.20" },
  21: { service: "FTP", descKey: "portinfo.21" },
  22: { service: "SSH", descKey: "portinfo.22" },
  23: { service: "Telnet", descKey: "portinfo.23" },
  25: { service: "SMTP", descKey: "portinfo.25" },
  53: { service: "DNS", descKey: "portinfo.53" },
  67: { service: "DHCP", descKey: "portinfo.67" },
  69: { service: "TFTP", descKey: "portinfo.69" },
  80: { service: "HTTP", descKey: "portinfo.80" },
  110: { service: "POP3", descKey: "portinfo.110" },
  123: { service: "NTP", descKey: "portinfo.123" },
  135: { service: "MSRPC", descKey: "portinfo.135" },
  139: { service: "NetBIOS", descKey: "portinfo.139" },
  143: { service: "IMAP", descKey: "portinfo.143" },
  161: { service: "SNMP", descKey: "portinfo.161" },
  389: { service: "LDAP", descKey: "portinfo.389" },
  443: { service: "HTTPS", descKey: "portinfo.443" },
  445: { service: "SMB", descKey: "portinfo.445" },
  465: { service: "SMTPS", descKey: "portinfo.465" },
  514: { service: "Syslog", descKey: "portinfo.514" },
  587: { service: "SMTP submission", descKey: "portinfo.587" },
  636: { service: "LDAPS", descKey: "portinfo.636" },
  993: { service: "IMAPS", descKey: "portinfo.993" },
  995: { service: "POP3S", descKey: "portinfo.995" },
  1433: { service: "MSSQL", descKey: "portinfo.1433" },
  1521: { service: "Oracle", descKey: "portinfo.1521" },
  2049: { service: "NFS", descKey: "portinfo.2049" },
  2375: { service: "Docker", descKey: "portinfo.2375" },
  3306: { service: "MySQL", descKey: "portinfo.3306" },
  3389: { service: "RDP", descKey: "portinfo.3389" },
  5432: { service: "PostgreSQL", descKey: "portinfo.5432" },
  5900: { service: "VNC", descKey: "portinfo.5900" },
  6379: { service: "Redis", descKey: "portinfo.6379" },
  8080: { service: "HTTP-alt", descKey: "portinfo.8080" },
  8443: { service: "HTTPS-alt", descKey: "portinfo.8443" },
  9200: { service: "Elasticsearch", descKey: "portinfo.9200" },
  11211: { service: "Memcached", descKey: "portinfo.11211" },
  27017: { service: "MongoDB", descKey: "portinfo.27017" },
};

export function portInfo(port: number): PortInfo | undefined {
  return PORT_INFO[port];
}
