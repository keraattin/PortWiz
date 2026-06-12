package scan

import (
	"context"
	"encoding/xml"
	"os/exec"
	"strconv"
	"strings"

	"github.com/portwiz/portwiz/agent/internal/contracts"
)

// NmapAvailable reports whether the nmap binary is on PATH.
func NmapAvailable() bool {
	_, err := exec.LookPath("nmap")
	return err == nil
}

type nmapRun struct {
	Hosts []struct {
		Ports struct {
			Port []struct {
				PortID  int `xml:"portid,attr"`
				Service struct {
					Name    string `xml:"name,attr"`
					Product string `xml:"product,attr"`
					Version string `xml:"version,attr"`
				} `xml:"service"`
			} `xml:"port"`
		} `xml:"ports"`
	} `xml:"host"`
}

type serviceInfo struct {
	name    string
	product string
	version string
}

// EnrichWithNmap runs `nmap -sV` per host and fills service/product/version on
// matching ports. It is a no-op when nmap is not installed (the connect
// scanner's results are still returned).
func EnrichWithNmap(ctx context.Context, hosts []contracts.Host) {
	if !NmapAvailable() {
		return
	}
	for hi := range hosts {
		host := &hosts[hi]
		if len(host.Ports) == 0 {
			continue
		}
		portArgs := make([]string, 0, len(host.Ports))
		for _, p := range host.Ports {
			portArgs = append(portArgs, strconv.Itoa(p.Port))
		}
		out, err := exec.CommandContext(
			ctx, "nmap", "-sV", "-Pn", "-T4",
			"-p", strings.Join(portArgs, ","), "-oX", "-", host.IP,
		).Output()
		if err != nil {
			continue
		}
		var run nmapRun
		if err := xml.Unmarshal(out, &run); err != nil {
			continue
		}
		info := make(map[int]serviceInfo)
		for _, h := range run.Hosts {
			for _, p := range h.Ports.Port {
				info[p.PortID] = serviceInfo{p.Service.Name, p.Service.Product, p.Service.Version}
			}
		}
		for pi := range host.Ports {
			si, ok := info[host.Ports[pi].Port]
			if !ok {
				continue
			}
			if si.name != "" {
				name := si.name
				host.Ports[pi].Service = &name
			}
			if si.product != "" {
				product := si.product
				host.Ports[pi].Product = &product
			}
			if si.version != "" {
				version := si.version
				host.Ports[pi].Version = &version
			}
		}
	}
}
