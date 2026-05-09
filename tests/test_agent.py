print("1. Starting script...")
import sys
import os

print("2. Importing Biomni Agent A1...")
try:
    from biomni.agent import A1
    print("3. Imported A1")
    from biomni.config import default_config
    print("4. Imported default_config")
except Exception as e:
    print(f"Error during import: {e}")
    sys.exit(1)

def main():
    print("5. Initializing Biomni A1 Agent...")
    try:
        agent = A1(
            path='./data',
            llm='Qwen/Qwen3.6-35B-A3B-FP8',
            source='Custom',
            base_url='http://localhost:8000/v1',
            api_key='EMPTY',
            expected_data_lake_files=[]
        )
        print("6. Agent initialized successfully.")
    except Exception as e:
        print(f"Error during initialization: {e}")
        sys.exit(1)
    
    test_question = "What is the role of the BRCA1 gene in human biology?"
    print(f"\n7. Submitting test question: {test_question}\n")
    
    result = agent.go(test_question)
    
    print("\n=== Response ===")
    print(result)

if __name__ == "__main__":
    main()
