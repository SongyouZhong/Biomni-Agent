import asyncio
import websockets
import json
import sys

async def test_stream():
    uri = "ws://localhost:8080/api/v1/chat/stream"
    try:
        print(f"Connecting to {uri} ...")
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to Biomni Agent API Gateway!\n")
            
            query = "用 Python 在沙箱里写一段代码，打印一句问候语并计算 2 的 10 次方，然后运行它。"
            if len(sys.argv) > 1:
                query = sys.argv[1]
                
            request = {
                "query": query,
                "llm": "Qwen/Qwen3.6-35B-A3B-FP8", # Local AIDD model
                "source": "Custom",
                "base_url": "http://localhost:8000/v1",
                "api_key": "EMPTY"
            }
            
            print(f"发送指令: '{query}'\n")
            print("="*60)
            await websocket.send(json.dumps(request))
            
            # 接收流式响应
            while True:
                response_str = await websocket.recv()
                response = json.loads(response_str)
                
                status = response.get("status")
                
                if status == "thinking":
                    print("🤔 [网关] 正在初始化 Agent 规划器...")
                    print("-" * 60)
                    
                elif status == "streaming":
                    # 每次 Agent 思考或执行工具后，打印最新进展
                    output = response.get("output", "")
                    if output:
                        # 覆盖当前屏幕的简单做法，或是直接追加打印
                        print(f"\r{output}")
                        print("-" * 60)
                        
                elif status == "completed":
                    print("\n🎉 [网关] Agent 任务执行完毕，连接正常断开！")
                    break
                    
                elif status == "error":
                    print(f"\n❌ [网关] 发生异常: {response.get('message')}")
                    break
                    
    except ConnectionRefusedError:
        print("❌ 无法连接到服务器。请确保在另一个终端运行了 `conda run -n biomni_agent python backend/main.py`")
    except Exception as e:
        print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    asyncio.run(test_stream())
