"""
Simple test script for LLM integration.
Tests both Groq and Ollama fallback.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dent_bot.llm import get_llm_client
from dent_bot.prompts import get_system_prompt


def test_llm():
    """Test LLM with a simple question."""
    print("=" * 60)
    print("Hotel Bot LLM Test")
    print("=" * 60)
    print()
    
    # Get system prompt
    system_prompt = get_system_prompt()
    print("System Prompt:")
    print("-" * 60)
    print(system_prompt[:200] + "..." if len(system_prompt) > 200 else system_prompt)
    print()
    
    # Get LLM client
    client = get_llm_client()
    print(f"Using: {'Groq' if client.use_groq else 'Ollama (fallback)'}")
    print(f"Model: {client.model}")
    print()
    
    # Test questions
    test_questions = [
        "Merhaba, nasılsın?",
        "Oda fiyatlarınızı öğrenebilir miyim?",
        "25 Aralık 2025 için müsait odanız var mı?",
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"Test {i}: {question}")
        print("-" * 60)
        
        try:
            response = client.simple_query(question, system_prompt=system_prompt)
            print(f"Yanıt: {response}")
            print()
        except Exception as e:
            print(f"HATA: {e}")
            print()
            import traceback
            traceback.print_exc()
            print()
    
    print("=" * 60)
    print("Test tamamlandı!")
    print("=" * 60)


if __name__ == "__main__":
    test_llm()

