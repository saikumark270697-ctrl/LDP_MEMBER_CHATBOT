# Liberty Dental Plan AI Chatbot POC

This is a Streamlit proof of concept for a Liberty Dental Plan public website AI chatbot.

## Scope

- Answers only from public website / Contentful-style content included in the POC.
- Helps users navigate member, provider, broker, teledentistry, grievance, and contact pages.
- Redirects account-specific questions to secure portals.
- Does not access personal member data, claims, eligibility, benefits, or secure systems.

## Run locally

Install dependencies:

```powershell
pip install -r requirements.txt
```

Start the Streamlit app:

```powershell
streamlit run app.py
```

## POC demo talking points

- This is a website advisory assistant, not an authenticated member support bot.
- The real implementation can connect to published Contentful content.
- The bot should only answer from approved website content.
- Secure/account-specific actions are redirected to existing Liberty portals.
- Guardrails are included for personal data, claims, eligibility, benefits, and medical advice.
