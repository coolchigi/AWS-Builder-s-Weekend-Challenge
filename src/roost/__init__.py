"""Roost: a small platform for always-on agents on AWS.

Each app wakes on a schedule, senses the world, reasons over what it remembers,
publishes a page, and alerts you when something changed. That whole lifecycle
lives here and is written once. An app is one adapter (see adapters/) deployed as
its own isolated stack from the shared template.yaml.
"""
