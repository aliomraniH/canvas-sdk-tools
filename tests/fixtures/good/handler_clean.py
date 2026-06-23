from __future__ import annotations

import json

import requests
from canvas_sdk.handlers import BaseHandler


class MyHandler(BaseHandler):
    def compute(self):
        obs_units = self.observation.unit
        payload = json.dumps({"ok": True})
        requests.get("https://example.com/Observation/123")
        results = Model.objects.filter(id__in=[1, 2, 3])
        weight = {"units": "lb"}
        token = self.context.get("_token")
        return obs_units, payload, results, weight, token
