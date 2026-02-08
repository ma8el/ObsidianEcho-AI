#!/usr/bin/env python3
"""CLI utility to generate API keys."""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.security import generate_api_key


def main() -> None:
    """Generate and print a new API key."""
    parser = argparse.ArgumentParser(description="Generate a new API key for ObsidianEcho-AI")
    parser.add_argument(
        "-n",
        "--number",
        type=int,
        default=1,
        help="Number of keys to generate (default: 1)",
    )
    parser.add_argument(
        "--yaml",
        action="store_true",
        help="Output in YAML format ready to add to config",
    )

    args = parser.parse_args()

    if args.yaml:
        print("# Add to your config/main.yaml under auth.api_keys:")
        for i in range(args.number):
            key = generate_api_key()
            print(f'  - key_id: "key-{i+1}"')
            print(f'    name: "API Key {i+1}"')
            print(f'    key: "{key}"')
            print('    status: "active"')
            if i < args.number - 1:
                print()
    else:
        for _ in range(args.number):
            key = generate_api_key()
            print(key)


if __name__ == "__main__":
    main()
