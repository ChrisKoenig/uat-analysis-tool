# Field Portal User Guide

How to use the Field Submission Portal to submit issues, review AI analysis,
search for related features, and create UAT work items.

Last Updated: February 23, 2026

---

## Getting Started

Open the Field Portal in your browser:

```
http://localhost:3001
```

You will be prompted to sign in with your Microsoft account. Click
**"Sign in with Microsoft"** to authenticate via Entra ID.

After signing in, your name appears in the header and the wizard begins at
Step 1.

---

## Wizard Overview

The portal is a 9-step guided wizard. A progress stepper at the top of every
page shows where you are:

```
1. Submit → 2. Quality → 3. Analysis → 4. Review → 5. Search → 6. IDs → 7. Related → 8. Select → 9. Created
```

- The **current step** is highlighted.
- **Completed steps** show a ✓ checkmark and are clickable — you can go back to
  any completed step without losing your data.

---

## Step 1 — Submit an Issue

Enter the details of the issue you want to submit.

| Field | Required | What to enter |
|-------|----------|--------------|
| **Issue Title** | Yes | A specific, descriptive title. Include the Azure service or product name. |
| **Customer Scenario / Description** | Yes | Describe what the customer needs, why, and any technical details. Minimum 5 words recommended. |
| **Business Impact** | Recommended | Describe the business impact if the issue is not resolved. |

**Tips for a good submission:**
- Be specific in the title — "*Azure Route Server capacity request for East US
  region*" is better than "*Capacity issue*".
- Include customer context, deal size, and timeline in the description.
- Always fill in Business Impact — it significantly improves AI classification
  accuracy.

Click **"Submit for Analysis"** when ready. A loading overlay appears while the
system evaluates your input quality.

---

## Step 2 — Quality Review

The system scores your input quality on a 0–100 scale.

### Score Outcomes

| Score | Color | What happens |
|-------|-------|-------------|
| **80–100** | Green | **Good Quality** — your input meets standards. You can continue immediately. |
| **50–79** | Amber | **Improvement Suggested** — you can continue, but adding more detail will improve analysis accuracy. |
| **Below 50** | Red | **Submission Blocked** — you must update your input before continuing. |

### Quality Breakdown

Four dimensions are scored individually (0–25 each):

| Dimension | What it measures |
|-----------|-----------------|
| **Title Clarity** | Is the title specific and descriptive? |
| **Description Quality** | Does the description include sufficient context? |
| **Business Impact** | Is the business impact explained? |
| **Actionability** | Can someone act on this information? |

Each dimension shows its score, a label (Good / Fair / Needs Work), and a
reason sentence explaining the rating.

### Your Options

| Button | What it does |
|--------|-------------|
| **← Update Input** | Go back to Step 1 with your fields pre-filled to revise |
| **Continue to Analysis →** | Proceed to AI analysis (disabled if blocked) |
| **Cancel** | Discard and start over |

---

## Step 3 — AI Analysis (Loading)

The system runs AI context analysis on your submission. This typically takes
10–15 seconds. A spinner is displayed while processing.

On completion, you are automatically taken to the Analysis Results page.

If analysis fails, an error message is shown with a **"← Start Over"** button.

---

## Step 4 — Review Analysis Results

This is the most important step. The system presents its AI classification
for your review.

### What You'll See

- **Category** — the type of issue (e.g., Technical Support, Feature Request,
  AOAI Capacity).
- **Intent** — what the submitter is trying to accomplish (e.g., Seeking
  Guidance, Capacity Request).
- **Business Impact** — Low, Medium, High, or Critical.
- **Confidence** — how confident the AI is in its classification (0–100%).
- **Source** — whether the classification came from AI ("llm") or pattern
  matching ("pattern").
- **Context Summary** — a brief description of the issue in the AI's words.
- **Key Concepts** — detected keywords and topics.
- **Products** — detected Microsoft products and Azure services.

### AI Offline Warning

If the AI service was unavailable, you'll see a yellow banner: **"AI
Classification Unavailable — Pattern Matching Used."** Pattern matching is less
accurate. You can click **"🔄 Retry with AI"** to attempt AI classification
again.

### Reviewing the Classification

You have three options:

| Button | When to use |
|--------|------------|
| **"Looks Good — Continue →"** | The classification is correct. Proceeds to search. |
| **"Modify Classification"** | The classification needs correction. Opens the correction form. |
| **"Reject & Start Over"** | The submission itself is wrong. Discards and returns to Step 1. |

### Correcting the Classification

If you click **"Modify Classification"**, a correction form appears with:

| Field | Options |
|-------|---------|
| **Correct Category** | technical_support, feature_request, cost_billing, capacity, aoai_capacity, service_request, information, general — or keep current |
| **Correct Intent** | escalation, information, action_required, consultation, feature_request, general — or keep current |
| **Correct Business Impact** | Low, Medium, High, Critical — or keep current |
| **Notes** | Free text explaining why the classification is wrong |

Then choose:

| Button | What it does |
|--------|-------------|
| **"Reanalyze with Corrections"** | Re-runs AI analysis with your hints. The page refreshes with new results. |
| **"Save Corrections & Continue"** | Saves your feedback for model learning and moves to the next step. |
| **"Cancel Edits"** | Collapses the correction form without saving. |

> **Your corrections matter.** Every correction is stored and used to improve
> the AI's accuracy over time.

### Detailed Analysis View

Click **"🔍 See Detailed Analysis"** for a deep dive including:

- Full AI reasoning (classification reasoning, pattern analysis steps,
  confidence breakdown).
- Data sources consulted (which data sources were used, available, or skipped).
- Domain entities: Azure Services, Technologies, Technical Areas, Regions.
- Recommended search strategy flags.
- The same approve/correct workflow as the summary view.

---

## Step 5 — Search Results

The system searches Microsoft Learn, TFT features, and other resources based
on your issue.

### Category-Specific Guidance

Depending on the classified category, you may see guidance banners:

| Category | Guidance |
|----------|---------|
| **Technical Support** | Consider opening a CSS Compass support case; work with your CSAM for reactive escalation. |
| **Billing** | Billing is out of scope — use the GetHelp portal. |
| **AOAI Capacity** | Review AOAI capacity guidelines; complete from Milestone in MSX. |
| **General Capacity** | AI capacity → AI Capacity Hub; Non-AI → SharePoint guidelines. |
| **Feature Request** | Tracked in TFT system — select matching features below. |

### Microsoft Learn Resources

Documentation links are shown with titles and descriptions. Click any title to
open the article in a new tab. The first 3 are shown by default; click
**"Show more"** to see all.

### Related TFT Features (Feature Requests)

For feature requests, a collapsible section shows related TFT features
ranked by similarity. The search uses the **ADO Work Item Search API**
(same engine as UAT search) with a 3-phase strategy:

1. **Phase 1** — Search by AI-detected service names + ServiceTree-resolved names
2. **Phase 2** — Search by the full issue title
3. **Phase 3** — WIQL broad fallback (newest features, no keyword filter)

Results are scored using 5 signals: service-name overlap (30%),
title similarity (25%), token overlap (20%), description match (15%),
and exact-match boost (10%).

- Each feature shows an ID (clickable link to ADO), title, match percentage,
  similarity bar, description preview, and state badge.
- **Check the boxes** next to features you want to link to your UAT.
- Features are sorted by relevance (highest match first).

Click **"Continue →"** when ready.

---

## Step 6 — Opportunity & Milestone IDs

Enter optional IDs to link the UAT to MSX:

| Field | Description | Example |
|-------|-------------|---------|
| **Opportunity ID** | MSX Opportunity identifier | 12345678 |
| **Milestone ID** | MSX Milestone identifier | MS-2026-001 |

These are recommended but not required. If you leave both blank and click
**Continue**, a warning appears. Click **Continue** again to skip.

---

## Step 7 — Searching for Similar UATs (Loading)

The system uses **AI-powered search** to find similar UATs in Azure DevOps from
the last 180 days. It leverages the AI analysis from Step 3 — detected Azure
services, technologies, and semantic keywords — to search using the ADO Work
Item Search API (full-text relevance ranking) instead of simple keyword
filtering.

A spinner is displayed while the 3-phase search runs:
1. Search by AI-detected service names (e.g. "Copilot Studio SharePoint")
2. Search by full issue title
3. Broad fallback if few results found

- If similar UATs are found → you proceed to Step 8 to review them.
- If no similar UATs exist → you still see Step 8 with a "No similar UATs
  found" message and can continue to create a new UAT.
- If the search fails → you can click **"Skip & Create UAT →"** to proceed
  anyway, or **"← Start Over"**.

---

## Step 8 — Select Related UATs

UATs are displayed in a **collapsible section** ranked by similarity (highest
first). Click the header to expand/collapse the list.

- Each UAT shows an ID (clickable link to ADO), title, match percentage,
  similarity bar, description preview, state badge, creation date, and assignee.
- **Select up to 5 UATs** to link to your new work item by checking their
  boxes. Click anywhere on a row to toggle the checkbox.

Then click:
- **"Create UAT with N linked →"** if you selected UATs.
- **"Create UAT →"** if you didn't select any.

---

## Step 9 — UAT Created

The system creates the UAT work item in Azure DevOps.

### Success

A green confirmation banner appears with:

- **Work Item ID** — clickable link to the new item in ADO.
- **State** and **Assigned To**.
- **Title**.
- **Opportunity ID** and **Milestone ID** (if provided).
- **Linked TFT Features** — list of linked feature IDs (if selected in Step 5).
- **Linked Related UATs** — list of linked UAT IDs (if selected in Step 8).

### What's Next

| Button | What it does |
|--------|-------------|
| **"Submit Another Issue"** | Resets the wizard and starts a new submission |
| **"View in Azure DevOps ↗"** | Opens the created work item in ADO |
| **"Done"** | Resets the wizard back to Step 1 |

### If Creation Fails

A red error banner appears with the error message. Click **"← Start Over"**
to begin again.

---

## Quick Reference

### Complete Flow Summary

```
Sign in → Enter issue details → Quality check → AI analysis →
Review/correct classification → Search resources → Enter IDs →
Find similar UATs → Link related items → UAT created in ADO
```

### When to Correct the AI

Correct the classification when:
- The **category** is wrong (e.g., labeled "Feature Request" but it's really
  "Technical Support").
- The **intent** is wrong (e.g., labeled "Seeking Guidance" but the customer is
  "Reporting Issue").
- The **business impact** is underestimated or overestimated.
- The **confidence is low** (<50%) — the AI is unsure and welcomes your input.

### Understanding Confidence Scores

| Range | Color | Meaning |
|-------|-------|---------|
| **80–100%** | Green | High confidence — classification is likely correct |
| **50–79%** | Amber | Medium confidence — review carefully |
| **Below 50%** | Red | Low confidence — correction is recommended |

### Understanding Match Percentages (Search Results)

When reviewing TFT features or similar UATs:

| Range | Color | Meaning |
|-------|-------|---------|
| **≥80%** | Green | Strong match — very likely related |
| **50–79%** | Amber | Moderate match — review to confirm |
| **Below 50%** | Red | Weak match — probably not related |

---

## Tips

- **Be descriptive in Step 1.** The more context you provide, the better the AI
  classification and the more relevant the search results.
- **Always fill in Business Impact.** It's not required but significantly
  improves the quality score and classification accuracy.
- **Review the AI classification carefully.** If it's wrong, correct it — your
  corrections train the model for future submissions.
- **Use "Reanalyze with Corrections"** if you want to see updated results
  immediately. Use "Save Corrections & Continue" if you just want to record the
  feedback and move on.
- **Link related features and UATs.** Linking helps the triage team see context
  and avoid duplicate work.
- **Bookmark the portal URL.** You can return to `http://localhost:3001` any
  time to start a new submission.
