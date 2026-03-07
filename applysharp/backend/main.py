"""
CV Optimizer Backend — FastAPI
AI: Google Gemini 2.5 Flash Lite (free)
Fix: Robust JSON extraction, simplified prompts, better error handling
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
# SESSION STORE
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
# API CLIENTS
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
        _gemini_model = genai.GenerativeModel(
            "gemini-2.5-flash-lite",
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                response_mime_type="application/json",  # Force JSON output
            )
        )
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
# INTELLIGENCE GATHERING
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
            r = get_tavily().search(query=query, max_results=3)
            results[key] = r.get("results", [])
        except Exception:
            results[key] = []
    return results


def format_intel(intel: dict) -> str:
    labels = {
        "container_a":  "ATS & Resume Science",
        "container_b":  "Company Intelligence",
        "container_c":  "Role Intelligence",
        "company_tips": "Company-Specific Tips",
    }
    lines = []
    for key, label in labels.items():
        items = intel.get(key, [])
        if items:
            lines.append(f"\n=== {label} ===")
            for r in items[:2]:
                lines.append(f"Source: {r.get('url','')}\n{r.get('content','')[:300]}\n")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# AI CALL + ROBUST JSON EXTRACTION
# ─────────────────────────────────────────────
def call_ai(prompt: str) -> str:
    model    = get_gemini()
    response = model.generate_content(prompt)
    return response.text


def extract_json(text: str) -> dict:
    if not text:
        return {}

    # Step 1 — strip markdown fences
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*",     "", text)
    text = text.strip()

    # Step 2 — try parsing the whole thing directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Step 3 — find the outermost { ... } block
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass

    # Step 4 — try fixing common issues: trailing commas, unescaped newlines
    try:
        cleaned = re.sub(r",\s*([}\]])", r"\1", text[start:end+1])  # remove trailing commas
        cleaned = re.sub(r"\n",          r"\\n", cleaned)             # escape newlines
        return json.loads(cleaned)
    except Exception:
        pass

    return {}


def safe_str(val) -> str:
    """Make sure a value is a plain string"""
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        return "\n".join(str(v) for v in val)
    return str(val) if val else ""


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status":           "ok",
        "sessions_active":  len(sessions),
        "gemini_key_set":   bool(os.getenv("GEMINI_API_KEY")),
        "tavily_key_set":   bool(os.getenv("TAVILY_API_KEY")),
        "password_set":     bool(os.getenv("APP_PASSWORD")),
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
    if not verify_password(password):
        raise HTTPException(401, "Wrong password. Access denied.")

    ip = get_ip(request)
    limited, msg = check_rate_limit(ip)
    if limited:
        raise HTTPException(429, msg)

    company         = sanitize(company,         MAX_FIELD_LENGTH)
    role            = sanitize(role,            MAX_FIELD_LENGTH)
    location        = sanitize(location,        MAX_FIELD_LENGTH)
    job_description = sanitize(job_description, MAX_JD_LENGTH)

    if not all([company, role, location, job_description]):
        raise HTTPException(400, "All text fields are required.")
    if len(job_description) < 80:
        raise HTTPException(400, "Job description too short — paste the full JD.")

    cv_bytes = await cv_file.read()
    if len(cv_bytes) > MAX_FILE_SIZE:
        raise HTTPException(400, "CV file exceeds 5 MB.")
    cv_text = parse_pdf(cv_bytes, "CV")

    linkedin_text = ""
    if linkedin_file and linkedin_file.filename:
        li_bytes = await linkedin_file.read()
        if len(li_bytes) <= MAX_FILE_SIZE:
            try:
                linkedin_text = parse_pdf(li_bytes, "LinkedIn PDF")
            except HTTPException:
                linkedin_text = ""

    request_log[ip].append(time.time())
    intel         = gather_intelligence(company, role, location)
    intel_summary = format_intel(intel)

    analysis_prompt = f"""You are a CV analyst and ATS specialist. Analyse this job application.

COMPANY: {company}
ROLE: {role}
LOCATION: {location}

JOB DESCRIPTION:
{job_description[:2500]}

CANDIDATE CV:
{cv_text[:2500]}

LINKEDIN PROFILE:
{linkedin_text[:1500] if linkedin_text else "Not provided"}

MARKET INTELLIGENCE:
{intel_summary[:2000]}

Return ONLY a JSON object with these exact keys. No text before or after the JSON:

{{
  "gaps_found": ["list gaps and missing keywords here"],
  "ai_words_detected": ["list any of these words found in CV: spearheaded leveraged orchestrated streamlined pioneered facilitated demonstrated fostered cultivated navigated synergize dynamic results-driven passionate detail-oriented proactive"],
  "auto_fixes": ["list grammar spelling and passive voice issues found"],
  "linkedin_contradictions": ["list any date title or company mismatches between LinkedIn and CV"],
  "abc_intersection": ["list top 3 to 5 items appearing in ATS best practices AND company culture AND role requirements"],
  "questions": [
    {{
      "id": "q1",
      "question": "write your question here",
      "context": "explain why this matters for the CV"
    }}
  ],
  "heads_up_tips": [
    {{
      "tip": "write the tip here",
      "source": "source name",
      "source_url": "",
      "action_taken": "what we will do in the CV"
    }}
  ]
}}"""

    try:
        raw      = call_ai(analysis_prompt)
        analysis = extract_json(raw)
    except Exception as e:
        raise HTTPException(500, f"AI analysis failed: {str(e)}")

    # If JSON came back empty, use safe defaults so the app doesn't break
    if not analysis:
        analysis = {
            "gaps_found": ["Could not auto-detect gaps — please review manually"],
            "ai_words_detected": [],
            "auto_fixes": [],
            "linkedin_contradictions": [],
            "abc_intersection": [],
            "questions": [],
            "heads_up_tips": [],
        }

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

    banned = ', '.join(ai_words) if ai_words else "none detected"

    generate_prompt = f"""You are an elite CV writer and career strategist.

COMPANY: {ctx['company']}
ROLE: {ctx['role']}
LOCATION: {ctx['location']}

JOB DESCRIPTION:
{ctx['job_description'][:2500]}

ORIGINAL CV:
{ctx['cv_text'][:2500]}

LINKEDIN PROFILE:
{ctx['linkedin_text'][:1500] if ctx['linkedin_text'] else "Not provided"}

MARKET INTELLIGENCE:
{ctx['intel_summary'][:2000]}

TOP PRIORITIES (ABC intersection):
{abc}

CANDIDATE ANSWERS:
{answers_text}

STRICT RULES:
1. NO tables, columns, text boxes, graphics, icons or photos in CV
2. Plain text only with standard section headers: Summary, Experience, Education, Skills, Projects
3. Dates in Mon YYYY format only
4. BANNED words (remove all): {banned} and also: spearheaded leveraged orchestrated streamlined pioneered synergize dynamic passionate results-driven detail-oriented proactive innovative
5. Use strong verbs instead: Built Delivered Led Drove Reduced Grew Launched Solved Shipped Improved Designed Implemented Managed Scaled
6. Achievement-first bullets not responsibility-first
7. Vary bullet lengths naturally — mix short 8 word lines with longer 25 word lines
8. Never invent numbers — only use metrics the candidate confirmed
9. Summary must be specific to THIS company and role — no generic templates
10. Cover letter Para 1 must reference something specific about THIS company

Return ONLY a JSON object. No text before or after. No markdown fences:

{{
  "cv_ats_version": "write the complete plain text ATS CV here as a single string with newlines as \\n",
  "cv_human_version": "write the same CV slightly polished here as a single string with newlines as \\n",
  "cover_letter": "write the complete cover letter here as a single string with newlines as \\n",
  "linkedin_tips": [
    {{
      "section": "Headline",
      "current_issue": "describe what is weak",
      "recommended_text": "write exact replacement text",
      "why": "explain why for this specific role"
    }}
  ],
  "change_log": [
    {{
      "original": "original text",
      "changed_to": "new text",
      "reason": "why"
    }}
  ],
  "application_strategy": "write specific advice on who to contact how and when"
}}"""

    try:
        raw    = call_ai(generate_prompt)
        result = extract_json(raw)
    except Exception as e:
        raise HTTPException(500, f"CV generation failed: {str(e)}")

    # If JSON extraction failed, build a safe fallback from raw text
    if not result:
        result = {
            "cv_ats_version":      raw[:3000] if raw else "Generation failed — please try again.",
            "cv_human_version":    raw[:3000] if raw else "Generation failed — please try again.",
            "cover_letter":        "Cover letter generation failed — please try again.",
            "linkedin_tips":       [],
            "change_log":          [],
            "application_strategy": "Please try again for strategy tips.",
        }

    # Ensure all text fields are strings not lists
    for field in ["cv_ats_version", "cv_human_version", "cover_letter", "application_strategy"]:
        if field in result:
            result[field] = safe_str(result[field])

    sessions.pop(session_id, None)

    return {
        "status":             "complete",
        "output":             result,
        "heads_up_tips":      analysis.get("heads_up_tips", []),
        "auto_fixes_applied": analysis.get("auto_fixes", []),
        "ai_words_removed":   ai_words,
    }
