import os

# Must be set before any src imports so inngest.Inngest initialises in dev mode.
os.environ.setdefault("INNGEST_DEV", "1")
