# ApplySharp — Setup Guide
AI-powered CV optimizer. Private, password-protected, zero data storage.

---

## What You Need (Already Have)
- ✅ Claude API key
- ✅ Railway account
- ✅ Vercel account (just signed up)
- ✅ Tavily API key (just signed up)

---

## STEP 1 — Deploy Backend to Railway

### 1.1 Create a new Railway project
1. Go to railway.app → New Project
2. Click "Deploy from GitHub repo" OR "Deploy from local"
3. If using local: Install Railway CLI → `npm install -g @railway/cli`
4. In your terminal, go to the `backend/` folder and run: `railway login` then `railway init`

### 1.2 Set Environment Variables on Railway
Go to your Railway project → Variables tab → Add these one by one:

```
ANTHROPIC_API_KEY     = your_claude_api_key
TAVILY_API_KEY        = your_tavily_api_key
APP_PASSWORD          = choose_a_strong_password (share this with friends)
FRONTEND_URL          = https://your-app.vercel.app  ← fill in after Step 2
```

### 1.3 Deploy
Railway auto-detects the Dockerfile and deploys.
After deploy, copy your Railway URL — it looks like:
`https://cvoptimizer-backend-xxxx.railway.app`

---

## STEP 2 — Deploy Frontend to Vercel

### 2.1 Push frontend to GitHub
Create a new GitHub repo. Push the `frontend/` folder to it.

### 2.2 Connect to Vercel
1. Go to vercel.com → New Project
2. Import your GitHub repo
3. Vercel auto-detects Next.js — no config needed

### 2.3 Set Environment Variable on Vercel
Go to Project Settings → Environment Variables → Add:

```
NEXT_PUBLIC_API_URL = https://your-railway-backend-xxxx.railway.app
```

(Use the Railway URL from Step 1.3)

### 2.4 Deploy
Click Deploy. Your app will be live at `https://your-app.vercel.app`

---

## STEP 3 — Connect Them Together

1. Copy your Vercel URL (e.g. `https://applysharp.vercel.app`)
2. Go back to Railway → Variables
3. Update `FRONTEND_URL` to your Vercel URL
4. Railway will redeploy automatically

---

## STEP 4 — Test It

1. Open your Vercel URL
2. Enter the password you set in `APP_PASSWORD`
3. Fill in the form with a test job and upload a CV
4. Make sure your CV follows the rules shown on screen (no tables, no columns)

---

## Security Features Built In

| Feature | Details |
|---------|---------|
| Password gate | Single password, no accounts, no Gmail farming |
| Rate limiting | Max 2 CV analyses per hour, 5 per day per IP |
| File size limit | Max 5MB per PDF |
| Input sanitization | All text fields validated and capped |
| Session-based | CV text stays on server only, client gets a session ID |
| Auto-deletion | Session data deleted after generation completes |
| No database | Nothing persisted anywhere |
| CORS locked | Backend only accepts requests from your Vercel URL |
| API keys hidden | Stored only in Railway env vars, never in code |

---

## Sharing the Tool

Just share:
- **URL**: your Vercel URL
- **Password**: the APP_PASSWORD you set

That's it. Anyone with both can use it. No accounts, no signup, no Gmail spam.

---

## Costs

| Service | Cost |
|---------|------|
| Railway hosting | Free tier (always-on is ~$5/month — check their current plan) |
| Vercel hosting | Free forever at this scale |
| Tavily searches | Free: 1,000/month — more than enough |
| Claude API | ~$0.10–0.25 per CV generation (comes from your existing API credits) |

---

## How to Download LinkedIn PDF

Tell your friend:
1. Go to linkedin.com/in/yourprofile
2. Click the **"More"** button on your profile
3. Click **"Save to PDF"**
4. Upload that PDF alongside your CV

---

## Troubleshooting

**"Could not extract text from CV"**
→ The CV is a scanned image, not a real PDF. Re-export from Word or Google Docs as PDF.

**"Session expired"**
→ The analysis took too long and the 1-hour session expired. Re-upload and start again.

**"Too many requests"**
→ Rate limit hit. Wait 1 hour for the hourly limit, or until the next day for the daily limit.

**Railway not connecting to Vercel**
→ Make sure FRONTEND_URL in Railway matches exactly (include https://, no trailing slash).

**"Wrong password"**
→ Check for typos, extra spaces. The password is case-sensitive.
