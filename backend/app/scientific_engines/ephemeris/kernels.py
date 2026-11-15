"""Pinned NAIF kernel inventory and process-wide SPICE initialization."""
from functools import lru_cache
from hashlib import file_digest
import os
from pathlib import Path
from threading import RLock

import spiceypy as spice
from spiceypy.utils.exceptions import SpiceyError

BASE = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/"
DEFAULT_DIRECTORY = Path(__file__).resolve().parents[4] / "data" / "cache" / "ephemeris"
KERNELS = {
    "lsk/naif0012.tls": "678e32bdb5a744117a467cd9601cd6b373f0e9bc9bbde1371d5eee39600a039b",
    "spk/planets/de440s.bsp": "c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2",
    "pck/moon_pa_de440_200625.bpc": "60cd55aa401ea2ea97360636f567554bfe4e37bb829f901b4460a455dfaf783f",
    "fk/satellites/moon_de440_250416.tf": "a47c71e9c9f33796bdafb2c9d69a7ee447b6016ecad80f71cd6f3e479f9cf768",
    "pck/pck00011.tpc": "3dff7b1dbeceaa01f25467767d3fa25816051c85d162d1edf04acb310ee28bb1",
}
LOCK = RLock()
BODY_FRAME = "MOON_ME_DE440_ME421"
LIGHT_TIME_MARGIN_S = 1200
STATE_MARGIN_S = 2


class KernelUnavailable(RuntimeError):
    pass


def inventory():
    return [{"file": Path(relative).name, "url": BASE + relative, "sha256": digest}
            for relative, digest in KERNELS.items()]


def verified(path, sha256):
    with path.open("rb") as handle:
        return file_digest(handle, "sha256").hexdigest() == sha256


def spice_path(path):
    # CSPICE file I/O uses narrow paths on Windows. The default cache can be
    # reached through a relative ASCII path even under a Unicode project root.
    try:
        return os.path.relpath(path)
    except ValueError:
        return str(path)


@lru_cache(maxsize=1)
def _load():
    directory = Path(os.environ.get("LUNA_SPICE_KERNEL_DIR", DEFAULT_DIRECTORY)).resolve()
    paths = {item["file"]: directory / item["file"] for item in inventory()}
    for item in inventory():
        path = paths[item["file"]]
        try:
            if not verified(path, item["sha256"]):
                raise KernelUnavailable(f"SHA-256 mismatch for {path.name}.")
        except OSError as exc:
            raise KernelUnavailable(f"Missing or unreadable NAIF kernel {path.name}. Run scripts/download_spice_kernels.py.") from exc
    files = {key: spice_path(path) for key, path in paths.items()}
    loaded = []
    try:
        for name in files.values():
            spice.furnsh(name)
            loaded.append(name)
        spk = files["de440s.bsp"]
        window = spice.spkcov(spk, 10)
        for body in (3, 301, 399):
            window = spice.wnintd(window, spice.spkcov(spk, body))
        orientation = spice.pckcov(files["moon_pa_de440_200625.bpc"], 31008)
        common = spice.wnintd(window, orientation)
        if spice.wncard(common) != 1:
            raise KernelUnavailable("Expected one continuous common DE440 trajectory and orientation interval.")
        start, end = spice.wnfetd(common, 0)
        # SPKCPO evaluates neighboring states as part of its correction.
        return start + LIGHT_TIME_MARGIN_S, end - STATE_MARGIN_S
    except (SpiceyError, KernelUnavailable) as exc:
        for name in reversed(loaded):
            spice.unload(name)
        raise KernelUnavailable(f"Unable to initialize the pinned NAIF kernel bundle: {exc}") from exc


def coverage():
    with LOCK:
        start, end = _load()
        return {"start_et_tdb_s": start, "end_et_tdb_s": end,
                "start_utc": spice.et2utc(start, "ISOC", 6) + "Z",
                "end_utc": spice.et2utc(end, "ISOC", 6) + "Z"}
