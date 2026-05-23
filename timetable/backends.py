import bcrypt
from django.contrib.auth.backends import BaseBackend
from .models import UnifiedUser


class PhpBcryptBackend(BaseBackend):
    """
    Custom authentication backend that verifies passwords hashed by PHP's password_hash().
    PHP uses $2y$ prefix while Python bcrypt uses $2b$. They are interchangeable.
    Also supports Django's native password hashing for new passwords.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        try:
            # Try to find by username OR email
            try:
                user = UnifiedUser.objects.get(username=username)
            except UnifiedUser.DoesNotExist:
                try:
                    user = UnifiedUser.objects.get(email=username)
                except UnifiedUser.DoesNotExist:
                    return None

            if not user.is_active:
                return None

            stored_hash = user.password

            # Handle PHP bcrypt hashes ($2y$...)
            if stored_hash.startswith('$2y$') or stored_hash.startswith('$2b$'):
                # Replace $2y$ with $2b$ for Python compatibility
                python_hash = stored_hash.replace('$2y$', '$2b$', 1)
                try:
                    if bcrypt.checkpw(password.encode('utf-8'), python_hash.encode('utf-8')):
                        return user
                except Exception:
                    return None

            # Handle Django's native pbkdf2 hashes
            elif stored_hash.startswith('pbkdf2_'):
                from django.contrib.auth.hashers import check_password
                if check_password(password, stored_hash):
                    return user

            # Fallback: plain text comparison (for development only)
            elif stored_hash == password:
                return user

            return None

        except Exception:
            return None

    def get_user(self, user_id):
        try:
            return UnifiedUser.objects.get(pk=user_id)
        except UnifiedUser.DoesNotExist:
            return None
