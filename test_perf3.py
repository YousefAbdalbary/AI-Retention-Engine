import time
import asyncio
from backend.api.routers.connectors_api import get_connectors_status

async def main():
    print("Starting get_connectors_status...")
    t0 = time.time()
    res = await get_connectors_status()
    print(f"get_connectors_status took {time.time()-t0:.4f} seconds")

asyncio.run(main())
