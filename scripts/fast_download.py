import os
import subprocess
import sys

PARTS = 32


def fetch(url, out):
    head = subprocess.run(
        ["curl", "-sIL", "--max-time", "30", url],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    size = None
    for line in head.splitlines():
        line = line.strip().lower()
        if line.startswith("content-length:"):
            size = int(line.split(":", 1)[1])
    if not size:
        sys.exit(f"could not determine size of {url}")

    chunk = size // PARTS
    ranges = [
        (i * chunk, (size - 1) if i == PARTS - 1 else (i + 1) * chunk - 1)
        for i in range(PARTS)
    ]
    procs = []
    for i, (start, end) in enumerate(ranges):
        procs.append(
            subprocess.Popen(
                [
                    "curl",
                    "-sS",
                    "-L",
                    "--max-time",
                    "7200",
                    "-r",
                    f"{start}-{end}",
                    "-o",
                    f"{out}.part{i}",
                    url,
                ]
            )
        )
    codes = [p.wait() for p in procs]
    if any(c != 0 for c in codes):
        sys.exit(f"some part downloads failed for {url}: exit codes {codes}")

    for i, (start, end) in enumerate(ranges):
        part = f"{out}.part{i}"
        actual = os.path.getsize(part)
        if actual != end - start + 1:
            sys.exit(f"part {i} of {out} is {actual} bytes, expected {end - start + 1}")

    with open(out, "wb") as dest:
        for i in range(PARTS):
            with open(f"{out}.part{i}", "rb") as src:
                while True:
                    block = src.read(1 << 24)
                    if not block:
                        break
                    dest.write(block)
            os.remove(f"{out}.part{i}")
    print(f"downloaded {out} ({size} bytes)")


if __name__ == "__main__":
    fetch(sys.argv[1], sys.argv[2])
