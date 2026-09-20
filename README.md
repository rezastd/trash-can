# Which Bin? — trash-can classifier

Point your phone camera at trash, get told which can it goes in.

Pipeline: phone photo → local vision model describes the item as
structured text → Jev (TypeSafe System One) classifies the description
into one of your configured bins, with confidence and runner-up.

Decisions and scope: [docs/spec.md](docs/spec.md).

## Prerequisites

- Python 3.11+ via [uv](https://docs.astral.sh/uv/), Node 20+
- A `JEV_API_KEY` in `.env` (already present in this project)
- A vision model server on `http://localhost:1234/v1` (LM Studio default),
  with a vision-capable model loaded. Two options:
  - **LM Studio** (intended): start the server (Developer tab → Start
    Server, port 1234) with a vision model loaded — `google/gemma-4-e2b`
    (MLX) is confirmed vision-capable for this pipeline.
  - **llama-server fallback** (verified working with the same model files):
    `llama-server -m ~/.lmstudio/models/lmstudio-community/gemma-4-12B-it-QAT-GGUF/gemma-4-12B-it-QAT-Q4_0.gguf --mmproj ~/.lmstudio/models/lmstudio-community/gemma-4-12B-it-QAT-GGUF/mmproj-gemma-4-12B-it-QAT-BF16.gguf --host 127.0.0.1 --port 1234`

## Setup

```sh
uv sync
cd frontend && npm install && npm run build && cd ..
```

## Run

Terminal 1 — vision server (pick one option from Prerequisites).

Terminal 2 — the app, with HTTPS so the phone camera works:

```sh
TRASHCAN_HOST=0.0.0.0 TRASHCAN_PORT=8000 \
TRASHCAN_TLS_CERT=certs/cert.pem TRASHCAN_TLS_KEY=certs/key.pem \
uv run python -m backend.app
```

On your phone (same Wi-Fi): open `https://192.168.1.9:8000`
(or `https://DNID3335L01.local:8000`). The certificate is self-signed,
so tap through the browser warning (Show Details → visit this website).
For local use without a phone: `http://127.0.0.1:8000` with no TLS vars.

Frontend dev mode (optional): `cd frontend && npm run dev` — `/api`
proxies to the backend on port 8000.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `JEV_API_KEY` (or `TYPESAFE_API_KEY`) | — | Jev API key, server-side only |
| `TRASHCAN_HOST` / `TRASHCAN_PORT` | `127.0.0.1` / `8000` | App bind address |
| `TRASHCAN_TLS_CERT` / `TRASHCAN_TLS_KEY` | — | TLS pair; set both or neither |
| `LMSTUDIO_BASE_URL` | `http://localhost:1234/v1` | OpenAI-compatible vision endpoint |
| `LMSTUDIO_MODEL` | first loaded model | Vision model id override |
| `LMSTUDIO_TIMEOUT` / `JEV_TIMEOUT` | `180` / `60` | Stage timeouts (seconds) |

If the Mac's Wi-Fi IP changes, regenerate the cert so the SAN matches:

```sh
HOST="$(scutil --get LocalHostName)" IP="$(ipconfig getifaddr en0)"
openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
  -keyout certs/key.pem -out certs/cert.pem -subj "/CN=$HOST.local" \
  -addext "subjectAltName=DNS:localhost,DNS:$HOST.local,IP:127.0.0.1,IP:$IP"
```

## Manual test checklist (v1 acceptance)

From [docs/spec.md](docs/spec.md): point the phone at one item per bin
plus confusing items, and judge by eye.

- [ ] Clean cardboard → Recycle
- [ ] Banana peel / food scraps → Compost
- [ ] Chip bag / styrofoam → Landfill
- [ ] Battery → Hazardous
- [ ] Greasy pizza box (recyclable material, compost-ruining residue?)
- [ ] Coffee cup (mixed materials — check the runner-up reads sensibly)
- [ ] Edit bins in the Bins tab → next classification uses them
- [ ] Note end-to-end latency on the real phone path

## Troubleshooting

- `GET /api/health` shows `jev_configured` and bin count.
- `/api/classify` 502 names the failing stage (vision server vs Jev).
- Camera shows the upload tip instead of video: you opened the app over
  plain HTTP — use the `https://` address above.
