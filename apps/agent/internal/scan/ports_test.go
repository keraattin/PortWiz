package scan

import (
	"reflect"
	"testing"
)

func TestParsePorts(t *testing.T) {
	t.Parallel()
	cases := []struct {
		spec string
		want []int
	}{
		{"22,80,443", []int{22, 80, 443}},
		{"1-3", []int{1, 2, 3}},
		// top-N draws from the curated prevalence-ordered commonPorts list, so
		// top-5 is the five most common ports (sorted), not ports 1..5.
		{"top-5", []int{21, 22, 23, 80, 443}},
		{"80, 79 ,80", []int{79, 80}}, // dedup + sort + whitespace
		{"443,1-2", []int{1, 2, 443}},
	}
	for _, c := range cases {
		got, err := ParsePorts(c.spec)
		if err != nil {
			t.Fatalf("ParsePorts(%q) unexpected error: %v", c.spec, err)
		}
		if !reflect.DeepEqual(got, c.want) {
			t.Errorf("ParsePorts(%q) = %v, want %v", c.spec, got, c.want)
		}
	}
}

func TestParsePortsInvalid(t *testing.T) {
	t.Parallel()
	for _, spec := range []string{"", "0", "70000", "5-3", "abc", "top-0", "top-x"} {
		if _, err := ParsePorts(spec); err == nil {
			t.Errorf("ParsePorts(%q) expected error, got nil", spec)
		}
	}
}

// TestParsePortsTopCoverage guards the fix for top-N: it must cover the common
// high-numbered service ports (which a naive 1..N range silently missed) and
// return exactly N sorted, unique ports.
func TestParsePortsTopCoverage(t *testing.T) {
	t.Parallel()
	got, err := ParsePorts("top-1000")
	if err != nil {
		t.Fatalf("ParsePorts(top-1000) unexpected error: %v", err)
	}
	if len(got) != 1000 {
		t.Fatalf("top-1000 returned %d ports, want 1000", len(got))
	}
	set := make(map[int]struct{}, len(got))
	for i, p := range got {
		if _, dup := set[p]; dup {
			t.Errorf("top-1000 has duplicate port %d", p)
		}
		set[p] = struct{}{}
		if i > 0 && got[i-1] >= p {
			t.Errorf("top-1000 not strictly ascending at index %d: %d >= %d", i, got[i-1], p)
		}
	}
	// These are all above 1000, so the old 1..N logic missed every one of them.
	for _, want := range []int{3306, 3389, 5432, 6379, 8080, 8443, 27017, 9200} {
		if _, ok := set[want]; !ok {
			t.Errorf("top-1000 missing common service port %d", want)
		}
	}
	// A small top-N stays curated: top-100 still includes the busiest DB port.
	top100, err := ParsePorts("top-100")
	if err != nil {
		t.Fatalf("ParsePorts(top-100) unexpected error: %v", err)
	}
	if len(top100) != 100 {
		t.Fatalf("top-100 returned %d ports, want 100", len(top100))
	}
	found := false
	for _, p := range top100 {
		if p == 3306 {
			found = true
			break
		}
	}
	if !found {
		t.Error("top-100 missing MySQL port 3306")
	}
}

func TestExpandTargets(t *testing.T) {
	t.Parallel()
	got, err := ExpandTargets([]string{"10.0.0.0/30", "10.0.0.1", "192.168.1.5"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []string{"10.0.0.0", "10.0.0.1", "10.0.0.2", "10.0.0.3", "192.168.1.5"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("ExpandTargets = %v, want %v", got, want)
	}
}

func TestExpandTargetsInvalid(t *testing.T) {
	t.Parallel()
	if _, err := ExpandTargets([]string{"not-an-ip"}); err == nil {
		t.Error("expected error for invalid target")
	}
}
