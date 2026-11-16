# One-time setup for running the site locally on a new Windows machine.
# Safe to run again: it skips anything that is already done.
#
# Run from the repo root in a VS Code terminal:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_dev.ps1

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

function Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }
function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}

# 1. System tools ------------------------------------------------------------
Step '1. Installing tools with winget (skips anything already installed)'
if (-not (Have 'winget')) { throw 'winget is missing. Install "App Installer" from the Microsoft Store, then run this again.' }

Refresh-Path
$hasPy312 = $false
if (Have 'py') { & py -3.12 --version *> $null; $hasPy312 = ($LASTEXITCODE -eq 0) }

# Skip a tool if its command already works, however it was installed
$tools = @(
    @{ Id = 'Python.Python.3.12'; Name = 'Python 3.12'; Present = $hasPy312 },
    @{ Id = 'OpenJS.NodeJS.LTS';  Name = 'Node.js';     Present = (Have 'node') },
    @{ Id = 'Git.Git';            Name = 'Git';         Present = (Have 'git') },
    @{ Id = 'Heroku.HerokuCLI';   Name = 'Heroku CLI';  Present = (Have 'heroku') }
)
foreach ($t in $tools) {
    if ($t.Present) { Write-Host "   $($t.Name): already installed"; continue }
    winget list --id $t.Id --exact --accept-source-agreements | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Host "   $($t.Name): already installed"; continue }
    Write-Host "   $($t.Name): installing..."
    winget install --id $t.Id --exact --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { Write-Warning "$($t.Name) may not have installed (exit $LASTEXITCODE)." }
}
# The silent Heroku installer does not add itself to PATH
$herokuBin = 'C:\Program Files\heroku\bin'
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ((Test-Path $herokuBin) -and ($userPath -notlike "*$herokuBin*")) {
    [Environment]::SetEnvironmentVariable('Path', $userPath.TrimEnd(';') + ";$herokuBin", 'User')
}
Refresh-Path

# 2. Python virtual environment ---------------------------------------------
Step '2. Python virtual environment (.venv) and packages'
$py = $null
if (Have 'py') {
    $out = & py -3.12 -c "import sys; print(sys.executable)"
    if ($LASTEXITCODE -eq 0) { $py = "$out".Trim() }
}
if (-not $py) {
    foreach ($c in "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe", "$env:ProgramFiles\Python312\python.exe") {
        if (Test-Path $c) { $py = $c; break }
    }
}
if (-not $py) { throw 'Python 3.12 not found. Close and reopen VS Code, then run this script again.' }
Write-Host "   Using $py"

if (-not (Test-Path '.venv\Scripts\python.exe')) { & $py -m venv .venv }
$vpy = (Resolve-Path '.venv\Scripts\python.exe').Path
& $vpy -m pip install --upgrade pip --quiet
& $vpy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'pip install failed (see the error above).' }

# 3. Node packages (Sass) ----------------------------------------------------
Step '3. Node packages (Sass compiler)'
if (-not (Have 'npm')) { throw 'npm not found. Close and reopen VS Code, then run this script again.' }
npm install
if ($LASTEXITCODE -ne 0) { throw 'npm install failed.' }

# 4. Local .env --------------------------------------------------------------
Step '4. Local .env file'
if (Test-Path '.env') {
    Write-Host '   .env already exists, leaving it alone'
} else {
    $key = (& $vpy -c "from django.core.management.utils import get_random_secret_key as k; print(k())").Trim()
    $lines = @(
        '# Local development settings. Never commit this file (it is in .gitignore).',
        "SECRET_KEY='$key'",
        'DEBUG=True',
        '',
        '# Cloudinary (media uploads). Copy from the Cloudinary dashboard,',
        '# or run: heroku config -a am04',
        'CLOUDINARY_CLOUD_NAME=',
        'CLOUDINARY_API_KEY=',
        'CLOUDINARY_API_SECRET=',
        '',
        '# Optional: contact form email (Gmail app password)',
        'EMAIL_HOST_USER=',
        'EMAIL_HOST_PASSWORD='
    )
    # UTF-8 without BOM, so python-dotenv reads the first key correctly
    [IO.File]::WriteAllText((Join-Path (Get-Location) '.env'), ($lines -join "`n") + "`n", (New-Object Text.UTF8Encoding $false))
    Write-Host '   Created .env with a new local SECRET_KEY and DEBUG=True'
    Write-Warning 'Fill in the Cloudinary values in .env so images and uploads work.'
}

# 5. Build CSS and set up the local database ---------------------------------
Step '5. Compile SCSS and set up the local SQLite database'
npm run sass
& $vpy manage.py migrate
if ($LASTEXITCODE -ne 0) {
    Write-Warning 'migrate failed. Most likely the Cloudinary values in .env are empty; fill them in and run this script again.'
} else {
    & $vpy manage.py check
}

# 6. VS Code extensions ------------------------------------------------------
Step '6. VS Code extensions'
if (Have 'code') {
    foreach ($ext in 'ms-python.python', 'ms-python.vscode-pylance', 'batisteo.vscode-django') {
        code --install-extension $ext --force | Out-Null
        Write-Host "   $ext"
    }
} else {
    Write-Host '   "code" command not on PATH; install the recommended extensions from the Extensions panel instead.'
}

Step 'Done'
Write-Host @'
Next:
  1. Close and reopen VS Code so it picks up the new PATH and the .venv interpreter.
  2. git config --global user.name "Adhenz Miranda"
     git config --global user.email "<your GitHub email>"
  3. Start the site:  npm run dev   (then open http://127.0.0.1:8000)
     Admin locally:   http://127.0.0.1:8000/admin-dev/
     First time:      .venv\Scripts\python manage.py createsuperuser
'@
