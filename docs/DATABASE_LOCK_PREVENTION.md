# Database Lock Prevention Guide

## Problem

SQLite databases can become locked when:

- Multiple Django server processes run simultaneously
- Large file uploads (photos/videos) cause long-running transactions
- Concurrent write operations attempt to access the database

## Solutions Implemented

### 1. SQLite Timeout Configuration ✅

**Location:** `projects/settings.py`

```python
if 'sqlite' in DATABASES['default']['ENGINE']:
    DATABASES['default']['OPTIONS'] = {
        'timeout': 20,  # Wait up to 20 seconds for database lock
        'check_same_thread': False,  # Allow multi-threaded access
    }
```

**What it does:** Increases the time Django waits for a locked database before throwing an error.

### 2. Increased Upload Limits ✅

**Location:** `projects/settings.py`

```python
DATA_UPLOAD_MAX_MEMORY_SIZE = 104857600  # 100MB (from default 2.5MB)
FILE_UPLOAD_MAX_MEMORY_SIZE = 104857600  # 100MB
DATA_UPLOAD_MAX_NUMBER_FILES = 100  # Allow up to 100 files per request
```

**What it does:** Allows large media uploads without Django rejecting them prematurely.

### 3. Atomic Transactions ✅

**Location:** `projects/admin.py`

```python
@transaction.atomic
def save_model(self, request, obj, form, change):
    """Wrap save in atomic transaction to prevent partial saves on database locks."""
    super().save_model(request, obj, form, change)

@transaction.atomic
def save_formset(self, request, form, formset, change):
    """Wrap formset save in atomic transaction to prevent partial saves."""
    super().save_formset(request, form, formset, change)
```

**What it does:** Ensures all-or-nothing saves - if one part fails, everything rolls back (no partial data).

## Best Practices

### ✅ DO:

1. **Only run ONE Django server at a time**

   ```powershell
   # Check for running servers
   Get-Process | Where-Object {$_.ProcessName -like "*python*"}

   # Stop all Python processes if needed
   Get-Process | Where-Object {$_.ProcessName -like "*python*"} | Stop-Process -Force
   ```

2. **Upload media in batches**

   - Instead of 20+ files at once, try 5-10 at a time
   - This reduces transaction time and database lock risk

3. **Check for stale journal files**

   ```powershell
   # If you see database lock errors, check for this file:
   Test-Path "db.sqlite3-journal"

   # If it exists, stop all servers and delete it:
   Remove-Item "db.sqlite3-journal" -Force
   ```

4. **Stop servers properly**
   - Use `Ctrl+C` in the terminal
   - Don't just close the terminal window

### ❌ DON'T:

1. **Don't run multiple servers** (npm run dev multiple times)
2. **Don't close terminals without stopping the server**
3. **Don't upload 50+ files in a single form submission**
4. **Don't ignore "database is locked" warnings** - investigate immediately

## Recovery Steps

If you encounter a database lock error:

1. **Stop all Django processes:**

   ```powershell
   Get-Process | Where-Object {$_.ProcessName -like "*python*"} | Stop-Process -Force
   ```

2. **Remove stale journal file (if exists):**

   ```powershell
   Remove-Item "db.sqlite3-journal" -Force
   ```

3. **Restart the server (once):**

   ```powershell
   npm run dev
   ```

4. **Try your operation again**

## Long-term Solutions

### Consider PostgreSQL for Production

SQLite is great for development but has limitations:

- ❌ Poor concurrent write performance
- ❌ No true multi-user support
- ❌ File locks can cause issues

PostgreSQL benefits:

- ✅ Excellent concurrent write handling
- ✅ True multi-user database
- ✅ Better for large file metadata storage
- ✅ Already configured in your Heroku deployment

### Migration command (when ready):

```bash
# Backup current data
python manage.py dumpdata > backup.json

# Update DATABASE_URL in .env to PostgreSQL
# DATABASE_URL=postgres://user:pass@localhost/dbname

# Run migrations
python manage.py migrate

# Restore data
python manage.py loaddata backup.json
```

## Monitoring

Watch for these warning signs:

- Multiple Python processes in Task Manager
- `db.sqlite3-journal` file persists after server restart
- Slow response times on admin uploads
- Partial data saves (project created but no photos)

## Current Status

✅ SQLite timeout increased to 20 seconds  
✅ Upload limits increased to 100MB  
✅ Atomic transactions implemented  
✅ File upload limits expanded  
⚠️ Still using SQLite (consider PostgreSQL for production)

---

**Last Updated:** January 2, 2026  
**Related Docs:** [SECURITY_DOCUMENTATION.md](SECURITY_DOCUMENTATION.md)
