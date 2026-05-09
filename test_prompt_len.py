import sys
import os
sys.path.append(os.getcwd())
try:
    from biomni.agent.a1 import A1
    from biomni.model.retriever import ToolRetriever
    
    print("Initializing A1 Agent...")
    agent = A1()
    
    # Get the tools
    tools = agent.tool_registry.tools
    print(f"Total tools loaded: {len(tools)}")
    
    retriever = ToolRetriever()
    resources = {
        "tools": tools,
        "data_lake": [],
        "libraries": [],
        "know_how": []
    }
    
    tools_str = retriever._format_resources_for_prompt(resources.get("tools", []))
    
    char_len = len(tools_str)
    token_len = char_len // 4 # rough estimate 4 chars per token
    
    try:
        import tiktoken
        enc = tiktoken.encoding_for_model("gpt-4o")
        token_len = len(enc.encode(tools_str))
    except ImportError:
        pass
        
    print(f"Tools String Character Length: {char_len}")
    print(f"Tools String Token Length (gpt-4o): {token_len}")
    
except Exception as e:
    print(f"Error: {e}")
