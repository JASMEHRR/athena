# Good morning, JasMehr

Athena is being built. This file is kept up to date as work finishes.

## What's ready
- **The app works**: Today, Subjects, Learn, Review (flashcards), Practice (quick quiz, answer writing, case practice, timed mock papers), Plan (calendar and .ics export), Insights, Library (search), Sources and Settings.
- **Lessons for 7 of 28 decks** (29 topics, 109 lesson parts, 274 check questions, 182 flashcards, 71 professor examples), every one checked against your slides:
  - AIB: Session 2 (Adoption of AI)
  - FAR: Financial Accounting Concepts and Dr/Cr rules
  - MM: Session 1 (Introduction to Marketing)
  - OML: Introduction to OB
  - QTM: Module 1 (quantitative techniques, sampling, data types, scales)
  - SCE: Introduction to Entrepreneurship
  - SiP-I: Organization selection presentation
- **Still to write: 21 decks**, then the exam-style question banks (needed for answer writing and mock papers).
- All 28 decks are read in with a picture of every slide; past papers typed in (BE MST 2025, SCE MST 2025, EMDM MST 2023, your AIB tutorial sheet); a session map for 7 subjects.
- Reminders, Google Classroom sync and the refresh spec are built but not switched on.

## How to open Athena
Double-click **Open Athena** at the top of the Athena folder. It opens http://127.0.0.1:8765 in your browser. Keep that window open while you study.

To keep it one click away, right-click **Open Athena** and choose **Pin to Start**, or **Show more options**, then **Pin to taskbar**.

## Needs you
1. **Your end-semester exam dates.** I found no EST datesheet anywhere. When you get it, drop a photo or PDF into `inbox\_exams\` (or type the dates in Athena's Settings page once it's ready). Until then the planner spreads subjects evenly.
2. **Missing slides, by subject.** Your end-term exams mostly test the classes after the MST, and almost none of those slides are on this PC. Grab these from Classroom or your professors, and drop each subject's files into its own folder in `inbox\` (for example `inbox\Marketing Management\`):
   - **AIB:** sessions 6 onwards (AI vs ML vs DL vs NLP, data, classification, regression, clustering, Excel with AI, prompt engineering, AI in marketing, finance, HR, supply chain, KPIs).
   - **Business Economics:** elasticity, indifference curves and budget line, demand forecasting, production and cost, market structures.
   - **EMDM:** no slides at all. Also the official teaching plan PDF (`1b.BA5213_EMDM_TeachingPlan_MBA26-28.pdf` on Classroom).
   - **ES-I:** no slides and no syllabus.
   - **FAR:** sessions 1 to 5 and 11 to 23 (financial statements, ratio analysis, inventory, depreciation, cash flow, notes to accounts, Satyam, sustainability reporting).
   - **Marketing Management:** sessions 5 to 24, especially 13 to 24 (product, branding, pricing, distribution, communication), which is the whole EST.
   - **OML:** Module 2 (Foundations of Individual Behaviour), Module 3 (Personality), Module 4 (Perception and Attitude) from Classroom, plus motivation, groups, leadership, culture and change.
   - **QTM:** dispersion (Module 2.2), and Modules 7 to 10 (linear programming, assignment and transportation, decision theory).
   - **SCE:** everything after the introduction (challenges, personality, opportunities, ideas, business model canvas, forms of business, process, financing, business plan, e-business, ethics).
   - **SiP-I:** only the organization-selection template is here; add any SiP slides you have.
3. **Old past papers in your Downloads folder.** The 2025 MST papers for QTM, FAR, MM, OML, SiP-I and AIB were downloaded but never moved. Put them in `inbox\_pyqs\`.
4. **Four files I skipped because I wasn't sure your professor shared them:** `FAR\Havells India Ltd Analysis.pdf`, `FAR\CIN details.pdf`, `FAR\Reading 1_Conceptual Framework.pdf` (86-page reading), and the OML Robbins textbook. If any are from your professor and you want lessons from them, tell me.

5. **Optional: let Athena pull slides from Google Classroom.** Free, but it needs a one-time setup in your own Google account (about 10 minutes):
   1. Go to console.cloud.google.com and sign in with your Thapar account (jsingh_mba26@thapar.edu).
   2. Top bar: project picker, then **New project**, name it `Athena`, **Create**.
   3. Menu, **APIs & Services**, **Library**: search **Google Classroom API**, click **Enable**. Do the same for **Google Drive API**.
   4. **APIs & Services**, **OAuth consent screen**: choose **External** (or Internal if offered), app name `Athena`, your email in both email boxes, **Save and continue** through the screens.
   5. On **Test users**, click **Add users** and add your own email. (Warning: in Testing mode Google makes you sign in again every 7 days. That is normal.)
   6. **APIs & Services**, **Credentials**, **Create credentials**, **OAuth client ID**, application type **Desktop app**, **Create**, then **Download JSON**.
   7. Rename the downloaded file to `credentials.json` and put it in the `secrets` folder inside the Athena folder (create the folder if needed).
   8. Open PowerShell in the Athena folder and run `.venv\Scripts\python -m athena.sync_classroom`. A browser window asks you to allow read-only access. It downloads slides into `inbox\` and adds assignment due dates to the Plan calendar.
   Warning: your university may block third-party apps on Thapar accounts. If Google says the app is blocked, skip this and keep using the inbox folder.

6. **Optional: turn on study reminders.** Open PowerShell in the Athena folder and run `powershell -ExecutionPolicy Bypass -File scripts\install-reminders.ps1`. Undo with `scripts\uninstall-reminders.ps1`.

After adding files, run `.\run-overnight.ps1 -Spec REFRESH.md`.

## What I decided for you
- Lessons use only your slides. Where an exam topic has no slides, Athena says so instead of teaching it from elsewhere.
- Slide pictures come from the PowerPoint already on your PC (opened read-only).
- Details in DECISIONS.md.

## Known issues
- Only 7 decks have lessons so far, so Today's plan and quizzes cover those subjects only.
- No exam-style question bank yet, so Answer writing, Case practice and Mock paper say "no questions yet".
- "Extra help" YouTube picks are built but not fetched yet.

## How to continue
Run `.\run-overnight.ps1` again to resume, or `.\run-overnight.ps1 -Spec REFRESH.md` after adding PPTs.
