# GitHub Actions workflows

`ci.yml` runs Ruff, unittest, and a dependency audit. After CI passes on main, the deploy job builds the container and deploys it to Cloud Run.
