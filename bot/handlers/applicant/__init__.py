# Applicant handlers package initializer
# Intentionally left minimal to avoid circular imports.
# Import handler modules directly in bot/main.py, e.g.:
#   import bot.handlers.applicant.resume_creation as resume_creation
# This prevents loading submodules during package import.

__all__: list[str] = []
