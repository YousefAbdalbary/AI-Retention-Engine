import time
import asyncio
from backend.api.routers.dashboard import analytics

async def main():
    print("Starting analytics...")
    t0 = time.time()
    res = await analytics()
    print(f"analytics took {time.time()-t0:.4f} seconds")

asyncio.run(main())
