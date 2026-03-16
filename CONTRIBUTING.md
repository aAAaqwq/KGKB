# Contributing to KGKB

Thank you for your interest in contributing to KGKB! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git

### Local Development

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/KGKB.git
cd KGKB

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..

# Create config
cp config.example.yaml ~/.kgkb/config.yaml
```

## Project Structure

```
KGKB/
├── backend/          # FastAPI backend
│   ├── api/          # API routes
│   ├── models/       # Data models
│   ├── services/     # Business logic
│   └── main.py       # App entry point
├── frontend/         # React frontend
│   ├── src/
│   │   ├── components/
│   │   ├── views/
│   │   └── App.tsx
│   └── package.json
├── cli/              # CLI commands
│   └── kgkb/
│       ├── __init__.py
│       └── main.py
├── docs/             # Documentation
└── tests/            # Test files
```

## Coding Standards

### Python

- Follow PEP 8
- Use type hints
- Write docstrings for functions
- Run `black .` and `ruff check .` before committing

### TypeScript/React

- Use functional components with hooks
- Follow Airbnb style guide
- Run `npm run lint` before committing

## Commit Convention

We use conventional commits:

```
feat: add new feature
fix: fix a bug
docs: update documentation
refactor: code refactoring
test: add/update tests
chore: maintenance tasks
```

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes
3. Add/update tests
4. Ensure all tests pass
5. Update documentation if needed
6. Submit PR with clear description

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
