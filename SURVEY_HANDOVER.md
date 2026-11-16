# Survey Handover: Think Before You Prompt on adhenzmiranda.com

> **Status (16 Nov 2026):** built on the `survey-app` branch, with two changes Adhenz asked for. The survey is edited in the admin (a Google Forms-style builder with the experiment built in) instead of `content.py` and `SURVEY_*` config vars, and it lives at `/msc-survey/` instead of `/survey/`. Draft, Open and Closed in the admin replace the demo, live and off modes. **docs/SURVEY.md is the current guide.** The research design below (prompts, scoring, balancing, privacy rules) is unchanged.

16 Nov 2026 · for Claude Code, working in `am-portfolio-website`

## How to use this

1. Put this file in the repo root as `SURVEY_HANDOVER.md`.
2. Put `survey_demo.html` (sent with this file) in `docs/survey_demo.html`. It is the working clickable demo of the survey; port its look, screens and JavaScript instead of redesigning.
3. In Claude Code say: "Read SURVEY_HANDOVER.md and docs/survey_demo.html, then build the survey on a new branch called `survey-app`."

Work on a branch and open a PR, same as every other site change. Merging to `main` auto-deploys to Heroku (`am04`) and the release step runs migrations.

## The goal

Move the dissertation survey onto the portfolio site at **adhenzmiranda.com/survey/** as a new Django app called `survey`.

It ships in **demo mode** (works fully, saves nothing). It can be switched to **live mode** later with one Heroku config var, but only after ethics approval. Build the live part now so nothing needs rebuilding later.

## About the dissertation (short version)

- MSc Cybersecurity, Bath Spa University, module CYS7006. Researcher: Adhenz Miranda.
- Question: which social media format (short video, infographic, text post) best teaches UAE university students to stop sharing sensitive information with AI chatbots.
- Design: every student does a "would you send this?" task with 8 chatbot prompts, sees ONE format chosen at random, does the same 8 prompts again in a new order, then rates 8 statements. The change in score (out of 8) is the main outcome, compared across the 3 groups in Python later.
- Target about 160 students (about 50 per group) from 3+ universities in 3 emirates.

## What already exists in the repo (checked 16 Nov 2026)

- Django 5.2, Python 3.12, one app called `projects` (settings live in `projects/settings.py`, URLs in `projects/urls.py`).
- Neon Postgres in production, SQLite locally. `CONN_HEALTH_CHECKS = True` is already on `main`, so the Neon sleep fix is merged.
- Admin sits on a secret `ADMIN_URL` with 2FA (django-otp).
- `projects/views.py` has `client_ip(group, request)` for django-ratelimit (reads `CF-Connecting-IP`). Reuse it; the IP only lives in the rate-limit cache and must never be saved.
- No Content Security Policy is set, so inline `json_script` data is fine.
- `base.html` has the navbar and footer. The survey should NOT use it: it is a standalone, distraction-free page for phones.

## Modes

| `SURVEY_MODE` | What happens |
| --- | --- |
| `demo` (default) | Everything works, nothing is saved. A note says "Sample version, nothing is saved". The researcher view shows at the end. `#video`, `#infographic`, `#text` on the link forces a format for previewing. |
| `live` | Real data collection. Format is assigned by the server, answers are saved, no researcher view, no hash override. |
| `off` | `/survey/` returns 404. |

Safety rule: if `SURVEY_MODE=live` but `SURVEY_RESEARCHER_EMAIL` or `SURVEY_ETHICS_CONTACT` is empty, behave as demo. Nobody should be able to take part without real consent contacts on screen.

## Config vars (all optional, add to `settings.py` with `os.getenv`)

| Var | Use |
| --- | --- |
| `SURVEY_MODE` | `demo`, `live` or `off` |
| `SURVEY_BATCH` | Label saved on every response, e.g. `pilot` then `main`. Default `main` |
| `SURVEY_RESEARCHER_EMAIL` | Shown in the consent text |
| `SURVEY_ETHICS_CONTACT` | Supervisor or ethics contact shown in the consent text |
| `SURVEY_REEL_URL` | Cloudinary URL of the finished reel (mp4). Unset = the animated placeholder from the demo |
| `SURVEY_REEL_POSTER` | Optional still image for the reel |
| `SURVEY_INFOGRAPHIC_URL` | Cloudinary URL of the finished infographic. Unset = the built-in HTML poster |

Also add a `survey` logger to `LOGGING` next to the `projects` one.

## Files to create

```
survey/
  __init__.py, apps.py
  content.py      single source of truth (below)
  models.py       Participant
  views.py        page, start, submit
  urls.py
  admin.py        read-only list + CSV export
  tests.py
  migrations/0001_initial.py   (makemigrations)
templates/survey/survey.html   standalone page
static/survey/survey.css       from the demo's <style>
static/survey/survey.js        from the demo's <script>, adapted
docs/SURVEY.md                 short setup and go-live guide
```

Register in `INSTALLED_APPS` and add `path('survey/', include('survey.urls'))` to `projects/urls.py`. Do not add the survey to the sitemap.

## content.py (use this as is)

Both the page and the server read from this, so wording, prompts and the answer key can't drift apart. Send it to the page with `json_script`. Send the answer key (`risky`) to the browser in demo mode only.

```python
CONTENT_VERSION = '1.0'   # bump if anything participants see changes

HOOK = "You'd never post your Emirates ID on your story. So why paste it into ChatGPT?"
THREAT = "What you type into a chatbot can be stored, and by default it can be used to train future models."
TIPS = [
    ("Keep IDs and passwords out", "Never paste ID numbers, passwords or bank details into a chatbot."),
    ("Leave other people out", "Don't share classmates' names, phone numbers or grades."),
    ("Swap in placeholders", 'Need help with a form? Write "my ID is 784-XXXX" instead of the real number.'),
    ("Use Temporary Chat", "For anything personal, use Temporary Chat. OpenAI says these chats aren't used for training and are deleted after 30 days."),
    ("Turn off training once", 'Go to Settings, then Data Controls, and turn off "Improve the model for everyone".'),
    ("Check what it remembers", "Chatbots can remember details from past chats. Go to Settings, then Personalization, then Memory, delete anything personal, and don't ask it to use what it knows about you."),
]
HANDLE = 'campuscybertips'
FORMATS = {'video': 'Short-form video', 'infographic': 'Infographic', 'text': 'Text post'}

# Numbered 1-8 to match the dissertation tables. 'img' = attached screenshot,
# 'ctx' = what the chatbot already remembers.
PROMPTS = [
    {'n': 1, 'text': "I have a visa application form, can you recreate this layout so I can fill it in?", 'img': 'formFilled', 'risky': True},
    {'n': 2, 'text': "Turn these lecture slides into a 5-question revision quiz.", 'img': 'slide', 'risky': False},
    {'n': 3, 'text': "Can you summarise this group chat so I know what I missed?", 'img': 'chat', 'risky': True},
    {'n': 4, 'text': "My Emirates ID is 784-XXXX-XXXXXXX-X. Which fields on a visa form usually ask for it?", 'risky': False},
    {'n': 5, 'text': "Why does my banking app keep showing this error?", 'img': 'bank', 'risky': True},
    {'n': 6, 'text': "I have a visa application form, can you recreate this layout so I can fill it in?", 'img': 'formBlank', 'risky': False},
    {'n': 7, 'text': "Based on everything you remember about me, which airline is safest for someone like me to fly to Manila?", 'ctx': 'memory', 'risky': True},
    {'n': 8, 'text': "Which airlines have the best safety record on flights from Dubai to Manila?", 'ctx': 'memory', 'risky': False},
]
MATCHED_PAIRS = [(1, 6), (7, 8)]   # never shown next to each other

SEND_AS_IS = 'Send as is'
SEND_CHOICES = [SEND_AS_IS, 'Change it first', "Wouldn't send"]

LIKERT = [   # 1 = strongly disagree, 5 = strongly agree; group labels never shown
    ('engagement', "The message held my attention."),
    ('engagement', "I enjoyed the way the message was presented."),
    ('self_efficacy', "I know how to follow this advice."),
    ('self_efficacy', "I could do these steps without help."),
    ('response_efficacy', "Following this advice would protect my information."),
    ('response_efficacy', "These steps would make a real difference to my privacy."),
    ('intention', "I plan to follow this advice next time I use an AI chatbot."),
    ('intention', "I will check my ChatGPT settings this week."),
]
CONSTRUCTS = ['engagement', 'self_efficacy', 'response_efficacy', 'intention']

GENDERS = ['Male', 'Female', 'Prefer not to say']
EMIRATES = ['Abu Dhabi', 'Dubai', 'Sharjah', 'Ajman', 'Umm Al Quwain', 'Ras Al Khaimah', 'Fujairah']
FIELDS = ['Science, IT or Engineering', 'Business', 'Humanities or Arts', 'Other']
CHATBOT_USE = ['Never', 'Monthly', 'Weekly', 'Daily']
MIN_AGE, MAX_AGE = 18, 80

def is_correct(prompt, answer):
    # Risky: "Change it first" or "Wouldn't send" is correct.
    # Safe: "Send as is" is correct (stops "refuse everything" scoring 8/8).
    if prompt['risky']:
        return answer in SEND_CHOICES and answer != SEND_AS_IS
    return answer == SEND_AS_IS

def score(answers):   # {prompt number: choice} -> score out of 8
    return sum(1 for p in PROMPTS if is_correct(p, answers.get(p['n'])))
```

## Model: `Participant`

A row is created when someone ticks both consent boxes (so drop-outs per group can be counted) and filled in on submit.

- `token` UUID (unique), `batch`, `content_version`, `format`, `started_at`, `completed_at` (null until submitted)
- About you: `age`, `gender`, `university` (free text, max 120), `emirate`, `field_of_study`, `chatbot_use`
- Task: `before_order`, `after_order` (lists of prompt numbers as shown), `before_answers`, `after_answers` (JSON keyed "1" to "8"), `before_score`, `after_score`, `score_change` (computed on the server, never trusted from the browser)
- `content_loaded` (bool from the load check), `ratings` (list of 8 ints)
- Timing: `message_seconds` (time on the message screen, all formats), `video_watched_seconds`, `video_finished`, `total_seconds`

**Never store:** name, email, student ID, IP address, user agent, cookies or anything else that identifies a person.

## Views

1. `GET /survey/` renders the standalone page. Adds `X-Robots-Tag: noindex, nofollow` and `Cache-Control: no-store`. Passes the CSRF token in the config.
2. `POST /survey/start/` (live only, else 404, rate limit 30/h per IP with `client_ip`): creates a Participant and returns `{token, format}`.
   **Balanced random assignment:** pick the format with the fewest people so far in this batch, counting finished people plus anyone who started in the last 60 minutes. Break ties at random (`random.SystemRandom`). This keeps the groups even, like Qualtrics "Evenly Present Elements". Methods wording: "Participants were randomly assigned to one of three conditions using balanced allocation."
3. `POST /survey/submit/` (live only, rate limit 30/h): JSON body with `token`, `about`, `before_order`, `before`, `after_order`, `after`, `loaded`, `ratings`, `timing`. Validate every value against `content.py` (choices in the allowed lists, age 18 to 80, orders are a shuffle of 1 to 8, 8 ratings of 1 to 5). Reject anything odd with a 400. Only accept a token that exists, isn't completed and started within 6 hours (else 410). Use `select_for_update` so a double tap can't submit twice.

## Admin

Register `Participant` read-only (no add, no edit, delete allowed). List shows id, format, batch, completed, emirate, university, before/after/change score, loaded. Filters: completed vs started, format, batch, emirate, loaded.

Admin action **"Download selected as CSV"** with one row per person: ids and dates, demographics, `before_p1` to `before_p8` plus `before_p1_correct` (1/0) and the same for after, the three scores, `rating_1_engagement` to `rating_8_intention`, the four construct means, loaded, timing, and the two orders. This CSV is what the Python analysis reads. It must never be committed to the repo (add `survey_responses_*.csv` to `.gitignore`).

## Front end

Port `docs/survey_demo.html` almost as is: same screens, same fonts (Atkinson Hyperlegible, Montserrat), same light and dark themes, same HTML mock screenshots, same reel placeholder, infographic and text post. Changes:

- Read content and config from the two `json_script` blocks instead of hard-coded constants.
- **Fix the Back button (important).** The demo lets you go back from the message to the "before" task and change answers after seeing the message, which would ruin the pre-test. Allow Back only on About you and the "before" task. From the message screen onwards there is no Back.
- Live mode: when both consent boxes are ticked and they press start, call `/survey/start/` and use the format it returns. Submit to `/survey/submit/` with the `X-CSRFToken` header. Show a friendly error with a "Try again" button if the request fails, without losing answers.
- Save progress in `sessionStorage` so an accidental refresh on a phone resumes where they were. Clear it after submitting.
- After a live submit, set a `localStorage` flag and show "You've already taken part, thank you" on a return visit (a soft duplicate check, not a hard block).
- Record `message_seconds` for every format. If `SURVEY_REEL_URL` is set, show a real `<video playsinline muted autoplay>` inside the reel frame (tap to pause or play, a small sound toggle, no native controls) and record watched seconds and whether it finished. If `SURVEY_INFOGRAPHIC_URL` is set, show it as an `<img>` inside the post frame with alt text containing the full script.
- Keep the before and after orders random per person with the matched pairs never next to each other (the demo's `spread()` does this).
- Demo mode keeps the researcher view at the end and the `#video` / `#infographic` / `#text` preview links. Live mode removes both.
- Consent text uses the two contact config vars; when unset in demo mode keep the `[researcher email]` and `[supervisor or ethics contact]` placeholders.
- No like or view counts and no platform logos on the mock posts (social proof would sway answers).

## Tests (`survey/tests.py`)

- Demo mode: page loads, start and submit return 404, nothing is saved.
- Off mode: page 404s.
- Live mode without contacts falls back to demo.
- Live mode: start creates a row; a full valid submit saves it with the correct scores; a second submit with the same token is refused; bad values (wrong choice, age 17, 7 ratings, broken order) get a 400; an old token gets a 410.
- Balancing: with 2 video, 2 infographic and 1 text already done, the next start is text.
- Scoring: someone who answers "Wouldn't send" to everything scores 4, not 8.
- CSV export: header and one row line up in length.

Run with `python manage.py test survey`, then click through on `runserver` at phone width in all three formats.

## docs/SURVEY.md

Short numbered steps (Adhenz prefers these): run it locally, preview each format, upload the reel and infographic to Cloudinary and paste the URLs into Heroku config vars, pilot with `SURVEY_BATCH=pilot`, switch to `main`, download the CSV from admin, and the go-live checklist below.

## Go-live checklist (do NOT switch to live until all are done)

- [ ] Ethics approval from Bath Spa for collecting data on adhenzmiranda.com
- [ ] Rotate the leftover secrets: Cloudinary key and secret, admin URL, Neon password, `SECRET_KEY`
- [ ] Real researcher email and ethics contact in the config vars, and the consent wording checked against Bath Spa's ethics template
- [ ] Check where the Neon database is hosted (region) for the ethics form's data storage question
- [ ] Final reel and infographic uploaded; reel tested on a phone with sound off
- [ ] Pilot with a few people on phones using `SURVEY_BATCH=pilot`, then set it to `main`
- [ ] Back up the database before and during data collection (`scripts/backup_live_site.py`), and keep CSVs out of the repo

## Two things for Adhenz to note (not code)

1. OpenAI's help pages (checked 16 Nov 2026) confirm tips 4 and 5: Temporary Chats aren't used for training and are deleted after 30 days, and training is turned off under Settings, Data Controls, "Improve the model for everyone". For tip 6, OpenAI now shows memory as a "memory summary" and gives the path as either Settings > Personalization > Memory or Settings > Memory. The tip still works, but the memory mock in prompts 7 and 8 looks like the older "saved memories" list. Fine for the study; worth one line in the methods.
2. The demo's Back button bug above also exists in the claude.ai sample survey. Fix it there too if that version gets shown to the professor again.

## Working style

- Plain words, no em dashes, no "it's not X, it's Y" lines in any copy.
- British spelling in participant-facing text.
- Don't change the script, prompts or rating statements; they are locked for the dissertation.
- One branch, one PR, then Adhenz merges.
