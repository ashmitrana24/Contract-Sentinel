"""Ingestion pipeline benchmark.

Uploads PDFs concurrently against a running ClauseGuard API stack,
polls each job to completion, and computes:
- Total documents processed
- Wall clock time
- Throughput (docs / min)
- End-to-end latency percentiles (p50, p95, p99)

Exits non-zero if any job fails or times out.
Run with: python -m clauseguard.bench.ingest_bench --pdf-dir ...
"""

from __future__ import annotations

import argparse
import concurrent.futures
import math
import sys
import time
from pathlib import Path

import httpx


def percentile(data: list[float], pct: float) -> float:
    """Calculate the pct-th percentile (0-100) of sorted data."""
    if not data:
        return 0.0
    k = (len(data) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return data[int(k)]
    d0 = data[int(f)] * (c - k)
    d1 = data[int(c)] * (k - f)
    return d0 + d1


def upload_and_wait(
    client: httpx.Client,
    pdf_path: Path,
    base_url: str,
    timeout: float = 120.0,
    poll_interval: float = 0.2,
) -> tuple[bool, float, str]:
    """Upload a single PDF, poll its job, and return (success, duration_seconds, message)."""
    start_time = time.perf_counter()
    url = f"{base_url.rstrip('/')}/v1/documents"

    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        resp = client.post(
            url,
            files={"file": (pdf_path.name, pdf_bytes, "application/pdf")},
            timeout=30.0,
        )
        if resp.status_code not in (200, 202):
            return False, time.perf_counter() - start_time, f"Upload HTTP {resp.status_code}: {resp.text}"

        data = resp.json()
        job_id = data.get("job_id")
        if not job_id:
            return False, time.perf_counter() - start_time, "No job_id returned"

        # Poll job status
        job_url = f"{base_url.rstrip('/')}/v1/jobs/{job_id}"
        deadline = time.perf_counter() + timeout

        while time.perf_counter() < deadline:
            jresp = client.get(job_url, timeout=10.0)
            if jresp.status_code == 200:
                jdata = jresp.json()
                status = jdata.get("status")
                if status == "succeeded":
                    return True, time.perf_counter() - start_time, "succeeded"
                if status == "dead":
                    error = jdata.get("last_error") or "dead"
                    return False, time.perf_counter() - start_time, f"Job dead: {error}"
            time.sleep(poll_interval)

        return False, time.perf_counter() - start_time, f"Timed out after {timeout}s"
    except Exception as exc:
        return False, time.perf_counter() - start_time, f"Exception: {exc}"


def run_bench(
    pdf_dir: Path,
    base_url: str = "http://localhost:8000",
    concurrency: int = 5,
    max_docs: int | None = None,
    timeout: float = 120.0,
) -> int:
    """Run the benchmark and print results."""
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"ERROR: No PDF files found in {pdf_dir}", file=sys.stderr)
        return 1

    if max_docs:
        pdf_files = pdf_files[:max_docs]

    total_docs = len(pdf_files)
    print("=== ClauseGuard Ingestion Benchmark ===")
    print(f"Directory:    {pdf_dir}")
    print(f"Total PDFs:   {total_docs}")
    print(f"Concurrency:  {concurrency}")
    print(f"Target API:   {base_url}")
    print("---------------------------------------")

    latencies: list[float] = []
    failures: list[tuple[str, str]] = []

    wall_start = time.perf_counter()

    with httpx.Client(timeout=60.0) as client:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_file = {
                executor.submit(upload_and_wait, client, p, base_url, timeout): p
                for p in pdf_files
            }

            completed = 0
            for future in concurrent.futures.as_completed(future_to_file):
                p = future_to_file[future]
                completed += 1
                try:
                    success, duration, msg = future.result()
                    if success:
                        latencies.append(duration)
                    else:
                        failures.append((p.name, msg))
                except Exception as exc:
                    failures.append((p.name, str(exc)))

                if completed % 10 == 0 or completed == total_docs:
                    print(f"Progress: {completed}/{total_docs} completed ({len(failures)} failed)")

    wall_time = time.perf_counter() - wall_start
    docs_per_min = (len(latencies) / wall_time) * 60.0 if wall_time > 0 else 0.0

    latencies.sort()
    p50 = percentile(latencies, 50.0)
    p95 = percentile(latencies, 95.0)
    p99 = percentile(latencies, 99.0)

    print("\n================ Results ================")
    print(f"Documents submitted:  {total_docs}")
    print(f"Documents succeeded:  {len(latencies)}")
    print(f"Documents failed:     {len(failures)}")
    print(f"Wall time:            {wall_time:.2f} s")
    print(f"Throughput:           {docs_per_min:.1f} docs/min")
    print(f"Latency p50:          {p50:.3f} s")
    print(f"Latency p95:          {p95:.3f} s")
    print(f"Latency p99:          {p99:.3f} s")
    print("=========================================")

    if failures:
        print("\nFailures:")
        for name, reason in failures[:10]:
            print(f"  - {name}: {reason}")
        if len(failures) > 10:
            print(f"  ... and {len(failures) - 10} more")
        return 1

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="ClauseGuard Ingestion Benchmark")
    parser.add_argument("--pdf-dir", type=Path, required=True, help="Directory containing PDF files")
    parser.add_argument("--api-url", type=str, default="http://localhost:8000", help="API base URL")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent client upload workers")
    parser.add_argument("--max-docs", type=int, default=None, help="Maximum number of PDFs to process")
    parser.add_argument("--timeout", type=float, default=120.0, help="Per-document timeout in seconds")

    args = parser.parse_args()
    exit_code = run_bench(
        pdf_dir=args.pdf_dir,
        base_url=args.api_url,
        concurrency=args.concurrency,
        max_docs=args.max_docs,
        timeout=args.timeout,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
