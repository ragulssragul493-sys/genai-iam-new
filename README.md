# GenAI Identity & Access Management (IAM)

A beginner-friendly Flask + SQLite project for managing access to Generative AI platforms.

## Features
- Login with hashed passwords
- Admin and user roles
- AI platform catalog
- User access requests
- Admin approve/reject workflow
- Enable/disable users
- Audit log
- Responsive Bootstrap UI

## Run locally

### Windows
```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000

### Demo accounts
- Admin: admin@example.com / admin123
- User: user@example.com / user123

## Security notes
This is an academic/demo project. For production, add HTTPS, CSRF protection, secure environment-based secrets, MFA/SSO, rate limiting, stronger session settings, database migrations, granular RBAC/ABAC policies, API-key vaulting, and centralized audit monitoring.
