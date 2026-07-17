# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Security Properties & Threat Model

AgentGuard is a security and governance tool. Its primary threat model focuses on **Agentic Hallucination** and **Excessive Autonomy**.

### Threats Mitigated
1. **Tool Output Fabrication:** An LLM fabricating the results of a tool it never called.
2. **Error State Masking:** An LLM receiving an error from a tool but narrating it as a success to downstream nodes.
3. **Audit Trail Tampering:** Agents cannot modify the cryptographic receipts stored in DynamoDB, ensuring non-repudiation of tool executions.

### Trust Boundaries
- **Agent to Proxy:** Untrusted. The proxy assumes the agent may send malformed inputs.
- **Proxy to DynamoDB:** Trusted. The proxy has IAM permissions to write receipts.
- **Downstream to Verify:** Untrusted. The verifier assumes the downstream node may have been passed fabricated data by the agent.

## Reporting a Vulnerability

If you discover a vulnerability in the receipt hashing mechanism, DynamoDB implementation, or verification logic, please report it securely.

**Do not open a public GitHub issue.**

Please email `ojack@merkabacreatives.org` with the subject `[Security] AgentGuard Vulnerability`. Include steps to reproduce and potential impact. You will receive a response within 48 hours.
