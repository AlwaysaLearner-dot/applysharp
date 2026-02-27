import { useState, useRef, useCallback } from 'react'
import Head from 'next/head'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ─────────────────────────────────────────────
// STAGE CONSTANTS
// ─────────────────────────────────────────────
const STAGES = {
  PASSWORD: 'password',
  INPUT: 'input',
  ANALYZING: 'analyzing',
  QUESTIONS: 'questions',
  GENERATING: 'generating',
  RESULTS: 'results',
}

// ─────────────────────────────────────────────
// UTILITY
// ─────────────────────────────────────────────
function copyToClipboard(text) {
  navigator.clipboard.writeText(text).catch(() => {
    const el = document.createElement('textarea')
    el.value = text
    document.body.appendChild(el)
    el.select()
    document.execCommand('copy')
    document.body.removeChild(el)
  })
}

// ─────────────────────────────────────────────
// SMALL COMPONENTS
// ─────────────────────────────────────────────
function Tag({ children, color = 'gold' }) {
  const colors = {
    gold: 'bg-gold/10 text-gold border-gold/20',
    danger: 'bg-danger/10 text-danger border-danger/20',
    success: 'bg-success/10 text-success border-success/20',
    info: 'bg-info/10 text-info border-info/20',
    muted: 'bg-muted/10 text-ghost border-muted/20',
  }
  return (
    <span className={`inline-block text-xs font-mono px-2 py-0.5 rounded border ${colors[color]}`}>
      {children}
    </span>
  )
}

function Card({ children, className = '' }) {
  return (
    <div className={`bg-panel border border-border rounded-xl p-5 ${className}`}>
      {children}
    </div>
  )
}

function Spinner({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className="animate-spin">
      <circle cx="12" cy="12" r="10" stroke="#1e2938" strokeWidth="3" fill="none" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="#e8b44a" strokeWidth="3" fill="none" strokeLinecap="round" />
    </svg>
  )
}

function GoldButton({ children, onClick, disabled, loading, type = 'button', className = '' }) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`relative flex items-center justify-center gap-2 px-6 py-3 bg-gold text-ink font-semibold font-sans text-sm rounded-lg transition-all hover:bg-gold/90 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed ${className}`}
    >
      {loading && <Spinner size={16} />}
      {children}
    </button>
  )
}

function GhostButton({ children, onClick, className = '' }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-2.5 text-sm text-ghost border border-border rounded-lg hover:border-gold/40 hover:text-light transition-all ${className}`}
    >
      {children}
    </button>
  )
}

function SectionTitle({ label, title }) {
  return (
    <div className="mb-6">
      <p className="font-mono text-xs text-gold/70 mb-1 tracking-widest uppercase">{label}</p>
      <h2 className="font-display text-2xl text-bright">{title}</h2>
    </div>
  )
}

// ─────────────────────────────────────────────
// FILE DROP ZONE
// ─────────────────────────────────────────────
function FileZone({ label, sublabel, file, onFile, accept = '.pdf', required }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef()

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) onFile(f)
  }, [onFile])

  const handleChange = (e) => {
    const f = e.target.files[0]
    if (f) onFile(f)
  }

  return (
    <div>
      <label className="block text-sm text-ghost mb-2 font-sans">
        {label} {required && <span className="text-gold">*</span>}
        {sublabel && <span className="text-muted ml-1 text-xs">— {sublabel}</span>}
      </label>
      <div
        className={`drop-zone border-2 border-dashed border-border rounded-xl p-6 text-center cursor-pointer ${dragging ? 'active' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current.click()}
      >
        <input ref={inputRef} type="file" accept={accept} onChange={handleChange} />
        {file ? (
          <div className="flex items-center justify-center gap-3">
            <svg className="w-5 h-5 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-success font-mono text-sm">{file.name}</span>
            <span className="text-muted text-xs">({(file.size / 1024).toFixed(0)} KB)</span>
          </div>
        ) : (
          <div>
            <svg className="w-8 h-8 text-muted mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="text-ghost text-sm">Drop PDF here or <span className="text-gold">click to browse</span></p>
            <p className="text-muted text-xs mt-1">Max 5MB · PDF only</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────
// STAGE: PASSWORD
// ─────────────────────────────────────────────
function PasswordStage({ onSuccess }) {
  const [pwd, setPwd] = useState('')
  const [error, setError] = useState('')
  const [show, setShow] = useState(false)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!pwd.trim()) { setError('Enter the access password.'); return }
    onSuccess(pwd.trim())
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md animate-fade-up">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gold/10 border border-gold/20 mb-4">
            <svg className="w-7 h-7 text-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h1 className="font-display text-3xl text-bright">ApplySharp</h1>
          <p className="text-ghost text-sm mt-2 font-sans">AI-powered CV intelligence. Private access only.</p>
        </div>

        <Card>
          <form onSubmit={handleSubmit}>
            <label className="block text-sm text-ghost mb-2">Access Password</label>
            <div className="relative mb-4">
              <input
                type={show ? 'text' : 'password'}
                value={pwd}
                onChange={(e) => { setPwd(e.target.value); setError('') }}
                placeholder="Enter password..."
                className="w-full bg-ink border border-border rounded-lg px-4 py-3 text-bright font-mono text-sm focus:outline-none focus:border-gold/50 pr-12"
              />
              <button type="button" onClick={() => setShow(!show)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ghost">
                {show ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                )}
              </button>
            </div>
            {error && <p className="text-danger text-xs mb-3 font-mono">{error}</p>}
            <GoldButton type="submit" className="w-full">Access ApplySharp →</GoldButton>
          </form>
        </Card>

        <p className="text-center text-muted text-xs mt-6 font-mono">
          Private tool · Data deleted after processing
        </p>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────
// STAGE: INPUT FORM
// ─────────────────────────────────────────────
const CV_RULES = [
  { ok: true, text: 'File format: PDF only' },
  { ok: false, text: 'No tables — use plain bullet points' },
  { ok: false, text: 'No text boxes, columns, or multi-column layouts' },
  { ok: false, text: 'No graphics, icons, photos, or decorative elements' },
  { ok: false, text: 'No headers/footers containing important information (ATS ignores them)' },
  { ok: true, text: 'Standard fonts only: Arial, Calibri, Georgia, Times New Roman' },
  { ok: true, text: 'Consistent date format: e.g. Jan 2022 (not 01/22 or Jan\'22)' },
  { ok: true, text: 'Standard section headings: Experience, Education, Skills, Projects' },
  { ok: false, text: 'No photos (especially for US, UK, Canada applications)' },
]

function InputStage({ password, onAnalyze }) {
  const [form, setForm] = useState({ company: '', role: '', location: '', jobDescription: '' })
  const [cvFile, setCvFile] = useState(null)
  const [linkedinFile, setLinkedinFile] = useState(null)
  const [error, setError] = useState('')
  const [rulesChecked, setRulesChecked] = useState(false)

  const update = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }))

  const handleSubmit = (e) => {
    e.preventDefault()
    setError('')

    if (!rulesChecked) { setError('Please confirm you have read the CV upload rules.'); return }
    if (!form.company || !form.role || !form.location || !form.jobDescription) {
      setError('All fields are required.'); return
    }
    if (!cvFile) { setError('Please upload your CV as a PDF.'); return }
    if (form.jobDescription.length < 100) {
      setError('Job description is too short. Please paste the full JD.'); return
    }

    const fd = new FormData()
    fd.append('password', password)
    fd.append('company', form.company)
    fd.append('role', form.role)
    fd.append('location', form.location)
    fd.append('job_description', form.jobDescription)
    fd.append('cv_file', cvFile)
    if (linkedinFile) fd.append('linkedin_file', linkedinFile)

    onAnalyze(fd)
  }

  return (
    <div className="min-h-screen pb-20">
      {/* Header */}
      <header className="border-b border-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-gold/10 border border-gold/20 flex items-center justify-center">
            <svg className="w-4 h-4 text-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <span className="font-display text-lg text-bright">ApplySharp</span>
        </div>
        <Tag color="muted">Private</Tag>
      </header>

      <div className="max-w-3xl mx-auto px-4 pt-12">
        <div className="mb-10 animate-fade-up">
          <p className="font-mono text-xs text-gold/70 mb-2 tracking-widest uppercase">Step 01</p>
          <h2 className="font-display text-3xl text-bright mb-2">Tell us about the role</h2>
          <p className="text-ghost text-sm">We'll analyse the job, your CV, and the company — then build you the best possible application.</p>
        </div>

        {/* CV Rules Card */}
        <Card className="mb-8 animate-fade-up stagger-1">
          <div className="flex items-start gap-3 mb-4">
            <svg className="w-5 h-5 text-gold mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="text-bright text-sm font-semibold mb-1">Before uploading your CV — read this</p>
              <p className="text-ghost text-xs">ATS systems read your CV like a robot. Formatting that looks good to humans breaks the parser. Your CV must meet these rules or ATS will silently filter you out.</p>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-1.5">
            {CV_RULES.map((r, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className={`shrink-0 mt-0.5 text-xs font-mono ${r.ok ? 'text-success' : 'text-danger'}`}>
                  {r.ok ? '✓' : '✗'}
                </span>
                <span className={`text-xs font-sans ${r.ok ? 'text-ghost' : 'text-light'}`}>{r.text}</span>
              </div>
            ))}
          </div>
          <label className="flex items-center gap-2 mt-4 cursor-pointer">
            <input
              type="checkbox"
              checked={rulesChecked}
              onChange={(e) => setRulesChecked(e.target.checked)}
              className="w-4 h-4 accent-gold"
            />
            <span className="text-xs text-ghost">I confirm my CV follows these rules</span>
          </label>
        </Card>

        <form onSubmit={handleSubmit} className="space-y-6 animate-fade-up stagger-2">
          {/* Job Details */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { field: 'company', label: 'Company Name', placeholder: 'e.g. Google' },
              { field: 'role', label: 'Job Role', placeholder: 'e.g. Backend Engineer' },
              { field: 'location', label: 'Location', placeholder: 'e.g. Singapore / Remote' },
            ].map(({ field, label, placeholder }) => (
              <div key={field}>
                <label className="block text-sm text-ghost mb-1.5">{label} <span className="text-gold">*</span></label>
                <input
                  type="text"
                  value={form[field]}
                  onChange={update(field)}
                  placeholder={placeholder}
                  maxLength={200}
                  className="w-full bg-ink border border-border rounded-lg px-4 py-3 text-bright text-sm focus:outline-none focus:border-gold/50 placeholder:text-muted"
                />
              </div>
            ))}
          </div>

          {/* Job Description */}
          <div>
            <label className="block text-sm text-ghost mb-1.5">
              Job Description <span className="text-gold">*</span>
              <span className="text-muted ml-2 text-xs">— Paste the full JD here (the more complete, the better)</span>
            </label>
            <textarea
              value={form.jobDescription}
              onChange={update('jobDescription')}
              placeholder="Paste the complete job description here — include responsibilities, requirements, preferred skills, everything..."
              maxLength={8000}
              rows={8}
              className="w-full bg-ink border border-border rounded-lg px-4 py-3 text-bright text-sm focus:outline-none focus:border-gold/50 placeholder:text-muted font-sans"
            />
            <p className="text-right text-xs text-muted mt-1 font-mono">{form.jobDescription.length}/8000</p>
          </div>

          {/* File Uploads */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <FileZone
              label="Your CV"
              sublabel="must follow rules above"
              file={cvFile}
              onFile={setCvFile}
              required
            />
            <FileZone
              label="LinkedIn Profile PDF"
              sublabel="optional but recommended"
              file={linkedinFile}
              onFile={setLinkedinFile}
            />
          </div>

          {/* LinkedIn PDF Instructions */}
          <div className="bg-info/5 border border-info/10 rounded-lg p-4">
            <p className="text-info text-xs font-semibold mb-1.5">How to download your LinkedIn PDF</p>
            <ol className="text-ghost text-xs space-y-1 list-none">
              <li><span className="text-info font-mono">01.</span> Go to your LinkedIn profile</li>
              <li><span className="text-info font-mono">02.</span> Click the "More" button → "Save to PDF"</li>
              <li><span className="text-info font-mono">03.</span> Upload that PDF here</li>
            </ol>
          </div>

          {/* Privacy notice */}
          <div className="flex items-start gap-2 text-xs text-muted">
            <svg className="w-4 h-4 text-muted mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            <span>Your CV and data are processed in memory and deleted immediately after your session. Nothing is stored on our servers.</span>
          </div>

          {error && (
            <div className="bg-danger/10 border border-danger/20 rounded-lg px-4 py-3 text-danger text-sm">
              {error}
            </div>
          )}

          <GoldButton type="submit" className="w-full py-4 text-base">
            Analyse My Application →
          </GoldButton>
        </form>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────
// STAGE: ANALYZING (loading)
// ─────────────────────────────────────────────
const ANALYSIS_STEPS = [
  'Parsing your CV...',
  'Gathering ATS intelligence (Container A)...',
  'Researching company culture (Container B)...',
  'Mapping role requirements (Container C)...',
  'Finding ABC intersection — highest priority items...',
  'Detecting gaps and AI patterns...',
  'Preparing your questions...',
]

function AnalyzingStage() {
  const [step, setStep] = useState(0)
  useState(() => {
    const interval = setInterval(() => {
      setStep(s => Math.min(s + 1, ANALYSIS_STEPS.length - 1))
    }, 2200)
    return () => clearInterval(interval)
  })

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="text-center max-w-md">
        <div className="relative inline-flex items-center justify-center mb-8">
          <div className="w-20 h-20 rounded-full bg-gold/10 border border-gold/20 flex items-center justify-center">
            <svg className="w-9 h-9 text-gold animate-pulse-slow" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <div className="absolute inset-0 rounded-full border border-gold/20 ping-slow" />
        </div>
        <h2 className="font-display text-2xl text-bright mb-2">Analysing your application</h2>
        <p className="text-ghost text-sm mb-8">This takes 30–60 seconds. We're gathering live intelligence across three data containers.</p>
        <div className="space-y-2 text-left">
          {ANALYSIS_STEPS.map((s, i) => (
            <div key={i} className={`flex items-center gap-3 transition-all duration-500 ${i <= step ? 'opacity-100' : 'opacity-20'}`}>
              <div className={`w-4 h-4 rounded-full border flex items-center justify-center shrink-0 ${i < step ? 'bg-success border-success' : i === step ? 'border-gold' : 'border-border'}`}>
                {i < step && <svg className="w-2.5 h-2.5 text-ink" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>}
                {i === step && <div className="w-1.5 h-1.5 rounded-full bg-gold animate-pulse" />}
              </div>
              <span className={`text-xs font-mono ${i === step ? 'text-gold' : i < step ? 'text-ghost' : 'text-muted'}`}>{s}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────
// STAGE: QUESTIONS (communication box)
// ─────────────────────────────────────────────
function QuestionsStage({ analysisData, password, onGenerate }) {
  const [answers, setAnswers] = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const questions = analysisData?.questions || []
  const gaps = analysisData?.gaps_found || []
  const autoFixes = analysisData?.auto_fixes || []
  const headsUp = analysisData?.heads_up_tips || []
  const aiWords = analysisData?.ai_words_detected || []
  const contradictions = analysisData?.linkedin_contradictions || []

  const updateAnswer = (id, val) => setAnswers(a => ({ ...a, [id]: val }))

  const handleGenerate = async () => {
    setError('')
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          password,
          session_id: analysisData.session_id,
          user_answers: answers,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Generation failed.')
      onGenerate(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen pb-20">
      <header className="border-b border-border px-6 py-4 flex items-center justify-between">
        <span className="font-display text-lg text-bright">ApplySharp</span>
        <Tag color="gold">Analysis Complete</Tag>
      </header>

      <div className="max-w-3xl mx-auto px-4 pt-10 space-y-6">
        <div className="animate-fade-up">
          <p className="font-mono text-xs text-gold/70 mb-2 tracking-widest uppercase">Step 02</p>
          <h2 className="font-display text-3xl text-bright mb-2">We found some things</h2>
          <p className="text-ghost text-sm">Answer a few questions to help us personalise your CV accurately. Then we'll generate everything.</p>
        </div>

        {/* Heads Up Tips */}
        {headsUp.length > 0 && (
          <Card className="animate-fade-up stagger-1 border-gold/20">
            <div className="flex items-center gap-2 mb-4">
              <svg className="w-4 h-4 text-gold" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <h3 className="text-gold text-sm font-semibold">Heads Up — Recruiter Intelligence</h3>
            </div>
            <div className="space-y-3">
              {headsUp.map((tip, i) => (
                <div key={i} className="bg-ink/50 rounded-lg p-4 border border-border">
                  <p className="text-light text-sm mb-2">{tip.tip}</p>
                  <div className="flex items-center justify-between gap-4 flex-wrap">
                    {tip.source_url ? (
                      <a href={tip.source_url} target="_blank" rel="noopener noreferrer"
                        className="text-xs text-info font-mono hover:underline">
                        ↗ {tip.source}
                      </a>
                    ) : (
                      <span className="text-xs text-muted font-mono">{tip.source}</span>
                    )}
                    {tip.action_taken && (
                      <Tag color="success">{tip.action_taken}</Tag>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Analysis Summary */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 animate-fade-up stagger-2">
          {gaps.length > 0 && (
            <Card>
              <p className="font-mono text-xs text-danger mb-3">GAPS DETECTED ({gaps.length})</p>
              <ul className="space-y-1.5">
                {gaps.map((g, i) => (
                  <li key={i} className="text-xs text-ghost flex items-start gap-1.5">
                    <span className="text-danger mt-0.5 shrink-0">→</span>{g}
                  </li>
                ))}
              </ul>
            </Card>
          )}
          {aiWords.length > 0 && (
            <Card>
              <p className="font-mono text-xs text-danger mb-3">AI WORDS TO REMOVE ({aiWords.length})</p>
              <div className="flex flex-wrap gap-1.5">
                {aiWords.map((w, i) => <Tag key={i} color="danger">{w}</Tag>)}
              </div>
            </Card>
          )}
          {autoFixes.length > 0 && (
            <Card>
              <p className="font-mono text-xs text-success mb-3">AUTO-FIXES ({autoFixes.length})</p>
              <ul className="space-y-1.5">
                {autoFixes.map((f, i) => (
                  <li key={i} className="text-xs text-ghost flex items-start gap-1.5">
                    <span className="text-success mt-0.5 shrink-0">✓</span>{f}
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        {/* LinkedIn contradictions */}
        {contradictions.length > 0 && (
          <Card className="border-danger/20 animate-fade-up stagger-2">
            <p className="font-mono text-xs text-danger mb-3">LINKEDIN VS CV MISMATCHES</p>
            {contradictions.map((c, i) => (
              <div key={i} className="text-xs text-ghost flex items-start gap-1.5">
                <span className="text-danger shrink-0">⚠</span>{c}
              </div>
            ))}
          </Card>
        )}

        {/* Questions */}
        {questions.length > 0 && (
          <Card className="animate-fade-up stagger-3">
            <p className="font-mono text-xs text-gold/70 mb-4 tracking-widest uppercase">Answer these to sharpen your CV</p>
            <div className="space-y-5">
              {questions.map((q, i) => (
                <div key={q.id}>
                  <div className="flex items-start gap-2 mb-2">
                    <span className="font-mono text-xs text-gold/50 mt-0.5 shrink-0">Q{i + 1}</span>
                    <div>
                      <p className="text-light text-sm">{q.question}</p>
                      <p className="text-muted text-xs mt-0.5">{q.context}</p>
                    </div>
                  </div>
                  <textarea
                    rows={2}
                    value={answers[q.id] || ''}
                    onChange={(e) => updateAnswer(q.id, e.target.value)}
                    placeholder="Your answer (or leave blank if not applicable)..."
                    className="w-full bg-ink border border-border rounded-lg px-4 py-2.5 text-bright text-sm focus:outline-none focus:border-gold/50 placeholder:text-muted resize-none font-sans"
                  />
                </div>
              ))}
            </div>
          </Card>
        )}

        {error && (
          <div className="bg-danger/10 border border-danger/20 rounded-lg px-4 py-3 text-danger text-sm">
            {error}
          </div>
        )}

        <div className="flex gap-4">
          <GoldButton onClick={handleGenerate} loading={loading} disabled={loading} className="flex-1 py-4 text-base">
            {loading ? 'Generating your application...' : 'Generate My CV, Cover Letter & Tips →'}
          </GoldButton>
        </div>

        <p className="text-center text-muted text-xs font-mono">This will take 30–60 seconds</p>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────
// STAGE: GENERATING (loading)
// ─────────────────────────────────────────────
function GeneratingStage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="text-center">
        <div className="relative inline-flex items-center justify-center mb-8">
          <div className="w-20 h-20 rounded-full bg-gold/10 border border-gold/20 flex items-center justify-center">
            <svg className="w-9 h-9 text-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </div>
          <div className="absolute inset-0 rounded-full border border-gold/20 ping-slow" />
        </div>
        <h2 className="font-display text-2xl text-bright mb-2">Writing your application</h2>
        <p className="text-ghost text-sm">Generating your CV, cover letter, and LinkedIn tips...<br />Almost there.</p>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────
// STAGE: RESULTS
// ─────────────────────────────────────────────
function ResultsStage({ data, onRestart }) {
  const [activeTab, setActiveTab] = useState('cv-ats')
  const [copied, setCopied] = useState('')

  const output = data?.output || {}
  const headsUp = data?.heads_up_tips || []
  const autoFixes = data?.auto_fixes_applied || []
  const aiWords = data?.ai_words_removed || []
  const changeLog = output?.change_log || []
  const linkedinTips = output?.linkedin_tips || []

  const handleCopy = (text, key) => {
    copyToClipboard(text)
    setCopied(key)
    setTimeout(() => setCopied(''), 2000)
  }

  const TABS = [
    { id: 'cv-ats', label: 'CV (ATS)', icon: '📄' },
    { id: 'cv-human', label: 'CV (Polished)', icon: '✨' },
    { id: 'cover', label: 'Cover Letter', icon: '📝' },
    { id: 'linkedin', label: 'LinkedIn Tips', icon: '🔗' },
    { id: 'strategy', label: 'Strategy', icon: '🎯' },
    { id: 'changelog', label: 'Change Log', icon: '📋' },
  ]

  const tabContent = {
    'cv-ats': output?.cv_ats_version,
    'cv-human': output?.cv_human_version,
    'cover': output?.cover_letter,
  }

  return (
    <div className="min-h-screen pb-20">
      <header className="border-b border-border px-6 py-4 flex items-center justify-between sticky top-0 bg-ink/80 backdrop-blur z-10">
        <span className="font-display text-lg text-bright">ApplySharp</span>
        <div className="flex items-center gap-3">
          <Tag color="success">Complete</Tag>
          <GhostButton onClick={onRestart}>New Application</GhostButton>
        </div>
      </header>

      {/* Heads Up Banner */}
      {headsUp.length > 0 && (
        <div className="bg-gold/5 border-b border-gold/10 px-6 py-3">
          <div className="max-w-5xl mx-auto flex items-center gap-3 flex-wrap">
            <span className="font-mono text-xs text-gold shrink-0">⚡ RECRUITER TIPS APPLIED</span>
            <div className="flex gap-2 flex-wrap">
              {headsUp.slice(0, 3).map((t, i) => (
                <Tag key={i} color="gold">{t.tip.split('.')[0].substring(0, 50)}</Tag>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="max-w-5xl mx-auto px-4 pt-8">
        {/* Summary row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8 animate-fade-up">
          {[
            { label: 'AI Words Removed', val: aiWords.length, color: 'danger' },
            { label: 'Auto-Fixes Applied', val: autoFixes.length, color: 'success' },
            { label: 'Changes Made', val: changeLog.length, color: 'info' },
            { label: 'LinkedIn Tips', val: linkedinTips.length, color: 'gold' },
          ].map(({ label, val, color }) => (
            <Card key={label} className="text-center">
              <p className={`font-display text-3xl text-${color}`}>{val}</p>
              <p className="text-ghost text-xs mt-1">{label}</p>
            </Card>
          ))}
        </div>

        {/* Tabs */}
        <div className="border-b border-border mb-6 flex gap-0 overflow-x-auto animate-fade-up stagger-1">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`px-4 py-3 text-xs font-mono whitespace-nowrap transition-colors border-b-2 ${
                activeTab === t.id
                  ? 'border-gold text-gold'
                  : 'border-transparent text-ghost hover:text-light'
              }`}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="animate-fade-up stagger-2">
          {/* Text output tabs */}
          {['cv-ats', 'cv-human', 'cover'].includes(activeTab) && tabContent[activeTab] && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <div>
                  {activeTab === 'cv-ats' && <p className="text-xs text-ghost font-mono">ATS-optimised version — plain text, maximum keyword density. Use this to submit via online forms.</p>}
                  {activeTab === 'cv-human' && <p className="text-xs text-ghost font-mono">Polished version — for emailing directly to a hiring manager or attaching to an application.</p>}
                  {activeTab === 'cover' && <p className="text-xs text-ghost font-mono">Tailored cover letter — company-specific, human-voiced, anti-AI-pattern.</p>}
                </div>
                <button
                  onClick={() => handleCopy(tabContent[activeTab], activeTab)}
                  className="flex items-center gap-2 px-3 py-1.5 bg-gold/10 border border-gold/20 rounded-lg text-gold text-xs font-mono hover:bg-gold/20 transition-all shrink-0"
                >
                  {copied === activeTab ? '✓ Copied!' : '⎘ Copy'}
                </button>
              </div>
              <Card>
                <pre className="font-mono text-xs text-light whitespace-pre-wrap leading-relaxed overflow-auto max-h-[600px]">
                  {tabContent[activeTab]}
                </pre>
              </Card>
            </div>
          )}

          {/* LinkedIn Tips */}
          {activeTab === 'linkedin' && (
            <div className="space-y-4">
              <p className="text-xs text-ghost font-mono">Specific, actionable LinkedIn improvements based on this role and company.</p>
              {linkedinTips.length === 0 ? (
                <Card><p className="text-ghost text-sm">No LinkedIn PDF was provided. Upload your LinkedIn PDF next time for personalised tips.</p></Card>
              ) : linkedinTips.map((tip, i) => (
                <Card key={i}>
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <Tag color="gold">{tip.section}</Tag>
                  </div>
                  {tip.current_issue && (
                    <div className="mb-2">
                      <p className="text-xs text-muted font-mono mb-1">CURRENT ISSUE</p>
                      <p className="text-danger text-sm">{tip.current_issue}</p>
                    </div>
                  )}
                  {tip.recommended_text && (
                    <div className="mb-2">
                      <p className="text-xs text-muted font-mono mb-1">RECOMMENDED</p>
                      <p className="text-success text-sm font-mono bg-success/5 rounded p-2">{tip.recommended_text}</p>
                    </div>
                  )}
                  {tip.why && <p className="text-ghost text-xs mt-2">{tip.why}</p>}
                </Card>
              ))}
            </div>
          )}

          {/* Strategy */}
          {activeTab === 'strategy' && (
            <Card>
              <p className="font-mono text-xs text-gold/70 mb-4 tracking-widest uppercase">Application Strategy</p>
              <p className="text-light text-sm leading-relaxed whitespace-pre-wrap">
                {output?.application_strategy || 'No strategy generated.'}
              </p>
            </Card>
          )}

          {/* Change Log */}
          {activeTab === 'changelog' && (
            <div className="space-y-3">
              <p className="text-xs text-ghost font-mono">Every change made to your CV — and exactly why. Full transparency.</p>
              {changeLog.length === 0 ? (
                <Card><p className="text-ghost text-sm">No detailed change log available.</p></Card>
              ) : changeLog.map((c, i) => (
                <Card key={i}>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-2">
                    <div>
                      <p className="text-xs font-mono text-danger mb-1">ORIGINAL</p>
                      <p className="text-sm text-ghost line-through">{c.original}</p>
                    </div>
                    <div>
                      <p className="text-xs font-mono text-success mb-1">CHANGED TO</p>
                      <p className="text-sm text-success">{c.changed_to}</p>
                    </div>
                  </div>
                  <p className="text-xs text-muted border-t border-border pt-2 mt-2">{c.reason}</p>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* AI Words removed notice */}
        {aiWords.length > 0 && (
          <Card className="mt-6 border-danger/10 animate-fade-up stagger-3">
            <p className="font-mono text-xs text-danger mb-3">AI-PATTERN WORDS REMOVED FROM YOUR CV</p>
            <div className="flex flex-wrap gap-2">
              {aiWords.map((w, i) => <Tag key={i} color="danger">{w}</Tag>)}
            </div>
            <p className="text-muted text-xs mt-3">These words are statistically flagged by recruiters and AI detectors as generated content. We replaced them with natural, specific language.</p>
          </Card>
        )}

        {/* Data deleted notice */}
        <div className="mt-8 text-center">
          <p className="text-muted text-xs font-mono flex items-center justify-center gap-2">
            <svg className="w-3.5 h-3.5 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            Your CV and data have been deleted from our servers.
          </p>
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────
// ROOT APP
// ─────────────────────────────────────────────
export default function App() {
  const [stage, setStage] = useState(STAGES.PASSWORD)
  const [password, setPassword] = useState('')
  const [analysisData, setAnalysisData] = useState(null)
  const [resultData, setResultData] = useState(null)

  const handlePasswordSuccess = (pwd) => {
    setPassword(pwd)
    setStage(STAGES.INPUT)
  }

  const handleAnalyze = (data) => {
    setAnalysisData(data)
    setStage(STAGES.QUESTIONS)
  }

  const handleGenerate = (data) => {
    setResultData(data)
    setStage(STAGES.RESULTS)
  }

  const handleRestart = () => {
    setAnalysisData(null)
    setResultData(null)
    setStage(STAGES.INPUT)
  }

  // The analyze call sets analyzing stage from InputStage via loading
  // but we expose a wrapper so InputStage can trigger analyzing stage
  const handleAnalyzeStart = (dataPromise) => {
    setStage(STAGES.ANALYZING)
    dataPromise.then(handleAnalyze).catch(() => setStage(STAGES.INPUT))
  }

  return (
    <>
      <Head>
        <title>ApplySharp — AI CV Optimiser</title>
        <meta name="description" content="Private AI-powered CV optimizer" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📄</text></svg>" />
      </Head>

      {stage === STAGES.PASSWORD && <PasswordStage onSuccess={handlePasswordSuccess} />}
      {stage === STAGES.INPUT && (
        <InputStageWrapper password={password} onAnalyze={handleAnalyze} onAnalyzing={() => setStage(STAGES.ANALYZING)} onError={() => setStage(STAGES.INPUT)} />
      )}
      {stage === STAGES.ANALYZING && <AnalyzingStage />}
      {stage === STAGES.QUESTIONS && (
        <QuestionsStage
          analysisData={analysisData}
          password={password}
          onGenerate={(data) => {
            setStage(STAGES.GENERATING)
            Promise.resolve(data).then(handleGenerate)
          }}
        />
      )}
      {stage === STAGES.GENERATING && <GeneratingStage />}
      {stage === STAGES.RESULTS && <ResultsStage data={resultData} onRestart={handleRestart} />}
    </>
  )
}

// Wrapper to coordinate analyzing stage transition
function InputStageWrapper({ password, onAnalyze, onAnalyzing, onError }) {
  const [loading, setLoading] = useState(false)

  const handleAnalyze = async (formData) => {
    setLoading(true)
    onAnalyzing()
    try {
      const res = await fetch(`${API}/api/analyze`, { method: 'POST', body: formData })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Analysis failed.')
      onAnalyze(data)
    } catch (err) {
      onError()
      alert(err.message)
    } finally {
      setLoading(false)
    }
  }

  return <InputStage password={password} onAnalyze={handleAnalyze} />
}
