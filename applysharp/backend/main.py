"""
CV Optimizer Backend — FastAPI
AI: Google Gemini (free tier)
Security: Rate limiting, CORS, input validation, session-based, auto-delete
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form, Body
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from tavily import TavilyClient
import pdfplumber
import io
import os
import time
import uuid
import json
import re
from collections import defaultdict
from typing import Optional

# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────
app = FastAPI(docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# SECURITY & RATE LIMITING
# ─────────────────────────────────────────────
request_log: dict = defaultdict(list)

MAX_PER_HOUR     = 3
MAX_PER_DAY      = 8
MAX_FILE_SIZE    = 5 * 1024 * 1024
MAX_JD_LENGTH    = 8000
MAX_FIELD_LENGTH = 300

APP_PASSWORD = os.getenv("APP_PASSWORD", "changeme")


def get_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return (request.client.host if request.client else None) or "unknown"


def check_rate_limit(ip: str):
    now = time.time()
    request_log[ip] = [t for t in request_log[ip] if now - t < 86400]
    hour_count = sum(1 for t in request_log[ip] if now - t < 3600)
    day_count  = len(request_log[ip])
    if hour_count >= MAX_PER_HOUR:
        return True, f"Max {MAX_PER_HOUR} analyses per hour. Try again soon."
    if day_count >= MAX_PER_DAY:
        return True, f"Daily limit of {MAX_PER_DAY} reached. Come back tomorrow."
    return False, ""


def verify_password(pwd: str) -> bool:
    return str(pwd).strip() == str(APP_PASSWORD).strip()


def sanitize(text: str, max_len: int) -> str:
    return str(text).strip()[:max_len]


# ─────────────────────────────────────────────
# SESSION STORE — in memory, auto deletes after 1hr
# ─────────────────────────────────────────────
sessions: dict = {}
SESSION_TTL = 3600


def create_session(data: dict) -> str:
    _cleanup_sessions()
    sid = str(uuid.uuid4())
    sessions[sid] = {"data": data, "created_at": time.time()}
    return sid


def get_session(sid: str):
    s = sessions.get(sid)
    if not s:
        return None
    if time.time() - s["created_at"] > SESSION_TTL:
        del sessions[sid]
        return None
    return s["data"]


def _cleanup_sessions():
    now  = time.time()
    dead = [k for k, v in sessions.items() if now - v["created_at"] > SESSION_TTL]
    for k in dead:
        del sessions[k]


# ─────────────────────────────────────────────
# API CLIENTS — lazy init (server starts even if keys missing)
# ─────────────────────────────────────────────
_gemini_model = None
_tavily       = None


def get_gemini():
    global _gemini_model
    if _gemini_model is None:
        key = os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise HTTPException(500, "GEMINI_API_KEY not set in Railway variables.")
        genai.configure(api_key=key)
        _gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite")
    return _gemini_model


def get_tavily():
    global _tavily
    if _tavily is None:
        key = os.getenv("TAVILY_API_KEY", "")
        if not key:
            raise HTTPException(500, "TAVILY_API_KEY not set in Railway variables.")
        _tavily = TavilyClient(api_key=key)
    return _tavily


# ─────────────────────────────────────────────
# PDF PARSING
# ─────────────────────────────────────────────
def parse_pdf(file_bytes: bytes, label: str = "file") -> str:
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text = "\n".join(
                page.extract_text() or "" for page in pdf.pages
            ).strip()
        if not text or len(text) < 30:
            raise HTTPException(
                400,
                f"Could not read text from {label}. "
                "Make sure it is a real text-based PDF — not a scanned image. "
                "Re-export from Word or Google Docs as PDF."
            )
        return text
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Failed to parse {label}: {str(e)}")


# ─────────────────────────────────────────────
# INTELLIGENCE GATHERING (Containers A / B / C)
# ─────────────────────────────────────────────
def gather_intelligence(company: str, role: str, location: str) -> dict:
    searches = [
        ("container_a",  f"ATS resume tips {role} hiring manager advice 2025"),
        ("container_b",  f"{company} hiring culture resume tips recruiter {location}"),
        ("container_c",  f"{role} resume best practices skills {location} requirements"),
        ("company_tips", f"{company} recruiter hiring manager LinkedIn resume advice"),
    ]
    results = {}
    for key, query in searches:
        try:
            r = get_tavily().search(query=query, max_results=4)
            results[key] = r.get("results", [])
        except Exception:
            results[key] = []
    return results


def format_intel(intel: dict) -> str:
    labels = {
        "container_a":  "CONTAINER A — ATS & Universal Resume Science",
        "container_b":  "CONTAINER B — Company Intelligence",
        "container_c":  "CONTAINER C — Role Intelligence",
        "company_tips": "COMPANY-SPECIFIC TIPS",
    }
    lines = []
    for key, label in labels.items():
        items = intel.get(key, [])
        if items:
            lines.append(f"\n=== {label} ===")
            for r in items[:3]:
                lines.append(f"Source: {r.get('url','')}\n{r.get('content','')[:350]}\n")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# AI CALL
# ─────────────────────────────────────────────
def call_ai(prompt: str, max_tokens: int = 2500) -> str:
    model    = get_gemini()
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=0.7,
        )
    )
    return response.text


def extract_json(text: str) -> dict:
    # Strip markdown fences if Gemini wraps response in ```json ... ```
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*",     "", text)
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.get("/health")
def health():
    """Open this URL in browser to confirm backend is alive and keys are set"""
    return {
        "status":          "ok",
        "sessions_active": len(sessions),
        "gemini_key_set":  bool(os.getenv("GEMINI_API_KEY")),
        "tavily_key_set":  bool(os.getenv("TAVILY_API_KEY")),
        "password_set":    bool(os.getenv("APP_PASSWORD")),
    }


@app.post("/api/analyze")
async def analyze(
    request:         Request,
    company:         str                  = Form(...),
    role:            str                  = Form(...),
    location:        str                  = Form(...),
    job_description: str                  = Form(...),
    cv_file:         UploadFile           = File(...),
    linkedin_file:   Optional[UploadFile] = File(None),
    password:        str                  = Form(...),
):
    # Auth
    if not verify_password(password):
        raise HTTPException(401, "Wrong password. Access denied.")

    # Rate limit
    ip = get_ip(request)
    limited, msg = check_rate_limit(ip)
    if limited:
        raise HTTPException(429, msg)

    # Validate inputs
    company         = sanitize(company,         MAX_FIELD_LENGTH)
    role            = sanitize(role,            MAX_FIELD_LENGTH)
    location        = sanitize(location,        MAX_FIELD_LENGTH)
    job_description = sanitize(job_description, MAX_JD_LENGTH)

    if not all([company, role, location, job_description]):
        raise HTTPException(400, "All text fields are required.")
    if len(job_description) < 80:
        raise HTTPException(400, "Job description too short — paste the full JD.")

    # Parse CV
    cv_bytes = await cv_file.read()
    if len(cv_bytes) > MAX_FILE_SIZE:
        raise HTTPException(400, "CV file exceeds 5 MB.")
    cv_text = parse_pdf(cv_bytes, "CV")

    # Parse LinkedIn (optional — failure is non-fatal)
    linkedin_text = ""
    if linkedin_file and linkedin_file.filename:
        li_bytes = await linkedin_file.read()
        if len(li_bytes) <= MAX_FILE_SIZE:
            try:
                linkedin_text = parse_pdf(li_bytes, "LinkedIn PDF")
            except HTTPException:
                linkedin_text = ""

    # Gather intelligence
    request_log[ip].append(time.time())
    intel         = gather_intelligence(company, role, location)
    intel_summary = format_intel(intel)

    # AI Analysis
    analysis_prompt = f"""You are an expert CV analyst and ATS specialist.

COMPANY: {company}
ROLE: {role}
LOCATION: {location}

JOB DESCRIPTION:
{job_description[:3500]}

CANDIDATE CV:
{cv_text[:3000]}

LINKEDIN PROFILE:
{linkedin_text[:2000] if linkedin_text else "Not provided"}

MARKET INTELLIGENCE:
{intel_summary[:2500]}

TASKS:
1. Find ALL gaps and weaknesses (missing keywords, vague achievements, passive voice, no metrics, employment gaps)
2. Detect AI-generated language — flag these words if found in CV: spearheaded, leveraged, orchestrated, streamlined, pioneered, facilitated, demonstrated, fostered, cultivated, navigated, synergize, dynamic, results-driven, passionate, detail-oriented, proactive
3. Find LinkedIn vs CV contradictions (dates, titles, companies)
4. Identify ABC Intersection — items in ATS best practices AND company culture AND role requirements
5. Extract company-specific recruiter tips from intelligence
6. Write max 5 targeted questions for info we cannot get from the CV that would change the output

NEVER ask: are you a strong match — useless.
ALWAYS ask if relevant: employment gap explanations, real metrics, referral at {company}, hidden relevant experience.

IMPORTANT: Reply ONLY with a valid JSON object. No markdown. No code fences. No explanation. Just the raw JSON:
{{
  "gaps_found": ["gap1", "gap2"],
  "ai_words_detected": ["word1"],
  "auto_fixes": ["Grammar: fixed X", "Spelling: corrected Y"],
  "linkedin_contradictions": ["issue1"],
  "abc_intersection": ["item1", "item2"],
  "questions": [
    {{
      "id": "q1",
      "question": "question text",
      "context": "why this matters"
    }}
  ],
  "heads_up_tips": [
    {{
      "tip": "actionable tip",
      "source": "source name",
      "source_url": "url or empty string",
      "action_taken": "what we will do in the CV"
    }}
  ]
}}"""

    try:
        raw      = call_ai(analysis_prompt, max_tokens=2000)
        analysis = extract_json(raw)
    except Exception as e:
        raise HTTPException(500, f"AI analysis failed: {str(e)}")

    session_id = create_session({
        "company":         company,
        "role":            role,
        "location":        location,
        "job_description": job_description,
        "cv_text":         cv_text[:3500],
        "linkedin_text":   linkedin_text[:2500],
        "intel_summary":   intel_summary[:3000],
        "analysis":        analysis,
    })

    return {
        "session_id":              session_id,
        "questions":               analysis.get("questions", []),
        "auto_fixes":              analysis.get("auto_fixes", []),
        "gaps_found":              analysis.get("gaps_found", []),
        "ai_words_detected":       analysis.get("ai_words_detected", []),
        "linkedin_contradictions": analysis.get("linkedin_contradictions", []),
        "heads_up_tips":           analysis.get("heads_up_tips", []),
    }


@app.post("/api/generate")
async def generate(request: Request, body: dict = Body(...)):
    # Auth
    if not verify_password(body.get("password", "")):
        raise HTTPException(401, "Wrong password.")

    session_id   = body.get("session_id", "")
    user_answers = body.get("user_answers", {})

    ctx = get_session(session_id)
    if not ctx:
        raise HTTPException(404, "Session expired. Please start again and re-upload your CV.")

    analysis     = ctx.get("analysis", {})
    ai_words     = analysis.get("ai_words_detected", [])
    abc          = ", ".join(analysis.get("abc_intersection", []))
    answers_text = (
        "\n".join(f"Q: {q}\nA: {a}" for q, a in user_answers.items())
        if user_answers else "No additional information provided."
    )

    generate_prompt = f"""You are an elite CV writer, ATS specialist, and career strategist.

COMPANY:  {ctx['company']}
ROLE:     {ctx['role']}
LOCATION: {ctx['location']}

JOB DESCRIPTION:
{ctx['job_description'][:3500]}

ORIGINAL CV:
{ctx['cv_text']}

LINKEDIN PROFILE:
{ctx['linkedin_text'] if ctx['linkedin_text'] else "Not provided"}

MARKET INTELLIGENCE:
{ctx['intel_summary']}

ABC INTERSECTION (optimise these first):
{abc}

CANDIDATE ANSWERS:
{answers_text}

RULES:

CV STRUCTURE (non-negotiable):
- NO tables, NO columns, NO text boxes, NO graphics, NO icons, NO photos
- Plain text only
- Section headers: Summary | Experience | Education | Skills | Projects | Certifications
- Dates: Mon YYYY only (e.g. Jan 2022)

ANTI-AI-DETECTION:
- BANNED words: {', '.join(ai_words) if ai_words else 'none found — still avoid globally'}
- Also always avoid: spearheaded, leveraged, orchestrated, streamlined, pioneered, facilitated, demonstrated, fostered, cultivated, navigated, synergize, dynamic, passionate, results-driven, detail-oriented, proactive, innovative
- Vary bullet lengths naturally — some 8 words, some 25 — never uniform
- Only use numbers the candidate confirmed are real — never invent percentages
- No real numbers available? Use specific qualitative detail instead
- Summary must be specific to THIS role at THIS company — zero templates

GOOD ACTION VERBS: Built, Delivered, Led, Drove, Reduced, Grew, Launched, Solved, Shipped, Cut, Improved, Designed, Implemented, Deployed, Managed, Negotiated, Trained, Established, Resolved, Automated, Scaled

COVER LETTER:
- Para 1: Specific hook about THIS company — no generic openers ever
- Para 2: Candidate background matched to their exact need
- Para 3: One concrete proof example with real detail
- Para 4: Confident close — not desperate, not arrogant

IMPORTANT: Reply ONLY with a valid JSON object. No markdown. No code fences. No explanation. Just raw JSON:
{{
  "cv_ats_version": "complete plain-text ATS optimised CV here",
  "cv_human_version": "same CV slightly polished for human reading",
  "cover_letter": "complete cover letter full text",
  "linkedin_tips": [
    {{
      "section": "section name e.g. Headline",
      "current_issue": "what is weak or wrong",
      "recommended_text": "exact replacement text to use",
      "why": "specific reason tied to this role and company"
    }}
  ],
  "change_log": [
    {{
      "original": "original text from CV",
      "changed_to": "new improved text",
      "reason": "why this change was made"
    }}
  ],
  "application_strategy": "specific advice on who to contact at this company, how, what to say, and timing"
}}"""

    try:
        raw    = call_ai(generate_prompt, max_tokens=4500)
        result = extract_json(raw)
    except Exception as e:
        raise HTTPException(500, f"CV generation failed: {str(e)}")

    if not result:
        raise HTTPException(500, "AI returned malformed output. Please try again.")

    # Delete session immediately after generation — no data left behind
    sessions.pop(session_id, None)

    return {
        "status":             "complete",
        "output":             result,
        "heads_up_tips":      analysis.get("heads_up_tips", []),
        "auto_fixes_applied": analysis.get("auto_fixes", []),
        "ai_words_removed":   ai_words,
    }
