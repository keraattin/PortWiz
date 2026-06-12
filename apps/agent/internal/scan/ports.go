package scan

import (
	"fmt"
	"net"
	"sort"
	"strconv"
	"strings"
)

// maxHosts caps CIDR expansion to avoid accidentally enumerating huge ranges.
const maxHosts = 65536

// ParsePorts turns a port spec into a sorted list of ports.
//
// Supported forms: "22,80,443", "1-1000", and "top-N" (treated as ports 1..N
// in the MVP; a curated top-ports list can replace this later).
func ParsePorts(spec string) ([]int, error) {
	spec = strings.TrimSpace(spec)
	if spec == "" {
		return nil, fmt.Errorf("empty port spec")
	}

	if strings.HasPrefix(spec, "top-") {
		n, err := strconv.Atoi(strings.TrimPrefix(spec, "top-"))
		if err != nil || n < 1 || n > 65535 {
			return nil, fmt.Errorf("invalid top-N spec %q", spec)
		}
		ports := make([]int, 0, n)
		for p := 1; p <= n; p++ {
			ports = append(ports, p)
		}
		return ports, nil
	}

	set := make(map[int]struct{})
	for _, part := range strings.Split(spec, ",") {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		if strings.Contains(part, "-") {
			bounds := strings.SplitN(part, "-", 2)
			lo, err1 := strconv.Atoi(strings.TrimSpace(bounds[0]))
			hi, err2 := strconv.Atoi(strings.TrimSpace(bounds[1]))
			if err1 != nil || err2 != nil || lo < 1 || hi > 65535 || lo > hi {
				return nil, fmt.Errorf("invalid port range %q", part)
			}
			for p := lo; p <= hi; p++ {
				set[p] = struct{}{}
			}
			continue
		}
		p, err := strconv.Atoi(part)
		if err != nil || p < 1 || p > 65535 {
			return nil, fmt.Errorf("invalid port %q", part)
		}
		set[p] = struct{}{}
	}
	if len(set) == 0 {
		return nil, fmt.Errorf("no ports in spec %q", spec)
	}

	ports := make([]int, 0, len(set))
	for p := range set {
		ports = append(ports, p)
	}
	sort.Ints(ports)
	return ports, nil
}

// ExpandTargets turns a list of IPs and CIDRs into a de-duplicated, ordered
// list of host IP strings.
func ExpandTargets(targets []string) ([]string, error) {
	seen := make(map[string]struct{})
	ordered := make([]string, 0)
	add := func(ip string) {
		if _, ok := seen[ip]; !ok {
			seen[ip] = struct{}{}
			ordered = append(ordered, ip)
		}
	}

	for _, raw := range targets {
		t := strings.TrimSpace(raw)
		if t == "" {
			continue
		}
		if ip := net.ParseIP(t); ip != nil {
			add(ip.String())
			continue
		}
		if _, ipnet, err := net.ParseCIDR(t); err == nil {
			ip := make(net.IP, len(ipnet.IP))
			copy(ip, ipnet.IP.Mask(ipnet.Mask))
			for ipnet.Contains(ip) {
				add(ip.String())
				if len(ordered) > maxHosts {
					return nil, fmt.Errorf("target expansion exceeds %d hosts", maxHosts)
				}
				incIP(ip)
			}
			continue
		}
		return nil, fmt.Errorf("invalid target %q (expected IP or CIDR)", t)
	}
	return ordered, nil
}

func incIP(ip net.IP) {
	for j := len(ip) - 1; j >= 0; j-- {
		ip[j]++
		if ip[j] > 0 {
			break
		}
	}
}
