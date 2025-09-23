import os, json, asyncio
from typing import Callable, Optional
from nats.aio.client import Client as NATS
from nats.js.api import StreamConfig, RetentionPolicy, ConsumerConfig

class NATSEventBus:
    def __init__(self):
        self.url   = os.getenv("NATS_URL","nats://nats:4222")
        self.stream= os.getenv("NATS_STREAM","platform")
        self.dlq   = f"{self.stream}.DLQ"
        self.nc    = NATS()
        self.js    = None

    async def start(self):
        await self.nc.connect(servers=[self.url])
        self.js = self.nc.jetstream()
        await self.js.add_stream(
            StreamConfig(name=self.stream, subjects=[f"{self.stream}.>"], retention=RetentionPolicy.Workqueue)
        )
        await self.js.add_stream(StreamConfig(name=self.dlq, subjects=[f"{self.dlq}.>"]))

    async def publish(self, subject: str, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        await self.js.publish(f"{self.stream}.{subject}", data)

    async def subscribe(self, pattern: str, cb: Callable, durable: str="worker", tenant_id: Optional[str]=None):
        subject = f"{self.stream}.{pattern}"
        cc = ConsumerConfig(durable_name=durable, ack_policy="explicit")
        sub = await self.js.subscribe(subject, durable=durable, manual_ack=True)
        async for msg in sub.messages:
            try:
                data = json.loads(msg.data)
                if tenant_id and data.get("tenant_id") != tenant_id:
                    await msg.ack()
                    continue
                await cb(data)
                await msg.ack()
            except Exception as e:
                await self.js.publish(f"{self.dlq}.{pattern}", msg.data)
                await msg.ack()

    async def replay(self, from_subject: str, cb: Callable):
        # simple replay: subscribe DLQ subject and feed to cb
        sub = await self.nc.subscribe(f"{self.dlq}.{from_subject}")
        async for msg in sub.messages:
            await cb(json.loads(msg.data))

