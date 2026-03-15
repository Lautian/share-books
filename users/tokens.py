from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Token generator for email address verification links.

    Reuses Django's built-in PasswordResetTokenGenerator which:
    - signs tokens with the secret key,
    - encodes user state (id, last_login, is_active, password hash),
    - includes a timestamp so tokens expire via PASSWORD_RESET_TIMEOUT.
    """

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{user.is_active}{user.email}"


email_verification_token = EmailVerificationTokenGenerator()
