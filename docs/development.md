# Checks before committing

Install development dependencies with the project:

```bash
uv sync --locked
uv run pre-commit install
uv run pre-commit run --all-files
```

Shortcuts: `make hooks` installs the Git hook, and `make pre-commit` checks the
entire repository. Install the hook in each new local clone. Once installed,
`git commit` runs checks on the files staged for that commit.

## Check suite

The configuration lives in [.pre-commit-config.yaml](../.pre-commit-config.yaml).

| Check | Purpose |
| --- | --- |
| detect-secrets | Find keys, tokens and suspicious secret values throughout the repository |
| known-key-formats | Additional patterns for LiteLLM / provider `sk-`, Tavily `tvly-` and RunPod `rpa_` keys |
| forbid-secret-files | Block `.env`, `.env.local` and private credential files, including files staged with `git add -f` |
| detect-private-key | Detect private-key contents |
| Ruff | Python linting and formatting checks; the version matches uv.lock |
| MyPy | Type checking for the application in `src/owl_rag` |
| Bandit | Check Python code for common security issues |
| Hadolint | Check `deploy/Dockerfile` |
| General checks | YAML/TOML, merge markers, files larger than 1000 KB, whitespace and file endings |

Ruff, MyPy and Bandit settings live in [pyproject.toml](../pyproject.toml).
Pre-commit installs isolated tool environments; the first run requires access to
GitHub and PyPI. Run tests separately with `make test`.

## Keys and local settings

Keep real keys in a local `.env`. `.gitignore` also excludes `.env.*` variants.
Templates such as `.env.example` and `.env.production.example` are allowed by
filename and have their contents scanned alongside the rest of the repository.

The hook blocks files named `id_rsa`, `id_dsa`, `id_ecdsa` and `id_ed25519`,
and extensions `.key`, `.p12`, `.pfx`, `.jks` and `.keystore`. PEM files are checked
by content through detect-private-key. The same `.env.*` patterns are excluded
from the Docker build context.

`uv.lock` is excluded from detect-secrets because it contains many hashes;
the additional known-key-format check still applies to it. Detect-secrets uses
`--no-verify`, so discovered values are not sent to providers to test whether a key
works. Exact expressions such as `os.environ/CHAT_API_KEY` are excluded from
detection because they reference environment variables.

This project does not need a secrets baseline. If a scanner reports a finding,
inspect the file locally and replace any real secret with an environment-variable
reference. False-positive exceptions should apply to a specific reviewed example.

Hooks help catch secrets before a commit, but the detectors cannot recognize every
possible type of credential.
