# Good morning, JasMehr

Athena is being built. This file is kept up to date as work finishes.

## What's ready
- **The app works**: Today, Subjects, Learn, Review (flashcards), Practice (quick quiz, answer writing, case practice, timed mock papers), Plan (calendar and .ics export), Insights, Library (search), Sources and Settings.
- **Lessons for all 28 decks** (152 topics, 642 lesson parts, 1,729 check questions, 1,022 flashcards, 374 professor examples), every one checked against your slides:
  - AIB: Sessions 2, 3 to 4, 4 to 5, and Chapters 2 to 3
  - BE: Sessions 1 to 2, 3, and 4 to 5
  - FAR: Concepts and Dr/Cr rules, the five elements (session discussion and the framework pages), Maynard cases A and B
  - MM: Sessions 1, 2 and 3
  - OML: Introduction to OB, People Express (case page and slides)
  - QTM: Modules 1, 2.1, 3, 4, 5 and 6
  - SCE: Introduction to Entrepreneurship, Social Entrepreneurship, business ideas list, pitching template
  - SiP-I: Organization selection presentation
- Where a practice question on a slide has no printed answer, the lesson works it out with the deck's own method.
- **Exam question banks for every subject**: 1,561 questions (787 multiple choice, 451 short answers, 285 long answers, plus differentiate and case questions), each written answer with a model answer and the key points to tick. AIB 365, BE 209, FAR 100, MM 130, OML 100, QTM 492, SCE 158, SiP-I 7. Answer writing, case practice and timed mock papers now all work. FAR numbers were rechecked one by one.
- **FAR exam on 27 Oct** is in the planner, so Today puts FAR first and saves the last two days for revision and a mock paper.
- When you finish a topic, Athena shows any past-paper questions on it, the frameworks it uses, and a button to practise exam answers.
- **Online copy**: https://athena-peach-iota.vercel.app (handy on your phone; progress there is not kept, so study on the PC app for real).
- **Ask your professor** (slide mistakes the lessons point out in one line):
  - BE s1-2 slide 58 prints MR = 50Q - 2Q (should read 50 - 2Q).
  - BE s3: the slide 14 graph and the slide 13 table give different numbers.
  - BE s4-5 slide 20: rearranging Qxs = 10 + 2Px gives Px = 0.5Qxs - 5, not the printed 5 + 0.5Qxs.
  - QTM Module 3: slide 14 writes 29.5% as 0.2905; slide 32 asks P(X >= 9) but works out P(X > 9).
  - QTM Module 6 slides 8, 9, 11: the critical t values were typed over, and the decision lines use the old values (the decision does not change).
  - QTM Module 5 slide 30: the coffee example uses a t test with a known population SD and says "Reject H1".
  - AIB: ChatGPT, Gemini and Watson are early AGI on one slide and ANI on others; UBI means two different things on slides 37 and 40; Era 5 starts 2022 on one slide and 2018 on another.
- All 28 decks are read in with a picture of every slide; past papers typed in (BE MST 2025, SCE MST 2025, EMDM MST 2023, your AIB tutorial sheet); a session map for 7 subjects.
- Reminders, Google Classroom sync and the refresh spec are built but not switched on.

## How to open Athena
Double-click **Open Athena** at the top of the Athena folder. It opens http://127.0.0.1:8765 in your browser. Keep that window open while you study.

To keep it one click away, right-click **Open Athena** and choose **Pin to Start**, or **Show more options**, then **Pin to taskbar**.

## Needs you
1. **Your other end-semester exam dates.** Only FAR (27 Oct) is in. Type the rest in Athena's Settings page, or drop the datesheet into `inbox\_exams\`. Until then the planner spreads the other subjects evenly.
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
   1. Go to console.cloud.google.com and sign in with your Thapar account.
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
- EMDM and ES-I have no slides here, so they have no lessons or questions. Add their slides to `inbox\` and run a refresh.
- QTM has no past papers or pattern file, so its mock papers use a standard MBA layout.
- "Extra help" YouTube picks (429 videos, 3 per topic) were chosen by search, not watched: some may be in Hindi or only loosely on topic. They are labelled "Extra help, not exam source"; exams follow your slides.
- 24 of the 44 past-paper questions cover things none of the slides here teach (for example the business model canvas, elasticity, backpropagation). The Library's Past papers tab marks them; those are the slides to get from Classroom first.

## How to continue
Run `.\run-overnight.ps1` again to resume, or `.\run-overnight.ps1 -Spec REFRESH.md` after adding PPTs.
