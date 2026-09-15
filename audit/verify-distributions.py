"""Verify installed wheel/sdist, legacy wrapper upgrades, copied scripts, and rollback."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
evidence = []


def run(args, **kwargs):
    result = subprocess.run(args, capture_output=True, timeout=120, **kwargs)
    evidence.append({"command": list(map(str, args)), "status": result.returncode,
                     "stdout": result.stdout.decode(errors="replace"),
                     "stderr": result.stderr.decode(errors="replace")})
    if result.returncode:
        raise RuntimeError(evidence[-1])
    return result.stdout


try:
    with tempfile.TemporaryDirectory(prefix="richless-install-") as directory:
        work = Path(directory)
        legacy = work / "legacy"
        shutil.copytree(root / "tests/fixtures/legacy", legacy)
        run(["uv", "build", str(legacy), "--out-dir", str(work / "old-dist")], cwd=work)
        old_wheel = next((work / "old-dist").glob("*.whl"))
        for artifact in sorted((root / "dist").glob("richless-0.4.0*")):
            envdir = work / artifact.suffix.replace(".", "env")
            run(["uv", "venv", "--python", sys.executable, str(envdir)], cwd=work)
            python = envdir / "bin/python"
            cli = envdir / "bin/richless"
            env = dict(os.environ, PATH=str(envdir / "bin") + os.pathsep + os.environ["PATH"])
            env.pop("PYTHONPATH", None)
            run(["uv", "pip", "install", "--python", str(python), str(old_wheel)], cwd=work)
            copied = work / "copied-init.sh"
            shutil.copyfile(legacy / "richless-init.sh", copied)
            # Upgrade the renderer while preserving an already-loaded old shell function.
            for shell in ("bash", "zsh", "/bin/sh"):
                command = f'. {shlex.quote(str(copied))}; '
                command += shlex.join(["uv", "pip", "install", "--python", str(python), str(artifact)])
                command += '; printf "# UPGRADE\\n\\n**works**\\n" | less --md'
                output = run([shell, "-c", command], cwd=work, env=env)
                assert b"UPGRADE" in output and b"works" in output
            installed = Path(run([str(cli), "--init-path"], cwd=work, env=env).decode().strip())
            assert installed.is_file() and installed.read_bytes() == (root / "richless-init.sh").read_bytes()
            shutil.copyfile(installed, copied)
            for shell in ("bash", "zsh", "/bin/sh"):
                output = run([shell, "-c", f'. {shlex.quote(str(copied))}; '
                              'printf "# COPIED\\n\\n**works**\\n" | less --md'], cwd=work, env=env)
                assert b"COPIED" in output and b"works" in output
            for alias in ("--md", "--markdown"):
                assert b"DIRECT" in run([str(cli), alias, "-"], input=b"# DIRECT\n", cwd=work, env=env)
            # Roll back the package and its matching copied integration together.
            run(["uv", "pip", "install", "--python", str(python), str(old_wheel)], cwd=work)
            shutil.copyfile(legacy / "richless-init.sh", copied)
            output = run(["/bin/sh", "-c", f'. {shlex.quote(str(copied))}; '
                          'printf "# ROLLBACK\\n\\n**works**\\n" | less --md'], cwd=work, env=env)
            assert b"ROLLBACK" in output
    print("Wheel, sdist, old loaded wrappers, copied scripts, and matched rollback passed.")
finally:
    destination = Path(os.environ.get("RICHLESS_INSTALL_EVIDENCE", "/tmp/richless-install-results.json"))
    destination.write_text(json.dumps(evidence, indent=2))
