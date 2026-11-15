"""Fetch the pinned NASA/JPL kernel bundle into the ignored data cache."""
import argparse
from pathlib import Path
from tempfile import NamedTemporaryFile
import sys
from shutil import copyfileobj
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.scientific_engines.ephemeris.kernels import DEFAULT_DIRECTORY, inventory, verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    directory = parser.parse_args().directory
    directory.mkdir(parents=True, exist_ok=True)
    for item in inventory():
        path = directory / item["file"]
        if path.exists() and verified(path, item["sha256"]):
            print(f"{path.name} verified")
            continue
        with NamedTemporaryFile(dir=directory, delete=False) as handle:
            temporary = Path(handle.name)
        try:
            with urlopen(item["url"], timeout=60) as response, temporary.open("wb") as target:
                copyfileobj(response, target)
            if not verified(temporary, item["sha256"]):
                raise ValueError(f"Downloaded kernel SHA-256 mismatch: {path.name}")
            temporary.replace(path)
            print(f"{path.name} downloaded and verified")
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
