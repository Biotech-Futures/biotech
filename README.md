# Contribution Workflow

To keep our collaboration structured and consistent, please follow these guidelines:

1. **Branching**
   - Each workflow (Workstream 1, 2, 3) should have **one dedicated branch**.  

2. **Development**
   - All work for that workflow should be committed to its branch.
   - Keep commits concise and descriptive.

3. **Pull Requests**
   - When a feature branch is finished, merge in with the dedicated `Workstream` branch by creating a **feature branch**.
   - Ensure your branch is up to date with `main` before creating the PR, by merging `main` with the dedicated `Workstream` branch. Verify E2E functionality.
   - When ready to merge changes, create a **pull request into `main`**.  
   - Request reviews from at least one teammate before merging.

> ❗
>
> This flow ensures that we are constantly pulling from and merging `main` into our `Workstream` branches, avoiding our branches being both behind and ahead of `main`.

5. **Main Branch**
   - The `main` branch should always remain **stable** and **deployment-ready**.
   - Direct commits to `main` are **not allowed**.
  
5. **.gitignore**
   - Add rules to exclude compiled object files (e.g., `*.o`, `*.obj`) so they are not tracked in the repo.  
   - Add rules to exclude poll-related files or directories (e.g., `poll/` or `*.poll`).  
   - Ensure the `.gitignore` is committed so everyone follows the same rules.
