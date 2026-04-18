import sys
from helpers import *


def main():
    ensure_daemon()
    exec(sys.stdin.read())


if __name__ == "__main__":
    main()
