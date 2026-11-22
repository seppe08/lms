## Install

Install `sentry-sdk` from PyPI:

```bash
pip install "sentry-sdk" "fastapi"
```

## Configure SDK

If you have the `fastapi` package in your dependencies, the FastAPI integration will be enabled automatically when you initialize the Sentry SDK. Initialize the Sentry SDK before your app has been initialized:

```python
from fastapi import FastAPI
import sentry_sdk

sentry_sdk.init(
    dsn="https://8058f0b6a84516fc8508d0486f993573@o4512473920438272.ingest.us.sentry.io/4512473971294208",
    # To customize collected data (user info, request bodies, AI inputs/outputs),
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/
    # data_collection={"user_info": False},
)

app = FastAPI()
```

The above configuration captures both error and performance data. To reduce the volume of performance data captured, change `traces_sample_rate` to a value between 0 and 1.

## Verify

You can easily verify your Sentry installation by creating a route that triggers an error:

```python
@app.get("/sentry-debug")
async def trigger_error():
    division_by_zero = 1 / 0
```

Logs require Python SDK version `2.68.0` or higher. If you already have an older version installed, upgrade it with `pip install --upgrade sentry-sdk`.

You can send logs to Sentry using the Sentry logging APIs:

```python
import sentry_sdk

# Send logs directly to Sentry
sentry_sdk.logger.info("This is an info log message")
sentry_sdk.logger.warning("This is a warning message")
sentry_sdk.logger.error("This is an error message")
```

You can also forward logs from Python's built-in logging module by setting `capture_sentry_logs=True` on the `LoggingIntegration`:

```python
import logging

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

sentry_sdk.init(
    # ...
    integrations=[
        LoggingIntegration(capture_sentry_logs=True),
    ],
)

# Your existing logging setup
logger = logging.getLogger(__name__)

# These logs will be automatically sent to Sentry
logger.info("This will be sent to Sentry")
logger.warning("User login failed")
logger.error("Something went wrong")
```

When you open [http://localhost:8000/sentry-debug/](http://localhost:8000/sentry-debug/) with your browser, a transaction in the Performance section of Sentry will be created.Additionally, an error event will be sent to Sentry and will be connected to the transaction.It takes a couple of moments for the data to appear in Sentry.
