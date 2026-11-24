"""Build a distributable with frontend assets. Node/Git are needed only on the build machine.

Usage: python scripts/build-package.py /path/to/CapChristmas-Windows.zip
The user installs Python dependencies with scripts/install.ps1; no Node on the user machine.
"""
from pathlib import Path
import subprocess
import sys
import zipfile
import os

ROOT = Path(__file__).resolve().parents[1]


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/build-package.py OUTPUT.zip")
    output = Path(sys.argv[1]).resolve()
    npm = "npm.cmd" if os.name == "nt" else "npm"
    subprocess.run([npm, "ci"], cwd=ROOT / "frontend", check=True)
    subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", check=True)
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    files = [ROOT / name for name in tracked if name]
    files.extend(p for p in (ROOT / "frontend/dist").rglob("*") if p.is_file())
    # Allowlisted tracked source + built assets only. Never package local sessions, keys or dependencies.
    for path in files:
        relative = path.relative_to(ROOT)
        if any(part in ("data", ".venv", "node_modules", ".git") for part in relative.parts):
            raise SystemExit(f"Refusing private/dependency path: {relative}")
        if path.name.startswith(".env") and path.name != ".env.example":
            raise SystemExit("Refusing environment file")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            archive.write(path, "CapChristmas/" + path.relative_to(ROOT).as_posix())
        archive.writestr("CapChristmas/LAS-MIG.txt", """MEDELTOMTEN V2 – färdigbyggt paket

Node.js behövs INTE på din dator. Python 3.11+ och internet för installation krävs.

GRATIS TEST – ingen API-nyckel behövs:
1. Packa upp hela ZIP-filen. Öppna mappen CapChristmas i PowerShell.
2. Kör: powershell -ExecutionPolicy Bypass -File scripts\\install.ps1
3. Kör: powershell -ExecutionPolicy Bypass -File scripts\\start.ps1
4. Öppna http://127.0.0.1:8000/control och låt PowerShell vara öppet.
5. Skapa en session med Demoläge. Generera 5 syntetiska testteckningar.
6. Välj metoden V1 – legacy pixelmedel (offline). Granska flaggade bilder.
7. Öppna projektorvyn och välj Beräkna och starta show.
Detta testar appen och showen med den matematiska V1-metoden, inte AI-kvaliteten.

VALFRITT TEST AV RIKTIG AI – kostar pengar via ditt API-konto:
Skapa .env med: Copy-Item .env.example .env
Öppna filen: notepad .env
Fyll i OPENAI_API_KEY=din-nyckel och spara. Dela inte nyckeln.
Starta om appen och välj V2. AI-förberedelse kräver internet och API-saldo.

Nästa gång behövs bara startkommandot i steg 3. Sessioner sparas i data/ i appmappen.
README.md och docs/V2.md beskriver appen. Windows och live-AI har ännu inte verifierats här.
""")
    print(f"Created {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
