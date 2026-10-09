"""Provider broker: user-supplied credentials, endpoint profiles, adapters and dispatch.

Provider calls never write formal evidence. Adapters declare their capabilities explicitly;
a provider name in configuration is not an implemented integration, and no built-in adapter
claims conformance against a live service it has not been tested with.
"""
