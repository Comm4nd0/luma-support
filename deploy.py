#!/usr/bin/env python3
"""Deploy luma-support on the Hetzner host.

Pulls the latest master, rebuilds the Docker images, runs migrations
against the new image, and recreates the container stack. Idempotent —
safe to re-run.

Run as the user that owns the repo checkout. Requires `docker` and
`git` on PATH; the user must be in the `docker` group so it can talk
to the daemon without sudo.

Order of operations matters: migrations run in a one-off container
using the *new* image **before** the old long-running web container
is replaced. If a migration fails, the old code keeps serving traffic
and the deploy aborts cleanly.

    ./deploy.py                # pull, build, migrate, recreate
    ./deploy.py --no-pull      # rebuild current checkout
    ./deploy.py --no-build     # restart with existing images
    ./deploy.py --no-migrate   # skip the explicit migrate step
    ./deploy.py --prune        # also clean dangling images
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def step(msg: str) -> None:
    print(f"\n==> {msg}", flush=True)


def run(cmd: list[str], **kwargs) -> None:
    """Run a command, streaming output. Raises on non-zero exit."""
    print(f"  $ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True, **kwargs)


def capture(cmd: list[str], **kwargs) -> str:
    return subprocess.run(
        cmd, check=True, capture_output=True, text=True, **kwargs
    ).stdout.strip()


def _supports_compose_subcommand() -> bool:
    try:
        subprocess.run(
            ["docker", "compose", "version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def compose_cmd() -> list[str]:
    """Resolve `docker compose` vs legacy `docker-compose` once."""
    if shutil.which("docker") and _supports_compose_subcommand():
        return ["docker", "compose"]
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    sys.exit("error: neither `docker compose` nor `docker-compose` is on PATH")


def assert_clean_tree() -> None:
    """Refuse to deploy with uncommitted local changes."""
    dirty = capture(["git", "status", "--porcelain"], cwd=REPO_ROOT)
    if dirty:
        print("error: working tree has uncommitted changes:", file=sys.stderr)
        print(dirty, file=sys.stderr)
        print("commit or stash before deploying.", file=sys.stderr)
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--no-pull", action="store_true", help="Skip the git pull.")
    p.add_argument(
        "--no-build", action="store_true", help="Skip the docker image rebuild."
    )
    p.add_argument(
        "--no-migrate",
        action="store_true",
        help="Skip the explicit migrate step (the web container still migrates on start).",
    )
    p.add_argument(
        "--prune",
        action="store_true",
        help="Run `docker image prune -f` after the restart.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    compose = compose_cmd()

    if not (REPO_ROOT / ".env").exists():
        sys.exit(
            "error: .env not found at repo root. Copy .env.example and fill it "
            "in before deploying."
        )

    head_before = capture(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT)
    print(f"deploying luma-support from {REPO_ROOT}")
    print(f"current HEAD: {head_before}")

    if not args.no_pull:
        step("Pulling latest master")
        assert_clean_tree()
        run(["git", "fetch", "origin", "master"], cwd=REPO_ROOT)
        run(["git", "pull", "--ff-only", "origin", "master"], cwd=REPO_ROOT)
        head_after = capture(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT)
        if head_after == head_before:
            print(f"already up to date at {head_after}")
        else:
            print(f"new HEAD: {head_after}")

    if not args.no_build:
        step("Pulling base images (postgres, redis)")
        run(compose + ["pull", "postgres", "redis"], cwd=REPO_ROOT)

        step("Rebuilding the application image")
        run(compose + ["build", "--pull"], cwd=REPO_ROOT)

    if not args.no_migrate:
        step("Running migrations with the new image")
        # One-off container, auto-removed. depends_on=postgres healthcheck in
        # compose.yml means this waits for the DB before running. If this
        # exits non-zero the deploy aborts and the old web container keeps
        # serving — we never replace it with broken code.
        run(
            compose
            + ["run", "--rm", "web", "python", "manage.py", "migrate", "--noinput"],
            cwd=REPO_ROOT,
        )

    step("Recreating containers")
    # `up -d` recreates only services whose image or config changed; --remove-orphans
    # tidies up any service that was removed from compose.yml since last deploy.
    run(compose + ["up", "-d", "--remove-orphans"], cwd=REPO_ROOT)

    step("Container status")
    run(compose + ["ps"], cwd=REPO_ROOT)

    step("Recent web logs (last 40 lines)")
    # Don't `check=True` — logs failing shouldn't fail the deploy.
    subprocess.run(compose + ["logs", "--tail=40", "web"], cwd=REPO_ROOT)

    if args.prune:
        step("Pruning dangling images")
        run(["docker", "image", "prune", "-f"])

    print("\nDeploy complete.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        print(
            f"\nstep failed (exit {exc.returncode}): {' '.join(exc.cmd)}",
            file=sys.stderr,
        )
        sys.exit(exc.returncode)
    except KeyboardInterrupt:
        print("\ninterrupted.", file=sys.stderr)
        sys.exit(130)
