# Configuration Guide for python-toon

This file contains sensitive configuration information for publishing the package to PyPI.

**IMPORTANT: This file is gitignored and should NEVER be committed to the repository.**

## GitHub Actions Setup for PyPI Publishing

The python-toon repository uses GitHub Actions with trusted publishing (OIDC) for secure PyPI deployments.

### Step 1: Configure Trusted Publishing on PyPI

1. Go to https://pypi.org/manage/account/publishing/
2. Click "Add a new pending publisher"
3. Fill in the following information:
   - **PyPI Project Name**: `python-toon`
   - **Owner**: `xaviviro` (your GitHub username)
   - **Repository name**: `python-toon`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`
4. Click "Add"

### Step 2: Configure Trusted Publishing on TestPyPI (Optional but Recommended)

1. Go to https://test.pypi.org/manage/account/publishing/
2. Click "Add a new pending publisher"
3. Fill in the following information:
   - **PyPI Project Name**: `python-toon`
   - **Owner**: `xaviviro`
   - **Repository name**: `python-toon`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `testpypi`
4. Click "Add"

### Step 3: Create GitHub Environments

1. Go to your repository settings: `https://github.com/xaviviro/python-toon/settings/environments`
2. Click "New environment"
3. Create two environments:
   - **pypi** (for production releases)
   - **testpypi** (for testing)
4. For the `pypi` environment, optionally add:
   - Protection rules (require approval before deployment)
   - Deployment branches (limit to `main` branch only)

### Step 4: No Secrets Required!

With trusted publishing (OIDC), you **DO NOT** need to create any API tokens or secrets in GitHub. The workflow uses OpenID Connect to authenticate directly with PyPI.

## Publishing Workflow

### Automatic Publishing (Recommended)

**To PyPI (Production):**
1. Create a new release on GitHub with a version tag (e.g., `v0.1.0`)
2. GitHub Actions automatically builds and publishes to PyPI

**To TestPyPI (Testing):**
1. Go to Actions tab: `https://github.com/xaviviro/python-toon/actions`
2. Select the "Publish to PyPI" workflow
3. Click "Run workflow"
4. Choose the branch and click "Run workflow"
5. This will publish to TestPyPI for testing

### Manual Publishing (Alternative)

If you prefer to publish manually without GitHub Actions:

1. Install build tools:
   ```bash
   pip install build twine
   ```

2. Build the package:
   ```bash
   python -m build
   ```

3. Upload to TestPyPI (for testing):
   ```bash
   twine upload --repository testpypi dist/*
   ```
   - Username: `__token__`
   - Password: Your TestPyPI API token

4. Upload to PyPI (for production):
   ```bash
   twine upload dist/*
   ```
   - Username: `__token__`
   - Password: Your PyPI API token

### Creating API Tokens (Only for Manual Publishing)

If you choose manual publishing, you'll need API tokens:

**For PyPI:**
1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Give it a name (e.g., "python-toon-upload")
4. Set scope to "Project: python-toon" (after first upload)
5. Copy the token (starts with `pypi-`)
6. Store it securely (you won't see it again!)

**For TestPyPI:**
1. Go to https://test.pypi.org/manage/account/token/
2. Follow same steps as above

## Version Management

Version numbers are managed in two places:
1. `pyproject.toml` - Line 7: `version = "0.1.0"`
2. `src/toon/__init__.py` - Line 11: `__version__ = "0.1.0"`

**Remember to update both files before creating a new release!**

## Troubleshooting

### "Project not found" error on PyPI
- Make sure you've completed Step 1 (Trusted Publishing configuration)
- The project name must match exactly: `python-toon`
- Create the pending publisher BEFORE attempting the first publish

### "Environment protection rules" error
- Check your environment settings in GitHub
- Make sure you have proper permissions to deploy
- For protected environments, you may need approval from a repository admin

### "OIDC token verification failed"
- Verify the workflow name is exactly `publish.yml`
- Verify the environment name matches (`pypi` or `testpypi`)
- Check that the GitHub username/org matches

## Security Notes

- ✅ **DO**: Use trusted publishing (OIDC) for automated deployments
- ✅ **DO**: Protect the `pypi` environment with deployment protection rules
- ✅ **DO**: Limit `pypi` environment to `main` branch only
- ❌ **DON'T**: Commit API tokens to the repository
- ❌ **DON'T**: Share your API tokens with anyone
- ❌ **DON'T**: Use the same token for multiple projects

## Resources

- [PyPI Trusted Publishing Guide](https://docs.pypi.org/trusted-publishers/)
- [GitHub Actions Publishing Guide](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [Python Packaging User Guide](https://packaging.python.org/)
