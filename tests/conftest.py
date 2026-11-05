"""Put the integration folder on the path so the engine imports on its own.

The engine never imports Home Assistant, so these tests need only sgp4.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "custom_components" / "iss_track"))
