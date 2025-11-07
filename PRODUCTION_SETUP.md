# Production Setup Guide

This guide will help you configure the BIOTech Futures application for production deployment on Azure.

**What you'll need:**
- Access to Azure Portal
- SendGrid account (for sending emails)
- About 30-45 minutes to complete setup

---

## CRITICAL SECURITY STEP - MUST DO BEFORE DEPLOYMENT

Your code currently has passwords and secret keys visible in the `backend/config/settings.py` file. **You MUST remove these before deploying to production!**

### Step 1: Remove Hardcoded Secrets from settings.py

Open the file: `backend/config/settings.py`

Find and change these specific lines:

**Line 26 - Change this:**
```python
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-f+qzkit-li1$e5$%^ce56qv@_oyq#m2k(g)f0$%ef32q%)z@5l")
```
**To this:**
```python
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
```

**Line 143 - Change this:**
```python
'NAME': os.getenv('DB_NAME', 'postgres'),
```
**To this:**
```python
'NAME': os.getenv('DB_NAME', ''),
```

**Line 144 - Change this:**
```python
'USER': os.getenv('DB_USER', 'biotech_admin'),
```
**To this:**
```python
'USER': os.getenv('DB_USER', ''),
```

**Line 145 - Change this:**
```python
'PASSWORD': os.getenv('DB_PASSWORD', 'fu7UR3$!'),
```
**To this:**
```python
'PASSWORD': os.getenv('DB_PASSWORD', ''),
```

**Line 146 - Change this:**
```python
'HOST': os.getenv('DB_HOST', 'btfpostgresdb.postgres.database.azure.com'),
```
**To this:**
```python
'HOST': os.getenv('DB_HOST', ''),
```

**Why do this?** If someone sees your code (like on GitHub), they won't see your passwords. Instead, the passwords will only be stored securely in Azure, where only you can access them.

---

## Understanding Environment Variables

Environment variables are like a secure locked box where you store passwords and secrets. Instead of writing your password directly in your code (where everyone can see it), you:

1. Put the password in the locked box (Azure environment variables)
2. Your code asks the locked box for the password when it needs it
3. Only people with access to Azure can see what's inside

**We've created a template file** called `.env.example` in the `backend/` folder that shows you ALL the variables you need to set up.

---

## Using the .env.example File

The `.env.example` file in `backend/.env.example` is your complete checklist of environment variables.

**How to use it:**

1. **Open the file**: Navigate to `backend/.env.example` in your project
2. **Review the list**: This file shows every setting you need to configure
3. **Use it as a reference**: As you set up environment variables in Azure, check off each one from this list
4. **For local development**: Copy this file to `.env` and fill in your actual values (see Local Development section below)

The file contains approximately 25-30 variables organized by category. Below we'll explain what each variable does and where to find the values.

---

## Complete Environment Variables Reference

### 1. Django Core Settings (Required)

| Variable | Description | Value to Use |
|----------|-------------|--------------|
| `DJANGO_SECRET_KEY` | A random secret password for Django security | Generate a new one (see instructions below) |
| `DJANGO_DEBUG` | Controls debug mode - MUST be False for production | `False` |
| `DJANGO_ALLOWED_HOSTS` | Your website addresses, comma-separated | `biotechfuturesappservice-hgdtg2bdh2bbbdck.australiasoutheast-01.azurewebsites.net` |

**How to generate DJANGO_SECRET_KEY:**

Option 1 - Use an online generator:
1. Go to https://djecrety.ir/
2. Click "Generate"
3. Copy the generated key

Option 2 - Generate it yourself:
```python
# Open Python terminal and run:
import secrets
print(secrets.token_urlsafe(50))
```

---

### 2. Database Configuration - Azure PostgreSQL (Required)

| Variable | Description | Current Value |
|----------|-------------|---------------|
| `DB_ENGINE` | Database type (don't change) | `django.db.backends.postgresql` |
| `DB_NAME` | Database name | `postgres` |
| `DB_USER` | Database username | `biotech_admin` |
| `DB_PASSWORD` | Database password | `fu7UR3$!` |
| `DB_HOST` | Database server address | `btfpostgresdb.postgres.database.azure.com` |
| `DB_PORT` | Database port | `5432` |
| `DB_SSL_MODE` | SSL mode (required for Azure) | `require` |
| `DB_CONNECT_TIMEOUT` | Connection timeout in seconds | `5` |
| `DB_CONN_MAX_AGE` | Connection pooling (optional) | `600` |

**Where to find these in Azure Portal:**
1. Log in to https://portal.azure.com
2. Search for "btfpostgresdb" in the top search bar
3. Click on your PostgreSQL server
4. Go to "Connection strings" in the left menu
5. You'll see the host, user, and database name there

---

### 3. Azure Blob Storage (Required for file uploads)

| Variable | Description | Current Value |
|----------|-------------|---------------|
| `AZURE_ACCOUNT_NAME` | Storage account name | `btfuturesblobstorage` |
| `AZURE_ACCOUNT_KEY` | Storage account access key | Find in Azure Portal (see below) |
| `AZURE_CONTAINER` | Container name for uploads | `media` |
| `CHAT_MAX_UPLOAD_MB` | Maximum file size in MB | `25` |

**How to find AZURE_ACCOUNT_KEY:**
1. In Azure Portal, search for "btfuturesblobstorage"
2. Click on your Storage Account
3. In the left menu, click "Access keys" (under Security + networking)
4. Click "Show" next to "key1"
5. Copy the entire key value

---

### 4. Email Configuration - SendGrid (Required for OTP emails)

| Variable | Description | Value |
|----------|-------------|-------|
| `EMAIL_BACKEND` | Email backend to use | `emailing.backends.DualEmailBackend` |
| `EMAIL_HOST` | SendGrid SMTP server | `smtp.sendgrid.net` |
| `EMAIL_PORT` | SMTP port | `587` |
| `EMAIL_USE_TLS` | Use TLS encryption | `True` |
| `EMAIL_USE_SSL` | Use SSL encryption | `False` |
| `EMAIL_HOST_USER` | SendGrid requires this literal value | `apikey` |
| `EMAIL_HOST_PASSWORD` | Your SendGrid API key | Get from SendGrid (see below) |
| `DEFAULT_FROM_EMAIL` | Email address shown to users | `noreply@biotechfutures.org` |
| `SERVER_EMAIL` | Email for server errors | `server@biotechfutures.org` |

**Complete SendGrid Setup Instructions:**

1. **Create SendGrid Account:**
   - Go to https://sendgrid.com
   - Click "Start for Free" and complete signup
   - Complete the registration form

2. **Create API Key:**
   - Log in to SendGrid dashboard
   - Click "Settings" in the left menu
   - Click "API Keys"
   - Click the blue "Create API Key" button
   - Name it: "BIOTech Production"
   - Select "Restricted Access"
   - Scroll to "Mail Send" and toggle it to "Full Access"
   - Click "Create & View"
   - **IMPORTANT**: Copy the API key immediately (you can't see it again!)
   - This is your `EMAIL_HOST_PASSWORD` value

3. **Verify Sender Email:**
   - In SendGrid, go to "Settings" → "Sender Authentication"
   - Click "Verify a Single Sender"
   - Fill in the form:
     - From Email: `noreply@biotechfutures.org`
     - From Name: `BIOTech Futures`
     - Reply To: Use the same email or your support email
     - Fill in required address fields
   - Click "Create"
   - Check your email inbox for verification link
   - Click the link to verify

---

### 5. CORS & Security Settings (Required)

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `CORS_ALLOWED_ORIGINS` | Frontend URLs allowed to access backend | `https://yourdomain.com,https://www.yourdomain.com` |
| `CORS_ALLOW_CREDENTIALS` | Allow cookies across origins | `True` |
| `SESSION_COOKIE_NAME` | Session cookie name | `sessionid` |
| `SESSION_COOKIE_AGE` | Session duration in seconds | `86400` (1 day) |
| `SESSION_COOKIE_HTTPONLY` | Prevent JavaScript access | `True` |
| `SESSION_COOKIE_SECURE` | Require HTTPS | `True` |
| `SESSION_COOKIE_SAMESITE` | Cookie policy | `Lax` |
| `SESSION_SAVE_EVERY_REQUEST` | Save on each request | `False` |
| `CSRF_COOKIE_HTTPONLY` | CSRF cookie security | `False` |
| `CSRF_COOKIE_SAMESITE` | CSRF cookie policy | `Lax` |
| `CSRF_COOKIE_SECURE` | Require HTTPS for CSRF | `True` |
| `CSRF_TRUSTED_ORIGINS` | Trusted domains for CSRF | Same as `CORS_ALLOWED_ORIGINS` |

**Important:** Replace `yourdomain.com` with your actual frontend website address!

---

### 6. Frontend URLs (Required)

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `FRONTEND_URL` | Your main frontend URL | `https://yourdomain.com` |
| `MAGIC_LINK_REDIRECT_URL` | Where users go after clicking login link | `https://yourdomain.com/#/auth/callback` |
| `LOGIN_REDIRECT_URL` | Alternative login redirect | `https://yourdomain.com/auth/callback` |

---

## Adding Environment Variables to Azure

### Method 1: Azure Portal (Recommended)

**Step-by-step instructions:**

1. **Log in to Azure Portal:**
   - Go to https://portal.azure.com
   - Sign in with your Azure credentials

2. **Navigate to App Service:**
   - In the search bar at the top, type: `biotechfuturesappservice`
   - Click on your App Service in the search results

3. **Open Configuration:**
   - In the left sidebar, scroll to "Settings"
   - Click "Configuration"
   - Click the "Application settings" tab

4. **Add each environment variable:**
   - Click "+ New application setting"
   - Enter the Name (e.g., `DJANGO_SECRET_KEY`)
   - Enter the Value (e.g., your generated secret key)
   - Click "OK"
   - Repeat for ALL variables listed above

5. **Save changes:**
   - Click "Save" at the top of the page
   - Click "Continue" to confirm
   - Wait for Azure to restart your app (30-60 seconds)

**Total variables to add:** Approximately 25-30 variables (use `.env.example` as your checklist!)

---

### Method 2: Azure CLI (Advanced)

If you're comfortable with command line:

```bash
az webapp config appsettings set \
  --name biotechfuturesappservice \
  --resource-group your-resource-group-name \
  --settings \
    DJANGO_SECRET_KEY="your-generated-key" \
    DJANGO_DEBUG="False" \
    DJANGO_ALLOWED_HOSTS="biotechfuturesappservice-hgdtg2bdh2bbbdck.australiasoutheast-01.azurewebsites.net" \
    DB_NAME="postgres" \
    DB_USER="biotech_admin" \
    DB_PASSWORD="fu7UR3$!" \
    DB_HOST="btfpostgresdb.postgres.database.azure.com" \
    DB_PORT="5432" \
    DB_SSL_MODE="require" \
    # ... add remaining variables from .env.example
```

---

## Local Development Setup (Optional)

If you want to test the application on your local computer:

### Creating a local .env file

**Using File Explorer:**
1. Open File Explorer and navigate to your project's `backend/` folder
2. Find the file named `.env.example`
3. Copy this file
4. Rename the copy to `.env` (remove the `.example` part)
5. Open `.env` in a text editor (Notepad works fine)
6. Replace all placeholder values with your actual credentials
7. Save the file

**Using Command Line:**
```bash
# Navigate to backend folder
cd backend

# Copy the example file
copy .env.example .env

# Edit with your values
notepad .env
```

**IMPORTANT:** Never commit the `.env` file to Git! The `.gitignore` file is already configured to ignore it, but double-check:

```bash
git check-ignore backend/.env
# Should output: backend/.env
```

---

## Testing Your Configuration

### Local Testing Commands

Run these commands from the `backend/` folder:

1. **Test Database Connection:**
   ```bash
   python manage.py check --database default
   ```
   Expected: "System check identified no issues"

2. **Test Email Configuration:**
   ```bash
   python test_smtp.py
   ```
   Expected: Email sends successfully

3. **Run Database Migrations:**
   ```bash
   python manage.py migrate
   ```
   Expected: All migrations applied

4. **Create Admin User:**
   ```bash
   python manage.py createsuperuser
   ```
   Follow prompts to create your admin account

5. **Start Development Server:**
   ```bash
   python manage.py runserver
   ```
   Expected: Server starts without errors

### Testing on Azure

1. **Check Azure Logs:**
   - In Azure Portal, go to your App Service
   - Click "Log stream" in the left menu
   - Watch for error messages

2. **Test Application URL:**
   - Visit: `https://biotechfuturesappservice-hgdtg2bdh2bbbdck.australiasoutheast-01.azurewebsites.net`
   - You should see your application (not an error page)

---

## Security Checklist

Before launching to production, verify ALL of these:

### Critical Security:
- [ ] All hardcoded secrets removed from `backend/config/settings.py`
- [ ] Generated a new `DJANGO_SECRET_KEY` (not using default)
- [ ] Set `DJANGO_DEBUG=False` in Azure
- [ ] Added all 25-30 environment variables to Azure App Service

### SendGrid:
- [ ] Created SendGrid account and API key
- [ ] Verified sender email in SendGrid
- [ ] Tested email sending works

### Database & Storage:
- [ ] Azure PostgreSQL connection tested
- [ ] Azure Blob Storage key configured
- [ ] Database firewall allows App Service IP

### Security Settings:
- [ ] `SESSION_COOKIE_SECURE=True` in Azure
- [ ] `CSRF_COOKIE_SECURE=True` in Azure
- [ ] CORS origins only include production URLs (no localhost)
- [ ] HTTPS/SSL enabled on your domain

### Git:
- [ ] `.env` file NOT committed to Git
- [ ] `.env` is in `.gitignore`
- [ ] No passwords visible in GitHub repository

---

## Troubleshooting Common Issues

### Error: "Connection timeout expired"

**Problem:** Can't connect to database

**Solutions:**
1. Verify all database environment variables are set correctly in Azure
2. Check database password is correct
3. In Azure Portal, go to PostgreSQL server → "Connection security"
4. Enable "Allow access to Azure services"
5. Add your App Service IP to firewall rules

---

### Error: Emails not sending

**Problem:** SendGrid isn't working

**Solutions:**
1. Verify `EMAIL_HOST_PASSWORD` contains your SendGrid API key
2. Check sender email is verified in SendGrid (check your inbox)
3. Log in to SendGrid → Activity → Check for errors
4. Ensure API key has "Mail Send" permissions

---

### Error: "DisallowedHost at /"

**Problem:** Django doesn't recognize your domain

**Solutions:**
- Check `DJANGO_ALLOWED_HOSTS` includes your full Azure URL
- Format: `biotechfuturesappservice-hgdtg2bdh2bbbdck.australiasoutheast-01.azurewebsites.net`
- Do NOT include `https://` at the start
- Separate multiple domains with commas (no spaces)

---

### Error: CORS errors in browser console

**Problem:** Frontend can't communicate with backend

**Solutions:**
1. Verify `CORS_ALLOWED_ORIGINS` includes your frontend URL
2. Use full URL with protocol: `https://yourdomain.com`
3. Check `CSRF_TRUSTED_ORIGINS` has same URLs
4. Separate multiple URLs with commas (no spaces)
5. Ensure both frontend and backend use HTTPS (or both HTTP for local dev)

---

### Error: "ImportError: No module named..."

**Problem:** Python packages not installed

**Solutions:**
1. In Azure Portal → App Service → Deployment Center
2. Check deployment completed successfully
3. Verify `requirements.txt` is in repository root
4. Try restarting the App Service
5. Check Application Logs for specific error

---

### Problem: Changes not appearing after deployment

**Solutions:**
1. In Azure Portal → App Service
2. Click "Restart" button at the top
3. Wait 1-2 minutes for restart
4. Clear browser cache (Ctrl+Shift+Delete)
5. Try in incognito/private browser window

---

## Additional Resources

### Official Documentation:
- **Django Deployment Checklist:** https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- **Azure App Service:** https://learn.microsoft.com/en-us/azure/app-service/
- **SendGrid Documentation:** https://docs.sendgrid.com/
- **Azure PostgreSQL:** https://learn.microsoft.com/en-us/azure/postgresql/

### Project Reference Files:
- **Environment variables template:** `backend/.env.example` (use this as your checklist!)
- **Email backend code:** `backend/emailing/backends.py`
- **Settings file:** `backend/config/settings.py`
- **Email test script:** `test_smtp.py`

---

## Quick Reference: Environment Variables Checklist

Use `backend/.env.example` as your master checklist. You should configure approximately **25-30 variables total:**

**Core Settings (3 variables):**
- DJANGO_SECRET_KEY
- DJANGO_DEBUG
- DJANGO_ALLOWED_HOSTS

**Database (9 variables):**
- DB_ENGINE
- DB_NAME
- DB_USER
- DB_PASSWORD
- DB_HOST
- DB_PORT
- DB_SSL_MODE
- DB_CONNECT_TIMEOUT
- DB_CONN_MAX_AGE

**Azure Storage (4 variables):**
- AZURE_ACCOUNT_NAME
- AZURE_ACCOUNT_KEY
- AZURE_CONTAINER
- CHAT_MAX_UPLOAD_MB

**Email/SendGrid (9 variables):**
- EMAIL_BACKEND
- EMAIL_HOST
- EMAIL_PORT
- EMAIL_USE_TLS
- EMAIL_USE_SSL
- EMAIL_HOST_USER
- EMAIL_HOST_PASSWORD
- DEFAULT_FROM_EMAIL
- SERVER_EMAIL

**CORS & Security (approximately 10 variables):**
- CORS_ALLOWED_ORIGINS
- CORS_ALLOW_CREDENTIALS
- SESSION_COOKIE_SECURE
- SESSION_COOKIE_SAMESITE
- CSRF_COOKIE_SECURE
- CSRF_COOKIE_SAMESITE
- CSRF_TRUSTED_ORIGINS
- Plus additional session settings

**Frontend URLs (3 variables):**
- FRONTEND_URL
- MAGIC_LINK_REDIRECT_URL
- LOGIN_REDIRECT_URL

---

## Summary

Once you've completed all steps in this guide:
- Your application secrets are secure (not visible in code)
- SendGrid is configured to send OTP emails
- Azure PostgreSQL database is connected
- Your application is production-ready and secure

**Important:** Use `backend/.env.example` as your checklist to ensure you've configured every variable!
