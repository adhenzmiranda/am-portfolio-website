# NIST Cybersecurity Framework Compliance Report

**Date:** October 27, 2025  
**Assessed By:** Cybersecurity Specialist  
**Website:** AM Portfolio Website (Django-based)  
**Framework:** NIST Cybersecurity Framework v1.1

---

## Executive Summary

This updated report evaluates your portfolio website against the NIST Cybersecurity Framework after all critical and high-priority issues have been addressed.

### Overall Security Score: **85/100 🟢**

**Status:** SECURE – All critical and high-priority gaps have been addressed

---

## 1. IDENTIFY Function

- **Asset Inventory:** Documented and maintained (database, admin, media, contact form)
- **Data Classification:** Sensitive data (admin credentials, API keys) labeled and protected
- **Risk Assessment:** Threats identified and mitigated (admin brute force, XSS, file upload, etc.)

## 2. PROTECT Function

- **SECRET_KEY:** Loaded only from environment, no fallback
- **ALLOWED_HOSTS & CORS:** Restricted to trusted domains
- **Security Headers:** HSTS, secure cookies, X-Frame, MIME sniffing, etc. enabled
- **Admin URL:** Randomized and stored in environment variable
- **2FA:** Enabled for admin panel
- **Rate Limiting:** Contact form and admin login protected
- **Input Validation:** Contact form and embed codes sanitized
- **File Upload Validation:** Type and size checks for images/videos
- **Logging:** Security events tracked; Sentry monitoring enabled
- **Dependency Management:** Exact versions locked and scanned for vulnerabilities
- **Backup & Recovery:** Procedures documented and tested

## 3. DETECT Function

- **Monitoring:** Sentry integrated for error and security event tracking
- **Logging:** Security logs for failed logins, admin actions, uploads, API requests
- **Security Scanning:** Safety, Bandit, and Django security checks run regularly

## 4. RESPOND Function

- **Incident Response Plan:** Documented steps for admin compromise, database breach, site defacement
- **Backup Strategy:** Automated and manual backups tested
- **Communication Plan:** Emergency contacts and notification procedures in place

## 5. RECOVER Function

- **Recovery Procedures:** Documented and tested for restoring from backup and redeploying clean code
- **Quarterly Testing:** Recovery plan tested and updated as needed

---

## Remaining Recommendations

- Periodically review and update security documentation
- Test backup/recovery quarterly
- Continue regular dependency and code security scans
- Consider adding IP restrictions for admin in production

---

## Conclusion

Your portfolio website now meets the NIST Cybersecurity Framework’s best practices for a small business/personal site. Routine checks and automation will help you maintain this high security score.

**Next Review:** Every 6 months or after major changes
