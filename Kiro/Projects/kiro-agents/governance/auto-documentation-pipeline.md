# Auto-Documentation Pipeline — OrthoFlow

## Purpose
Automatically keep product documentation, marketing site, and brochure content in sync with deployed features. Triggered after successful feature deployments or on a weekly schedule.

## Trigger Conditions
1. **Post-deploy trigger**: When Watchtower updates containers AND CI passes, the documentation agent reviews the last N commits for feature additions/changes
2. **Weekly schedule**: Every Monday at 9 AM ET, run a full documentation audit
3. **Manual trigger**: `/task-internal orthoflow-ai: update documentation` via Slack

## Documents to Update

### 1. Product Overview (OrthoFlow/docs/specs/PRD.md)
- Feature list with current status (shipped/beta/planned)
- Module descriptions matching actual UI sections
- Technical capabilities list

### 2. Clinical Documentation (orthoflow-ai/OrthoFlow_Product_Overview_Clinical.md)
- Clinical features for orthodontic practices
- Workflow descriptions (patient flow, scheduling, charting)
- MyOrthoChart patient portal capabilities

### 3. Marketing Site Content (orthoflow-marketing/)
- Feature sections matching deployed capabilities
- Pricing page accuracy
- Comparison charts vs competitors

### 4. Brochure Content (orthoflow-brochure/)
- One-pager feature highlights
- Screenshot descriptions

## Documentation Rules
1. **Only document what exists and runs today** — never aspirational content
2. **Ortho-only** — no General Dentistry, Perio, Cosmetic references (those are future epic)
3. **Pricing must match**: Starter $299, Clinical $599, Enterprise $999
4. **Self-hosted infrastructure** — never reference AWS/Azure/cloud providers
5. **Match the UI terminology** — use exact labels from the sidebar and page headers

## Current Feature Set (as of August 2026)

### OrthoFlow (Staff App)
- **Dashboard**: Patient flow board (Lobby→Seated→Checked Out→Dismissed), Today's Huddle, day switching
- **Schedule**: Daily view by chair, drag-and-drop, check-in, dismiss, cancel, send reminder, virtual visit start
- **Patients**: Full patient list with search, treatment phase badges, flow status, delete, expandable info
- **Patient Chart**: Ortho tooth chart (brackets, wires, elastics, appliances), clinical notes, treatment phase, Next Visit planning
- **Invisalign**: Case management, ClinCheck workflow, stage tracking, provider account connection (Align Technology)
- **Appliances**: Lab management, prescription tracking, new order form with patient/lab/needed-by
- **CDT Codes**: 129 codes (88 common), searchable catalog
- **Finance**: Ledger, Invoices (AI classification 97-99%), Insurance, Claims (submitted/paid/denied), Payments, TC Proposals (with PDF print)
- **Communications**: Patient messages, staff chat (AI auto-reply), scheduled/automated messages, appointment reminders
- **Virtual Visits**: LiveKit video calling, staff initiates, patient joins from portal
- **Reports**: Financial (production, collections, AR aging, provider productivity) + Consultant (treatment starts, missing appts, observation, pending, overdue payments)
- **Invisalign**: Case management connected to Align Technology Doctor Site

### MyOrthoChart (Patient Portal)
- **Navigation**: Hamburger menu (Home, Schedule, Messages, Visits, Billing, Forms, Settings)
- **Home**: Treatment progress with milestones, quick actions, virtual visit join, paperwork notifications
- **Schedule**: Multi-step appointment booking (reason→provider→confirmation), reschedule
- **Messages**: Categorized (Conversations, Appointments, Automated), compose new
- **Visits**: Future visits with "It's time!" banner, past visit history, virtual vs in-person
- **Billing**: Balance due, responsible party, insurance card, manage payment methods
- **Forms**: 6 structured forms (Intake, Medical History, Consent, Financial, HIPAA, Photo/X-ray)
- **Settings**: Account info, notification preferences, privacy

### Roles
- Owner: Full access
- Doctor: Full access (can do everything from one account)
- Office Manager: Full access
- Dental Assistant: Clinical + Communications
- Front Desk: Scheduling + Finance + Communications
- Consultant: Reports access (practice optimization)
- Patient: MyOrthoChart portal

## Execution Steps

When triggered, the documentation agent should:

1. Read the current git log for recent feature commits
2. Compare against the current docs to find gaps
3. Update PRD.md with new/changed features
4. Update clinical doc with workflow changes
5. Flag marketing/brochure content that's outdated
6. Commit and push documentation changes
7. Post summary to Slack

## Agent Assignment
- **Primary**: code-agent (documentation generation)
- **Review**: qa-agent (verify accuracy against running app)
- **Deploy**: deploy-agent (if marketing site content changes)
