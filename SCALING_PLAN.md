# Climbing Gym v2.0 - Scaling Plan

**Goal:** Transform the current local grading tool into a global "virtual climbing gym" platform that any instructor can use, anywhere in the world.

**Timeline:** Ready for beta by Summer 2026 (~6 months)

---

## 1. Where We Are Now

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Google    │     │   Google    │     │    Your     │     │   GitHub    │
│   Forms     │────▶│   Drive     │────▶│   Laptop    │────▶│   Pages     │
│ (submit)    │     │ (storage)   │     │ (grading)   │     │ (dashboard) │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
      │                   │                   │                   │
      ▼                   ▼                   ▼                   ▼
  Manual setup      rclone sync          Python CLI         Static HTML
  per assignment    (manual)             (manual run)       (one password)
```

**Problems with current approach:**
- Everything runs on your laptop (can't scale)
- Manual sync steps (error-prone)
- Single password for everyone (no real privacy)
- Hard for other instructors to use
- No student portal (students use Google Forms)

---

## 2. Where We Want To Be

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           WEB APPLICATION                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │   Student    │  │  Instructor  │  │    Admin     │                   │
│  │   Portal     │  │  Dashboard   │  │    Panel     │                   │
│  │              │  │              │  │              │                   │
│  │ - Login      │  │ - All grades │  │ - Manage     │                   │
│  │ - Submit     │  │ - Analytics  │  │   courses    │                   │
│  │ - My grades  │  │ - Create     │  │ - Billing    │                   │
│  │ - Feedback   │  │   routes     │  │ - Users      │                   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                   │
│         │                 │                 │                           │
│         └─────────────────┼─────────────────┘                           │
│                           ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         API LAYER                                │   │
│  │   /submit    /grades    /routes    /courses    /users           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            SUPABASE                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │     Auth     │  │   Database   │  │   Storage    │  │   Edge      │ │
│  │              │  │  (Postgres)  │  │   (Files)    │  │  Functions  │ │
│  │ - Google SSO │  │              │  │              │  │             │ │
│  │ - Email/pwd  │  │ - Users      │  │ - Notebooks  │  │ - Grading   │ │
│  │ - Roles      │  │ - Courses    │  │ - Logbooks   │  │   worker    │ │
│  │              │  │ - Routes     │  │ - Reports    │  │             │ │
│  │              │  │ - Grades     │  │              │  │             │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         LLM GRADING SERVICE                             │
│                                                                         │
│   Your existing Python code, deployed as serverless functions           │
│   - Triggered when submission arrives                                   │
│   - Calls Anthropic/OpenAI API                                          │
│   - Writes results back to database                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Why Supabase?

| Feature | What It Gives You | Alternative |
|---------|-------------------|-------------|
| **Auth** | Google SSO, email/password, magic links. Students use school email. | Firebase Auth, Auth0 |
| **Database** | PostgreSQL with real-time subscriptions. Grades update live. | Firebase Firestore, PlanetScale |
| **Storage** | S3-compatible file storage for notebooks/submissions | AWS S3, Cloudflare R2 |
| **Edge Functions** | Run your Python grading code serverless (Deno/TypeScript, or call external Python) | AWS Lambda, Vercel Functions |
| **Row-Level Security** | Students automatically see ONLY their own data. No code needed. | Manual auth checks |
| **Free Tier** | 500MB database, 1GB storage, 500K edge function calls/month | Similar to Firebase |

**Bottom line:** Supabase handles 80% of the backend work. You focus on the grading logic (which already works).

---

## 4. Database Schema

```sql
-- USERS (handled by Supabase Auth, extended with profile)
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id),
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    role TEXT CHECK (role IN ('student', 'instructor', 'admin')),
    created_at TIMESTAMP DEFAULT NOW()
);

-- COURSES (the "climbing gym")
CREATE TABLE courses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code TEXT NOT NULL,           -- 'CHEM169'
    name TEXT NOT NULL,           -- 'Introduction to Bioinformatics'
    term TEXT,                    -- 'Winter 2026'
    instructor_id UUID REFERENCES profiles(id),
    settings JSONB,               -- {free_pass_routes: ['RID_007'], etc}
    created_at TIMESTAMP DEFAULT NOW()
);

-- ENROLLMENTS (who's in which course)
CREATE TABLE enrollments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID REFERENCES courses(id),
    student_id UUID REFERENCES profiles(id),
    enrolled_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(course_id, student_id)
);

-- ROUTES (assignments)
CREATE TABLE routes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID REFERENCES courses(id),
    code TEXT NOT NULL,           -- 'RID_001'
    name TEXT,                    -- 'The Warm-Up Wall'
    instructions_md TEXT,         -- Full markdown instructions
    route_type TEXT CHECK (route_type IN ('notebook', 'text')),
    exercises JSONB,              -- Parsed exercise definitions
    due_date TIMESTAMP,
    is_free_pass BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- SUBMISSIONS
CREATE TABLE submissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    route_id UUID REFERENCES routes(id),
    student_id UUID REFERENCES profiles(id),

    -- Files stored in Supabase Storage, paths here
    notebook_path TEXT,           -- 'submissions/uuid/notebook.ipynb'
    logbook_path TEXT,            -- 'submissions/uuid/logbook.txt'

    submitted_at TIMESTAMP DEFAULT NOW(),

    -- Grading status
    status TEXT CHECK (status IN ('pending', 'grading', 'graded', 'error')),
    graded_at TIMESTAMP,

    UNIQUE(route_id, student_id)  -- One submission per route per student
);

-- GRADES (the grading results)
CREATE TABLE grades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID REFERENCES submissions(id) UNIQUE,

    -- Overall
    is_sent BOOLEAN,              -- Did they "send" the route?
    overall_summary TEXT,

    -- Per-exercise breakdown (your current JSON structure)
    exercises JSONB,              -- [{exercise_id, rating, rationale, flags}, ...]

    -- Metadata
    graded_by TEXT,               -- 'anthropic/claude-sonnet-4-20250514'
    grading_duration_ms INTEGER,

    created_at TIMESTAMP DEFAULT NOW()
);
```

**Row-Level Security (the magic):**

```sql
-- Students can only see their own grades
CREATE POLICY "Students see own grades" ON grades
    FOR SELECT USING (
        submission_id IN (
            SELECT id FROM submissions WHERE student_id = auth.uid()
        )
    );

-- Instructors see all grades in their courses
CREATE POLICY "Instructors see course grades" ON grades
    FOR SELECT USING (
        submission_id IN (
            SELECT s.id FROM submissions s
            JOIN routes r ON s.route_id = r.id
            JOIN courses c ON r.course_id = c.id
            WHERE c.instructor_id = auth.uid()
        )
    );
```

With this, you write ZERO authorization code. The database enforces it automatically.

---

## 5. API Endpoints

These would be Supabase Edge Functions (or a separate FastAPI service):

```
STUDENTS:
  POST   /submit              Upload notebook + logbook for a route
  GET    /my-grades           Get all my grades across routes
  GET    /my-grades/:route    Get detailed feedback for one route
  GET    /routes              List available routes for my courses

INSTRUCTORS:
  GET    /courses/:id/students     List all students + their progress
  GET    /courses/:id/routes       List all routes + send rates
  GET    /courses/:id/grades       Export all grades (CSV/JSON)
  POST   /routes                   Create a new route
  PUT    /routes/:id               Update route instructions
  POST   /regrade/:submission_id   Re-run grading for a submission

GRADING (internal):
  POST   /grade               Called by queue when submission arrives
                              - Downloads files from storage
                              - Runs your Python grading logic
                              - Writes results to grades table
```

---

## 6. User Flows

### Student Submits Assignment

```
1. Student logs in (Google SSO with school email)
           │
           ▼
2. Sees their dashboard: routes with status (pending/submitted/sent)
           │
           ▼
3. Clicks "Submit" on RID_003
           │
           ▼
4. Uploads notebook.ipynb + logbook.txt
           │
           ▼
5. Files go to Supabase Storage
   Row created in `submissions` table (status: 'pending')
           │
           ▼
6. Edge Function triggered (or queue picks it up)
           │
           ▼
7. Grading runs (your existing Python logic)
           │
           ▼
8. Results written to `grades` table
   Submission status → 'graded'
           │
           ▼
9. Student sees feedback appear (real-time via Supabase subscriptions)
```

### Instructor Views Dashboard

```
1. Instructor logs in
           │
           ▼
2. Sees course overview:
   - 84 students enrolled
   - Route health heatmap (your current viz!)
   - Low completion alerts
           │
           ▼
3. Clicks on a route (RID_007)
           │
           ▼
4. Sees:
   - Exercise success rates
   - Common issues
   - List of students who haven't submitted
           │
           ▼
5. Can click any student to see their detailed feedback
```

---

## 7. Migration Path

### Phase 1: Backend Foundation (Month 1-2)

**Week 1-2: Set up Supabase**
```
- Create Supabase project
- Set up database schema (tables above)
- Configure Google OAuth (school domain)
- Test auth flow locally
```

**Week 3-4: Migrate grading logic**
```
- Wrap your Python grader in an API endpoint
- Deploy as Supabase Edge Function (or separate Railway/Render service)
- Test: submit file → grading runs → result in database
```

**Deliverable:** Can submit a file via API, get it graded, see result in database.

---

### Phase 2: Student Portal (Month 2-3)

**Week 5-6: Basic web app**
```
- Simple React/Next.js app (or even vanilla HTML + JS)
- Login page with Google SSO
- "My Grades" page showing all routes + status
```

**Week 7-8: Submission flow**
```
- File upload component
- Progress indicator while grading
- Detailed feedback view (like your current expandable panels)
```

**Deliverable:** Students can log in, submit, and see their own grades.

---

### Phase 3: Instructor Dashboard (Month 3-4)

**Week 9-10: Port current dashboard**
```
- Your beautiful Plotly visualizations → React components
- Route health heatmap
- Student lookup (but instructor sees all)
```

**Week 11-12: Management features**
```
- Create/edit routes
- Export grades to CSV
- Bulk re-grade
```

**Deliverable:** You can manage the course entirely through the web app.

---

### Phase 4: Polish + Beta (Month 4-6)

```
- Invite 1-2 other instructors to test
- Handle their feedback
- Documentation for new instructors
- Monitoring + error alerting
- Maybe: billing/usage tracking for future SaaS
```

---

## 8. What You Keep

Your existing code is valuable! Here's what carries over:

| Current | Future |
|---------|--------|
| `graderbot/grader.py` | Core of the grading Edge Function |
| `graderbot/route_parser.py` | Used when instructor creates route |
| `graderbot/prompts.py` | Same prompts, same quality |
| `graderbot/llm_client.py` | Same API calls to Anthropic/OpenAI |
| `graderbot/dashboard.py` | Port visualizations to React |
| Plotly charts | Same charts, embedded in web app |

**You're NOT starting over.** You're wrapping what works in a proper web architecture.

---

## 9. Cost Estimates

| Service | Free Tier | Paid (if needed) |
|---------|-----------|------------------|
| Supabase | 500MB db, 1GB storage, 500K function calls | $25/mo for Pro |
| Vercel (frontend) | 100GB bandwidth | $20/mo for Pro |
| Anthropic API | - | ~$0.01-0.05 per grading (current cost) |
| Domain | - | ~$12/year |

**For a single course (100 students, 10 routes, 1000 submissions):**
- Supabase free tier is plenty
- LLM costs: ~$10-50 total per term
- Total: Basically free

**For 10 courses (1000 students):**
- Supabase Pro: $25/mo
- LLM costs: ~$100-500 per term
- Total: ~$50-100/month

---

## 10. Questions to Decide Later

1. **Multi-instructor:** Can any instructor sign up, or invite-only?
2. **Branding:** "Climbing Gym" as the product name? Domain?
3. **Monetization:** Free for educators? Freemium? Per-student pricing?
4. **LLM choice:** Let instructors pick their own API keys, or centralized?
5. **Integrations:** Canvas LTI integration for grades sync?

---

## 11. Next Concrete Step

When you're ready to start (maybe over winter break?):

```bash
# 1. Create Supabase account
#    https://supabase.com - sign up with GitHub

# 2. Create new project
#    Name: climbing-gym
#    Region: West US (closest to you)
#    Password: (save this!)

# 3. Run schema migration
#    Go to SQL Editor, paste the schema from section 4

# 4. Enable Google Auth
#    Authentication → Providers → Google
#    Add your school domain as allowed

# 5. Test it
#    Create a test user, insert a test grade, verify RLS works
```

I can help you through each step when you're ready!

---

*Document created: 2026-01-27*
*Author: Claude + Alejandro*
