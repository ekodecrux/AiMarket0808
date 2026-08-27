# Autonomous Marketing Platform Component Assessment

## Knowledge-first retrieval candidate

[RAGFlow](https://github.com/infiniflow/ragflow) describes itself as an open-source RAG engine that combines a context engine with agent capabilities. Its documentation highlights deep document understanding, heterogeneous source ingestion, configurable embedding and LLM models, fused re-ranking, APIs, and grounded citations. This makes it a candidate for a future self-hosted knowledge layer that can retrieve approved marketing evidence before invoking a generation model. It should be evaluated as a service-side replacement or augmentation to the existing lightweight hybrid retrieval path rather than embedded in the mobile application.

## Forecasting and budget-analysis candidate

[PyMC-Marketing](https://www.pymc-marketing.io/en/stable/) is an open-source Python library for Bayesian marketing analytics. Its documentation states that it provides Marketing Mix Modeling and Customer Lifetime Value models with Bayesian uncertainty quantification, and includes budget optimization with channel allocation, saturation curves, and carry-over effects. It is a candidate for an offline or scheduled analytical service that produces confidence-bounded budget recommendations after sufficient clean historical data is available. It must not be represented as a guarantee of performance, and any spend-changing action should stay behind policy and user approval.

## Recommended architecture boundary

The mobile application should remain a guided operating surface. Connector credentials, source synchronization, embeddings, forecasting jobs, attribution data, and approval-policy enforcement belong in the existing backend or a dedicated service tier. The product should first reuse retrieved evidence and cached operating knowledge; it should only call a model for unresolved synthesis, content generation, or reasoning that cannot be served by deterministic workflows.

## Connector and workflow assessment

[n8n](https://docs.n8n.io/) documents self-hosted deployment, workflow construction, API endpoints, data transformations, execution tracking, and integrations. It is a potential service-side integration layer for provider OAuth callbacks, scheduled synchronization, and approval workflows; its licensing and provider-node fit must be reviewed before production adoption. The current task configuration exposes disabled options for Google Ads, Meta Ads Manager, Buffer, Metricool, Postiz, Publer API, and Publora. None should be silently enabled: each real account connection must proceed through the provider’s OAuth or API consent flow, with the business owner selecting scopes and confirming access.
