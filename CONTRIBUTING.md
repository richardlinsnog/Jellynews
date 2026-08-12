




# Contributing to JellyNews

Thank you for your interest in contributing!

## Getting Started

1. Fork the repository and clone it locally.
2. Create a virtual environment: `python -m venv .venv && source .venv/bin/activate`
3. Install backend deps: `pip install -r backend/requirements.txt`
4. Install frontend deps: `cd frontend && npm install`
5. Run the development server: `cd backend && uvicorn main:app --reload`

For frontend development, run `npm run dev` from the `frontend/` directory in a separate terminal.

## Development Workflow

- Create a feature branch from `main` for your changes.
- Write code and tests. Ensure the test suite passes before submitting.
- Use `ruff format` and `ruff check` for Python code. Use `prettier` for frontend code.
- Commit messages should follow [Conventional Commits](https://www.conventionalcommits.org/) (e.g. `feat:`, `fix:`, `docs:`).
- Open a pull request against `main`.

## Template Packages

Template packages are zip files containing a `manifest.json` and Jinja2 template files. See the [template spec](backend/templates/README.md) for details.

## Reporting Issues

- Search existing issues before opening a new one.
- Include steps to reproduce, expected behavior, and actual behavior.
- For security issues, please do NOT open a public issue — contact the maintainers directly.

## License

By contributing, you agree that your contributions will be licensed under the MIT License (see [LICENSE](LICENSE)).


