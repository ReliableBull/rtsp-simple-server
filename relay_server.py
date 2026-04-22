import asyncio
import json
import websockets

# drone_id -> websocket
jetson_clients = {}
gcs_clients = set()

async def handler(websocket):
    role = None
    drone_id = None

    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type")

            # 1) Jetson 등록
            if msg_type == "register_jetson":
                role = "jetson"
                drone_id = data["drone_id"]
                jetson_clients[drone_id] = websocket
                print(f"[Relay] Jetson registered: {drone_id}")

                await websocket.send(json.dumps({
                    "type": "register_ack",
                    "status": "ok",
                    "drone_id": drone_id
                }))

            # 2) GCS 등록
            elif msg_type == "register_gcs":
                role = "gcs"
                gcs_clients.add(websocket)
                print("[Relay] GCS registered")

                await websocket.send(json.dumps({
                    "type": "register_ack",
                    "status": "ok",
                    "role": "gcs"
                }))

            # 3) GCS -> ROI -> Relay -> Jetson
            elif msg_type == "roi":
                target_drone_id = data["drone_id"]

                if target_drone_id not in jetson_clients:
                    print(f"[Relay] No Jetson connected for drone_id={target_drone_id}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": f"Jetson {target_drone_id} not connected"
                    }))
                    continue

                jetson_ws = jetson_clients[target_drone_id]

                roi_packet = {
                    "type": "roi",
                    "drone_id": target_drone_id,
                    "x": int(data["x"]),
                    "y": int(data["y"]),
                    "w": int(data["w"]),
                    "h": int(data["h"])
                }

                await jetson_ws.send(json.dumps(roi_packet))
                print(f"[Relay] ROI forwarded to {target_drone_id}: {roi_packet}")

                await websocket.send(json.dumps({
                    "type": "roi_ack",
                    "status": "sent",
                    "drone_id": target_drone_id
                }))

            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}"
                }))

    except websockets.ConnectionClosed:
        print("[Relay] Connection closed")

    finally:
        if role == "jetson" and drone_id in jetson_clients:
            del jetson_clients[drone_id]
            print(f"[Relay] Jetson removed: {drone_id}")

        if role == "gcs" and websocket in gcs_clients:
            gcs_clients.remove(websocket)
            print("[Relay] GCS removed")

async def main():
    server = await websockets.serve(handler, "0.0.0.0", 8765)
    print("[Relay] WebSocket server started on 0.0.0.0:8765")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())