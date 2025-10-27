# Security Routine Checklist for Django Portfolio Website

This checklist summarizes all security controls implemented and provides routine tasks you can automate or regularly perform to maintain a secure development and production environment.

---

## 1. Admin Page Security

- **Custom Admin URL:** Your admin page is now accessible at a random, hard-to-guess URL (not `/admin/`).
  - **Routine:** Periodically change the admin URL to a new random path. Update bookmarks and inform trusted users only.
  - **Automate:** Use a script to generate a new admin URL and update `projects/urls.py`.

## 2. Two-Factor Authentication (2FA)

- **2FA Enabled:** Admin login requires a second factor (TOTP or trusted device).
  - **Routine:** Test 2FA login monthly. Ensure trusted device cookies are working for development convenience.
  - **Automate:** Set reminders to review 2FA logs and trusted device settings.

## 3. Dependency Management

- **Exact Versions Locked:** All Python packages are pinned in `requirements.txt`.
  - **Routine:** Run `python -m safety scan -r requirements.txt` monthly to check for vulnerabilities.
  - **Automate:** Add a CI/CD pipeline step to run safety checks on every deployment.

## 4. Monitoring & Error Tracking

- **Sentry Integrated:** Errors and security events are sent to Sentry.
  - **Routine:** Review Sentry dashboard weekly for new issues or suspicious activity.
  - **Automate:** Set up Sentry alerts for critical errors and security events.

## 5. Backup & Recovery

- **Local Database & Media Backup:** Procedures tested for backup and restore.
  - **Routine:** Backup `db.sqlite3` and local `media` folder before major changes or monthly.
  - **Automate:** Use scheduled scripts to copy these files to a secure location.
- **Cloudinary Media:** Most media is stored in Cloudinary.
  - **Routine:** Ensure Cloudinary credentials are backed up. Periodically export assets if needed.

## 6. Security Headers & CORS

- **Headers & CORS Configured:** Security headers and CORS are set for production.
  - **Routine:** Review `settings.py` after major updates or package changes.
  - **Automate:** Add a test to check for correct headers in HTTP responses.

## 7. Logging

- **Security Event Logging:** Key events are logged to `security.log`.
  - **Routine:** Review logs monthly for suspicious activity.
  - **Automate:** Set up log rotation and alerting for critical events.

## 8. File Upload Validation

- **Validation Implemented:** File uploads are checked for type and size.
  - **Routine:** Test file upload validation after updates to models or forms.
  - **Automate:** Add automated tests for file upload endpoints.

## 9. Incident Response & Documentation

- **Incident Response Plan:** Documented in `docs/SECURITY_DOCUMENTATION.md`.
  - **Routine:** Review and update documentation annually or after incidents.
  - **Automate:** Set calendar reminders for documentation review.

---

## What is MCP?

- **Model Context Protocol (MCP):** Used for advanced code analysis and automation in VS Code. It helps automate code reviews, dependency checks, and security scans. You don't need to interact with MCP directly; it works behind the scenes to keep your codebase secure and up-to-date.

---

## Recommended Automation Scripts

- Change admin URL script
- Automated backup script
- Safety vulnerability scan script
- Log review and rotation script
- Sentry alert configuration

---

## Final Notes

- All major security controls are now in place.
- Routine checks and automation will help maintain security as you develop.
- If you need help with any automation, ask for a script and it can be generated for you.

---

**Keep this checklist in your docs folder and refer to it regularly!**
