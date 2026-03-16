from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Token generator for email address verification links.

    Produces HMAC-signed, time-limited tokens (expiry controlled by
    PASSWORD_RESET_TIMEOUT).  The token hash covers:
    - user.pk  – ties the token to a specific account,
    - timestamp – makes tokens expire,
    - user.is_active – invalidates the token once the account is activated,
    - user.email – invalidates the token if the email address changes.

    A dedicated key_salt ensures these tokens cannot be confused with
    password-reset tokens or any other token type signed with the same key.
    """

    key_salt = "users.tokens.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{user.is_active}{user.email}"


email_verification_token = EmailVerificationTokenGenerator()
