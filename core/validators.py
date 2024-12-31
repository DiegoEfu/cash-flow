from django.core.exceptions import ValidationError

MAX_FILE_SIZE = 0.5 * 1024 * 1024

def file_size_validator(value): # add this to some file where you can import it from
    limit = MAX_FILE_SIZE
    if value.size > limit:
        raise ValidationError('File too large. Size should not exceed 0.5 MiB.')