# SudoPrivacy maintenance branch

This branch starts from upstream Deep Agents 0.7.16, commit `0114a3f824cd5e626acb7b64d3c8e24468319d09`. Upstream history and MIT licensing are retained.

The maintained SDK changes package initialization so backend-only applications can start without constructing the agent graph or importing provider SDKs. Public objects continue to come from their original defining modules. First concurrent public imports are serialized to preserve import initialization.

Maintained artifacts use a distinct post-release version. Consumers pin the wheel URL and SHA256; the upstream version alone does not identify these bytes. Backend, graph, filesystem, shell and middleware implementations remain the upstream 0.7.16 implementations.

Upstream workflows are preserved under `.github/upstream-workflows/` and are inactive. This fork does not publish to upstream PyPI, run upstream paid evaluations or update upstream release branches. The maintained SDK workflow protects imports, API identity, registration and package installation on Linux and Windows.
