"""Application layer — the user-facing front end.

The ML pipeline lives in ``src/``. This package is the product built on top of
it: it imports ``src.predict`` and never reaches past it into the model.
"""
