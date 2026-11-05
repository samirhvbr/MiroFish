# Start from an article URL (fork feature)

On Home, select **Article URL**, paste a public HTTPS article and click **Read article**. Inspect the title, retrieval time and extracted text. Choose a horizon in hours, then click **Generate / replace prompt** to use the existing LLM configuration. The summary and assumptions are AI-generated; review them and edit the normal **Simulation Prompt** field before clicking **Start Engine**. Regenerating replaces the prompt. You can also write your own prompt after reading the article.

Reading only retrieves HTML. Drafting only calls the configured LLM. Neither creates a project, creates a Zep graph, or runs a simulation. **Start Engine** continues the existing graph and simulation workflow with the reviewed source and edited question. The selected horizon is passed to configuration generation and takes precedence over the model's generated duration. The existing simulation run controls still apply.

## Supported sources

One public HTML article over HTTPS on port 443, with at most three redirects. Each destination must resolve entirely to public IP addresses; connections use those validated addresses while retaining TLS hostname verification. Credentials, local/private destinations, authenticated pages, paywall bypass, JavaScript rendering, crawling and web search are unsupported. No page scripts are executed. The importer requests uncompressed HTML and rejects other content types/encodings.

The importer uses a 20-second network deadline, a 2 MiB response limit and a 50,000-character extracted-text limit. It prefers `<article>`, then `<main>`, then ordinary page text, excluding common navigation/script/style containers. Extraction is deliberately simple: check the preview for missing or unrelated content. If extraction fails, try another URL or upload a document. No new packages or API keys are required.

## Snapshot and provenance

Previews are stored under `backend/uploads/source_previews` for 24 hours. Expired previews are removed on subsequent imports and cannot start new projects. Reading another URL does not reuse an earlier snapshot. Editing the URL invalidates its preview. Retrying prompt generation keeps the article available.

Starting a project copies the reviewed text into its `files` directory and `extracted_text.txt`; it does not fetch the page again. `project.json` stores the original/final URL, title, UTC retrieval time, SHA-256 of the UTF-8 text and relative text-file path in `sources`, plus the edited `simulation_requirement` and chosen `simulation_horizon_hours`. Older file-based projects retain their existing behavior.

API flow: `POST /api/graph/source/preview` with JSON `{ "url": "https://…" }`, then `POST /api/graph/source/<source_id>/draft` with `{ "horizon_hours": 72 }`. Only after user review, submit multipart `source_id`, `simulation_requirement` and `simulation_horizon_hours` to the existing `/api/graph/ontology/generate` endpoint. A project accepts either this snapshot or uploaded files.

## Validation

```sh
PYTHONPATH=backend python -m pytest backend/tests -q
node --test frontend/tests/*.test.js
npm run build --prefix frontend
```

Tests use synthetic HTML and simulated model/graph services. They do not validate paid LLM/Zep access or a full OASIS simulation.
