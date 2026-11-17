from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VALID = sorted((ROOT / "examples" / "valid").glob("*.sipl"))
INVALID = sorted((ROOT / "examples" / "invalid").glob("*.sipl"))

POWER = """begin
  R := 1;
  while Y > 0 do
  begin
    R := R * X;
    Y := Y - 1
  end
end
"""


@pytest.fixture
def power_source() -> str:
    return POWER
