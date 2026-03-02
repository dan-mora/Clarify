import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# The Anthropic client reads the API key and handles auth for all
# Claude API calls. We create it once here and import it wherever needed.
client = Anthropic(api_key=ANTHROPIC_API_KEY)
