# Dissertation survey: setup and go-live guide

The survey lives at **adhenzmiranda.com/msc-survey/** and is built in the admin, like a Google Form with the experiment built in. Code: the `survey` app.

## How it works

1. **Consent page.** Information, your contacts and the tick boxes. Ticking all of them and pressing start creates a response row, so drop-outs per group can be counted.
2. **Pages, in order.** Each page is a "section" in the admin:
   - **Questions:** multiple choice, checkboxes, dropdown, 1 to 5 scale, short answer, paragraph, number
   - **Text only**
   - **"Would you send this?" (before):** the 8 prompts in a random order
   - **Random media:** each person sees one group, picked by the server so the groups stay even
   - **"Would you send this?" (after):** the same prompts in a new random order
3. **Thank-you page.** Your logo, message, share image and a Share button. The site's navbar and footer only appear here.

Built-in rules:
- Back only works before the media page, so nobody can change their "before" answers after seeing it.
- Matched prompts (same pair group, e.g. 1 and 6) are never next to each other.
- Scores are worked out on the server. A refresh resumes where the person was. A second visit from the same phone shows "You've already taken part".

**Status:**

| Status | What visitors see |
| --- | --- |
| Draft | Page not found. Only you can preview it. |
| Open | The survey. Responses are saved. |
| Closed | Your "not accepting responses" page. |

The survey won't open until the admin's **Ready to open?** list is empty. It needs both contacts, the ethics reference and media for every active group.

**Locking.** Once anyone has started, the questions, prompts, media and consent text are frozen, so every response answered the same survey. To change them, either delete the pilot responses (that unlocks it) or use the **Duplicate as a new version** action.

## Steps

### 1. Run it locally

1. `npm run dev`, then log in at http://127.0.0.1:8000/admin-dev/ (make a one-time code with `.venv\Scripts\python manage.py addstatictoken admin`).
2. Open **Dissertation survey > Surveys > Think Before You Prompt**.
3. Click **Preview (nothing is saved)**. Add `#video`, `#infographic` or `#text` to the preview link to see a specific group. The preview ends with a researcher view showing the scores.

### 2. Add your media

1. In the survey's **Conditions** (media groups):
   - **Short-form video:** upload the reel. Vertical 9:16 mp4, burned-in captions, up to 100 MB. Optionally add a still image to show while it loads.
   - **Infographic:** upload the image (1080 x 1350) and fill in **Alt text** with the full script.
   - **Text post:** already filled in from the script. Edit it if needed.
2. All three should carry the same script, so the format is the only difference between groups.
3. Optional: under **Thank-you page**, upload a share image (1080 x 1920). Keep the tips and answers off it, so friends who take the survey later aren't primed.
4. Optional: upload your own screenshot for any prompt. Otherwise the built-in mock-ups are used.

### 3. Fill in the details on the live admin

The contacts aren't in the code (the repo is public), so enter them once on the live admin:

1. **Researcher email:** your email.
2. **Ethics contact:** your supervisor's email.
3. **Ethics approval reference:** once Bath Spa approves.

### 4. Pilot

1. Check **Batch** is `pilot` (it starts that way).
2. Set **Status** to **Open** and share the link with a few people. They should use phones, and try the video with the sound off.
3. Watch **Progress** on the survey page. Then download the CSV (**Responses as CSV**) and check it.
4. If anything participants see needs changing: set Status to **Closed**, delete the pilot responses (**Responses**, filter by batch `pilot`, select all, delete), edit, and reopen. Or keep them and use **Duplicate as a new version**.

### 5. Main data collection

1. Change **Batch** to `main`. Group balancing counts each batch on its own.
2. Share the link. The **QR code** links on the survey page download a PNG or SVG. Add a tag (e.g. `rak-poster`) so the CSV's `source` column shows where each person came from. Links shared from the thank-you page are tagged `shared`.
3. Back up the database regularly: `python scripts/backup_live_site.py --no-media`.

### 6. Close and export

1. Set **Status** to **Closed**. Visitors then see your closed message.
2. On the survey page, click **Responses as CSV: completed only**. It opens in Google Sheets (File > Import) or Python:
   ```python
   import pandas as pd
   df = pd.read_csv('survey_responses_msc-survey_2027-01-15.csv', encoding='utf-8-sig')
   main = df[(df.batch == 'main') & (df.completed == 1)]
   main.groupby('condition').score_change.describe()
   ```
3. Keep CSV files out of the repo. `survey_responses_*.csv` is gitignored.

## CSV columns

| Column | Meaning |
| --- | --- |
| `participant_id`, `token` | Row id and the random id of the response (not linked to a person) |
| `survey`, `survey_version`, `batch`, `source` | Which survey and version, pilot or main, and the recruitment tag |
| `condition` | Media group: `video`, `infographic` or `text` |
| `started_at`, `completed_at`, `completed` | UTC times; `completed` is 1 or 0 |
| `age`, `gender`, `university`, ... | One column per question, named by its code. Checkbox answers are joined with `; `. |
| `<code>_passed` | Attention-check questions only: 1 passed, 0 failed |
| `before_p1` ... `before_p8` | Choice per prompt: `send`, `change` or `dont_send` |
| `before_p1_correct` ... | 1 if correct. Risky prompts: `change` or `dont_send`. Safe prompts: `send`. |
| `after_...` | The same for the second round |
| `before_score`, `after_score`, `score_change` | Out of 8. `score_change` is the main outcome. |
| `mean_engagement`, `mean_self_efficacy`, ... | Mean of the scale questions in each construct |
| `message_seconds` | Time on the media page (all groups) |
| `video_watched_seconds`, `video_finished` | Video group only |
| `total_seconds` | Consent to submit |
| `before_order`, `after_order` | Prompt numbers in the order shown |

## Methods wording

- "Participants were randomly assigned to one of three conditions using balanced allocation."
- Prompt order was randomised per participant for both rounds, with matched prompts never shown consecutively.
- No names, emails, student IDs, IP addresses or device details were collected. IP addresses are held briefly in memory for rate limiting only and are never stored.
- Data is stored in a Neon Postgres database hosted on AWS `us-east-2` (United States).

## Go-live checklist

Do not set the survey to Open until all of these are done.

- [ ] Ethics approval from Bath Spa for collecting data on adhenzmiranda.com, and the reference entered in the admin
- [ ] Rotate the leftover secrets: Cloudinary key and secret, admin URL, Neon password, `SECRET_KEY`, Gmail app password
- [ ] Researcher email and ethics contact entered on the live admin; consent text checked
- [ ] Data storage location (Neon, AWS us-east-2) given on the ethics form
- [ ] Final reel and infographic uploaded; reel tested on a phone with the sound off
- [ ] Pilot with a few people on phones using batch `pilot`, then switch to `main`
- [ ] Back up the database before and during data collection, and keep CSVs out of the repo
