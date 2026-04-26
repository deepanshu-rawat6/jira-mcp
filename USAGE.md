# Usage Guide — Jira & Confluence MCP Server

This guide walks through real-world scenarios you can run with kiro-cli after setting up the `atlassian-unlocked` MCP server.

**Prerequisites:** Server installed and running. See [README.md](README.md) for setup.

Switch to the agent before starting any scenario:
```
/agent atlassian-unlocked
```

---

## Table of Contents

1. [Daily Standup — What am I working on?](#1-daily-standup)
2. [Bug Triage — Find, inspect, and assign bugs](#2-bug-triage)
3. [Sprint Planning — Create and link issues](#3-sprint-planning)
4. [Code Review Workflow — Comment and transition issues](#4-code-review-workflow)
5. [Confluence Knowledge Base — Search, read, and update docs](#5-confluence-knowledge-base)
6. [Release Notes — Generate and publish to Confluence](#6-release-notes)
7. [Cross-tool Workflow — Link Jira tickets to Confluence pages](#7-cross-tool-workflow)
8. [Safety Gating in Action — What confirmation looks like](#8-safety-gating-in-action)

---

## 1. Daily Standup

**Goal:** Quickly see what you're working on and what's blocked.

### What to ask

```
Find all issues assigned to me that are In Progress
```

```
Show me everything I updated in the last 2 days in the ENG project
```

```
Are there any issues blocking ENG-450?
```

### What happens

`jira_search` runs automatically (🟢 auto-approved). No confirmation needed.

### Example JQL kiro will use

```
assignee = currentUser() AND status = "In Progress"
project = ENG AND assignee = currentUser() AND updated >= -2d
```

### Sample output

```
Found 3 issue(s) (showing 3):
  ENG-450: Fix login timeout on mobile
    Status=In Progress  Assignee=You  Priority=High
  ENG-448: Update password reset flow
    Status=In Progress  Assignee=You  Priority=Medium
  ENG-441: Refactor auth middleware
    Status=In Progress  Assignee=You  Priority=Low
```

---

## 2. Bug Triage

**Goal:** Find open bugs, inspect details, add labels, and reassign.

### Step 1 — Find all open bugs

```
Show me all open bugs in the ENG project, ordered by priority
```

kiro runs `jira_search` with:
```
project = ENG AND issuetype = Bug AND status != Done ORDER BY priority ASC
```

### Step 2 — Inspect a specific bug

```
Get the full details of ENG-512
```

kiro runs `jira_get_issue("ENG-512")` — returns description, status, assignee, labels, and the last 3 comments.

### Step 3 — Add a triage label (auto-approved)

```
Add the label "needs-repro" to ENG-512
```

kiro runs `jira_add_label("ENG-512", "needs-repro")` automatically. No confirmation needed.

### Step 4 — Reassign the bug (requires confirmation)

```
Update ENG-512 to assign it to account ID 5b10a2844c20165700ede21g
```

kiro will say:
> I'm about to update ENG-512 — set assignee to account ID `5b10a2844c20165700ede21g`. Confirm?

After you say **yes**, it calls `jira_update_issue`.

### Step 5 — Add a comment (auto-approved)

```
Add a comment to ENG-512: "Reproduced on iOS 17.4. Assigning to mobile team."
```

Runs immediately, no confirmation.

---

## 3. Sprint Planning

**Goal:** Create a set of issues for an upcoming sprint and link them to an epic.

### Step 1 — Create a story (requires confirmation)

```
Create a story in ENG titled "Add OAuth2 support to the API gateway", medium priority, with description "Implement OAuth2 client credentials flow for service-to-service auth"
```

kiro will say:
> I'm about to create a new Story in project ENG:
> - Summary: "Add OAuth2 support to the API gateway"
> - Priority: Medium
> - Description: "Implement OAuth2 client credentials flow..."
>
> Confirm?

After **yes**, kiro calls `jira_create_issue` and returns:
```
Created ENG-601: https://yourcompany.atlassian.net/browse/ENG-601
```

### Step 2 — Create a sub-task

```
Create a task in ENG titled "Write unit tests for OAuth2 token validation", high priority
```

Same confirmation flow → creates ENG-602.

### Step 3 — Link the issues (requires confirmation)

```
Link ENG-602 to ENG-601 as "is blocked by"
```

kiro confirms:
> I'm about to create a link: ENG-602 is blocked by ENG-601. Confirm?

After **yes**, calls `jira_link_issues`.

### Step 4 — Verify the links

```
Show me the details of ENG-601
```

Returns the issue with its linked issues visible in the output.

---

## 4. Code Review Workflow

**Goal:** Move issues through the workflow as code is reviewed and merged.

### Step 1 — Find issues ready for review

```
Find all ENG issues in "In Review" status
```

### Step 2 — Add a review comment (auto-approved)

```
Add a comment to ENG-580: "LGTM — approved. Merging after CI passes."
```

Runs immediately.

### Step 3 — Transition to Done (requires explicit confirmation)

```
Move ENG-580 to Done
```

kiro will say:
> 🔴 DESTRUCTIVE action: I'm about to transition ENG-580 from "In Review" to "Done". This will trigger any associated automations.
>
> Please confirm by saying **yes, move ENG-580 to Done**.

You must respond with something explicit like:
```
yes, move ENG-580 to Done
```

kiro then calls `jira_transition_issue("ENG-580", "Done")` and returns:
```
Transitioned ENG-580: 'In Review' → 'Done'.
```

### What if the transition name is wrong?

```
Move ENG-580 to "Completed"
```

kiro returns:
```
Transition 'Completed' not found for ENG-580.
Available transitions: To Do, In Progress, In Review, Done
```

Use one of the listed names exactly.

---

## 5. Confluence Knowledge Base

**Goal:** Find, read, and update internal documentation.

### Step 1 — Find what spaces exist

```
List all Confluence spaces I have access to
```

`confluence_list_spaces` runs automatically. Returns space keys, names, and URLs.

### Step 2 — Search for a page

```
Search Confluence for pages about "deployment runbook"
```

kiro runs `confluence_search` with CQL:
```
text ~ "deployment runbook" AND type = page
```

Returns matching pages with IDs, spaces, and URLs.

### Step 3 — Read a page

```
Get the content of Confluence page 123456
```

`confluence_get_page("123456")` runs automatically. Returns the page title, metadata, and body as plain text (HTML stripped).

### Step 4 — Add a comment to a page (auto-approved)

```
Add a comment to page 123456: "Updated the staging section — see ENG-590 for context."
```

Runs immediately, no confirmation.

### Step 5 — Update a page (requires explicit confirmation)

```
Update Confluence page 123456 titled "Deployment Runbook" with this content:
## Overview
This runbook covers deploying the auth service to production.

## Steps
1. Run `make deploy ENV=prod`
2. Monitor Datadog for 10 minutes
3. Verify health check at /health
```

kiro will say:
> 🔴 DESTRUCTIVE action: I'm about to **replace all content** of page "Deployment Runbook" (ID 123456). This cannot be undone automatically.
>
> Please confirm by saying **yes, update page 123456**.

After explicit confirmation, calls `confluence_update_page` with the new content and increments the version number automatically.

---

## 6. Release Notes

**Goal:** Pull completed issues from a sprint and publish release notes to Confluence.

### Step 1 — Find completed issues

```
Find all ENG issues completed in the last 7 days
```

kiro uses:
```
project = ENG AND status = Done AND updated >= -7d ORDER BY updated DESC
```

### Step 2 — Get details on key issues

```
Get details on ENG-580, ENG-575, and ENG-560
```

kiro calls `jira_get_issue` three times and summarises.

### Step 3 — Create a release notes page (requires confirmation)

```
Create a Confluence page in space ID 98765 titled "Release Notes — v2.4.1" with this content:
## What's New
- ENG-580: Fixed login timeout on mobile (High priority)
- ENG-575: Added OAuth2 support to API gateway
- ENG-560: Improved password reset flow

## Bug Fixes
- ENG-512: Resolved iOS 17.4 auth crash

## Notes
Deployed to production on 2026-04-26.
```

kiro confirms:
> I'm about to create a new Confluence page:
> - Space ID: 98765
> - Title: "Release Notes — v2.4.1"
>
> Confirm?

After **yes**, creates the page and returns its URL.

---

## 7. Cross-tool Workflow

**Goal:** Connect Jira work to Confluence documentation in one session.

### Scenario: You're starting a new feature

```
1. Search Confluence for any existing design docs for "auth service refactor"
```
→ `confluence_search` runs automatically.

```
2. Get the content of page 445566 (the existing design doc)
```
→ `confluence_get_page` runs automatically.

```
3. Create a Jira epic in ENG titled "Auth Service Refactor Q2" with description "See Confluence page 445566 for design"
```
→ kiro confirms → `jira_create_issue` with type Epic.

```
4. Create 3 stories under that epic for: API layer, DB migrations, and integration tests
```
→ kiro confirms each → creates ENG-610, ENG-611, ENG-612.

```
5. Add a comment to Confluence page 445566: "Jira epic created: ENG-610. Stories: ENG-611, ENG-612, ENG-613."
```
→ `confluence_add_comment` runs automatically.

---

## 8. Safety Gating in Action

This section shows exactly what the confirmation flow looks like for each tier.

### 🟢 Auto-approved — no prompt

```
You: Find all open bugs in ENG
kiro: [calls jira_search immediately]
      Found 12 issue(s)...
```

```
You: Add a comment to ENG-123 saying "Fixed in PR #456"
kiro: [calls jira_add_comment immediately]
      Comment added to ENG-123 (id=10234).
```

### ⚠️ WRITE — AI confirms before calling

```
You: Create a bug in ENG titled "Null pointer in checkout flow"

kiro: I'm about to create a new Bug in project ENG:
      - Summary: "Null pointer in checkout flow"
      - Type: Bug
      
      Shall I proceed?

You: yes

kiro: [calls jira_create_issue]
      Created ENG-620: https://yourcompany.atlassian.net/browse/ENG-620
```

If you say **no** or change your mind:
```
You: actually make it a Story not a Bug

kiro: Got it. I'll create a Story instead.
      Creating Story in ENG: "Null pointer in checkout flow"
      Confirm?
```

### 🔴 DESTRUCTIVE — explicit confirmation required

```
You: Move ENG-620 to Done

kiro: 🔴 This will transition ENG-620 from its current status to "Done" and
      may trigger automations or notifications.
      
      To confirm, please say: yes, move ENG-620 to Done

You: yes move it

kiro: I need explicit confirmation. Please say exactly:
      "yes, move ENG-620 to Done"

You: yes, move ENG-620 to Done

kiro: [calls jira_transition_issue]
      Transitioned ENG-620: 'In Progress' → 'Done'.
```

Vague responses are not accepted for destructive actions. The agent is instructed to require the resource name in the confirmation.

---

## Tips

**Finding a page ID:** Open the page in your browser. The URL looks like:
```
https://yourcompany.atlassian.net/wiki/spaces/ENG/pages/123456/Page+Title
                                                           ^^^^^^
                                                           This is the page ID
```

**Finding an account ID for assignee:** Ask kiro to search for the issue currently assigned to that person, then get the issue — the assignee's account ID is in the raw data. Or use the Jira user picker in the browser and inspect the network request.

**CQL examples for Confluence search:**
```
space = ENG AND title ~ "runbook"
type = page AND text ~ "kubernetes" AND space = DEVOPS
label = "architecture" AND lastModified >= "2026-01-01"
```

**JQL examples for Jira search:**
```
project = ENG AND sprint in openSprints()
assignee = currentUser() AND status != Done
priority = High AND created >= -7d AND project = ENG
issuetype = Bug AND labels = "regression"
```
