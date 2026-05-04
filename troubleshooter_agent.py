import os
import json
import requests
from dotenv import load_dotenv
from google_adk.agents import Agent
from google_adk.tools import tool

load_dotenv()

# Configure the agent
agent = Agent(
    name="TroubleshooterAgent",
    description="A support agent that helps diagnose issues with the Website Monitor app.",
    instructions="""You are a helpful support assistant.
Your job is to diagnose issues with the Website Monitor application.
You can read the configuration file, read logs, and ping URLs to see if they are reachable.
If the user complains about Discord notifications not working, check the config and verify the webhook URL.
If the user complains about the website not being checked, read the logs and ping the URL."""
)

@tool(
    name="read_config",
    description="Reads the current configuration file (config.json) to see settings."
)
def read_config() -> str:
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Error: config.json file not found. The application might not be configured yet."
    except Exception as e:
        return f"Error reading config: {e}"

@tool(
    name="read_logs",
    description="Reads the last 50 lines of the application log (app.log)."
)
def read_logs() -> str:
    try:
        with open("app.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
            return "".join(lines[-50:])
    except FileNotFoundError:
        return "Error: app.log file not found."
    except Exception as e:
        return f"Error reading logs: {e}"

@tool(
    name="ping_url",
    description="Tries to perform a GET request to a specified URL to check if it's reachable."
)
def ping_url(url: str) -> str:
    try:
        response = requests.get(url, timeout=10)
        return f"Success: HTTP {response.status_code}"
    except requests.RequestException as e:
        return f"Failed to reach URL: {e}"

agent.add_tool(read_config)
agent.add_tool(read_logs)
agent.add_tool(ping_url)

if __name__ == "__main__":
    print("Welcome to Website Monitor Troubleshooter!")
    print("Describe the issue you are facing (e.g., 'Notifications are not working').")
    print("Type 'exit' to quit.")
    
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ['exit', 'quit']:
            break
            
        try:
            # Assuming agent.run is the method to invoke it. Let's use invoke or chat
            # According to standard ADK it might be agent(user_input) or agent.chat(user_input)
            response = agent.run(user_input)
            print(f"\nAgent: {response}")
        except Exception as e:
            print(f"\nError communicating with agent: {e}")
