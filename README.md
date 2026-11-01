# Folio Finance Auditor — Flask + Firebase + Render

Live ledger for a class fund (and any other funds) with real-time totals, audit flags,
Excel import/export, and a file auditor. Only you can sign in.

## 1. Firebase (database)
1. Go to https://console.firebase.google.com -> Add project.
2. Build -> Firestore Database -> Create database -> Production mode -> pick a region.
3. Project settings (gear) -> Service accounts -> Generate new private key.
   A .json file downloads. KEEP IT SECRET - never upload it to GitHub.

## 2. GitHub
1. Create a new **private** repository.
2. Upload every file in this folder (app.py, storage.py, templates/, requirements.txt,
   public/, render.yaml, .gitignore, README.md). Do NOT upload the Firebase .json key.

## 3. Render
1. https://dashboard.render.com -> New -> Blueprint -> pick your repo (uses render.yaml).
   (Or New -> Web Service: Build `pip install -r requirements.txt`, Start `gunicorn app:app --workers 1 --threads 4`.)
2. Fill in the environment variables:
   - APP_USERNAME : your login name
   - APP_PASSWORD : a strong password
   - FIREBASE_CREDENTIALS : open the Firebase .json key in Notepad, copy EVERYTHING, paste it here
   - SECRET_KEY : auto-generated (if not, type any long random text)
3. Deploy. Open your .onrender.com link and sign in.

Free Render plans sleep after ~15 min idle; the first visit then takes ~30-60 s.

## 3b. Vercel (alternative to Render)
1. Push this folder to GitHub (never the Firebase .json key).
2. https://vercel.com/new -> import the repo. Framework is detected as Flask; no build command needed.
3. Settings -> Environment Variables (all required): APP_USERNAME, APP_PASSWORD, SECRET_KEY (long random text),
   FIREBASE_CREDENTIALS (paste the whole .json key). Deploy.
Notes: static files live in public/static (Vercel serves them from its CDN). Uploads are limited to ~4 MB on Vercel.
The app refuses to start on Vercel if SECRET_KEY/APP_USERNAME/APP_PASSWORD are missing. Without Firebase,
data is lost between requests, so FIREBASE_CREDENTIALS is effectively required there.

## Run on your computer
    python -m pip install --upgrade pip
    pip install --only-binary=:all: -r requirements.txt
    python app.py        # http://localhost:5000  (login admin / admin)
Without FIREBASE_CREDENTIALS it saves to local_db.json instead of Firebase.

## Redesigned interface (v5)
Charcoal sidebar, light dashboard, real-time balance, monthly cash-flow chart,
expense chart, editable ledger, searchable transactions, multiple funds and owner login.
This folder uses Python, Flask, Firebase Admin, Jinja HTML templates, plain CSS and
plain browser JavaScript. No Vite, React, Node, npm, or frontend build command.
Browser JavaScript provides live calculations; Flask handles login, storage and spreadsheets.
Charts are drawn locally with the browser canvas; no external chart package is needed.

## Localhost (Windows Command Prompt)
1. Extract this ZIP and open the `finaudit` folder, then open Command Prompt there.
2. Run:
```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install --only-binary=:all: -r requirements.txt
```
3. Set `APP_USERNAME` and `APP_PASSWORD` to your chosen values using the Windows
   `set VARIABLE=value` command in the same window. Do not commit real credentials.
4. Run `python app.py`, then open http://localhost:5000.
The existing admin/admin default is for local testing only. Never deploy with it.

## Upgrade from v4
Replace app.py, templates/, and add static/. Keep your existing local_db.json
if testing locally. Keep your existing Render environment variables and Firebase
credentials; this update does not change the Firestore fund format.
Push the updated source to GitHub and let Render redeploy.

## Privacy and storage notes
There is no public registration. Only the configured owner credentials can sign in.
The login page is public, but ledger pages, APIs and spreadsheet downloads require
an owner session. Use HTTPS on Render and keep all credentials out of GitHub.
The default local storage file is only for development: Render's temporary disk
is not durable. Set FIREBASE_CREDENTIALS before storing real online fund records.
The current storage format uses one Firestore document per fund, which is subject
to Firestore's 1 MiB document limit; keep funds small and export backups regularly.
Audit flags indicate entries to review, not proof of fraud. No sample balances are
inserted. All dashboard totals and chart data come from your actual transactions.
Firebase credentials were not available for hosted integration testing; local
login, fund saving and spreadsheet workflows were verified separately.
