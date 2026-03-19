import logging
from aiohttp import web

logger = logging.getLogger(__name__)


async def health_check(request):
    return web.json_response({"status": "ok"})


async def start_health_server(port: int = 8080):
    app = web.Application()
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health check server running on port {port}")
    return runner
