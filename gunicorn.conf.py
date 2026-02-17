# Gunicorn Configuration File
# This file is used to configure Gunicorn settings if command line arguments are not provided.
# However, docker-compose.yml command overrides these.

import multiprocessing

# Workers
# Reduced to 1 to prevent memory exhaustion on limited resources (e.g. Render Free Tier)
workers = 1
threads = 2

# Timeouts
# Increased to 120s to allow slow startups and avoid "WORKER TIMEOUT" errors
timeout = 120
graceful_timeout = 30

# Binding
bind = "0.0.0.0:8000"

# Logging
loglevel = "info"
accesslog = "-"  # stdout
errorlog = "-"   # stderr
