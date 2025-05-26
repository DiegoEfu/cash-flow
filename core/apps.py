"""
core/apps.py

This file contains the configuration for the core application.
It includes the configuration and ready method for the core application.

"""

from django.apps import AppConfig

class CoreConfig(AppConfig):
    """
    Summary:
        The configuration for the core application.

    Properties:
        name (str): The name of the application.
        default_auto_field (str): The default auto field for models in this application.

    Methods:
        ready(): Override of the AppConfig ready method to import the core's signal handlers.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
