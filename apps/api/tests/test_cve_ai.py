"""AI CVE summarization: real-data-only prompt and hallucination scrubbing.

The AI never invents CVE data. These tests pin the two guarantees: the prompt
carries only the given findings, and any CVE id the model emits that was not in
the input is scrubbed before it reaches the caller.
"""

from __future__ import annotations

from dataclasses import dataclass

from portwiz_api.core.cve_ai import (
    build_cve_summary_prompt,
    scrub_unlisted_cves,
    summarize_cves,
)


@dataclass
class _F:
    cve_id: str
    cvss: float | None
    severity: str
    service: str | None
    version: str | None
    summary: str


def _finding(cid: str, cvss: float | None = 7.5, sev: str = "high") -> _F:
    return _F(cid, cvss, sev, "nginx", "1.24.0", f"A flaw in {cid}")


def test_prompt_lists_only_given_cves() -> None:
    prompt = build_cve_summary_prompt([_finding("CVE-2024-0001"), _finding("CVE-2024-0002")])
    assert "CVE-2024-0001" in prompt
    assert "CVE-2024-0002" in prompt
    # Grounding: the CVE block is clearly marked as the only referenceable data.
    assert "authoritative data" in prompt


def test_prompt_handles_empty() -> None:
    assert "(no CVEs)" in build_cve_summary_prompt([])


def test_scrub_removes_unlisted_cve() -> None:
    text = "Patch CVE-2024-0001 now. Ignore the made-up CVE-9999-9999."
    out = scrub_unlisted_cves(text, {"CVE-2024-0001"})
    assert "CVE-2024-0001" in out
    assert "CVE-9999-9999" not in out
    assert "[unverified CVE removed]" in out


def test_scrub_is_case_insensitive() -> None:
    out = scrub_unlisted_cves("see cve-2024-0001 details", {"CVE-2024-0001"})
    assert "cve-2024-0001" in out  # matched case-insensitively, kept as-is


class _FakeProvider:
    name = "fake"

    async def complete(self, system: str, user: str) -> str:
        return "Top priority: CVE-2024-0001. Bonus invented CVE-1234-5678 to ignore."


async def test_summarize_scrubs_hallucinated_ids() -> None:
    out = await summarize_cves(_FakeProvider(), [_finding("CVE-2024-0001")])
    assert "CVE-2024-0001" in out
    assert "CVE-1234-5678" not in out
