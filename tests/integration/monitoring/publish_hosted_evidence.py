"""Publish existing approved replay reports and prepare project-scoped SQL.

This is an explicit owner-run hosted check, never an ordinary CI test. It uses
the production Storage adapter; SQL is reviewed/executed separately through
the project connector when direct PostgreSQL is unavailable.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from psycopg import sql

from predictive_maintenance.cloud.config import Phase2Settings
from predictive_maintenance.cloud.models import CloudFoundationError, ObjectIdentity
from predictive_maintenance.cloud.object_store import SupabaseObjectRepository
from predictive_maintenance.monitoring.models import canonical_json_bytes, sha256_bytes
from predictive_maintenance.monitoring.publication import reconcile_monitoring_objects
from supabase import create_client


def _insert(table: str, values: dict[str, Any]) -> str:
    return (
        sql.SQL("insert into ops.{} ({}) values ({}) on conflict do nothing;")
        .format(
            sql.Identifier(table),
            sql.SQL(",").join(sql.Identifier(key) for key in values),
            sql.SQL(",").join(
                value if isinstance(value, sql.Composable) else sql.Literal(value)
                for value in values.values()
            ),
        )
        .as_string()
    )


def _object_id(identity: ObjectIdentity) -> sql.Composed:
    return sql.SQL(
        "(select object_id from ops.data_objects "
        "where bucket_name={} and object_key={})"
    ).format(sql.Literal(identity.bucket_name), sql.Literal(identity.object_key))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-project-ref", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prior-storage-evidence", type=Path)
    parser.add_argument("--publish-approved-phase7", action="store_true", required=True)
    args = parser.parse_args()
    settings = Phase2Settings.from_env()
    if settings.app_env != "cloud" or urlsplit(
        settings.supabase_url.reveal()
    ).hostname != (f"{args.expected_project_ref}.supabase.co"):
        raise RuntimeError("Hosted target is not the explicitly approved project.")
    root = args.evidence_root.resolve()
    if os.name == "nt" and not str(root).startswith("\\\\?\\"):
        root = Path("\\\\?\\" + str(root))
    summary = json.loads((root / "summary.json").read_bytes())
    release_id = summary["release_id"]
    repository = SupabaseObjectRepository(
        create_client(
            settings.supabase_url.reveal(), settings.supabase_secret_key.reveal()
        )
    )
    identities: list[ObjectIdentity] = []
    if args.prior_storage_evidence is not None:
        prior = json.loads(args.prior_storage_evidence.read_bytes())
        for record in prior["objects"]:
            identity = ObjectIdentity(
                settings.derived_bucket,
                record["key"],
                "derived",
                record["sha256"],
                record["byte_size"],
                "application/json",
            )
            stored = repository.read(identity.bucket_name, identity.object_key)
            if (
                len(stored) != identity.byte_size
                or sha256_bytes(stored) != identity.sha256
            ):
                raise RuntimeError("Prior hosted evidence changed or disappeared.")
            identities.append(identity)
    statements = ["begin;"]
    outcomes: list[dict[str, Any]] = []
    for field, identity_field in (
        ("reference_id", "reference_id"),
        ("prediction_report_id", "report_id"),
        ("performance_report_id", "report_id"),
    ):
        digest = summary[field]
        matches = list((root / "object-store").rglob(f"{digest}.json"))
        if len(matches) != 1:
            raise RuntimeError("Expected exactly one immutable replay object.")
        path = matches[0]
        payload = path.read_bytes()
        value = json.loads(payload)
        if (
            value.pop(identity_field) != digest
            or sha256_bytes(canonical_json_bytes(value)) != digest
        ):
            raise RuntimeError("Replay object identity is invalid.")
        if field == "reference_id":
            key = f"reports/monitoring/{release_id}/references/{digest}.json"
        else:
            key = (
                f"reports/monitoring/{release_id}/{summary['window_id']}/{digest}.json"
            )
        identity = ObjectIdentity(
            settings.derived_bucket,
            key,
            "derived",
            sha256_bytes(payload),
            len(payload),
            "application/json",
        )
        first = repository.put_verified(path, identity)
        second = repository.put_verified(path, identity)
        if not second.reused or repository.read(identity.bucket_name, key) != payload:
            raise RuntimeError("Hosted object reuse or download verification failed.")
        with tempfile.TemporaryDirectory(prefix="phase7-hosted-conflict-") as temporary:
            conflicting_payload = b"controlled different bytes"
            conflicting_path = Path(temporary) / "conflict.json"
            conflicting_path.write_bytes(conflicting_payload)
            conflicting = ObjectIdentity(
                identity.bucket_name,
                key,
                "derived",
                sha256_bytes(conflicting_payload),
                len(conflicting_payload),
                "application/json",
            )
            try:
                repository.put_verified(conflicting_path, conflicting)
            except CloudFoundationError as error:
                if error.code != "object.identity_conflict":
                    raise
            else:
                raise RuntimeError("Hosted put-if-absent accepted conflicting bytes.")
        public_url = (
            f"{settings.supabase_url.reveal()}/storage/v1/object/public/"
            f"{identity.bucket_name}/{key}"
        )
        anonymous_status = httpx.get(public_url, timeout=30).status_code
        if anonymous_status < 400:
            raise RuntimeError("Private monitoring object was anonymously readable.")
        if identity not in identities:
            identities.append(identity)
        outcomes.append(
            {
                "sha256": identity.sha256,
                "byte_size": len(payload),
                "key": key,
                "first_reused": first.reused,
                "repeat_reused": second.reused,
                "conflict_rejected": True,
                "anonymous_status": anonymous_status,
            }
        )
        statements.append(
            _insert(
                "data_objects",
                {
                    "bucket_name": identity.bucket_name,
                    "object_key": key,
                    "zone": "derived",
                    "sha256": identity.sha256,
                    "byte_size": len(payload),
                    "content_type": "application/json",
                    "verification_state": "verified",
                    "verified_at": sql.SQL("now()"),
                },
            )
        )
        if field == "reference_id":
            statements.append(
                _insert(
                    "monitoring_references",
                    {
                        **{
                            name: value[name]
                            for name in (
                                "release_id",
                                "feature_snapshot_id",
                                "policy_id",
                                "reference_contract_version",
                                "row_count",
                                "engine_count",
                                "sampled_row_count",
                            )
                        },
                        "reference_id": digest,
                        "profile_sha256": identity.sha256,
                        "profile_object_id": _object_id(identity),
                    },
                )
            )
        else:
            window = value["window"]
            statements.append(
                _insert(
                    "monitoring_windows",
                    {
                        **{
                            name: window[name]
                            for name in (
                                "release_id",
                                "reference_id",
                                "policy_id",
                                "feature_snapshot_id",
                                "source_partition",
                                "membership_sha256",
                                "row_count",
                                "engine_count",
                                "replay_sequence",
                                "window_contract_version",
                            )
                        },
                        "window_id": summary["window_id"],
                    },
                )
            )
            statements.append(
                _insert(
                    "monitoring_reports",
                    {
                        "report_id": digest,
                        "window_id": summary["window_id"],
                        "parent_report_id": value["parent_report_id"],
                        "label_snapshot_id": value["label_snapshot_id"],
                        "report_contract_version": value["report_contract_version"],
                        "report_sha256": identity.sha256,
                        "report_object_id": _object_id(identity),
                        **{
                            column: value[section]["status"]
                            for column, section in (
                                ("data_quality_status", "data_quality"),
                                ("feature_shift_status", "feature_shift"),
                                ("prediction_shift_status", "prediction_shift"),
                                ("service_status", "service_health"),
                                ("performance_status", "delayed_performance"),
                            )
                        },
                    },
                )
            )
    findings = reconcile_monitoring_objects(
        tuple(identities),
        bucket=settings.derived_bucket,
        prefix=f"reports/monitoring/{release_id}",
        repository=repository,
    )
    if findings:
        raise RuntimeError(
            "Hosted monitoring reconciliation found a mismatch or orphan."
        )
    statements.append("commit;")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "record-evidence.sql").write_text(
        "\n".join(statements) + "\n", encoding="utf-8"
    )
    result = {
        "evidence_class": "hosted_supabase_storage",
        "objects": outcomes,
        "prior_objects_verified": len(identities) - len(outcomes),
        "reconciliation_findings": len(findings),
        "direct_postgres_adapter_exercised": False,
    }
    (args.output / "storage-evidence.json").write_bytes(canonical_json_bytes(result))
    print(json.dumps({"verified_objects": len(outcomes), "reconciliation_findings": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
