import argparse


def main() -> int:
    parser = argparse.ArgumentParser(prog="brokentool")
    parser.parse_args()
    print("brokentool ok")
    return 0
