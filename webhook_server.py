# webhook_server.py
import os
import asyncio
import logging
import time
from aiohttp import web

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# Load environment variables
try:
    WEBHOOK_VERIFY = os.environ.get("webhook_verify")
    PORT = int(os.environ.get("WEBHOOK_PORT", 4446))
except Exception as e:
    logging.critical(f"Failed to read environment variables: {e}")
    raise SystemExit(1)

if not WEBHOOK_VERIFY:
    logging.critical("WEBHOOK_VERIFY environment variable not set! Exiting...")
    raise SystemExit(1)

BOT = None  # Will be set from your bot file
START_TIME = time.time()  # Track when the server started

async def recieve_vote(request):
    try:
        signature = request.headers.get("Authorization")
        if signature != WEBHOOK_VERIFY:
            logging.warning("Received invalid webhook request (wrong secret)")
            return web.Response(status=403, text="Forbidden")

        try:
            data = await request.json()
        except Exception as e:
            logging.error(f"Failed to parse JSON: {e}")
            data = {}

        user_id = data.get("user")
        logging.info(f"Vote received from user {user_id}")

        # Inform your bot about the vote
        if BOT and hasattr(BOT, "handle_vote"):
            try:
                await BOT.handle_vote(user_id)
                logging.info(f"Reward handled for user {user_id}")
            except Exception as e:
                logging.error(f"Error handling vote for user {user_id}: {e}")

        return web.Response(text="Vote received")

    except Exception as e:
        logging.exception(f"Unexpected error while processing vote: {e}")
        return web.Response(status=500, text="Internal Server Error")

async def check_supporter(request):
    logging.info("Supporter status checked")
    return web.Response(text="Supporter status checked")

async def uptime(request):
    """Return server uptime in seconds."""
    elapsed = int(time.time() - START_TIME)
    return web.Response(text=f"Server is running ⏱ Uptime: {elapsed} seconds")

async def start_webhook_server(bot=None):
    global BOT
    BOT = bot

    try:
        app = web.Application()
        app.add_routes([
            web.post("/", recieve_vote),              # POST-only webhook
            web.get("/supporter", check_supporter),  # GET supporter
            web.post("/supporter", check_supporter), # POST supporter
            web.get("/uptime", uptime)                # GET uptime route
        ])

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", PORT)
        await site.start()
        logging.info(f"✅ Webhook server running on 127.0.0.1:{PORT}")

        while True:
            await asyncio.sleep(3600)

    except OSError as e:
        logging.critical(f"❌ Port {PORT} may already be in use or blocked: {e}")
    except Exception as e:
        logging.exception(f"❌ Failed to start webhook server: {e}")
    finally:
        if 'runner' in locals():
            await runner.cleanup()
            logging.info("Webhook server cleaned up")

if __name__ == "__main__":
    try:
        logging.info("Starting webhook server...")
        asyncio.run(start_webhook_server())
    except KeyboardInterrupt:
        logging.info("Server stopped manually (KeyboardInterrupt)")
    except Exception as e:
        logging.exception(f"Server crashed unexpectedly: {e}")
