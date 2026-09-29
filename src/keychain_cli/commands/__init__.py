"""Command implementations. Each module exposes one ``run_<command>`` function.

Commands depend only on the ``SecretStore`` protocol and the prompt seam; they never import
the Security framework bindings directly.
"""
