from __future__ import annotations

obs = Observation.objects.filter(dbid__in=[1, 2, 3])
weight = obs.units
val = weight.lb
cond = Condition.objects.get(id=patient_id)
