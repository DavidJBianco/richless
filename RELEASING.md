# Releasing richless

## Initial Setup (one-time)

### 1. PyPI Trusted Publishing

1. Create a [PyPI account](https://pypi.org/account/register/) if you don't have one.
2. Go to **pypi.org → Your Account → Publishing** and add a "pending publisher":
   - **PyPI project name:** `richless`
   - **Owner:** `DavidJBianco`
   - **Repository:** `richless`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
3. In the `richless` GitHub repo, go to **Settings → Environments** and create an environment named `pypi`.

### 2. Homebrew Tap

1. Create a new GitHub repository: **`DavidJBianco/homebrew-tools`**
2. Add a `Formula/` directory to the repo (can be empty initially).

After setup, users will install richless via:
```bash
brew install DavidJBianco/tools/richless
```

## Releasing a New Version

### 1. Bump the version

Edit `pyproject.toml` and update the `version` field.

### 2. Commit, tag, and push

```bash
git add pyproject.toml
git commit -m "Bump version to X.Y.Z"
git tag vX.Y.Z
git push origin main --tags
```

### 3. Wait for PyPI publish

The `publish.yml` GitHub Action triggers on the tag push. It builds the
sdist/wheel and publishes to PyPI via Trusted Publishing. Check the Actions
tab to confirm it succeeded.

### 4. Update the Homebrew formula

Wait a minute for PyPI to propagate, then generate the updated formula:

```bash
# In a temporary venv (not your dev environment)
python3 -m venv /tmp/poet-env
source /tmp/poet-env/bin/activate
pip install richless homebrew-pypi-poet
python3 scripts/generate-formula.py > /path/to/homebrew-tools/Formula/richless.rb
deactivate
```

Review the generated formula, then commit and push to the tap repo:

```bash
cd /path/to/homebrew-tools
git add Formula/richless.rb
git commit -m "Update richless to X.Y.Z"
git push
```

### 5. Verify

```bash
# Test PyPI install
python3 -m venv /tmp/test-env
source /tmp/test-env/bin/activate
pip install richless
richless --help
deactivate

# Test Homebrew install
brew update
brew install DavidJBianco/tools/richless
richless --help
```

After `brew install`, verify the caveats message shows the correct path for
`richless-init.sh`.

## Pre-release Checks

Before tagging a release, verify the sdist is correct:

```bash
uv build
tar tzf dist/richless-*.tar.gz
```

Confirm the archive contains:
- `richless.py`
- `richless-init.sh`
- `LICENSE`
- `README.md`
