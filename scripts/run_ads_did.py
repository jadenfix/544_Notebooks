#!/usr/bin/env python3
"""Run the provider-free paid-search notebook workflow from any directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from econ544.ads_did import analyze_paid_search, load_paid_search


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, help="optional paid-search CSV")
    parser.add_argument("--output", type=Path, help="write the JSON receipt atomically")
    args = parser.parse_args()

    frame, source = load_paid_search(args.data)
    result, _ = analyze_paid_search(frame)
    receipt = {
        "workflow": "paid-search difference-in-differences",
        "scope": "bundled historical classroom dataset; no live advertising platform",
        "dataset": source.name,
        "dataset_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "result": result.as_dict(),
    }
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        destination = args.output.expanduser().resolve()
        aliases_source = destination == source.resolve()
        if destination.exists():
            aliases_source = aliases_source or destination.samefile(source)
        if aliases_source:
            parser.error("output must not overwrite the input dataset")
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                staging = Path(handle.name)
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())
            staging.replace(destination)
        finally:
            if staging is not None:
                staging.unlink(missing_ok=True)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
