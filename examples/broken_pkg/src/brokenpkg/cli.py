import argparse


def main() -> int:
    parser = argparse.ArgumentParser(prog="brokentool")
    parser.add_argument("--name", default="world")
    args = parser.parse_args()
    print(f"brokentool ok: {args.name}")
    return 0
