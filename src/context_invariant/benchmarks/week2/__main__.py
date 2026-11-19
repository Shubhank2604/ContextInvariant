"""python -m context_invariant.benchmarks.week2: separate, locked offline entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from context_invariant.benchmarks.week2.audit import audit_evaluation
from context_invariant.benchmarks.week2.models import Mode
from context_invariant.benchmarks.week2.preflight import json_bytes, make_freeze, preflight
from context_invariant.benchmarks.week2.runner import run_evaluation
from context_invariant.benchmarks.week2.synthetic import write_synthetic


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    synthetic = commands.add_parser("synthetic", help="create only labelled development fixtures")
    synthetic.add_argument("--output-directory", type=Path, required=True)
    synthetic.add_argument("--developer-curated", action="store_true")
    freeze = commands.add_parser(
        "freeze", help="freeze committed source/configuration and environment"
    )
    freeze.add_argument("--output", type=Path, required=True)
    for name in ("preflight", "run", "audit"):
        command = commands.add_parser(name)
        command.add_argument("--inputs", type=Path, required=True)
        command.add_argument("--keys", type=Path, required=True)
        command.add_argument("--freeze", type=Path, required=True)
        command.add_argument("--developer-curated", action="store_true")
        command.add_argument("--curation-record", type=Path)
        command.add_argument(
            "--synthetic",
            action="store_true",
            help="unsigned development only; never final evidence",
        )
        command.add_argument("--seal", type=Path)
        command.add_argument("--signature", type=Path)
        command.add_argument("--public-key", type=Path)
        command.add_argument("--trusted-key-sha256")
        if name == "run":
            command.add_argument("--output-directory", type=Path, required=True)
        if name == "audit":
            command.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "synthetic":
            write_synthetic(args.output_directory, developer_curated=args.developer_curated)
            print(args.output_directory)
            return
        if args.command == "freeze":
            snapshot = make_freeze()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("xb") as output:
                output.write(json_bytes(snapshot.model_dump(mode="json")))
            print(args.output)
            return
        mode: Mode = "synthetic_development" if args.synthetic else "sealed_final"
        if args.developer_curated:
            mode = "developer_curated_development" if args.synthetic else "developer_curated"
        evidence = dict(
            seal_path=args.seal,
            signature_path=args.signature,
            public_key_path=args.public_key,
            trusted_key_sha256=args.trusted_key_sha256,
            curation_path=args.curation_record,
        )
        if args.command == "preflight":
            cases, _, result = preflight(args.inputs, args.keys, args.freeze, mode=mode, **evidence)
            print(
                json.dumps(
                    {
                        "status": "passed",
                        "case_count": len(cases),
                        "mode": mode,
                        "seal_verified": result["seal_verified"],
                        "selectors_run": False,
                        **{
                            key: result[key]
                            for key in (
                                "review_arrangement",
                                "independent_human_review",
                                "developer_approval_recorded",
                            )
                            if key in result
                        },
                    },
                    indent=2,
                )
            )
        elif args.command == "run":
            print(
                run_evaluation(
                    args.inputs,
                    args.keys,
                    args.freeze,
                    args.output_directory,
                    mode=mode,
                    **evidence,
                )
            )
        else:
            print(
                json.dumps(
                    audit_evaluation(
                        args.bundle, args.inputs, args.keys, args.freeze, mode=mode, **evidence
                    ),
                    indent=2,
                )
            )
    except (ValueError, OSError) as error:
        parser.exit(2, f"Week 2 {args.command} rejected: {error}\n")


if __name__ == "__main__":
    main()
