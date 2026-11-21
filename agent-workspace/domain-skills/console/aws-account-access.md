# AWS — account onboarding and operator access

Applies to `console.aws.amazon.com`, regional console hosts and `signin.aws.amazon.com`.

## Identity and ownership

- Verify the current account before provisioning. A browser session, CLI default
  profile and another client's cached credentials can refer to different accounts.
- New organization member accounts require distinct working email addresses. An alias
  on an already-routed mail domain does not require per-address DNS records.
- Keep company operator access separate from product runtime/service credentials.
  Never create root access keys to make an automation flow convenient.
- After configuring an explicit CLI profile, verify it with STS. For a subprocess
  supplied separate IAM credentials, remove inherited `AWS_*` selections so a client
  profile or session does not silently override the intended identity.

## Identity Center setup

- Organization onboarding selects a single Identity Center region. Review region and
  encryption defaults rather than assuming the wizard selected the intended key type.
- The initial user-password dialog contains a heading and a separate value with similar
  one-time-password wording. Capture the actual value in memory, not the heading, and
  store it before closing the once-only result.
- Initial portal login can require both MFA enrollment and a password change. Verify
  the final login and replace the saved temporary password with the final password.
- An authenticator registration secret belongs in an OTP field in the secret manager.
  Never print it, put it in a screenshot, or reuse an unrelated account's OTP field.
- Check the installed AWS CLI's supported commands before using newer native login
  workflows; an older package-manager installation may lack them.

## Embedded console tools

- CloudShell can be a same-process iframe rather than a separately listed OOPIF.
  Inspect the frame tree before assuming an iframe target exists; use the frame's
  execution context when required. Terminal DOM output can be wrapped and should not
  be treated as one command result per visible line.
- Console URLs can contain authentication workflow state or callback query values.
  Report only the host/path when diagnosing navigation, not the full authentication URL.
