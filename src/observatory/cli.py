"""One operational entry point; all mutation stays inside the selected workspace."""
import argparse
import asyncio
import functools
import http.server
import json
from pathlib import Path

from .build import build, verify
from .collect import Collector, Policy, discover
from .storage import Lake, read_json


def parser():
    root = argparse.ArgumentParser(prog="observatory", description="Open Finance Brasil · Observatory")
    root.add_argument("--lake", type=Path, default=Path("data"), help="Diretório isolado do lake")
    sub = root.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import", help="Importar bronze legado sem alterar a origem")
    imp.add_argument("source", type=Path)
    disc = sub.add_parser("discover", help="Resolver participantes e catálogo")
    disc.add_argument("--groups", type=Path, default=Path("config/groups.json"))
    disc.add_argument("--directory", type=Path, help="Replay de um Diretório salvo; omitido consulta a fonte oficial")
    collect = sub.add_parser("collect", help="Coletar catálogo com checkpoints")
    collect.add_argument("--resume", help="Retomar snapshot; endpoints completos são preservados")
    collect.add_argument("--concurrency", type=int, default=8)
    collect.add_argument("--per-host", type=int, default=2)
    collect.add_argument("--interval", type=float, default=.25)
    collect.add_argument("--max-pages", type=int, default=400)
    for command in ("build", "verify"):
        child = sub.add_parser(command)
        child.add_argument("--snapshot")
        if command == "build":
            child.add_argument("--output", type=Path, default=Path("dist"))
            child.add_argument("--memory", default="1GB")
            child.add_argument("--threads", type=int, default=4)
    sub.add_parser("status", help="Última publicação e evidências de execução")
    docs = sub.add_parser("docs", help="Gerar documentação HTML autocontida do build publicado")
    docs.add_argument("--output", type=Path, default=Path("docs/documentacao.html"))
    serve = sub.add_parser("serve", help="Servir dashboard local somente em loopback")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--directory", type=Path, default=Path("dist"))
    return root


def main():
    args = parser().parse_args()
    try:
        if args.command == "serve":
            directory = args.directory.resolve()
            if not (directory / "index.html").exists():
                raise ValueError("Execute observatory build antes de servir")
            handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
            server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
            print(f"Observatory: http://127.0.0.1:{args.port}", flush=True)
            try:
                server.serve_forever()
            finally:
                server.server_close()
            return
        lake = Lake(args.lake)
        if args.command == "docs":
            from .documentation import generate
            latest = read_json(lake.root / "latest.json")
            result = {"documentation": str(generate(lake.root / "gold" / latest["build_id"], args.output).resolve())}
        elif args.command == "verify":
            result = verify(lake, args.snapshot)
        elif args.command == "status":
            latest = read_json(lake.root / "latest.json")
            result = read_json(lake.root / "gold" / latest["build_id"] / "build.json")
        else:
            with lake.lock():
                if args.command == "import":
                    from .storage import import_legacy
                    manifest = import_legacy(lake, args.source)
                    result = {"snapshot_id": manifest["snapshot_id"], "endpoints": len(manifest["captures"]), "source_unchanged": True}
                elif args.command == "discover":
                    result = discover(lake, args.groups, args.directory)
                    result = {"targets": len(result["targets"]), "members": len(result["evidence"]), "directory_sha": result["directory_sha"]}
                elif args.command == "collect":
                    policy = Policy(concurrency=args.concurrency, per_host=args.per_host, interval=args.interval, max_pages=args.max_pages)
                    result = asyncio.run(Collector(lake, policy).run(read_json(lake.root / "catalog.json"), args.resume))
                    result = {"snapshot_id": result["snapshot_id"], "endpoints": len(result["captures"])}
                else:
                    result = build(lake, args.snapshot, args.output, args.memory, args.threads)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError, FileNotFoundError) as error:
        raise SystemExit(f"Falha: {error}") from error


if __name__ == "__main__":
    main()
