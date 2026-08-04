package scan

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strconv"
	"testing"

	"github.com/portwiz/portwiz/agent/internal/contracts"
)

func TestLikelyTLS(t *testing.T) {
	t.Parallel()
	if !likelyTLS(&contracts.Port{Port: 443}) {
		t.Error("443 should be treated as TLS by port")
	}
	if likelyTLS(&contracts.Port{Port: 80}) {
		t.Error("80 should not be treated as TLS by port")
	}
	https := "ssl/http"
	if !likelyTLS(&contracts.Port{Port: 9999, Service: &https}) {
		t.Error("a TLS-announcing service should trigger on a non-standard port")
	}
	plain := "http"
	if likelyTLS(&contracts.Port{Port: 9999, Service: &plain}) {
		t.Error("a plain service should not trigger a handshake")
	}
}

func TestGrabCertAndEnrich(t *testing.T) {
	t.Parallel()
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {}))
	defer srv.Close()

	u, err := url.Parse(srv.URL)
	if err != nil {
		t.Fatalf("parse server url: %v", err)
	}
	host := u.Hostname()
	port, err := strconv.Atoi(u.Port())
	if err != nil {
		t.Fatalf("parse server port: %v", err)
	}

	// grabCert reads the presented leaf certificate regardless of trust.
	info := grabCert(context.Background(), host, port)
	if info == nil {
		t.Fatal("grabCert returned nil for a live TLS server")
	}
	if info.NotBefore == "" || info.NotAfter == "" {
		t.Errorf("validity window not captured: %+v", info)
	}
	if info.SigAlg == "" {
		t.Error("signature algorithm not captured")
	}

	// A plain port with no TLS is skipped (no handshake completes).
	if got := grabCert(context.Background(), host, 1); got != nil {
		t.Errorf("expected nil cert for a closed/plain port, got %+v", got)
	}

	// EnrichWithTLS wires the summary onto the port when the service hints TLS,
	// even though the test server listens on a random non-standard port.
	svc := "ssl/http"
	hosts := []contracts.Host{{
		IP:    host,
		Ports: []contracts.Port{{Port: port, Protocol: "tcp", State: "open", Service: &svc}},
	}}
	EnrichWithTLS(context.Background(), hosts)
	if hosts[0].Ports[0].TLS == nil {
		t.Fatal("EnrichWithTLS did not attach a certificate summary")
	}
	if hosts[0].Ports[0].TLS.NotAfter == "" {
		t.Error("attached certificate summary is missing notAfter")
	}
}
