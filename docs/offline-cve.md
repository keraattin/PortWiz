# Offline CVE enrichment (air-gapped installs)

PortWiz can match a discovered service and version against known CVEs. By default
it queries the online [NVD](https://nvd.nist.gov/) API, which needs outbound
internet access. Compliance and air-gapped networks often have none, so PortWiz
also ships an **offline** source: you import an NVD data feed once, and all
lookups then run against that local copy with no outbound access.

Both sources sit behind the same interface, so the rest of PortWiz (the CVE
findings table, the scheduled re-check, the AI brief) works identically either
way. CVE data is always authoritative from NVD; nothing is invented.

## When to use it

- Your PortWiz host cannot reach `services.nvd.nist.gov`.
- Your security policy forbids the control plane making outbound calls.
- You want reproducible lookups against a fixed, reviewed CVE dataset.

If your host has internet access, the online **NVD** source is simpler (nothing
to import) and stays current automatically.

## 1. Get an NVD feed (on a connected machine)

The offline store expects **NVD API 2.0 JSON** (the same shape the online source
reads). The legacy 1.1 data feeds are retired, so use 2.0-format JSON. Plain
`.json` and gzipped `.json.gz` are both accepted, up to 100 MB per file.

The simplest way to produce feed files is to page through the NVD 2.0 API on an
internet-connected machine and save each response. Each response is already a
valid feed file (it contains a `vulnerabilities` array):

```bash
# Save NVD in 2000-CVE pages. An NVD API key raises the rate limit; without one,
# stay well under 5 requests / 30s. Adjust the loop bound to totalResults.
base="https://services.nvd.nist.gov/rest/json/cves/2.0"
for start in $(seq 0 2000 20000); do
  curl -s "$base?resultsPerPage=2000&startIndex=$start" \
    -o "nvd-$start.json"
  sleep 6
done
```

You can also narrow the download to what you actually run (smaller, faster to
refresh), for example by keyword or by a published-date window:

```bash
curl -s "$base?keywordSearch=openssh&resultsPerPage=2000" -o nvd-openssh.json
```

Transfer the resulting `.json` (or `.json.gz`) files to the air-gapped host by
whatever process your policy allows (removable media, one-way transfer, etc.).

## 2. Import the feed into PortWiz

1. Open **Settings → CVE**.
2. Turn **CVE enrichment** on.
3. Set **Source** to **Offline (uploaded NVD feed)**.
4. Choose a feed file and click **Import feed**. The result line shows how many
   entries were imported and the total now available offline.
5. Repeat for each file. Importing upserts by CVE id, so re-importing a newer
   file updates existing entries and never duplicates.
6. Click **Save** so the offline source stays selected.

The import is admin-only and recorded in the immutable audit log
(`cve.feed_imported`, with the file name and counts).

> API equivalent: `POST /api/v1/cve/import` with a multipart `file` field.

## 3. Run a check

- On the **CVE** page, click **Recheck** to look up the current open ports that
  carry a version, or set **Re-check every N hours** in Settings for an automatic
  cadence.
- Findings are stored per asset and port and listed newest and highest-severity
  first. An optional AI brief summarizes them in plain language (it only ever
  summarizes the real stored findings).

## How matching works

For each discovered service, the offline source keyword-matches the **product
name** against each CVE's stored text (its description plus the vendor and product
names from the CVE's CPE entries), returns the highest-CVSS matches (bounded), and
applies your **minimum CVSS** filter. This mirrors the online NVD keyword search.

**Version is not used to filter.** NVD records which versions are affected in
structured CPE ranges (`versionStartIncluding` / `versionEndExcluding`), not in
free text, so a naive substring match on the version would wrongly discard most
range-based CVEs. PortWiz therefore surfaces the product's known CVEs ranked by
severity and leaves version applicability for an analyst to confirm, exactly as
the online keyword search does.

Practical implications:

- Matching is by **product name**, so a discovered product whose name differs
  from NVD's CPE naming (for example an nmap banner label vs. the CPE product id)
  may match loosely or not at all. Treat results as a prioritized starting point.
- Coverage is only as fresh as your **last import**. Refresh periodically by
  downloading recent NVD data and re-importing.

## Keeping it current

Re-run step 1 on a schedule that fits your risk posture (for example monthly, or
after a major disclosure), transfer the new files, and re-import them. Because the
import upserts, you can import just the recent/modified window rather than the
full dataset each time.
