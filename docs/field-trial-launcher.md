# Field-trial launcher

Use `scripts/mockingbird-field-trial` for the bounded local field runtime. It
starts exactly one loopback backend and one loopback Vite frontend in the
`mockingbird-field-trial` tmux session. It never starts or reconfigures a
Camera Node.

Before starting, create the ignored `data/field-trial.env` from the template
below. Keep local model paths and any credentials only in that ignored file.
The launcher loads it for both processes and refuses to declare the trial
healthy unless MegaDetector reports ready.

```sh
scripts/mockingbird-field-trial start
scripts/mockingbird-field-trial status
scripts/mockingbird-field-trial logs
scripts/mockingbird-field-trial open-browser
scripts/mockingbird-field-trial stop
```

Logs and non-secret operator metadata are retained under
`/tmp/mockingbird-field-trial`. Stopping sends the backend its normal shutdown
signal before closing the detached session, so existing durable monitoring can
close its active exposure interval safely.

```sh
# data/field-trial.env (ignored; never commit this file)
MOCKINGBIRD_MEGADETECTOR_MODEL_PATH=/your/local/model.pt
MOCKINGBIRD_MEGADETECTOR_RUNTIME_CACHE_PATH=data/runtime/megadetector
```
