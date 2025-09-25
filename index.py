import argparse
from pathlib import Path
from indexer import build_index, build_index_multi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", required=True, help="Path to anthropic-data directory (comma-separated for multiple)")
    ap.add_argument("--out", required=True, help="Output folder for index (creates chatgpt.db)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    exports = [e.strip() for e in args.export.split(',') if e.strip()]
    if len(exports) <= 1:
        build_index(Path(exports[0]), out_dir)
    else:
        from pathlib import Path as _P
        build_index_multi([( _P(e).name or "default", _P(e)) for e in exports], out_dir)


if __name__ == "__main__":
    main()


