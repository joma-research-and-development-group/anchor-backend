import hashlib
from uuid import UUID

from app.models.experiment_variant import ExperimentVariant


def deterministic_assign(experiment_id: UUID, device_id: UUID, variants: list[ExperimentVariant]) -> ExperimentVariant:
    """Deterministically assign a device to a variant using hash-based bucketing."""
    raw = f"{experiment_id}:{device_id}"
    hash_val = int(hashlib.sha256(raw.encode()).hexdigest(), 16)
    total_weight = sum(v.weight for v in variants)
    bucket = hash_val % total_weight
    cumulative = 0
    for variant in variants:
        cumulative += variant.weight
        if bucket < cumulative:
            return variant
    return variants[-1]
