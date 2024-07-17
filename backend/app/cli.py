"""Command-Line Interface (CLI) for database setup, synthetic seeding, ML training, evaluation, and batch inference."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.data_generator import generate_synthetic_dataset
from app.database import SessionLocal, init_db
from app.decision_engine import refresh_predictions_and_queues
from app.import_export import (
    export_orders_csv,
    export_predictions_csv,
    export_suppliers_csv,
    generate_executive_pdf_report,
)
from app.ml_pipeline import resolve_artifact_path, train_and_evaluate_all_models
from app.models import ModelRegistry
from app.monitoring import compute_monitoring_diagnostics


def _run_migrations() -> dict[str, Any]:
    """Apply Alembic migrations up to head for the configured database."""
    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    command.upgrade(cfg, "head")
    return {"status": "migrations_applied", "revision": "head"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sri-cli",
        description="Predictive Supplier Risk Intelligence CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Initialize database schema")
    sub.add_parser("migrate", help="Apply Alembic schema migrations up to head")

    seed_p = sub.add_parser("seed", help="Seed reproducible synthetic procurement dataset")
    seed_p.add_argument("--suppliers", type=int, default=55)
    seed_p.add_argument("--historical-orders", type=int, default=2400)
    seed_p.add_argument("--open-orders", type=int, default=140)
    seed_p.add_argument("--seed", type=int, default=42)
    seed_p.add_argument("--force", action="store_true")

    train_p = sub.add_parser("train", help="Train, tune, calibrate, and evaluate all ML models")
    train_p.add_argument("--seed", type=int, default=42)

    sub.add_parser("predict", help="Run batch inference on open orders and populate review queue")
    sub.add_parser("inspect-model", help="Inspect champion model metrics and feature importances")
    sub.add_parser("drift-check", help="Run prediction distribution and feature drift diagnostics")

    exp_p = sub.add_parser("export-report", help="Export PDF and CSV reports to disk")
    exp_p.add_argument("--output-dir", type=str, default=".")

    sub.add_parser("bootstrap-all", help="Initialize DB, seed data, train models, and run batch predictions")

    args = parser.parse_args(argv)

    # Alembic manages schema creation itself; run before create_all to avoid conflicts.
    if args.command == "migrate":
        print(json.dumps(_run_migrations(), indent=2))
        return 0

    init_db()
    db = SessionLocal()

    try:
        if args.command == "init-db":
            print(json.dumps({"status": "database_initialized"}, indent=2))
            return 0

        if args.command == "seed":
            res = generate_synthetic_dataset(
                db=db,
                num_suppliers=args.suppliers,
                num_historical_orders=args.historical_orders,
                num_open_orders=args.open_orders,
                seed=args.seed,
                force_reset=args.force,
            )
            print(json.dumps(res, indent=2))
            return 0

        if args.command == "train":
            res = train_and_evaluate_all_models(db=db, random_seed=args.seed)
            print(json.dumps(res, indent=2))
            return 0

        if args.command == "predict":
            res = refresh_predictions_and_queues(db=db)
            print(json.dumps(res, indent=2))
            return 0

        if args.command == "inspect-model":
            champ = (
                db.query(ModelRegistry)
                .filter(ModelRegistry.is_champion.is_(True))
                .first()
            )
            if not champ:
                print(json.dumps({"error": "No champion model found."}, indent=2))
                return 1
            info = {
                "model_version": champ.model_version,
                "algorithm_name": champ.algorithm_name,
                "display_name": champ.display_name,
                "selection_rationale": champ.selection_rationale,
                "artifact_sha256": champ.artifact_sha256,
                "metrics": json.loads(champ.metrics_json),
                "top_features": json.loads(champ.feature_importance_json)[:8],
            }
            print(json.dumps(info, indent=2))
            return 0

        if args.command == "drift-check":
            res = compute_monitoring_diagnostics(db=db)
            print(json.dumps(res, indent=2))
            return 0

        if args.command == "export-report":
            out_dir = Path(args.output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            csv_path = out_dir / "risk_predictions_report.csv"
            orders_path = out_dir / "purchase_order_ledger.csv"
            suppliers_path = out_dir / "supplier_scorecards.csv"
            pdf_path = out_dir / "executive_risk_report.pdf"
            csv_path.write_text(export_predictions_csv(db), encoding="utf-8")
            orders_path.write_text(export_orders_csv(db), encoding="utf-8")
            suppliers_path.write_text(export_suppliers_csv(db), encoding="utf-8")
            pdf_path.write_bytes(generate_executive_pdf_report(db))
            print(
                json.dumps(
                    {
                        "status": "exported",
                        "csv_report": str(csv_path),
                        "orders_csv": str(orders_path),
                        "suppliers_csv": str(suppliers_path),
                        "pdf_report": str(pdf_path),
                    },
                    indent=2,
                )
            )
            return 0

        if args.command == "bootstrap-all":
            seed_res = generate_synthetic_dataset(db=db)
            champ = (
                db.query(ModelRegistry)
                .filter(ModelRegistry.is_champion.is_(True))
                .first()
            )
            resolved_champ = resolve_artifact_path(champ.artifact_path) if champ else None
            if not champ or not resolved_champ or not resolved_champ.exists():
                train_res = train_and_evaluate_all_models(db=db)
                pred_res = refresh_predictions_and_queues(db=db)
            else:
                train_res = {"status": "already_trained", "champion": champ.model_version}
                pred_res = refresh_predictions_and_queues(db=db)
            print(
                json.dumps(
                    {
                        "seed": seed_res,
                        "train": train_res,
                        "predictions": pred_res,
                    },
                    indent=2,
                )
            )
            return 0
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
