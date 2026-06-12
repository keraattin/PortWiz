// Command agent is the PortWiz distributed scan agent.
//
// One agent is deployed per VLAN/segment. It receives ScanJob orders from the
// control plane, runs port discovery and service fingerprinting locally, and
// POSTs ScanResult back over HTTPS.
//
// M0 scaffold: this only heartbeats the control plane to prove connectivity.
// Real scanning (naabu library + nmap-service-probes) is wired in M2.
package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func getenv(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func main() {
	apiURL := getenv("PORTWIZ_API_URL", "http://localhost:8000")
	agentID := getenv("PORTWIZ_AGENT_ID", "agent-local")
	interval := 30 * time.Second

	log.Printf("PortWiz scan agent starting (id=%s, api=%s)", agentID, apiURL)
	log.Print("M0 stub: real scanning (naabu + nmap-service-probes) lands in M2.")

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	client := &http.Client{Timeout: 5 * time.Second}
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	heartbeat(ctx, client, apiURL)
	for {
		select {
		case <-ctx.Done():
			log.Print("shutting down")
			return
		case <-ticker.C:
			heartbeat(ctx, client, apiURL)
		}
	}
}

func heartbeat(ctx context.Context, client *http.Client, apiURL string) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, apiURL+"/health", nil)
	if err != nil {
		log.Printf("heartbeat: build request failed: %v", err)
		return
	}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("heartbeat: control plane unreachable: %v", err)
		return
	}
	defer func() { _ = resp.Body.Close() }()
	log.Printf("heartbeat: control plane responded %d", resp.StatusCode)
}
