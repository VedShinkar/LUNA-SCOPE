"""Fetch the exact NASA SVS and PDS products used by Lunar Explorer."""
from hashlib import file_digest
from pathlib import Path
import shutil
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1] / "data" / "cache" / "lunar-experience"
SVS = "https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/"
PDS = "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/img/"
PRODUCTS = {
    "lroc_color_2k.jpg": (SVS, "f7130a1822681fa7512d7dcfd40db8c10b9ba4f06777910348698260ed7a2170"),
    "ldem_4.tif": (SVS, "330afa2556a86fd05ac6ba2f912f246600fdade35de2a0d90593d50d07b01b65"),
    "ldem_85s_40m.lbl": (PDS, "d8105776af7fb79b1862ffa3946d013ec34f4dc6a00b7f6bff22ef8f768a5d3d"),
    "ldem_85s_40m.img": (PDS, "1609e9b860748e0b9952a7239c51b37d3b2a799d35e9fc3c258526711cc1e51d"),
}


def sha256(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, (base, digest) in PRODUCTS.items():
        output = ROOT / name
        if output.is_file() and sha256(output) == digest:
            print(f"Verified {name}")
            continue
        temporary = output.with_suffix(output.suffix + ".part")
        print(f"Downloading {name}", flush=True)
        try:
            with urlopen(base + name, timeout=60) as source, temporary.open("wb") as target:
                shutil.copyfileobj(source, target)
            if sha256(temporary) != digest:
                raise ValueError(f"Unexpected SHA-256 for {name}")
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
