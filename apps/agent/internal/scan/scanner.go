// Package scan implements port discovery and service detection.
//
// The default Scanner is a dependency-free TCP connect scanner. The Scanner
// interface is deliberately small so a naabu-based implementation (SYN scans,
// higher throughput) can be swapped in behind it later.
package scan

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"net"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/portwiz/portwiz/agent/internal/contracts"
)

// Scanner discovers open ports (and optionally services) for a scan job.
type Scanner interface {
	Scan(ctx context.Context, job contracts.ScanJob) ([]contracts.Host, error)
}

// ConnectScanner performs unprivileged TCP connect scanning.
type ConnectScanner struct {
	DialTimeout   time.Duration
	BannerTimeout time.Duration
	Concurrency   int
}

// NewConnectScanner returns a scanner with sensible defaults.
func NewConnectScanner() *ConnectScanner {
	return &ConnectScanner{
		DialTimeout:   2 * time.Second,
		BannerTimeout: 1 * time.Second,
		Concurrency:   256,
	}
}

// Scan connects to every (host, port) and returns the responding hosts with
// their open ports (and any banner grabbed on connect).
func (s *ConnectScanner) Scan(ctx context.Context, job contracts.ScanJob) ([]contracts.Host, error) {
	ips, err := ExpandTargets(job.Targets)
	if err != nil {
		return nil, err
	}
	ports, err := ParsePorts(job.Ports)
	if err != nil {
		return nil, err
	}

	concurrency := s.Concurrency
	if concurrency < 1 {
		concurrency = 1
	}
	sem := make(chan struct{}, concurrency)
	var wg sync.WaitGroup
	var mu sync.Mutex
	openByIP := make(map[string][]contracts.Port)

	for _, ip := range ips {
		for _, port := range ports {
			select {
			case <-ctx.Done():
				wg.Wait()
				return nil, ctx.Err()
			default:
			}
			wg.Add(1)
			sem <- struct{}{}
			go func(ip string, port int) {
				defer wg.Done()
				defer func() { <-sem }()
				if p, ok := s.probe(ctx, ip, port); ok {
					mu.Lock()
					openByIP[ip] = append(openByIP[ip], p)
					mu.Unlock()
				}
			}(ip, port)
		}
	}
	wg.Wait()

	hosts := make([]contracts.Host, 0, len(openByIP))
	for _, ip := range ips {
		ps, ok := openByIP[ip]
		if !ok || len(ps) == 0 {
			continue
		}
		sort.Slice(ps, func(i, j int) bool { return ps[i].Port < ps[j].Port })
		hosts = append(hosts, contracts.Host{IP: ip, Ports: ps})
	}
	return hosts, nil
}

func (s *ConnectScanner) probe(ctx context.Context, ip string, port int) (contracts.Port, bool) {
	addr := net.JoinHostPort(ip, strconv.Itoa(port))
	dialer := net.Dialer{Timeout: s.DialTimeout}
	conn, err := dialer.DialContext(ctx, "tcp", addr)
	if err != nil {
		return contracts.Port{}, false
	}
	defer conn.Close()

	p := contracts.Port{Port: port, Protocol: "tcp", State: "open"}

	// Best-effort banner grab: many services (e.g. SSH, SMTP, FTP) speak first.
	_ = conn.SetReadDeadline(time.Now().Add(s.BannerTimeout))
	buf := make([]byte, 512)
	if n, _ := conn.Read(buf); n > 0 {
		banner := strings.TrimSpace(string(buf[:n]))
		if banner != "" {
			sum := sha256.Sum256([]byte(banner))
			hash := hex.EncodeToString(sum[:])
			p.Banner = &banner
			p.BannerSHA256 = &hash
		}
	}
	return p, true
}
