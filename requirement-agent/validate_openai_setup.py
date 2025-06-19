#!/usr/bin/env python3
"""
Script to validate OpenAI setup and test the API connection.
Checks if the API key is loaded from .env and tests a simple API call.
"""
import os
import openai
from dotenv import load_dotenv

def check_api_key():
    """Check if OpenAI API key is available from environment."""
    print("🔍 Checking OpenAI API key...")
    
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not found in environment variables.")
        print("💡 SOLUTION: Make sure you have a .env file with OPENAI_API_KEY=your_key_here")
        return None
    
    if not api_key.startswith("sk-"):
        print("⚠️  WARNING: API key doesn't start with 'sk-'. This might be invalid.")
        print(f"📄 Current key: {api_key[:20]}...")
        return api_key
    
    print(f"✅ API key found: {api_key[:20]}...")
    return api_key

def test_openai_connection(api_key):
    """Test the OpenAI API connection with a simple request."""
    print("\n🧪 Testing OpenAI API connection...")
    
    try:
        # Set the API key
        openai.api_key = api_key
        
        # Make a simple test request
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say hello"}],
            max_tokens=50,
            temperature=0.1
        )
        
        # Extract the assistant's reply
        assistant_reply = response.choices[0].message.content.strip()
        
        print("✅ SUCCESS: OpenAI API connection working!")
        print(f"🤖 Assistant's reply: {assistant_reply}")
        return True
        
    except openai.error.AuthenticationError:
        print("❌ ERROR: Authentication failed. Invalid API key.")
        print("💡 SOLUTION: Check your API key in the .env file.")
        return False
    except openai.error.RateLimitError:
        print("⚠️  ERROR: Rate limit exceeded. Try again later.")
        print("💡 SOLUTION: Wait a moment and try again, or check your API usage limits.")
        return False
    except openai.error.APIError as e:
        print(f"❌ ERROR: OpenAI API error: {str(e)}")
        print("💡 SOLUTION: Check OpenAI service status or try again later.")
        return False
    except openai.error.InvalidRequestError as e:
        print(f"❌ ERROR: Invalid request: {str(e)}")
        print("💡 SOLUTION: Check the request parameters.")
        return False
    except Exception as e:
        print(f"❌ ERROR: Unexpected error: {str(e)}")
        print("💡 SOLUTION: Check your internet connection and try again.")
        return False

def validate_requirements():
    """Validate that required packages are installed."""
    print("\n📦 Checking required packages...")
    
    try:
        import openai
        print(f"✅ openai package found (version: {openai.__version__})")
        
        # Check if it's the expected version format (v0.28.x)
        if openai.__version__.startswith("0.28"):
            print("✅ Using OpenAI SDK v0.28.x (correct for this implementation)")
        else:
            print(f"⚠️  WARNING: Using OpenAI SDK v{openai.__version__}")
            print("💡 NOTE: This implementation is designed for v0.28.x")
            
    except ImportError:
        print("❌ ERROR: openai package not found.")
        print("💡 SOLUTION: Install with 'pip install openai==0.28.1'")
        return False
    
    try:
        from dotenv import load_dotenv
        print("✅ python-dotenv package found")
    except ImportError:
        print("❌ ERROR: python-dotenv package not found.")
        print("💡 SOLUTION: Install with 'pip install python-dotenv'")
        return False
    
    return True

def main():
    """Main validation function."""
    print("=" * 60)
    print("🔧 OpenAI Setup Validator")
    print("=" * 60)
    
    # Check requirements
    if not validate_requirements():
        print("\n❌ Missing required packages. Please install them first.")
        return 1
    
    # Check API key
    api_key = check_api_key()
    if not api_key:
        print("\n❌ API key validation failed.")
        return 1
    
    # Test connection
    if not test_openai_connection(api_key):
        print("\n❌ OpenAI API connection test failed.")
        return 1
    
    print("\n" + "=" * 60)
    print("✅ All validations passed! OpenAI setup is working correctly.")
    print("🚀 You're ready to use the Requirement Agent!")
    return 0

if __name__ == "__main__":
    exit(main()) 