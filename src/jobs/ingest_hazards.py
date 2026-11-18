"""Step 3 job wrapper: python src/jobs/ingest_hazards.py --catalog <name> [--drop-sample]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingest.hazards import main  # noqa: E402

if __name__ == "__main__":
    main()
