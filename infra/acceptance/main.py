import asyncio
import json
import sys

import httpx
from acceptance import acceptance


async def main():
    base, scenario = sys.argv[1:3]
    max_days, limit = map(int, sys.argv[3:5])
    ready = False
    async with httpx.AsyncClient(timeout=2, trust_env=False) as client:
        for _ in range(100):
            try:
                if (await client.get(base + "/actuator/health")).status_code == 200:
                    ready = True
                    break
            except httpx.HTTPError:
                pass
            await asyncio.sleep(.5)
    if not ready:
        result = {"passed": False, "cases": [{"name": "isolated application starts", "passed": False, "details": "Health check timed out"}]}
    else:
        try:
            result = await acceptance(base, scenario, max_days, limit)
        except httpx.HTTPError as error:
            result = {"passed": False, "cases": [{"name": "HTTP acceptance completes", "passed": False, "details": type(error).__name__}]}
    print(json.dumps(result))


if __name__ == "__main__":
    asyncio.run(main())
