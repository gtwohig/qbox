# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |
| < latest | :x:               |

## Reporting a Vulnerability

If you discover a security vulnerability within QBox, please report it by
emailing the maintainers directly rather than opening a public issue.

**Please include:**

1. A description of the vulnerability
2. Steps to reproduce the issue
3. Potential impact
4. Any suggested fixes (optional)

**What to expect:**

- Acknowledgment of your report within 48 hours
- Regular updates on the progress of addressing the vulnerability
- Credit in the release notes (unless you prefer to remain anonymous)

## Security Considerations

QBox uses several internal mechanisms that have security implications:

### Frame Inspection

QBox inspects and modifies Python stack frames to replace references after
observation. This is an intentional feature but means:

- Code running in the same process can observe values through QBox
- Frame locals are modified through implementation-specific mechanisms

### Background Thread

QBox runs a daemon thread with an asyncio event loop. This thread:

- Executes all coroutines submitted to QBox
- Runs until interpreter shutdown
- Has access to any values passed to coroutines

### isinstance Patching

The optional `enable_qbox_isinstance()` feature patches `builtins.isinstance`.
This global modification affects all code in the process.

## Best Practices

1. Don't wrap sensitive coroutines (e.g., cryptographic operations) in QBox
   if you're concerned about value inspection
2. Use `cancel_on_delete=True` (default) to ensure coroutines are cancelled
   when QBoxes are garbage collected
3. Be cautious with `enable_qbox_isinstance()` in library code - prefer
   ABC registration with `mimic_type` instead
