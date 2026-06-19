from __future__ import annotations

import requests


def correct_observation(obs_id: str) -> None:
    # All three are forbidden on an immutable Observation.
    requests.delete(f"https://canvas.example/Observation/{obs_id}")
    requests.put(f"https://canvas.example/Observation/{obs_id}", json={})
    requests.patch(f"https://canvas.example/Observation/{obs_id}", json={})
