"""Prepare and verify the Skyfield ephemeris used by saju calculations."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from app.domain.saju.services.solar_term_boundaries import (
    SKYFIELD_CACHE_ENV,
    SKYFIELD_EPHEMERIS,
    SKYFIELD_EPHEMERIS_SHA256,
    SKYFIELD_EPHEMERIS_SIZE_BYTES,
    _file_sha256,
)


def default_data_dir() -> Path:
    configured_dir = os.environ.get(SKYFIELD_CACHE_ENV)
    if configured_dir:
        return Path(configured_dir)
    return Path.home() / ".cache" / "saju-skyfield"


def ephemeris_path(data_dir: Optional[Path] = None) -> Path:
    return (data_dir or default_data_dir()) / SKYFIELD_EPHEMERIS


def build_status(path: Path) -> Dict[str, Any]:
    exists = path.exists()
    size = path.stat().st_size if exists else None
    sha256 = _file_sha256(path) if exists else None
    return {
        "ephemeris": SKYFIELD_EPHEMERIS,
        "path": str(path),
        "exists": exists,
        "size_bytes": size,
        "expected_size_bytes": SKYFIELD_EPHEMERIS_SIZE_BYTES,
        "sha256": sha256,
        "expected_sha256": SKYFIELD_EPHEMERIS_SHA256,
        "size_matches": size == SKYFIELD_EPHEMERIS_SIZE_BYTES if exists else False,
        "sha256_matches": sha256 == SKYFIELD_EPHEMERIS_SHA256 if exists else False,
    }


def check_ephemeris(path: Path) -> Dict[str, Any]:
    status = build_status(path)
    if not status["exists"]:
        raise FileNotFoundError(
            f"Missing Skyfield ephemeris at {path}. "
            "Run this command with --download before deploying."
        )
    if not status["size_matches"]:
        raise ValueError(
            f"Invalid Skyfield ephemeris size at {path}: "
            f"{status['size_bytes']} != {SKYFIELD_EPHEMERIS_SIZE_BYTES}"
        )
    if not status["sha256_matches"]:
        raise ValueError(
            f"Invalid Skyfield ephemeris sha256 at {path}: "
            f"{status['sha256']} != {SKYFIELD_EPHEMERIS_SHA256}"
        )
    return status


def download_ephemeris(path: Path, *, refresh: bool = False) -> Dict[str, Any]:
    if path.exists() and not refresh:
        return build_status(path)

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and refresh:
        path.unlink()

    from skyfield.api import Loader

    loader = Loader(str(path.parent))
    loaded = loader(SKYFIELD_EPHEMERIS)
    loaded_path = Path(getattr(loaded, "filename", path))
    if loaded_path != path and loaded_path.exists() and not path.exists():
        loaded_path.replace(path)
    return build_status(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download and verify the Skyfield ephemeris before runtime.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=default_data_dir(),
        help=f"Directory for {SKYFIELD_EPHEMERIS}; defaults to ${SKYFIELD_CACHE_ENV} or user cache.",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download the ephemeris if missing.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Remove and re-download the ephemeris.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify file size and SHA256.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON status.",
    )
    args = parser.parse_args()

    path = ephemeris_path(args.data_dir)
    if args.download or args.refresh:
        status = download_ephemeris(path, refresh=args.refresh)
    else:
        status = build_status(path)

    if args.check or not (args.download or args.refresh):
        status = check_ephemeris(path)

    if args.json:
        print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    else:
        state = "ok" if status["size_matches"] and status["sha256_matches"] else "not_ready"
        print(
            f"Skyfield ephemeris {state}: {status['path']} "
            f"size={status['size_bytes']} sha256={status['sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
