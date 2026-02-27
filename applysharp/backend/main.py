"""
CV Optimizer Backend — FastAPI
Security: Rate limiting, session-based context, input validation, CORS
Data: Processed in memory, never persisted. Sessions auto-deleted after 1 hour.
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form, Body
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import io
import os
import time
import uuid
import json
import re
from collections import defaultdict
from typing import Optional
from anthropic import Anthropic
from tavily import TavilyClient

# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────
app = FastAPI(docs_url=None, redoc_url=None)  # Disable docs in production

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "X-App-Password"],
)

# ─────────────────────────────────────────────
# SECURITY & RATE LIMITING
# ─────────────────────────────────────────────
request_log: dict[str, list[float]] = defaultdict(list)

MAX_PER_HOUR = 2        # Max CV analysis starts per hour per IP
MAX_PER_DAY = 5         # Max CV analysis starts per day per IP
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_JD_LENGTH = 8000
MAX_FIELD_LENGTH = 300

APP_PASSWORD = os.getenv("APP_PASSWORD", "changeme")


def get_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host or "unknown"


def check_rate_limit(ip: str) -> tuple[bool, str]:
    now = time.time()
    # Clean entries older than 24h
    request_log[ip] = [t for t in request_log[ip] if now - t < 86400]

    hour_count = sum(1 for t in request_log[ip] if now - t < 3600)
    day_count = len(request_log[ip])

    if hour_count >= MAX_PER_HOUR:
        return True, f"Slow down — max {MAX_PER_HOUR} analyses per hour. Try again soon."
    if day_count >= MAX_PER_DAY:
        return True, f"Daily limit hit — max {MAX_PER_DAY} CVs per day. Come back tomorrow."
    return False, ""


def verify_password(pwd: str) -> bool:
    return pwd.strip() == APP_PASSWORD.strip()


def sanitize(text: str, max_len: int) -> str:
    return str(text).strip()[:max_len]


# ─────────────────────────────────────────────
# SESSION STORE (in-memory, auto-expires 1hr)
# Server holds CV text — client only gets session_id
# ─────────────────────────────────────────────
sessions: dict[str, dict] = {}
SESSION_TTL = 3600


def create_session(data: dict) -> str:
    cleanup_sessions()
    sid = str(uuid.uuid4())
    sessions[sid] = {"data": data, "created_at": time.time()}
    return sid


def get_session(sid: str) -> dict | None:
    s = sessions.get(sid)
    if not s:
        return None
    if time.time() - s["created_at"] > SESSION_TTL:
        del sessions[sid]
        return None
    return s["data"]


def cleanup_sessions():
    now = time.time()
    expired = [k for k, v in sessions.items() if now - v["created_at"] > SESSION_TTL]
    for k in expired:
        del sessions[k]


# ─────────────────────────────────────────────
# API CLIENTS
# ─────────────────────────────────────────────
claude_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


# ─────────────────────────────────────────────
# PDF PARSING
# ─────────────────────────────────────────────
def parse_pdf(file_bytes: bytes, label: str = "file") -> str:
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text = "\n".join(
                page.extract_text() or "" for page in pdf.pages
            ).strip()
        if not text or len(text) < 50:
            raise HTTPException(
                status_code=400,
                detail=f"Could not read text from {label}. Make sure it's not a scanned image PDF."
            )
        return text
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse {label}: {str(e)}")


# ─────────────────────────────────────────────
# INTELLIGENCE GATHERING (Containers A, B, C)
# ─────────────────────────────────────────────
def gather_intelligence(company: str, role: str, location: str) -> dict:
    results = {}
    searches = [
        ("container_a", f"ATS resume tips {role} hiring manager advice 2024 2025"),
        ("container_b", f"{company} company culture hiring resume tips recruiter {location}"),
        ("container_c", f"{role} resume best practices skills {location} job requirements"),
        ("company_tips", f"{company} recruiter hiring manager resume advice LinkedIn tips"),
    ]
    trusted_domains = [
        "linkedin.com", "glassdoor.com", "indeed.com",
        "jobscan.co", "shrm.org", "hbr.org", "lever.co",
        "greenhouse.io", "workday.com"
    ]
    for key, query in searches:
        try:
            r = tavily_client.search(
                query=query,
                max_results=4,
                include_domains=trusted_domains if key in ("container_a", "container_c") else None
            )
            results[key] = r.get("results", [])
        except Exception:
            results[key] = []
    return results


def format_intel(intel: dict) -> str:
    sections = {
        "container_a": "CONTAINER A — ATS & Universal Resume Science",
        "container_b": "CONTAINER B — Company Intelligence",
        "container_c": "CONTAINER C — Role Intelligence",
        "company_tips": "COMPANY-SPECIFIC TIPS & RECRUITER INSIGHTS",
    }
    lines = []
    for key, label in sections.items():
        items = intel.get(key, [])
        if items:
            lines.append(f"\n=== {label} ===")
            for r in items[:3]:
                url = r.get("url", "")
                content = r.get("content", "")[:400]
                lines.append(f"Source: {url}\n{content}\n")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# CLAUDE HELPERS
# ─────────────────────────────────────────────
def call_claude(prompt: str, max_tokens: int = 2500) -> str:
    resp = claude_client.messages.create(
        model="claude-opus-4-5",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.content[0].text


def extract_json(text: str) -> dict:
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "sessions_active": len(sessions)}


@app.post("/api/analyze")
async def analyze(
    request: Request,
    company: str = Form(...),
    role: str = Form(...),
    location: str = Form(...),
    job_description: str = Form(...),
    cv_file: UploadFile = File(...),
    linkedin_file: Optional[UploadFile] = File(None),
    password: str = Form(...),
):
    # 1. Auth
    if not verify_password(password):
        raise HTTPException(status_code=401, detail="Wrong password. Access denied.")

    # 2. Rate limit
    ip = get_ip(request)
    limited, msg = check_rate_limit(ip)
    if limited:
        raise HTTPException(status_code=429, detail=msg)

    # 3. Input validation
    company = sanitize(company, MAX_FIELD_LENGTH)
    role = sanitize(role, MAX_FIELD_LENGTH)
    location = sanitize(location, MAX_FIELD_LENGTH)
    job_description = sanitize(job_description, MAX_JD_LENGTH)

    if not company or not role or not location or not job_description:
        raise HTTPException(status_code=400, detail="All fields are required.")

    # 4. Parse CV
    cv_bytes = await cv_file.read()
    if len(cv_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="CV file exceeds 5MB limit.")
    cv_text = parse_pdf(cv_bytes, "CV")

    # 5. Parse LinkedIn PDF (optional)
    linkedin_text = ""
    if linkedin_file and linkedin_file.filename:
        li_bytes = await linkedin_file.read()
        if len(li_bytes) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="LinkedIn PDF exceeds 5MB limit.")
        linkedin_text = parse_pdf(li_bytes, "LinkedIn PDF")

    # 6. Gather intelligence (rate-counted only here, not on generate)
    request_log[ip].append(time.time())
    intel = gather_intelligence(company, role, location)
    intel_summary = format_intel(intel)

    # 7. Analysis prompt — detect gaps, questions, auto-fixes, heads-up tips
    analysis_prompt = f"""You are an expert CV analyst, ATS specialist, and career strategist. Analyze this job application thoroughly.

COMPANY: {company}
ROLE: {role}
LOCATION: {location}

JOB DESCRIPTION:
{job_description[:3500]}

CANDIDATE'S CV:
{cv_text[:3000]}

LINKEDIN PROFILE (if provided):
{linkedin_text[:2000] if linkedin_text else "Not provided"}

MARKET INTELLIGENCE:
{intel_summary[:3000]}

IMPORTANT ANALYSIS TASKS:
1. Find ALL gaps, mismatches, errors (employment gaps, skills missing from JD, weak language, passive voice, responsibility-lists instead of achievements, missing quantification)
2. Find what AI detection will flag — overused words like "spearheaded, leveraged, orchestrated, streamlined, pioneered, facilitated, demonstrated, fostered, cultivated, navigated, synergize, dynamic, results-driven, passionate" — list them if found in the CV
3. Detect LinkedIn vs CV contradictions (dates, titles, companies)
4. Find the ABC Intersection — items that appear in ALL THREE: (A) ATS best practices + (B) company intelligence + (C) role requirements — these are HIGHEST priority
5. Extract company-specific tips or warnings from the intelligence
6. Generate targeted questions (max 6) for things we genuinely CANNOT determine from the CV — only ask if the answer would meaningfully change the output

Questions to ALWAYS include if relevant:
- Employment gaps explanation
- Real numbers (team size, revenue, users, % improvements) for any vague achievements
- Do you have a referral or LinkedIn connection at {company}?
- Any relevant experience not shown on CV?
- Anything the CV gets wrong or misrepresents?

Questions to NEVER ask:
- Are you a strong match or stretch? (they don't know, and it doesn't help us)
- Generic questions answerable from the CV

Respond ONLY with this JSON structure, no other text:
{{
  "gaps_found": ["specific gap 1", "specific gap 2"],
  "ai_words_detected": ["word1", "word2"],
  "auto_fixes": ["Grammar: fixed X", "Spelling: corrected Y", "Passive voice: changed Z"],
  "linkedin_contradictions": ["issue1"],
  "abc_intersection": ["highest priority item 1", "item 2", "item 3"],
  "questions": [
    {{
      "id": "q1",
      "question": "exact question text",
      "context": "one sentence why this matters for the CV",
      "type": "text"
    }}
  ],
  "heads_up_tips": [
    {{
      "tip": "specific actionable tip",
      "source": "source name (e.g. LinkedIn post by [Company] recruiter / Glassdoor interview review)",
      "source_url": "url if available",
      "action_taken": "what the tool will do about it in the CV"
    }}
  ]
}}"""

    raw = call_claude(analysis_prompt, max_tokens=2000)
    analysis = extract_json(raw)

    # 8. Store in session (CV text stays server-side)
    session_data = {
        "company": company,
        "role": role,
        "location": location,
        "job_description": job_description,
        "cv_text": cv_text[:3500],
        "linkedin_text": linkedin_text[:2500],
        "intel_summary": intel_summary[:3000],
        "analysis": analysis,
    }
    session_id = create_session(session_data)

    return {
        "session_id": session_id,
        "questions": analysis.get("questions", []),
        "auto_fixes": analysis.get("auto_fixes", []),
        "gaps_found": analysis.get("gaps_found", []),
        "ai_words_detected": analysis.get("ai_words_detected", []),
        "linkedin_contradictions": analysis.get("linkedin_contradictions", []),
        "heads_up_tips": analysis.get("heads_up_tips", []),
    }


@app.post("/api/generate")
async def generate(request: Request, body: dict = Body(...)):
    # Auth
    if not verify_password(body.get("password", "")):
        raise HTTPException(status_code=401, detail="Wrong password.")

    session_id = body.get("session_id", "")
    user_answers = body.get("user_answers", {})

    ctx = get_session(session_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Session expired. Please re-upload your CV and start again.")

    analysis = ctx.get("analysis", {})
    answers_text = "\n".join(
        [f"Q: {q}\nA: {a}" for q, a in user_answers.items()]
    ) if user_answers else "Candidate provided no additional information."

    abc = ", ".join(analysis.get("abc_intersection", []))
    ai_words = analysis.get("ai_words_detected", [])

    generate_prompt = f"""You are an elite CV writer, ATS specialist, career strategist, and cover letter writer. Generate a complete job application package.

─── CONTEXT ───
Company: {ctx['company']}
Role: {ctx['role']}
Location: {ctx['location']}
Job Description: {ctx['job_description'][:3500]}

─── ORIGINAL CV ───
{ctx['cv_text']}

─── LINKEDIN PROFILE ───
{ctx['linkedin_text'] if ctx['linkedin_text'] else "Not provided"}

─── MARKET INTELLIGENCE ───
{ctx['intel_summary']}

─── ABC INTERSECTION (HIGHEST PRIORITY — optimize for these first) ───
{abc}

─── CANDIDATE'S ANSWERS TO CLARIFYING QUESTIONS ───
{answers_text}

─── STRICT CV GENERATION RULES ───

STRUCTURE RULES (non-negotiable):
- NO tables, NO text boxes, NO columns, NO graphics, NO icons
- Plain text structure ONLY — ATS must read every word
- Standard section headers: Summary, Experience, Education, Skills, Projects, Certifications
- Consistent date format: Mon YYYY (e.g. Jan 2022)

ANTI-AI-DETECTION RULES (critical):
- BANNED words (found in original CV: {', '.join(ai_words) if ai_words else 'none detected, still avoid globally'}):
  spearheaded, leveraged, orchestrated, streamlined, pioneered, facilitated, demonstrated,
  fostered, cultivated, navigated, synergize, dynamic, passionate, results-driven,
  detail-oriented, proactive, innovative, strategic thinker, strong communication skills
- Vary bullet point lengths NATURALLY — mix 8-word punchy lines with 20-25 word detailed ones
- ONLY use numbers/percentages the candidate confirmed as real in their answers
- Where no real numbers: use specific qualitative language ("across a 4-person team" not "significantly improved efficiency by X%")
- Summary must be specific to THIS role at THIS company — zero templates allowed
- Use the candidate's natural voice from their answers — pull their actual phrases and style

STRONG ACTION VERBS to use:
Built, Delivered, Led, Drove, Reduced, Grew, Launched, Solved, Shipped, Cut, Doubled,
Improved, Designed, Implemented, Deployed, Authored, Coordinated, Produced, Managed,
Negotiated, Trained, Established, Resolved, Automated, Migrated, Scaled, Revamped

CONTENT RULES:
- Achievement-first bullets, not responsibility-first ("Built X that reduced Y by Z" not "Responsible for X")
- Put the most JD-keyword-rich content in the top third of the CV (ATS and human both scan here first)
- Remove everything irrelevant to this specific role
- If LinkedIn profile provided and differs from CV, align them consistently

COVER LETTER RULES:
- Para 1: Hook — specific thing about THIS company (use intelligence gathered) — no generic openers
- Para 2: Bridge — how candidate's specific background connects to their exact need
- Para 3: Proof — one concrete example not fully shown in CV
- Para 4: Close — clear confident ask, not desperate or arrogant
- Same anti-AI rules apply — no banned words, varied sentence length, human voice
- Location-aware: if international role, naturally address availability/timezone if relevant

LINKEDIN TIPS RULES:
- Specific, actionable changes only
- Not generic advice — tailored to this company and role
- Prioritize: Headline, About section, top 3 experience descriptions, Skills section

Respond ONLY with this exact JSON structure, no other text:
{{
  "cv_ats_version": "complete optimized CV as plain text — this is the full document",
  "cv_human_version": "same CV with light formatting improvements — still no tables",
  "cover_letter": "complete tailored cover letter — full text",
  "linkedin_tips": [
    {{
      "section": "Headline",
      "current_issue": "what is wrong or weak",
      "recommended_text": "exact new text to use",
      "why": "specific reason tied to this role/company"
    }}
  ],
  "change_log": [
    {{
      "original": "original text from CV",
      "changed_to": "what we changed it to",
      "reason": "specific reason"
    }}
  ],
  "application_strategy": "specific advice: who to contact at this company, how, what to say, timing — based on what we know about their hiring process"
}}"""

    raw = call_claude(generate_prompt, max_tokens=4500)
    result = extract_json(raw)

    if not result:
        raise HTTPException(
            status_code=500,
            detail="Generation failed. The AI response was malformed. Please try again."
        )

    # Clean up session immediately after generation
    if session_id in sessions:
        del sessions[session_id]

    return {
        "status": "complete",
        "output": result,
        "heads_up_tips": analysis.get("heads_up_tips", []),
        "auto_fixes_applied": analysis.get("auto_fixes", []),
        "ai_words_removed": ai_words,
    }
