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
// Supported forms: "22,80,443", "1-1000", and "top-N". "top-N" means the N most
// relevant ports: the curated commonPorts list (below), which is ordered by
// real-world prevalence, taken in order and then, once that list is exhausted,
// topped up with the lowest-numbered ports not already included until N ports
// are selected. This guarantees that high-numbered but common service ports
// (3306, 3389, 5432, 6379, 8080, 8443, 27017, ...) are always covered, which a
// naive 1..N range silently misses.
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
		return topPorts(n), nil
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

// commonPorts is a curated list of the ports most worth scanning, ordered
// roughly by real-world prevalence so that a small "top-N" stays meaningful.
// The head mirrors the classic nmap top-ports ranking; the tail adds the
// database, cache, message-queue, and orchestration service ports a modern
// estate exposes. Duplicates are harmless: topPorts de-duplicates as it builds.
var commonPorts = []int{
	// Most prevalent services (nmap top-100 head).
	80, 23, 443, 21, 22, 25, 3389, 110, 445, 139,
	143, 53, 135, 3306, 8080, 1723, 111, 995, 993, 5900,
	1025, 587, 8888, 199, 1720, 465, 548, 113, 81, 6001,
	10000, 514, 5060, 179, 1026, 2000, 8443, 8000, 32768, 554,
	26, 1433, 49152, 2001, 515, 8008, 49154, 1027, 5666, 646,
	5000, 5631, 631, 49153, 8081, 2049, 88, 79, 5800, 106,
	2121, 1110, 49155, 6000, 513, 990, 5357, 427, 49156, 543,
	544, 5101, 144, 7, 389, 8009, 3128, 444, 9999, 5009,
	7070, 5190, 3000, 5432, 1900, 3986, 13, 1029, 9, 5051,
	6646, 49157, 1028, 873, 1755, 2717, 4899, 9100, 119, 37,
	// Database, cache, and datastore service ports.
	6379, 27017, 27018, 9200, 9300, 11211, 5984, 9042, 1521, 1830,
	5433, 3050, 7199, 7000, 7001, 8087, 8091, 8529, 28015, 4200,
	// Message queues, streaming, and orchestration.
	9092, 2181, 2375, 2376, 2379, 2380, 5672, 15672, 61616, 1883,
	8883, 4369, 25672, 6443, 10250, 10255, 8181, 8500, 8300, 8600,
	// Remote access, directory, and management.
	5985, 5986, 636, 464, 3268, 3269, 161, 162, 123, 500,
	4500, 1194, 1812, 1813, 5222, 5269, 5280, 3690, 1080, 9090,
	9091, 8161, 8086, 5601, 3260, 992, 992, 8140, 4848, 7474,
	// Misc common web/app and monitoring ports.
	8010, 8082, 8083, 8085, 8089, 8280, 8880, 9000, 9001, 9200,
	3001, 4000, 4040, 5000, 5555, 6060, 7080, 7443, 9443, 25565,
}

// topPorts returns the n most relevant ports, sorted ascending. It walks
// commonPorts (prevalence order) first, then fills any remainder with the
// lowest-numbered ports not yet chosen, so the common high-numbered service
// ports are always present regardless of n.
func topPorts(n int) []int {
	seen := make(map[int]bool, n)
	result := make([]int, 0, n)
	add := func(p int) {
		if p >= 1 && p <= 65535 && !seen[p] {
			seen[p] = true
			result = append(result, p)
		}
	}
	for _, p := range commonPorts {
		if len(result) >= n {
			break
		}
		add(p)
	}
	for p := 1; p <= 65535 && len(result) < n; p++ {
		add(p)
	}
	sort.Ints(result)
	return result
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
