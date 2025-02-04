import sys

from atomicshop.wrappers import githubw


def main():
    githubw.github_wrapper_main_with_args()


if __name__ == "__main__":
    sys.exit(main())