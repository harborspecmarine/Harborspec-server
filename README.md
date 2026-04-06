# HarborSPEC™ Order Server

Receives orders from cart.html via direct POST → generates branded invoice PDF → emails to orders@harborspecmarine.com and the customer.

---

## ⚠️ Fix Email Going to Spam — Do This First

Emails from this server were landing in spam because SendGrid was sending on behalf of
a @gmail.com address. Gmail's security policy (DMARC) blocks any server other than
Gmail's own from sending as a Gmail address — spam filters catch it every time.

The fix is to send from your own domain (orders@harborspecmarine.com) and tell
SendGrid it's authorized to do so. This is a one-time setup.

### Step A — Create the mailbox in IONOS
1. Log into your IONOS account → Email → Create Mailbox
2. Create: orders@harborspecmarine.com
3. Optional: set it to forward to your personal Gmail so you read everything in one place
   (IONOS → Email → your new mailbox → Forwarding)

### Step B — Authenticate your domain in SendGrid
This tells every mail server on the internet that SendGrid is authorized to send
on behalf of harborspecmarine.com. Without this, emails go to spam.

1. Log into sendgrid.com
2. Go to Settings → Sender Authentication → Authenticate a Domain
3. Choose IONOS as your DNS host (or select "Other" if not listed)
4. Enter: harborspecmarine.com
5. SendGrid will generate 3 DNS records that look like this:

```
TYPE    NAME                                    VALUE
CNAME   em123.harborspecmarine.com              u123456.wl.sendgrid.net
CNAME   s1._domainkey.harborspecmarine.com      s1.domainkey.u123456.sendgrid.net
CNAME   s2._domainkey.harborspecmarine.com      s2.domainkey.u123456.sendgrid.net
```

   (Your actual values will be different — copy exactly what SendGrid shows you)

6. Add those 3 records in IONOS:
   - IONOS → Domains & SSL → your domain → DNS → Add Record → CNAME
   - Repeat for all 3
7. Back in SendGrid, click Verify — it can take up to 30 minutes to propagate
8. Also go to Settings → Sender Authentication → Verify a Single Sender
   and verify orders@harborspecmarine.com

### Step C — Update Railway environment variable
Change one variable in Railway → your project → Variables:

```
ORDERS_EMAIL = orders@harborspecmarine.com
```

That's it. All outbound email — to you and to customers — will now come from
orders@harborspecmarine.com, pass authentication checks, and land in the inbox.

---

## Deploy to Railway

### Step 1 — Create a GitHub repo
1. Go to github.com and create a new repo called `harborspec-server`
2. Upload all files in this folder to that repo

### Step 2 — Deploy on Railway
1. Go to railway.app and sign up
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your `harborspec-server` repo
4. Railway will detect the Procfile and deploy automatically

### Step 3 — Set Environment Variables
In Railway → your project → Variables → add all of these:

| Variable         | Value                                            | Required |
|------------------|--------------------------------------------------|----------|
| ORDERS_EMAIL     | orders@harborspecmarine.com                      | Yes      |
| SENDGRID_API_KEY | (your SendGrid API key — see below)              | Yes      |
| SMTP_USER        | harborspecmarineorders@gmail.com                 | Yes      |
| SMTP_PASS        | (your Gmail App Password — see below)            | Yes      |
| WEBHOOK_TOKEN    | (make up any secret word, e.g. harbor2025)       | Yes      |
| ALLOWED_ORIGIN   | https://harborspecmarine.com                     | Yes      |
| INVOICE_START    | 0 (or bump this after any restart to skip ahead) | Optional |

Note: SMTP_USER and SMTP_PASS are your Gmail credentials for the IMAP fallback
polling only — not for sending. Sending always goes through SendGrid.

### Step 4 — Get Gmail App Password (for IMAP fallback polling)
1. Go to myaccount.google.com
2. Security → 2-Step Verification (must be enabled first)
3. Security → App Passwords
4. Create one named "HarborSPEC Server"
5. Copy the 16-character password → use as SMTP_PASS

### Step 5 — Get SendGrid API Key (for outbound email)
1. Go to sendgrid.com → sign up or log in
2. Settings → API Keys → Create API Key
3. Give it "Mail Send" permission
4. Copy the key → use as SENDGRID_API_KEY

### Step 6 — Test it
Visit: https://YOUR-RAILWAY-URL.railway.app/health
Should return: {"status": "ok", "sendgrid": true, "smtp": true}

---

## How it works

1. Customer places order on harborspecmarine.com/cart.html
2. cart.html POSTs the order JSON directly to /order on this server
3. Server assigns an invoice number (format: HS-260405-001)
4. ReportLab generates a branded navy/brass PDF invoice
5. SendGrid emails the PDF to you at orders@harborspecmarine.com
6. SendGrid emails a copy + confirmation to the customer
7. Gmail IMAP polling runs every 5 minutes as a fallback in case the direct POST ever fails

---

## Invoice Numbers

Format: HS-YYMMDD-SEQ (e.g. HS-260405-001)

- Date prefix makes every number naturally unique across restarts
- Sequence resets to 001 each calendar day — that's fine because the date changes
- If you ever need to start from a higher number (e.g. after a redeploy mid-day),
  set the INVOICE_START environment variable to the number you want to start from

---

## Files

- `app.py`          — Flask server, order endpoint, email sender
- `invoice.py`      — PDF invoice generator (ReportLab)
- `requirements.txt`— Python dependencies (Flask, gunicorn, reportlab)
- `Procfile`        — tells Railway how to run the server

---

## Changes from original version

- **Spam fix**: Emails were going to spam because SendGrid was sending as a @gmail.com
  address — Gmail's DMARC policy blocks this. Fix is to send from orders@harborspecmarine.com
  with SendGrid domain authentication (DKIM/SPF DNS records in IONOS). Full steps above.
- **Invoice counter**: Was using /tmp which resets on every Railway restart — now
  date-prefixed (HS-YYMMDD-SEQ), crash-proof
- **CORS**: Was open to all origins (*) — now restricted to harborspecmarine.com
  via ALLOWED_ORIGIN env var
- **Email body**: Now includes production notes / measurements per line item
  (important for dust cover orders)
- **Invoice PDF**: Now renders measurement/notes sub-line under item name when present
- **Procfile**: Added --workers 2 --timeout 60 to handle concurrent orders and slow
  PDF generation
- **requirements.txt**: Added (was missing — Railway cannot install dependencies without it)
- **SENDGRID_API_KEY**: Was missing from README setup instructions
