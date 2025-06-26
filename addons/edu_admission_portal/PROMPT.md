You are a senior Odoo 17 Community developer and expert in XML-RPC, Webhooks, TDD, and modern UX/UI best practices. You will code a complete production-grade Odoo module from scratch.

---

📦 MODULE NAME: edu_admission_portal

🌐 CONTEXT:
The module must connect to LimeSurvey 6.13.0 (hosted locally via XAMPP) using:
- XML-RPC API (RemoteControl2) for form synchronization
- A custom webhook plugin that pushes real-time responses from LimeSurvey to Odoo (via POST JSON)

---

🎯 GOAL:
Create an automated, dynamic and admin-friendly admission platform:
- Dynamically import & manage admission forms from LimeSurvey
- Automatically receive responses with file uploads via webhook
- Create candidate records without manual field mapping (store unmatched fields as JSON)
- Use pipelines, document preview, email tools and dashboards

---

📁 PROJECT STRUCTURE TO GENERATE:

edu_admission_portal/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── limesurvey_server_config.py
│   ├── admission_form_template.py
│   └── admission_candidate.py
├── controllers/
│   └── webhook_controller.py
├── views/
│   ├── limesurvey_server_views.xml
│   ├── form_template_views.xml
│   ├── candidate_views.xml
│   └── menus.xml
├── security/
│   ├── ir.model.access.csv
│   └── security.xml
├── data/
│   └── cron.xml
├── tests/
│   └── test_admission_sync.py

---

✅ IMPLEMENTATION STEPS (code each in full, 1 file at a time)

1. [ ] Define `limesurvey.server.config` model:
  - Fields: name, base_url, api_username, api_password, connection_status, last_sync_date
  - Add button: “Test & Connect”
  - Upon success, auto sync forms using XML-RPC (list_surveys)

2. [ ] Define `admission.form.template` model:
  - Fields: sid, title, description, is_active, owner, sync_status
  - Sync from LimeSurvey dynamically via API
  - Store each form metadata in Odoo

3. [ ] Define `admission.candidate` model:
  - Fields: name, form_id (Many2one), response_data (JSON), attachments, status (selection)
  - Automatically created when webhook is triggered
  - Initial status: “new”
  - Use dynamic field storage for unmatched questions

4. [ ] Create REST controller: `/admission/webhook/submit`
  - Accepts JSON from LimeSurvey with token, form SID, answers, and file data
  - Validate token + prevent duplicates
  - Store file uploads in attachments with correct naming

5. [ ] Create views:
  - Server config form view with test connection button
  - Form template kanban & tree view with sync button
  - Candidate pipeline kanban with statuses: new → complete → shortlisted → invited → accepted/refused

6. [ ] Add helper UI features:
  - Document preview widgets (PDF/image inline)
  - Validation checkboxes (e.g. “payment confirmed”)
  - Email templates per step with tracking log per candidate

7. [ ] Add dashboard:
  - KPIs per campaign: applications count, status distribution, completion rate, etc.
  - Graphs and filters by form, criteria (e.g. BAC level), and export options

8. [ ] Add cron job to re-sync forms hourly (optional toggle)

9. [ ] Secure access rights:
  - Admin = full access
  - Reviewer = read-only + evaluation tools
  - Candidate = no access

10. [ ] Write TDD tests for:
  - XML-RPC sync
  - Webhook endpoint
  - Model creation and UI actions

---

🧠 BEST PRACTICES TO FOLLOW

- Use Odoo 17 ORM standards
- UI in French: all labels, views, and buttons
- Use domain-specific naming (sid, pipeline_status, extra_data)
- Group fields by section (base, sync, security, pipeline)
- Add tooltips and help texts where relevant
- Clean, production-ready, tested Python code
- UX: use sheets, groups, statusbadges, kanban colors, and actions smartly

---

Once done, generate and explain each file in sequence. Start by creating the `__manifest__.py` and `__init__.py` files for the module.

--- ADDITIONAL TASK ---

11. [ ] Generate a LimeSurvey plugin named `WebhookSubmit`:
- Built for LimeSurvey 6.13 (PHP)
- Hook into `afterSurveyComplete`
- Format responses and uploaded files into a JSON payload
- POST to Odoo endpoint: /admission/webhook/submit
- Include form SID, token, all responses, and base64-encoded files
- Handle error logging inside LimeSurvey
- Token must be read from plugin settings (admin-configurable)
- Fully documented plugin folder structure (config.xml, WebhookSubmit.php, views/)
