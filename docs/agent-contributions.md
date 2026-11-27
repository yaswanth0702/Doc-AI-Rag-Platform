# Agent contributions and release results

This report covers the release that added page-filtered PDF search, Markdown search exports, and Railway hosting. Four Codex agents worked on it. The names below are their roles in the development session.

## Who did what

| Agent | Work completed | Result |
| --- | --- | --- |
| Feature (`/root/feature`) | Added the optional PDF page field to Streamlit and the `/search` API, scoped exact and hybrid results to the selected page, and added regression tests. Configured the hosted UI to use its assigned backend URL. | Readers can search one PDF page or clear the field to search the entire document. |
| Packaging (`/root/packaging`) | Wrote the Dockerfile, build exclusions, and Python launcher for FastAPI and Streamlit. Tested startup, health checks, shutdown, and worker failure handling. | One container serves the UI. FastAPI listens on loopback, and the launcher passes the Gemini key only to the backend. |
| QA (`/root/qa`) | Ran the automated suite and tested the app in Chromium with two synthetic PDFs, locally and on Railway. Found a mismatch between the selected workspace and displayed view when switching documents. | Confirmed the navigation fix and verified the final hosted search and download flow. |
| Lead and integration (`/root`) | Implemented the Markdown search-results download and its regression test, fixed the navigation issue found by QA, merged the changes, and deployed the tested revision to Railway. | The export includes the query, search method, source text, and page references. The deployed revision passed the browser checks below. |

## What was verified

| Check | Environment | Observed result |
| --- | --- | --- |
| Automated regression suite | Local backend and Streamlit tests | **26 tests passed.** Gemini responses in the automated tests were simulated. |
| Page filtering | Deployed app in Chromium | On a two-page PDF, exact search on page 2 returned only the Friday passage. Hybrid search on page 1 returned the Monday passage. A missing page returned no hits, and clearing the filter restored results from both pages. |
| Markdown download | Deployed app in Chromium | The downloaded file contained the query, selected page, and matching passage. The passage from the other page was excluded. |
| Document switching | Deployed app in Chromium | After a second PDF was uploaded, the selected view matched the visible controls, and search returned only the second document’s content. |
| Mobile layout | Deployed app in Chromium at 390 px width | The tested view fit without horizontal scrolling. |
| Deployment | Railway production | Railway reported `SUCCESS`. The homepage and Streamlit health endpoint both returned HTTP 200 during the release check. |
| Live Gemini chat | Railway production | **Unverified.** The release checks did not generate an answer using a live Gemini API key. |

## Release links

- [Feature and deployment changes in PR #6](https://github.com/yaswanth0702/Doc-AI-Rag-Platform/pull/6)
- [Navigation fix in PR #7](https://github.com/yaswanth0702/Doc-AI-Rag-Platform/pull/7)
- [Tested application revision `f584ea5`](https://github.com/yaswanth0702/Doc-AI-Rag-Platform/commit/f584ea5241023486f59ad1099990182d548465d9)
- [Hosted DocIntel app](https://docintel-production-f54c5a66.up.railway.app)
