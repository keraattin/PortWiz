// Command agent is the PortWiz distributed scan agent.
//
// One agent is deployed per VLAN/segment. It pulls ScanJob orders from the
// control plane, runs port discovery (and optional nmap service detection)
// locally, and POSTs a ScanResult back.
//
// Modes:
//
//	portwiz-agent run                    # poll-and-scan loop (default)
//	portwiz-agent scan --run-id <id> \   # one-shot scan, reports to a run
//	    --targets 10.0.0.0/24 --ports 1-1000
package main

import (
	"context"
	"crypto/rand"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/portwiz/portwiz/agent/internal/contracts"
	"github.com/portwiz/portwiz/agent/internal/report"
	"github.com/portwiz/portwiz/agent/internal/scan"
)

func getenv(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func getenvInt(key string, def int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
		log.Printf("invalid %s=%q, using default %d", key, os.Getenv(key), def)
	}
	return def
}

func main() {
	log.SetFlags(log.LstdFlags | log.LUTC)
	apiURL := getenv("PORTWIZ_API_URL", "http://localhost:8000")
	token := getenv("PORTWIZ_AGENT_TOKEN", "")
	agentID := getenv("PORTWIZ_AGENT_ID", "agent-local")
	pollSeconds := getenvInt("PORTWIZ_POLL_SECONDS", 15)

	mode := "run"
	args := os.Args[1:]
	if len(args) > 0 && !strings.HasPrefix(args[0], "-") {
		mode = args[0]
		args = args[1:]
	}

	switch mode {
	case "run":
		runLoop(apiURL, token, agentID, pollSeconds)
	case "scan":
		runScan(args, apiURL, token, agentID)
	default:
		log.Fatalf("unknown mode %q (use 'run' or 'scan')", mode)
	}
}

func runLoop(apiURL, token, agentID string, pollSeconds int) {
	client := report.New(apiURL, token, agentID)
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	// The control plane's per-agent config wins over the env default when reachable,
	// so an operator can retune cadence centrally; the env value is the fallback.
	if cfg, err := client.FetchConfig(ctx); err != nil {
		log.Printf("config fetch failed, using PORTWIZ_POLL_SECONDS=%d: %v", pollSeconds, err)
	} else if cfg.PollSeconds > 0 {
		pollSeconds = cfg.PollSeconds
	}

	log.Printf(
		"agent starting (id=%s api=%s poll=%ds nmap=%t)",
		agentID, apiURL, pollSeconds, scan.NmapAvailable(),
	)
	ticker := time.NewTicker(time.Duration(pollSeconds) * time.Second)
	defer ticker.Stop()

	for {
		pollOnce(ctx, client, agentID)
		select {
		case <-ctx.Done():
			log.Print("shutting down")
			return
		case <-ticker.C:
		}
	}
}

func pollOnce(ctx context.Context, client *report.Client, agentID string) {
	if err := client.Heartbeat(ctx); err != nil {
		log.Printf("heartbeat failed: %v", err)
	}
	job, ok, err := client.PollJob(ctx)
	if err != nil {
		log.Printf("poll failed: %v", err)
		return
	}
	if !ok {
		return
	}
	log.Printf("received job %s (run %s)", job.JobID, job.ScanRunID)
	result := executeJob(ctx, *job, agentID)
	if err := client.PostResult(ctx, result); err != nil {
		log.Printf("report failed: %v", err)
		return
	}
	log.Printf("reported job %s: %d hosts, %d open ports", job.JobID, len(result.Hosts), countPorts(result.Hosts))
}

func runScan(args []string, apiURL, token, agentID string) {
	fs := flag.NewFlagSet("scan", flag.ExitOnError)
	runID := fs.String("run-id", "", "scan run id to report against (required)")
	jobID := fs.String("job-id", "", "job id (generated when empty)")
	targets := fs.String("targets", "", "comma-separated IPs/CIDRs (required)")
	ports := fs.String("ports", "top-1000", "port spec, e.g. 1-1000 or 22,80,443")
	serviceDetection := fs.Bool("service-detection", true, "run nmap -sV when available")
	api := fs.String("api", apiURL, "control plane base URL")
	tok := fs.String("token", token, "agent token")
	_ = fs.Parse(args)

	if *runID == "" || *targets == "" {
		fs.Usage()
		log.Fatal("--run-id and --targets are required")
	}

	job := contracts.ScanJob{
		Version:          1,
		JobID:            orGenerate(*jobID),
		ScanRunID:        *runID,
		Targets:          splitComma(*targets),
		Ports:            *ports,
		ScanType:         "connect",
		ServiceDetection: *serviceDetection,
		RateLimitPPS:     1000,
	}

	ctx := context.Background()
	result := executeJob(ctx, job, agentID)
	client := report.New(*api, *tok, agentID)
	if err := client.PostResult(ctx, result); err != nil {
		log.Fatalf("report failed: %v", err)
	}
	log.Printf("reported run %s: %d hosts, %d open ports", *runID, len(result.Hosts), countPorts(result.Hosts))
}

func executeJob(ctx context.Context, job contracts.ScanJob, agentID string) contracts.ScanResult {
	started := time.Now().UTC()
	// Bound the scan to the dispatched budget so a large target/port range can't
	// block the poll loop indefinitely (0 = no explicit limit).
	if job.TimeoutSeconds > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, time.Duration(job.TimeoutSeconds)*time.Second)
		defer cancel()
	}
	scanner := scan.NewConnectScanner()
	hosts, err := scanner.Scan(ctx, job)

	status := "completed"
	var errPtr *string
	if err != nil {
		status = "failed"
		msg := err.Error()
		errPtr = &msg
		hosts = nil
	} else if job.ServiceDetection {
		scan.EnrichWithNmap(ctx, hosts)
	}

	return contracts.ScanResult{
		Version:    1,
		JobID:      job.JobID,
		ScanRunID:  job.ScanRunID,
		AgentID:    agentID,
		StartedAt:  started.Format(time.RFC3339),
		FinishedAt: time.Now().UTC().Format(time.RFC3339),
		Status:     status,
		Error:      errPtr,
		Hosts:      hosts,
	}
}

func countPorts(hosts []contracts.Host) int {
	total := 0
	for _, h := range hosts {
		total += len(h.Ports)
	}
	return total
}

func splitComma(s string) []string {
	parts := strings.Split(s, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if p = strings.TrimSpace(p); p != "" {
			out = append(out, p)
		}
	}
	return out
}

func orGenerate(id string) string {
	if id != "" {
		return id
	}
	return genUUIDv4()
}

func genUUIDv4() string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		log.Fatalf("uuid: %v", err)
	}
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}
