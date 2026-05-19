import os

# Provide harmless defaults so importing modules that read env doesn't blow up.
os.environ.setdefault("BOT_TOKEN", "123456789:AA" + "x" * 30)
os.environ.setdefault("ADMIN_CHAT_ID", "1")
