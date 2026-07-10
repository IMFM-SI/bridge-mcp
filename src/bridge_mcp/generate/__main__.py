"""The generation driver: `python -m bridge_mcp.generate <target>`.

Targets run in dependency order; `graphs` creates the database and refuses to
overwrite it, the others rebuild their own tables inside it.
"""

import argparse
import logging

from bridge_mcp.generate import graphs, pibase


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S"
    )
    parser = argparse.ArgumentParser(prog="python -m bridge_mcp.generate")
    parser.add_argument("target", choices=["graphs", "pibase", "all"])
    parser.add_argument(
        "--max-vertices",
        type=int,
        default=graphs.DEFAULT_MAX_VERTICES,
        help="largest graph order for the graphs target",
    )
    parser.add_argument("--file", help="read the π-Base bundle from a local file")
    arguments = parser.parse_args()
    if arguments.target in ("graphs", "all"):
        graphs.main(arguments.max_vertices)
    if arguments.target in ("pibase", "all"):
        pibase.main(arguments.file)


if __name__ == "__main__":
    main()
