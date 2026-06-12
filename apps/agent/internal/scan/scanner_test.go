package scan

import (
	"context"
	"net"
	"testing"
	"time"

	"github.com/portwiz/portwiz/agent/internal/contracts"
)

func TestConnectScannerFindsOpenPort(t *testing.T) {
	t.Parallel()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	defer ln.Close()
	go func() {
		for {
			conn, err := ln.Accept()
			if err != nil {
				return
			}
			conn.Close()
		}
	}()

	_, portStr, _ := net.SplitHostPort(ln.Addr().String())

	scanner := NewConnectScanner()
	scanner.DialTimeout = 500 * time.Millisecond
	scanner.BannerTimeout = 100 * time.Millisecond

	hosts, err := scanner.Scan(context.Background(), contracts.ScanJob{
		Targets: []string{"127.0.0.1"},
		Ports:   portStr,
	})
	if err != nil {
		t.Fatalf("scan: %v", err)
	}
	if len(hosts) != 1 {
		t.Fatalf("want 1 host, got %d", len(hosts))
	}
	if len(hosts[0].Ports) != 1 || hosts[0].Ports[0].State != "open" {
		t.Fatalf("want one open port, got %+v", hosts[0].Ports)
	}
}

func TestConnectScannerSkipsClosedPort(t *testing.T) {
	t.Parallel()
	// Bind then immediately release a port so it is (very likely) closed.
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	_, portStr, _ := net.SplitHostPort(ln.Addr().String())
	ln.Close()

	scanner := NewConnectScanner()
	scanner.DialTimeout = 300 * time.Millisecond

	hosts, err := scanner.Scan(context.Background(), contracts.ScanJob{
		Targets: []string{"127.0.0.1"},
		Ports:   portStr,
	})
	if err != nil {
		t.Fatalf("scan: %v", err)
	}
	if len(hosts) != 0 {
		t.Fatalf("want 0 hosts for a closed port, got %d", len(hosts))
	}
}
