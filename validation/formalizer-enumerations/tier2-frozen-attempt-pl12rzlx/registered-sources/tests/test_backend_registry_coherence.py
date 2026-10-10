"""Registered backend descriptors must match their closed selection schemas."""
from __future__ import annotations

import unittest

from verislop import canonical, schemas
from verislop.backends import registry


class BackendDescriptorSchemaCoherenceTests(unittest.TestCase):
    def test_frozen_selection_schema_pins_every_descriptor_field(self):
        for version, schema_name in (("0.1", "implementation-selection-v2.schema.json"),
                                     ("0.3", "implementation-selection-v3.schema.json")):
            with self.subTest(version=version):
                descriptor = registry.select(2, "vscore", "restricted_source", version)
                schema = canonical.load_file(schemas.schema_dir() / schema_name)
                self.assertIsNotNone(descriptor)
                self.assertEqual(descriptor, schema["properties"]["backend"]["const"],
                    "closed backend selection schema must change with the registered descriptor")
                self.assertEqual(version, descriptor["backend_version"])


if __name__ == "__main__":
    unittest.main()
