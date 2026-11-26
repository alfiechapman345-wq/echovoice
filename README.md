# EchoVoice

A self-hosted text-to-speech website powered by Piper. No app-imposed character quota, credits, subscriptions, or daily generation allowance.

## Deploy on Render
Use **New + → Blueprint** in Render and select this repository. Render reads `render.yaml`, installs dependencies, downloads the default English voice, and starts the web service.

## Notes
The free Render instance has limited CPU/RAM and may sleep when idle. Generation speed and practical passage size depend on server resources. Generated audio is stored on the instance filesystem and may be lost when a free instance restarts. Add a persistent disk for durable audio storage.

Voice model: Piper `en_US-lessac-medium`. Review the model's license before commercial use.
