"""
PRODUCTION EXAMPLE: Complete Integration with OpenAI API
Demonstrates real-world usage of the infinite context system
"""

import os
from typing import List, Dict, Any
from openai import OpenAI

from config import SystemConfig
from orchestrator import InfiniteContextOrchestrator


class InfiniteContextChatbot:
    """
    Production-ready chatbot with infinite context
    
    Features:
    - Full integration with OpenAI GPT-4
    - Automatic context management across all tiers
    - Streaming responses
    - Cost tracking
    - Session persistence
    """
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.orchestrator = InfiniteContextOrchestrator(config)
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=config.openai_api_key)
        
        # Cost tracking (GPT-4 Turbo prices as of 2024)
        self.cost_per_input_token = 0.01 / 1000   # $0.01 per 1K tokens
        self.cost_per_output_token = 0.03 / 1000  # $0.03 per 1K tokens
        self.total_cost = 0.0
    
    def chat(self, user_message: str, 
            importance_score: float = 0.7,
            stream: bool = False) -> Dict[str, Any]:
        """
        Process a chat message with infinite context
        
        Args:
            user_message: User's message
            importance_score: Message importance (0-1)
            stream: Whether to stream the response
        
        Returns:
            Dictionary with response and metadata
        """
        # Step 1: Process user message through orchestrator
        self.orchestrator.process_message(
            role="user",
            content=user_message,
            importance_score=importance_score
        )
        
        # Step 2: Generate context for this query
        context_data = self.orchestrator.generate_context(
            query=user_message,
            max_tokens=self.config.max_llm_context - 2000  # Reserve for response
        )
        
        # Step 3: Get messages for API call
        messages = context_data["contexts"]["tier1"]
        
        # Step 4: Call OpenAI API
        try:
            response = self.client.chat.completions.create(
                model=self.config.primary_llm,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                stream=stream
            )
            
            if stream:
                # Handle streaming
                full_response = ""
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        print(content, end="", flush=True)
                print()  # New line after streaming
                
                assistant_message = full_response
                usage = None  # Usage not available in streaming mode
            else:
                # Handle normal response
                assistant_message = response.choices[0].message.content
                usage = response.usage
            
            # Step 5: Process assistant response
            self.orchestrator.process_message(
                role="assistant",
                content=assistant_message,
                importance_score=0.5
            )
            
            # Step 6: Calculate cost (if usage available)
            cost = 0.0
            if usage:
                cost = (usage.prompt_tokens * self.cost_per_input_token +
                       usage.completion_tokens * self.cost_per_output_token)
                self.total_cost += cost
            
            return {
                "response": assistant_message,
                "context_tokens": context_data["total_tokens"],
                "response_tokens": usage.completion_tokens if usage else None,
                "total_tokens": usage.total_tokens if usage else None,
                "cost": cost,
                "total_cost": self.total_cost,
                "tiers_used": list(context_data["contexts"].keys())
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "response": None
            }
    
    def add_knowledge(self, content: str, source: str = "user"):
        """Add knowledge to the system"""
        self.orchestrator.add_knowledge_document(
            content=content,
            metadata={"source": source}
        )
    
    def set_preference(self, key: str, value: Any):
        """Set user preference"""
        self.orchestrator.set_user_preference(key, value)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        stats = self.orchestrator.get_system_stats()
        stats["total_cost_usd"] = round(self.total_cost, 4)
        return stats
    
    def save_session(self, filepath: str):
        """Save session to file"""
        self.orchestrator.export_session(filepath)


# ============================================================================
# INTERACTIVE DEMO
# ============================================================================

def run_interactive_demo():
    """Run an interactive demo of the infinite context system"""
    
    print("=" * 70)
    print("INFINITE CONTEXT CHATBOT - Production Demo")
    print("=" * 70)
    print("\nInitializing system...")
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  Warning: OPENAI_API_KEY not found in environment")
        print("Set it with: export OPENAI_API_KEY='your-key-here'")
        print("\nRunning in demo mode without actual API calls...\n")
        demo_mode = True
    else:
        demo_mode = False
    
    # Initialize chatbot
    config = SystemConfig()
    chatbot = InfiniteContextChatbot(config)
    
    # Set system message
    chatbot.orchestrator.tier1.set_system_message(
        "You are an AI assistant with infinite context capabilities. "
        "You have access to 4 tiers of memory: active conversation, "
        "compressed history, knowledge retrieval, and long-term entity memory."
    )
    
    print("\n✓ System initialized!")
    print("\nCommands:")
    print("  /add <text>  - Add knowledge to the system")
    print("  /pref <key> <value> - Set a preference")
    print("  /stats - Show system statistics")
    print("  /save - Save session")
    print("  /quit - Exit")
    print("\n" + "=" * 70 + "\n")
    
    # Demo conversation examples
    demo_messages = [
        "I'm building a transformer model for NLP tasks.",
        "What are the key components of a transformer architecture?",
        "How does self-attention work?"
    ]
    
    if demo_mode:
        print("DEMO MODE: Running with simulated responses\n")
        
        for i, msg in enumerate(demo_messages, 1):
            print(f"User: {msg}")
            
            # Process through system (no actual API call)
            chatbot.orchestrator.process_message("user", msg, importance_score=0.7)
            
            # Simulate response
            simulated_response = f"[Simulated response about: {msg[:50]}...]"
            chatbot.orchestrator.process_message("assistant", simulated_response)
            
            print(f"Assistant: {simulated_response}\n")
        
        # Show stats
        stats = chatbot.get_stats()
        print("\n" + "=" * 70)
        print("DEMO STATISTICS")
        print("=" * 70)
        print(f"\nSession Duration: {stats['session_duration_seconds']}s")
        print(f"Total Messages: {stats['total_messages']}")
        print(f"\nTier 1 (Active): {stats['tier1_stats']['total_messages']} messages")
        print(f"Tier 2 (Compressed): {stats['tier2_stats']['total_memories']} memories")
        print(f"Tier 3 (Retrieval): {stats['tier3_stats']['total_documents']} documents")
        print(f"Tier 4 (Persistent): {stats['tier4_stats']['total_entities']} entities")
        
        return
    
    # Interactive mode (with real API)
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.startswith("/"):
                parts = user_input.split(maxsplit=1)
                command = parts[0].lower()
                
                if command == "/quit":
                    print("\nGoodbye!")
                    break
                
                elif command == "/stats":
                    stats = chatbot.get_stats()
                    print(f"\n📊 System Statistics:")
                    print(f"  Session Duration: {stats['session_duration_seconds']}s")
                    print(f"  Total Messages: {stats['total_messages']}")
                    print(f"  Total Cost: ${stats['total_cost_usd']}")
                    print(f"  Tier 1: {stats['tier1_stats']['total_messages']} messages")
                    print(f"  Tier 2: {stats['tier2_stats']['total_memories']} memories")
                    print(f"  Tier 3: {stats['tier3_stats']['total_documents']} documents")
                    print(f"  Tier 4: {stats['tier4_stats']['total_entities']} entities\n")
                    continue
                
                elif command == "/save":
                    filepath = "/home/user/session_export.json"
                    chatbot.save_session(filepath)
                    print(f"✓ Session saved to {filepath}\n")
                    continue
                
                elif command == "/add":
                    if len(parts) > 1:
                        chatbot.add_knowledge(parts[1])
                        print("✓ Knowledge added\n")
                    else:
                        print("Usage: /add <text>\n")
                    continue
                
                elif command == "/pref":
                    if len(parts) > 1:
                        pref_parts = parts[1].split(maxsplit=1)
                        if len(pref_parts) == 2:
                            chatbot.set_preference(pref_parts[0], pref_parts[1])
                            print("✓ Preference set\n")
                        else:
                            print("Usage: /pref <key> <value>\n")
                    continue
                
                else:
                    print(f"Unknown command: {command}\n")
                    continue
            
            # Process chat message
            print("\n🤖 Assistant: ", end="", flush=True)
            result = chatbot.chat(user_input, stream=True)
            
            if result.get("error"):
                print(f"\n❌ Error: {result['error']}\n")
            else:
                print(f"\n💰 Cost: ${result['cost']:.4f} | Tokens: {result.get('total_tokens', 'N/A')}\n")
        
        except KeyboardInterrupt:
            print("\n\nInterrupted. Use /quit to exit properly.\n")
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    run_interactive_demo()
