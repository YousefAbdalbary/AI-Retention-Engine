import time
import asyncio
from backend.api.routers.dashboard import dashboard_overview
from backend.api.routers.customers import get_customers

async def main():
    print("Starting dashboard_overview...")
    t0 = time.time()
    res = await dashboard_overview()
    print(f"dashboard_overview took {time.time()-t0:.4f} seconds")
    
    print("Starting get_customers...")
    t0 = time.time()
    res = await get_customers(1, 25, "", "all", "all", "risk", "desc", "", "", "all", "all", "all")
    print(f"get_customers took {time.time()-t0:.4f} seconds")

asyncio.run(main())
