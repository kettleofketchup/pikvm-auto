from __future__ import annotations


class ModuleDocFragment:
    DOCUMENTATION = r"""
options:
    pikvm_host:
        description: PiKVM device hostname or IP address.
        type: str
        required: true
    pikvm_user:
        description: PiKVM username.
        type: str
        required: true
    pikvm_passwd:
        description:
            - PiKVM password.
            - If I(pikvm_totp_secret) is set, a TOTP code is generated and appended automatically.
        type: str
        required: true
        no_log: true
    pikvm_totp_secret:
        description: TOTP secret for 2FA (base32 encoded).
        type: str
        required: false
        no_log: true
    pikvm_verify_ssl:
        description: Validate SSL certificates. PiKVM uses self-signed certs by default.
        type: bool
        default: false
"""
