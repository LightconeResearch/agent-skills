# Lightcone repository map

File each report in one repository, chosen by the product the user was using.
Name it in the preview with a one-line reason.

| Feedback about | Repository |
| --- | --- |
| `lc`: setup, execution, environments, containers, provenance, cluster jobs | [lightcone-cli](https://github.com/LightconeResearch/lightcone-cli) |
| Lightcone Lab: Lab Home, JupyterLab integration, agent launch and chat, loading or refreshing files | [jupyterlab-lightcone](https://github.com/LightconeResearch/jupyterlab-lightcone) |
| The ASTRA format: fields, schema constraints, unclear specification, format changes | [astra-spec](https://github.com/LightconeResearch/astra-spec) |
| The `astra` CLI and Python package: validation, resolution, scaffolding, paper and evidence tools | [astra-tools](https://github.com/LightconeResearch/astra-tools) |
| Shared ASTRA UI components: rendering, layout, accessibility, dialogs, previews | [astra-ui](https://github.com/LightconeResearch/astra-ui) |
| Publications: MySTRA roles and directives, live values, MyST builds, themes and styling | [MySTRA](https://github.com/LightconeResearch/MySTRA) |
| Agent skills, plugins (this one included), hooks, agent guidance | [agent-skills](https://github.com/LightconeResearch/agent-skills) |
| A page on docs.lightconeresearch.org | [docs](https://github.com/LightconeResearch/docs) |

When the table doesn't settle it:

- **Lab symptoms** go to jupyterlab-lightcone; astra-ui only when the fault is
  clearly in how a shared component renders, not in loading or refreshing.
- **Docs** go where the page is published: docs.lightconeresearch.org → docs,
  astra-spec.org → astra-spec. Include the URL.
- **Several products**: file in the most affected one, name the others.
- **Unknown product**: ask what the user was using. There is no catch-all.
- **Suspected upstream cause** (astra-typescript, astra-theme, a third-party
  package): file with the product the user was using and give the suspicion as
  evidence. Those repositories are not destinations.
- **The user's own code** failing is not by itself a Lightcone defect. Describe
  what you saw without inventing a diagnosis.
