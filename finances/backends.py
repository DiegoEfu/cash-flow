"""
Email Authentication Backend

This is a custom authentication backend that uses email as the username,
instead of the default username. This is useful for users who don't want to
remember a username, and for users who want to use their email address as their
username.

This backend is a subclass of the Django built-in ModelBackend, and overrides
the authenticate method to use the email as the username.

"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(email=username)
        except UserModel.DoesNotExist:
            return None
        else:
            if user.check_password(password):
                return user
        return None