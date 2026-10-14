import asyncio
import json
import sys

import httpx
from acceptance import acceptance


async def main():
    base, scenario = sys.argv[1:3]
    max_days, limit = map(int, sys.argv[3:5])
    async with httpx.AsyncClient(timeout=2, trust_env=False) as client:
        for _ in range(100):
            try:
                if (await client.get(base + "/actuator/health")).status_code == 200:
                    result = await acceptance(base, scenario, max_days, limit)
                    print(json.dumps(result))
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(.5)
    print(json.dumps({"passed": False, "cases": [{"name": "isolated application starts", "passed": False, "details": "Health check timed out"}]}))


if __name__ == "__main__":
    asyncio.run(main())
