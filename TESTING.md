# Local verification — 29 October 2026

The project runs at `http://127.0.0.1:8000/` using the existing virtual environment.

## Run the project

```powershell
.\venv\Scripts\python.exe manage.py migrate --noinput
.\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

## Run the checks

```powershell
.\venv\Scripts\python.exe manage.py test --noinput
npm run test:e2e:chromium
```

For the fast browser regression check, run `npm run test:e2e:smoke`. To run the
backend suite and browser smoke check together, run `npm run test:unit` followed
by `npm run test:e2e:smoke`.

Playwright starts an isolated server on port 8001 with its own SQLite database in `test-runtime/`, migrates it, and prepares deterministic E2E accounts. The browser suite does not reset or write to the development database on port 8000. Optional `E2E_USERNAME`, `E2E_EDITOR_USERNAME`, `E2E_ADMIN_USERNAME`, and `E2E_PASSWORD` environment variables select other test accounts. `BASE_URL` changes the server URL.

## Verified workflows

- Journalist, Editor, and Admin login, re-login with an existing session, invalid credentials, logout, and protected-page redirects.
- Session cookie persistence, access-token renewal, rejection of revoked refresh tokens and disabled accounts, and server-side MFA verification. A separate browser contract test checks the MFA challenge form.
- Journalist draft creation without an image or location, field validation, tags, editing, article details containing quotes, submission, rejection feedback, and resubmission.
- Editor rejection with a reason, approval, publishing, and public availability after publication.
- Admin article editing, user listing across pages, moving a story to trash, and loss of public access after trashing. Backend tests cover user deletion permissions and prevention of self-deletion.
- Desktop, tablet, mobile, and narrow mobile layouts; additional 900px and 1100px header checks; public feed, dialogs, support chat, and shared workspace tools.
- Translation comparison, Hindi RSS and sitemap publishing, unread notification badges, reader digest history, and workspace-scoped quotas.

The workflow tests create uniquely named QA stories and clean up only those stories. Negative-login tests use unique nonexistent usernames so repeated runs do not lock the shared test accounts.

## Fixes included

- CSRF headers for browser authentication and dashboard mutations; one logout handler that ends the server session before clearing local state.
- Keep-signed-in preference, authenticator/backup-code input, and access renewal without extending the original refresh-token lifetime.
- Working article form steps, consistent title limits, correct email/category fields, optional image/location handling, saved tags, and author-scoped article counts.
- Workflow API integration for editorial actions, complete paginated article lists, search, safe text rendering, and working Editor/Admin article editing.
- Correct Admin user-list and trash endpoints, role-based user-management permissions, and valid empty HTTP 204 deletion responses.
- Intermediate-width header wrapping and usable form/dialog controls.
- Offline caching restricted to public assets and the homepage; private workspace and API responses are excluded.
- Local dashboard assets are used for browser tests, so editorial workflows do not depend on a public CDN being reachable.

This is local functional and regression testing. Live SMTP delivery, external payments, SSO providers, web push, and production deployment were not exercised. The local email backend prints messages to the development log.
