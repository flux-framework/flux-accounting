#!/usr/bin/env python3

import os
import sys
import argparse
from subprocess import Popen, PIPE

import flux
from flux.security import SecurityContext


def run_process(cmd, input=None):
    """Run command defined in `cmd` as a subprocess and return stdout

    If `input` is given, send to subprocess stdin.

    Copy any stderr to terminal and exit with error on subprocess failure.
    """

    with Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE) as proc:
        out, err = proc.communicate(input)
        if err:
            sys.stderr.write(err.decode("utf-8"))
        if proc.returncode != 0:
            sys.exit(1)
        return out.decode("utf-8").rstrip()


def main():

    if len(sys.argv) < 3:
        sys.exit(f"Usage: submit-as USERID [MINI OPTS...] COMMAND")

    userid = int(sys.argv[1])
    os.environ["FLUX_HANDLE_USERID"] = str(userid)

    submitcmd = ["flux", "job", "submit", "--flags=signed"]
    for arg in sys.argv[2:]:
        if "urgency" in arg:
            submitcmd.append(arg)

    runcmd = [
        "flux",
        "run",
        "--dry-run",
        "--setattr=system.exec.test.duration=0.1",
        *sys.argv[2:],
    ]
    jobspec = run_process(runcmd)

    signedJ = SecurityContext().sign_wrap_as(userid, jobspec, mech_type="none")

    jobid = run_process(submitcmd, input=signedJ)
    print(jobid)


if __name__ == "__main__":
    main()
