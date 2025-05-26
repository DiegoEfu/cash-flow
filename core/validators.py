from django.core.exceptions import ValidationError

"""
This module contains validators used in the application.
"""

MAX_FILE_SIZE = 0.5 * 1024 * 1024

def file_size_validator(value):
    """
    Validates the size of the uploaded file.

    Raises a ValidationError if the file size exceeds the maximum limit.

    Args:
        value: The uploaded file to validate.

    Raises:
        ValidationError: If the file size is greater than MAX_FILE_SIZE.
    """
    limit = MAX_FILE_SIZE
    if value.size > limit:
        raise ValidationError('File too large. Size should not exceed 0.5 MiB.')
