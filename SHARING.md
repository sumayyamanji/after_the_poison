# Sending the archive or putting the code on GitHub

## Easiest: ZIP through Google Drive

Upload `After-the-Poison-reproducibility-full.zip` to Google Drive and share the file with your supervisor/examiner as appropriate. They can download and extract it, read the README, inspect the supplied figures and run the scripts locally. Upload the ZIP as a single file, rather than thousands of raw records. Google Drive is file storage here; it does not execute the Python commands.

The full ZIP also reattaches the previously delivered dissertation PDF and Overleaf ZIP under `writing/`. Those writing files are unchanged by this packaging task.

## GitHub: readable code, configurations and figure data

Use `After-the-Poison-GitHub-ready.zip`, or extract the full archive and let its `.gitignore` exclude `raw_archives/`, `writing/`, generated `outputs/` and environments. Source, configs, plotting inputs, saved reports and figures remain tracked. This makes the evidence accessible without committing thousands of generated raw files.

### GitHub Desktop route

1. Extract the GitHub-ready ZIP.
2. In GitHub Desktop, add the extracted project folder. If prompted that it is not a repository, create a repository in that same folder.
3. Review the changes, create the initial commit, then choose **Publish repository**.
4. Start private if the dissertation has not yet been submitted or you do not yet want a public release.
5. Add the full ZIP as a GitHub Release attachment later, or put a Google Drive download link in the README. The code repository then points to a fixed data archive.

### Git command-line route

Create an empty repository on GitHub without adding a README, licence or .gitignore there (the local project already has its own README and .gitignore). From the extracted project folder:

```bash
git init -b main
git add .
git status
git commit -m "Add dissertation reproducibility code and reference results"
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

Replace `YOUR_REPOSITORY_URL` with the URL GitHub gives you. This requires Git and GitHub authentication. Review `git status` before committing. No repository has been created or published by this package.

GitHub's browser uploader is limited to 25 MiB per file and 100 files per upload. The full evidence ZIP is better as a Release attachment or Drive download, while GitHub Desktop/Git handles the project folder. This archive does not require Git LFS for the proposed layout.

Before a public release, add your preferred author/repository metadata and choose a licence if you want to grant reuse rights. No licence or author identity has been invented here.

## Official instructions checked for this guide

- https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github
- https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository
- https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github

These describe uploading/versioning files; they do not validate the research results.
