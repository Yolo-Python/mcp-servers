#!/usr/bin/env python3
"""
Weather MCP Server
Provides real-time weather data and forecasts via OpenWeatherMap API
"""
import asyncio
import json
import os
from typing import Optional
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions
from mcp.types import Tool, TextContent
from dotenv import load_dotenv
from weather_api import WeatherAPI

# Load environment variables
#load_dotenv()

# Initialize the MCP server
app = Server("weather-mcp")

# Global weather API instance
weather_api: Optional[WeatherAPI] = None

def get_weather_api() -> WeatherAPI:
    """Get or create weather API instance"""
    global weather_api

    if weather_api is None:
        api_key = os.getenv('OPENWEATHER_API_KEY')
        if not api_key:
            raise ValueError("OPENWEATHER_API_KEY environment variable is required")

        default_location = os.getenv('DEFAULT_LOCATION', 'New York,US')
        weather_api = WeatherAPI(api_key, default_location)

    return weather_api

@app.list_tools()
async def handle_list_tools():
    """List available weather tools"""
    return [
        Tool(
            name="get_current_weather",
            description="Get current weather conditions for a specified location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Location to get weather for (e.g., 'New York,US', 'London,UK', 'San Francisco,CA')"
                    }
                },
                "required": []  # location is optional - will use default if not provided
            }
        ),
        Tool(
            name="get_weather_forecast",
            description="Get multi-day weather forecast for a specified location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Location to get forecast for (e.g., 'New York,US', 'London,UK', 'San Francisco,CA')"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to forecast (1-5, default: 5)",
                        "minimum": 1,
                        "maximum": 5,
                        "default": 5
                    }
                },
                "required": []  # both parameters are optional
            }
        ),
        Tool(
            name="get_weather_suggestions",
            description="Get clothing and activity suggestions based on current weather conditions",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Location to get suggestions for (e.g., 'New York,US', 'London,UK', 'San Francisco,CA')"
                    }
                },
                "required": []  # location is optional
            }
        )
    ]

@app.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    """Handle tool execution"""
    try:
        weather = get_weather_api()

        if name == "get_current_weather":
            location = arguments.get("location")
            result = weather.get_current_weather(location)

            if result.get('success'):
                # Format the response nicely for Claude
                response = f"""**Current Weather for {result['location']}**

**Temperature**: {result['temperature']}°F (feels like {result['feels_like']}°F)
**Conditions**: {result['description']}
**Humidity**: {result['humidity']}%
**Wind**: {result['wind_speed']} mph
**Visibility**: {result['visibility']} miles

*Last updated: {result['timestamp']}*"""
            else:
                response = f"**Error getting current weather**: {result.get('error', 'Unknown error')}"

            return [TextContent(type="text", text=response)]

        elif name == "get_weather_forecast":
            location = arguments.get("location")
            days = arguments.get("days", 5)

            result = weather.get_forecast(location, days)

            if result.get('success'):
                response = f"**{days}-Day Weather Forecast for {result['location']}**\n\n"

                for forecast in result['forecasts']:
                    response += f"**{forecast['day']} ({forecast['date']})**\n"
                    response += f"   Temperature: {forecast['low_temp']}°F - {forecast['high_temp']}°F\n"
                    response += f"   Conditions: {forecast['description']}\n"
                    response += f"   Humidity: {forecast['humidity']}%, Wind: {forecast['wind_speed']} mph\n\n"
            else:
                response = f"**Error getting forecast**: {result.get('error', 'Unknown error')}"

            return [TextContent(type="text", text=response)]

        elif name == "get_weather_suggestions":
            location = arguments.get("location")
            result = weather.get_weather_suggestions(location)

            if result.get('success'):
                current_weather = result['current_weather']
                suggestions = result['suggestions']

                response = f"**Weather Suggestions for {current_weather['location']}**\n\n"
                response += f"**Current**: {current_weather['temperature']}°F, {current_weather['description']}\n\n"

                if suggestions['clothing']:
                    response += "**Clothing Recommendations**:\n"
                    for item in suggestions['clothing']:
                        response += f"   • {item}\n"
                    response += "\n"

                if suggestions['activities']:
                    response += "**Activity Suggestions**:\n"
                    for item in suggestions['activities']:
                        response += f"   • {item}\n"
                    response += "\n"

                if suggestions['alerts']:
                    response += "**Weather Alerts**:\n"
                    for alert in suggestions['alerts']:
                        response += f"   • {alert}\n"
            else:
                response = f"**Error getting suggestions**: {result.get('error', 'Unknown error')}"

            return [TextContent(type="text", text=response)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        error_msg = f"**Error executing {name}**: {str(e)}"
        return [TextContent(type="text", text=error_msg)]

async def main():
    """Main entry point for local testing"""
    try:
        # Verify we can initialize the weather API
        get_weather_api()
        print("Weather API initialized successfully")
        print("Starting Weather MCP Server...")

        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="weather-mcp",
                    server_version="1.0.0",
                    capabilities=app.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Make sure your .env file contains OPENWEATHER_API_KEY")
    except Exception as e:
        print(f"Error starting server: {e}")

if __name__ == "__main__":
    asyncio.run(main())