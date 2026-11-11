"""Inspect an ontology without needing an LLM or a running MCP host."""

import argparse
import json

from owl_rag.config import configured_store
from owl_rag.models import ContextOptions
from owl_rag.ontology import Ontology
from owl_rag.service import OntologyService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--format", choices=["xml", "turtle", "nt"])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--query")
    group.add_argument("--entity", help="Full IRI or an unambiguous class name")
    parser.add_argument(
        "--kind",
        default="all",
        choices=["all", "class", "property", "individual", "ontology", "other"],
    )
    parser.add_argument("--mode", choices=["lexical", "hybrid"], default="lexical")
    parser.add_argument("--context", action="store_true")
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    store = None
    try:
        if args.context and args.query is None:
            raise ValueError("--context requires --query")
        doc = Ontology.load("default", args.path, args.format)
        store = configured_store("owl_entities", required=True) if args.mode == "hybrid" else None
        service = OntologyService([doc], store)
        if args.query is not None:
            if args.context:
                result = service.retrieve_context(
                    "default",
                    args.query,
                    args.kind,
                    args.mode,
                    ContextOptions(max_depth=args.depth),
                )
            else:
                result = service.search_entities(
                    "default", args.query, args.kind, args.mode, limit=args.limit
                )
        elif args.entity:
            iri = str(doc.resolve_class(args.entity)) if ":" not in args.entity else args.entity
            result = service.get_entity("default", iri)
            result["relations"] = service.get_relations("default", iri, "both", limit=args.limit)
        else:
            result = service.list_classes("default", limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"owl-inspect: {exc}\n")
    finally:
        if store:
            store.client.close()


if __name__ == "__main__":
    main()
