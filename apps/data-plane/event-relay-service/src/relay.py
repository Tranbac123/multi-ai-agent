import httpx, asyncio, json, os
from .crypto import sign
from libs.data_plane.events.nats_event_bus import NATSEventBus

async def run_relay(settings, stop):
    bus = NATSEventBus()
    await bus.start()
    sem = asyncio.Semaphore(settings.webhook_concurrency)

    async def handle(msg: dict):
        # lookup subscribers: in real impl, query DB table event_subscriptions
        endpoints = msg.get("_endpoints", [])
        payload = json.dumps(msg).encode()
        async with httpx.AsyncClient(timeout=10) as client:
            async with sem:
                for url in endpoints:
                    headers = {"X-Signature": sign(settings.hmac_secret, payload)}
                    try:
                        await client.post(url, content=payload, headers=headers)
                    except Exception:
                        # TODO: publish to DLQ
                        pass

    task = asyncio.create_task(bus.subscribe("**", cb=handle, durable="event-relay"))
    await stop.wait()
    task.cancel()

