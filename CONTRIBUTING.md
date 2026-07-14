# Contribution guidelines

Contributing to this project should be as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features

## Github is used for everything

Github is used to host code, to track issues and feature requests, as well as accept pull requests.

Pull requests are the best way to propose changes to the codebase.

1. Fork the repo and create your branch from `main`.
2. If you've changed something, update the documentation.
3. Make sure your code lints (using [black](https://pypi.org/project/black/) and [flake8](https://pypi.org/project/flake8/)).
4. Test you contribution.
5. Issue that pull request!

## Any contributions you make will be under the MIT Software License

In short, when you submit code changes, your submissions are understood to be under the same [MIT License](http://choosealicense.com/licenses/mit/) that covers the project. Feel free to contact the maintainers if that's a concern.

## Report bugs using Github's [issues](../../issues)

GitHub issues are used to track public bugs.
Report a bug by [opening a new issue](../../issues/new/choose); it's that easy!

## Write bug reports with detail, background, and sample code

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can.
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

People *love* thorough bug reports.

## Use a Consistent Coding Style

Use [black](https://github.com/ambv/black) to make sure the code follows the style.

Use [flake8](https://pypi.org/project/flake8/) for linting.

## Setting Up Development Environment

We recommend using [uv](https://docs.astral.sh/uv/) for dependency management and virtual environment creation:

1. Install [uv](https://docs.astral.sh/uv/): Follow the [installation guide](https://docs.astral.sh/uv/#getting-started)
2. Create a virtual environment: `uv venv`
3. Activate the virtual environment: `source .venv/bin/activate` (on Windows: `.venv\Scripts\activate`)
4. Install dependencies: `uv pip install -r requirements-test.txt`
5. (Optional) Install the package in editable mode: `uv pip install -e .`

## Install pre-commit checks

To automatically run linting and formatting checks before each commit:

1. Install [pre-commit](https://pre-commit.com/): `uv pip install pre-commit` (it is part of `requirements-dev.txt` dependencies)
2. Install the git hooks: `pre-commit install`
3. (Optional) Run against all files: `pre-commit run --all-files`

The pre-commit hooks will now run automatically on each commit.

## Running Tests

To run the test suite with verbose output, showing detailed information about each test and generate coverage report:

```bash
PYTHONPATH=. pytest -vv --cov
```

## Bumping Version

Use [bump2version](https://pypi.org/project/bump2version/) bump the version:

1. Install bump2version: `uv pip install bump2version` (it is part of `requirements-dev.txt` dependencies)
2. Bump the version: `bumpversion patch` or `bumpversion minor` or `bumpversion major`
3. This will automatically update version numbers in configured files and create a commit with a tag

## Publishing Version

To publish a new version:

1. Push tags to the repository: `git push --follow-tags`
2. Create a release: `gh release create "$(git tag --list 'v*' --sort=-v:refname | head -n 1)" --title "$(git tag --list 'v*' --sort=-v:refname | head -n 1)" --generate-notes --verify-tag`

Or use the following script:

```shell
git push --follow-tags
tag="$(git tag --list 'v*' --sort=-v:refname | head -n 1)" && gh release create "$tag" --title "$tag" --generate-notes --verify-tag
```

## License

By contributing, you agree that your contributions will be licensed under its MIT License.
