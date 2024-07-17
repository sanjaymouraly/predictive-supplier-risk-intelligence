# Predictive Supplier Risk Intelligence

Predicts supplier risk from delivery, quality, financial, and disruption signals.

## Features

- Supplier and order management across 55+ global suppliers and 2,500+ purchase orders.
- Point-in-time delay probability, expected slip, and probability-weighted financial impact.
- Calibrated risk models with SHA-256 verified artifacts.
- Early-warning center with priority ranks, SLA due dates, and escalation workflow.
- Human review queue with capacity limits and authoritative decisions.
- What-if simulator for supplier reallocation, lead-time buffers, and shipping modes.

## Stack

Python, Node.js, FastAPI, Uvicorn, SQLAlchemy, Pydantic, NumPy, pandas, scikit-learn, SciPy

## Clone

```bash
git clone https://github.com/sanjaymouraly/predictive-supplier-risk-intelligence.git
cd predictive-supplier-risk-intelligence
```

## Setup

```bash
# The project ships a Docker Compose setup.
docker compose up --build
```

See `docs/` or the compose file for environment variables and ports.

## Run

```bash
docker compose up --build
```

## Tests

```bash
pytest -q
```

## Notes

- Sample data, when included, is synthetic.

## License

MIT © 2024 [Sanjay Mouraly](https://github.com/sanjaymouraly)
