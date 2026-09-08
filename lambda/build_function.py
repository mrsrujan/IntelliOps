#!/usr/bin/env python
"""
Build a Lambda deployment directory: copy source .py files + pip install deps.

Invoked by Terraform's local-exec instead of shelling to bash — Python handles
Windows paths correctly, whereas Git Bash on Windows chokes on `cd` into
paths that start with "C:/" combined with absolute-path globs.

Usage:
    python build_function.py <src_dir> <build_dir>

<src_dir>   absolute path to a Lambda function's source (e.g. lambda/rca_generator)
<build_dir> absolute path where the packaged .zip content should be staged
"""

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: build_function.py <src_dir> <build_dir>")

    src = Path(sys.argv[1]).resolve()
    build = Path(sys.argv[2]).resolve()

    if not src.is_dir():
        sys.exit(f"src is not a directory: {src}")

    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)

    py_files = list(src.glob("*.py"))
    if not py_files:
        sys.exit(f"no .py files found in {src}")
    for py in py_files:
        shutil.copy(py, build)

    requirements = src / "requirements.txt"
    if requirements.exists():
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "--quiet", "--disable-pip-version-check",
            "-r", str(requirements),
            "-t", str(build),
        ])

    print(f"built {len(py_files)} .py files + deps into {build}")


if __name__ == "__main__":
    main()
