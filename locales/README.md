# Localization

Language metadata lives in `languages.json`. Add a matching UTF-8 JSON catalog
to make a language available in the frontend selector and backend messages.
`pt-BR.json` provides Brazilian Portuguese; the generic `pt` tag and common
case/underscore variants resolve to that catalog. English remains the default
and fallback in this fork. The selector lists English, Chinese, then Brazilian
Portuguese, and remembers the user's choice in the browser.

Keep the same keys, array structure and `{placeholders}` in every catalog.
Translate complete messages rather than assembling fragments in English word
order. Leave API field names, enum values, tool names and protocol markers
unchanged. Display labels can be translated without changing those identifiers.

Brazilian Portuguese uses **grafo de conhecimento** for knowledge graph,
**dados de referência** for seed material, **perfil do agente** for persona,
and **rodada** for a simulation round. Distinguish time inside the simulated
scenario from elapsed execution time. Use natural Brazilian phrasing in actions,
empty states and errors instead of literal translations of the English copy.

`llmInstruction` controls generated natural-language text while preserving JSON
keys and required formatting. The optional `outputLanguage` is passed to newly
created OASIS/CAMEL agents before they interact. Selecting a language does not
translate previously saved reports or source documents.

This fork imports the contextual translation from Ewerton Lourenço's upstream
[PR #956](https://github.com/666ghj/MiroFish/pull/956), commit
`b9b3ca1be8958175c6ab4be3c70afc4dc025daef`, and adds translations for article
URLs, local AI configuration and graph retry controls.

Validation (no external API calls):

```sh
cd frontend
node --test tests/i18n.test.mjs
npm run build
cd ../backend
uv run pytest tests/test_localization.py
```
