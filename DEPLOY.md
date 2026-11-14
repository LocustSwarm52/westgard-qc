# Publishing and deploying

## 1. Put it on GitHub

This project has folders inside folders, so the easiest upload is GitHub Desktop (free, no command line):

1. Install GitHub Desktop and sign in.
2. **File → Add local repository**, choose the `westgard-qc` folder, and click **create a repository** when it asks.
3. Click **Publish repository**, untick "Keep this code private", and publish.

The hidden `.github` folder holds the automated tests. GitHub Desktop includes it; a drag-and-drop upload on the website may skip it.

After publishing, open the **Actions** tab. Each push shows a run, and a green check means all tests passed.

## 2. Put it online

This app has a backend and a database, so GitHub Pages can't host it. Use a host that runs Docker, such as Render:

1. Sign in at render.com with your GitHub account.
2. **New → PostgreSQL**: create a database and copy its **Internal Database URL**.
3. **New → Web Service**: pick the `westgard-qc` repository. Render detects the `Dockerfile`.
4. Under **Environment**, add:
   - `DATABASE_URL`: the database URL from step 2
   - `SECRET_KEY`: a long random string (mash the keyboard for 40+ characters)
5. Click **Create Web Service**. The first build takes a few minutes, and demo data loads on first start.

Check Render's current pricing before you start: free plans have limits, and a free database may expire after a set time.

When it's live, paste the link into the README's **Live demo** line and into your resume.
