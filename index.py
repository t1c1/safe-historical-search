import argparse
from pathlib import Path
from indexer import build_index, build_index_multi, build_knowledge_graph, build_dual_index


def main():
    ap = argparse.ArgumentParser(description="Build search index from AI conversation exports")
    ap.add_argument("--export", required=True, help="Path to export directory (comma-separated for multiple)")
    ap.add_argument("--out", required=True, help="Output folder for index")
    ap.add_argument("--kg", "--knowledge-graph", action="store_true", 
                    help="Build knowledge graph database (knowledge.db) instead of legacy format")
    ap.add_argument("--dual", action="store_true",
                    help="Build both legacy (chatgpt.db) and knowledge graph (knowledge.db)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    exports = [e.strip() for e in args.export.split(',') if e.strip()]
    sources = [(Path(e).name or "default", Path(e)) for e in exports]
    
    if args.dual:
        legacy_path, kg_path = build_dual_index(sources, out_dir)
        print(f"\nBuilt dual index: {legacy_path} and {kg_path}")
    elif args.kg:
        build_knowledge_graph(sources, out_dir)
    elif len(exports) <= 1:
        build_index(Path(exports[0]), out_dir)
    else:
        build_index_multi(sources, out_dir)


if __name__ == "__main__":
    main()


