"""Validate real-data recordings (task P1-T7).

    python scripts/validate_dataset.py data            # exit code 1 if any recording or rule fails
    python scripts/validate_dataset.py data --summary  # also print counts for docs/DATASET_CARD.md
"""
import sys

from chesstor.dataset import main

sys.exit(main())
