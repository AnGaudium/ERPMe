# NativeFlows

NativeFlows is a fully open-source ERP designed from the ground up for agentic workflows. It targets trading and manufacturing businesses (assembly included) worldwide, with CRM from day one. The accounting and inventory core follows the SAP model, every country-specific rule lives in a localization package, and the business core is fully deterministic: AI agents only propose, and the books never depend on an LLM being right.

**Status:** design phase (Build step 0). There is no code yet. The specification, decisions and design backlog are in [`docs/`](docs/README.md).

## Where to start

- Humans: read [docs/spec/01-vision.md](docs/spec/01-vision.md), then [docs/README.md](docs/README.md) for the full map.
- AI agents: read [AGENTS.md](AGENTS.md) first.

## License

The core will be licensed under AGPL-3.0; SDK and client libraries under Apache-2.0; documentation under CC BY-SA 4.0; the synthetic dataset under CC0. See [docs/spec/18-license-governance.md](docs/spec/18-license-governance.md). License texts: [LICENSE](LICENSE) (AGPL-3.0) for the repository, [docs/LICENSE](docs/LICENSE) (CC BY-SA 4.0) for the documentation in `docs/`. Further license files are added with the first SDK and the first synthetic dataset.
