# Security Documentation

## Incident Response Plan

### If Admin Account is Compromised

1. Change admin password immediately
2. Check admin logs for unauthorized actions
3. Review all recent project changes
4. Rotate SECRET_KEY in .env
5. Notify hosting provider (Heroku)

### If Database is Breached

1. Take site offline (maintenance mode)
2. Backup current database
3. Assess what data was accessed
4. Restore from clean backup
5. Update all passwords and keys
6. Review security logs

### If Site is Defaced

1. Take screenshots for evidence
2. Restore from Git backup
3. Check for backdoors in code
4. Scan for malware
5. Review server access logs

### Emergency Contacts

- Developer: [Your email]
- Hosting: support@heroku.com
- Database: [Database provider]

---

## Backup Strategy

- Automated daily backups using Heroku PG Backups
- Manual backup command: `heroku pg:backups:capture`
- Download backup: `heroku pg:backups:download`
- Store backups securely and test restores quarterly

---

## Recovery Procedures

### Restore from Backup

1. Access Heroku dashboard
2. Go to Datastore → Backups
3. Click "Restore" on latest clean backup
4. Test site functionality
5. Verify data integrity

### Redeploy Clean Code

1. Git checkout last known good commit
2. Push to Heroku: `git push heroku main`
3. Run migrations: `heroku run python manage.py migrate`
4. Collect static files: `heroku run python manage.py collectstatic`
5. Test all functionality

### Time Objectives

- Recovery Time: 4 hours maximum
- Data Loss: 24 hours maximum (daily backups)

---

## Admin Panel Access

- Admin panel is now accessible at a random URL (see `projects/urls.py` for current path)
- Two-factor authentication (2FA) is enabled with trusted device support (remembers device for 30 days)

---

## Security Logging

- All security events are logged to `security.log` in the project root
- Includes failed logins, admin actions, file uploads, and API requests

---

## File Upload Validation

- Only image files with extensions `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp` are allowed
- Maximum file size: 10MB

---

## Contact Form

- Rate limited to 5 submissions per hour per IP
- Recipient email is set via environment variable (`EMAIL_HOST_USER`)

---

## Monitoring & Error Tracking

- Recommended: Integrate Sentry or similar service for error and security event monitoring

---

## Dependency Management

- Lock all dependencies in `requirements.txt` using `pip freeze`
- Run `safety check` regularly for vulnerabilities

---

## Review & Update

- Review this documentation every 6 months or after major changes
- Update emergency contacts and procedures as needed
