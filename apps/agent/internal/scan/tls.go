package scan

import (
	"context"
	"crypto/tls"
	"crypto/x509/pkix"
	"net"
	"strconv"
	"strings"
	"time"

	"github.com/portwiz/portwiz/agent/internal/contracts"
)

// tlsHandshakeTimeout bounds a single certificate probe so a slow or silent
// port can't stall the enrichment pass.
const tlsHandshakeTimeout = 5 * time.Second

// implicitTLSPorts speak TLS immediately on connect (no STARTTLS negotiation),
// so a plain handshake yields the certificate. STARTTLS ports (25, 143, 110,
// 21, ...) are intentionally excluded: they need a protocol-specific upgrade
// the connect scanner does not perform, so a bare handshake there just fails.
var implicitTLSPorts = map[int]bool{
	443:   true, // https
	8443:  true, // https-alt
	9443:  true,
	4443:  true,
	993:   true, // imaps
	995:   true, // pop3s
	465:   true, // smtps
	636:   true, // ldaps
	990:   true, // ftps
	989:   true, // ftps-data
	563:   true, // nntps
	5061:  true, // sip-tls
	6443:  true, // kubernetes-api
	8883:  true, // mqtt-tls
	2376:  true, // docker-tls
	5986:  true, // winrm-https
	10250: true, // kubelet
}

// EnrichWithTLS attempts a TLS handshake on each open port that likely speaks
// implicit TLS and records the leaf certificate summary. Trust is deliberately
// NOT verified (InsecureSkipVerify): expired, self-signed, or otherwise
// untrusted certificates must still be captured, since surfacing those is the
// whole point of certificate monitoring.
func EnrichWithTLS(ctx context.Context, hosts []contracts.Host) {
	for hi := range hosts {
		host := &hosts[hi]
		for pi := range host.Ports {
			p := &host.Ports[pi]
			if p.Protocol != "tcp" || p.State != "open" || !likelyTLS(p) {
				continue
			}
			if info := grabCert(ctx, host.IP, p.Port); info != nil {
				p.TLS = info
			}
		}
	}
}

// likelyTLS decides whether a port is worth a TLS handshake: a known
// implicit-TLS port, or one whose detected service name announces TLS (so a
// certificate on a non-standard port is still found).
func likelyTLS(p *contracts.Port) bool {
	if implicitTLSPorts[p.Port] {
		return true
	}
	if p.Service != nil {
		s := strings.ToLower(*p.Service)
		if strings.Contains(s, "https") || strings.Contains(s, "ssl") || strings.Contains(s, "tls") {
			return true
		}
	}
	return false
}

// grabCert performs a TLS handshake and summarizes the leaf certificate, or
// returns nil if the port does not complete a TLS handshake.
func grabCert(ctx context.Context, ip string, port int) *contracts.TLSCertInfo {
	addr := net.JoinHostPort(ip, strconv.Itoa(port))
	dialer := &tls.Dialer{
		NetDialer: &net.Dialer{Timeout: tlsHandshakeTimeout},
		// Connecting by IP with no ServerName; accept any certificate so an
		// untrusted or expired one can still be read. Allow old TLS versions so
		// outdated services are captured rather than skipped.
		Config: &tls.Config{InsecureSkipVerify: true, MinVersion: tls.VersionTLS10},
	}
	hctx, cancel := context.WithTimeout(ctx, tlsHandshakeTimeout)
	defer cancel()
	conn, err := dialer.DialContext(hctx, "tcp", addr)
	if err != nil {
		return nil
	}
	defer conn.Close()
	tconn, ok := conn.(*tls.Conn)
	if !ok {
		return nil
	}
	state := tconn.ConnectionState()
	if len(state.PeerCertificates) == 0 {
		return nil
	}
	leaf := state.PeerCertificates[0]
	info := &contracts.TLSCertInfo{
		SubjectCN:  leaf.Subject.CommonName,
		Issuer:     issuerName(leaf.Issuer),
		NotBefore:  leaf.NotBefore.UTC().Format(time.RFC3339),
		NotAfter:   leaf.NotAfter.UTC().Format(time.RFC3339),
		SelfSigned: leaf.Subject.String() == leaf.Issuer.String(),
		SigAlg:     leaf.SignatureAlgorithm.String(),
	}
	if leaf.SerialNumber != nil {
		info.Serial = leaf.SerialNumber.Text(16)
	}
	sans := make([]string, 0, len(leaf.DNSNames)+len(leaf.IPAddresses))
	sans = append(sans, leaf.DNSNames...)
	for _, a := range leaf.IPAddresses {
		sans = append(sans, a.String())
	}
	if len(sans) > 0 {
		info.SANs = sans
	}
	return info
}

// issuerName prefers the issuer CN, falling back to the organization or the
// full RDN string so the field is never empty for a real certificate.
func issuerName(n pkix.Name) string {
	if n.CommonName != "" {
		return n.CommonName
	}
	if len(n.Organization) > 0 {
		return n.Organization[0]
	}
	return n.String()
}
