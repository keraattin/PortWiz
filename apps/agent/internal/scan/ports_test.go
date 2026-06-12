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
		{"top-5", []int{1, 2, 3, 4, 5}},
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
