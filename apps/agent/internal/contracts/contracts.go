// Package contracts defines the JSON shapes exchanged with the control plane.
// They mirror packages/contracts/*.schema.json.
package contracts

// ScanJob is a scan order received from the control plane.
type ScanJob struct {
	Version          int      `json:"version"`
	JobID            string   `json:"job_id"`
	ScanRunID        string   `json:"scan_run_id"`
	ScanProfileID    string   `json:"scan_profile_id,omitempty"`
	Targets          []string `json:"targets"`
	Ports            string   `json:"ports"`
	ScanType         string   `json:"scan_type"`
	ServiceDetection bool     `json:"service_detection"`
	RateLimitPPS     int      `json:"rate_limit_pps"`
	TimeoutSeconds   int      `json:"timeout_seconds,omitempty"`
	ScanSource       string   `json:"scan_source,omitempty"`
}

// Port is a single observed port on a host.
type Port struct {
	Port                  int      `json:"port"`
	Protocol              string   `json:"protocol"`
	State                 string   `json:"state"`
	Service               *string  `json:"service,omitempty"`
	Version               *string  `json:"version,omitempty"`
	Product               *string  `json:"product,omitempty"`
	Banner                *string  `json:"banner,omitempty"`
	BannerSHA256          *string  `json:"banner_sha256,omitempty"`
	FingerprintConfidence *float64 `json:"fingerprint_confidence,omitempty"`
}

// Host is a responding host with its open ports.
type Host struct {
	IP       string  `json:"ip"`
	Hostname *string `json:"hostname,omitempty"`
	Ports    []Port  `json:"ports"`
}

// ScanResult is POSTed back to the control plane after a scan.
type ScanResult struct {
	Version    int     `json:"version"`
	JobID      string  `json:"job_id"`
	ScanRunID  string  `json:"scan_run_id"`
	AgentID    string  `json:"agent_id"`
	StartedAt  string  `json:"started_at"`
	FinishedAt string  `json:"finished_at"`
	Status     string  `json:"status"`
	Error      *string `json:"error,omitempty"`
	Hosts      []Host  `json:"hosts"`
}
