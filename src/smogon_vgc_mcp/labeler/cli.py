"""``vgc-label`` entry point — starts the local FastAPI labeler.

Kept minimal; the FastAPI app itself lives in :mod:`labeler.app` and is
built in L2. This stub exists so the ``vgc-label`` script resolves and
fails with a clear message until routes land.
"""

from __future__ import annotations

import sys


def main() -> None:
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "vgc-label requires the 'labeler' extras. Install with:\n  uv sync --extra labeler\n"
        )
        sys.exit(1)

    try:
        from smogon_vgc_mcp.labeler.app import create_app  # noqa: F401
    except ImportError as exc:
        sys.stderr.write(f"Labeler app not yet available: {exc}\n")
        sys.exit(1)

    import uvicorn

    uvicorn.run(
        "smogon_vgc_mcp.labeler.app:create_app",
        factory=True,
        host="127.0.0.1",
        port=8765,
        reload=False,
    )


if __name__ == "__main__":
    main()
