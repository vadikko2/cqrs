# Contributing to python-cqrs

Thank you for your interest in contributing to `python-cqrs`! We welcome contributions of all kinds: bug fixes, new features, documentation improvements, and performance enhancements.

---

## 1. Prerequisites

- **Python Version:** Python **3.10** or higher (3.10, 3.11, 3.12, 3.13 are supported).
- **Git** installed on your system.
- *(Optional, for integration tests)*: **Docker** & **Docker Compose**. `docker-compose-test.yml` provides MySQL, PostgreSQL, and Redis. Kafka is available separately in `docker-compose-dev.yml` for local broker experiments; RabbitMQ is not defined in either Compose file.

---

## 2. Local Setup

1. **Fork and Clone the Repository:**
   ```bash
   git clone https://github.com/<your-username>/python-cqrs.git
   cd python-cqrs
   ```

2. **Create and Activate a Virtual Environment:**
   ```bash
   python -m venv .venv

   # On Linux/macOS:
   source .venv/bin/activate

   # On Windows:
   .venv\Scripts\activate
   ```

3. **Install Dependencies in Editable Mode:**
   Minimal developer install (tooling and tests):
   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

   Optionally also install example extras (FastAPI, FastStream, uvicorn, and related packages):
   ```bash
   pip install -e ".[dev,examples]"
   ```

4. **Set Up Pre-commit Hooks:**
   ```bash
   pre-commit install
   ```

---

## 3. Code Style & Quality Checks

We use several automated tools to maintain code quality. Please run these before submitting a pull request:

### Ruff (Linting & Formatting)
- Check linting rules:
  ```bash
  ruff check --config ruff.toml
  ```
- Automatically fix linting issues:
  ```bash
  ruff check --fix --config ruff.toml
  ```
- Check code formatting:
  ```bash
  ruff format --check --config ruff.toml
  ```
- Format code:
  ```bash
  ruff format --config ruff.toml
  ```

### Pyright (Static Type Checking)
Run type analysis across the codebase:
```bash
pyright src tests examples
```

### Vermin (Minimum Python Version Verification)
Ensure no features unsupported in Python 3.10 are introduced:
```bash
vermin --target=3.10- --violations --eval-annotations --backport typing_extensions --exclude=venv --exclude=build --exclude=.git --exclude=.venv src examples tests
```

---

## 4. Running Tests

Tests are organized under the `tests/` directory and executed with `pytest`.

### Unit Tests
Run the unit suite locally (no Docker required):
```bash
pytest -c ./tests/pytest-config.ini ./tests/unit
```

### Integration Tests with Docker
Integration tests need the services defined in `docker-compose-test.yml` (MySQL, PostgreSQL, Redis):
```bash
# Start test infrastructure
docker compose -f docker-compose-test.yml up -d

# Run integration tests
pytest -c ./tests/pytest-config.ini ./tests/integration

# Stop infrastructure when finished
docker compose -f docker-compose-test.yml down
```

---

## 5. Pull Request Guidelines

### Preferred PR Scope & Size
- **Small & Focused:** Keep PRs atomic and focused on a single change, fix, or feature. Smaller PRs are easier to review, test, and merge quickly.
- **Link Related Issues:** Reference the issue your PR resolves (e.g., `Fixes #123` or `Closes #123`) in the PR description.
- **Add Tests:** If you are adding a feature or fixing a bug, include corresponding unit or integration tests.
- **Update Documentation:** If your changes affect APIs or configuration, update the relevant documentation.

### PR Checklist
Before opening a PR, ensure:
- [ ] Code follows formatting standards (`ruff format`).
- [ ] Linter checks pass without errors (`ruff check`).
- [ ] Type checks pass (`pyright`).
- [ ] Unit tests pass locally (`pytest -c ./tests/pytest-config.ini ./tests/unit`).
- [ ] Commits have clear and descriptive messages.

---

## 6. Issue Labels

We use labels to categorize and track issues:
- `good first issue`: Ideal for newcomers looking to get familiar with the codebase.
- `help wanted`: Tasks where community assistance is actively sought.
- `bug`: A problem or unintended behavior in `python-cqrs`.
- `enhancement`: New feature requests or architectural improvements.
- `documentation`: Additions or improvements to guides, docstrings, or examples.

---

## 7. Community & Conduct

We are committed to providing a welcoming, inclusive, and respectful environment for everyone. Please be constructive and kind in discussions, code reviews, and issue reports.
