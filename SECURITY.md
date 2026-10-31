# Security

## Reporting a problem

Please do not open a public issue for a security problem. Use GitHub's private
"Report a vulnerability" option on the Security tab of this repository, or contact the maintainer
(NjeriCodeCraft) directly.

## What PRTriage does with data

- PR titles, descriptions and diffs are sent to the hosted Gemma 4 model through the Gemini API to produce a verdict.
- PR text is treated as untrusted. It is wrapped as data, the model is told not to obey it, and a code-side check
  downgrades PRs that try to manipulate the reviewer.
- Only public GitHub data is read. Author account age is shown in the page and is never sent to the model.
- API keys live in environment variables (`GEMINI_API_KEY`, optional `GITHUB_TOKEN`) and never in the repository.
- Triage endpoints are rate limited per client (`RATE_LIMIT_PER_MINUTE`).

## If a key leaks

Revoke it at https://aistudio.google.com/apikey (or in GitHub settings for a token), create a new one and update the host's environment variables.
