"""Stop only this assignment's named containers; preserve database volumes."""
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
subprocess.run(["docker", "rm", "-f", "urlshortner-demo"], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["docker", "rm", "-f", "urlshortner-demo-proxy"], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["docker", "compose", "stop"], cwd=root, check=True)
print("Containers stopped. Stop the workbench terminal with Ctrl+C. Data is preserved.")
