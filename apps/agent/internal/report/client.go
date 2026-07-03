// Package report is the agent's client for the control plane.
package report

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"runtime"
	"strings"
	"time"

	"github.com/portwiz/portwiz/agent/internal/contracts"
)

// Version is the agent build version reported to the control plane. Override at
// build time with: -ldflags "-X github.com/portwiz/portwiz/agent/internal/report.Version=x.y.z".
var Version = "dev"

// Client talks to the control plane using the agent bearer token.
type Client struct {
	BaseURL  string
	Token    string
	AgentID  string
	Version  string
	Platform string
	HTTP     *http.Client
}

// New builds a client for the given control plane base URL.
func New(baseURL, token, agentID string) *Client {
	return &Client{
		BaseURL:  strings.TrimRight(baseURL, "/"),
		Token:    token,
		AgentID:  agentID,
		Version:  Version,
		Platform: runtime.GOOS + "/" + runtime.GOARCH,
		HTTP:     &http.Client{Timeout: 30 * time.Second},
	}
}

func (c *Client) do(ctx context.Context, method, path string, body any) (*http.Response, error) {
	var reader io.Reader
	if body != nil {
		encoded, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		reader = bytes.NewReader(encoded)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.BaseURL+path, reader)
	if err != nil {
		return nil, err
	}
	if c.Token != "" {
		req.Header.Set("Authorization", "Bearer "+c.Token)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	return c.HTTP.Do(req)
}

// Heartbeat tells the control plane the agent is alive and reports its build
// version and platform so the server can surface fleet metadata.
func (c *Client) Heartbeat(ctx context.Context) error {
	body := map[string]string{"version": c.Version, "platform": c.Platform}
	resp, err := c.do(ctx, http.MethodPost, "/api/v1/agents/heartbeat", body)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("heartbeat: unexpected status %d", resp.StatusCode)
	}
	return nil
}

// Config is the agent's effective operational config from the control plane.
type Config struct {
	PollSeconds int `json:"poll_seconds"`
}

// FetchConfig retrieves this agent's effective config (poll cadence, etc.) so it
// can self-tune without a redeploy. Callers fall back to their env defaults on error.
func (c *Client) FetchConfig(ctx context.Context) (*Config, error) {
	resp, err := c.do(ctx, http.MethodGet, "/api/v1/agents/me/config", nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("config: unexpected status %d", resp.StatusCode)
	}
	var cfg Config
	if err := json.NewDecoder(resp.Body).Decode(&cfg); err != nil {
		return nil, err
	}
	return &cfg, nil
}

// PollJob asks for the next assigned job. ok is false when there is none.
func (c *Client) PollJob(ctx context.Context) (job *contracts.ScanJob, ok bool, err error) {
	resp, err := c.do(ctx, http.MethodGet, "/api/v1/agents/jobs", nil)
	if err != nil {
		return nil, false, err
	}
	defer resp.Body.Close()
	switch resp.StatusCode {
	case http.StatusNoContent:
		return nil, false, nil
	case http.StatusOK:
		var decoded contracts.ScanJob
		if err := json.NewDecoder(resp.Body).Decode(&decoded); err != nil {
			return nil, false, err
		}
		return &decoded, true, nil
	default:
		b, _ := io.ReadAll(resp.Body)
		return nil, false, fmt.Errorf("poll: status %d: %s", resp.StatusCode, strings.TrimSpace(string(b)))
	}
}

// PostResult uploads a completed scan result to the ingest endpoint.
func (c *Client) PostResult(ctx context.Context, result contracts.ScanResult) error {
	resp, err := c.do(ctx, http.MethodPost, "/api/v1/ingest/scan-results", result)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusAccepted {
		b, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("ingest: status %d: %s", resp.StatusCode, strings.TrimSpace(string(b)))
	}
	return nil
}
