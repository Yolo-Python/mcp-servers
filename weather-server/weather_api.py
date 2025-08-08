import requests
import json
from typing import Dict, List, Optional
from datetime import datetime

class WeatherAPI:
    def __init__(self, api_key: str, default_location: str = "New York,US"):
        self.api_key = api_key
        self.default_location = default_location
        self.base_url = "https://api.openweathermap.org/data/2.5"

    def get_current_weather(self, location: Optional[str] = None) -> Dict:
        loc = location or self.default_location
        url = f"{self.base_url}/weather"
        params = {
            "q": loc,
            "appid": self.api_key,
            "units": "imperial"
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            return {
                "location": f"{data['name']}, {data['sys']['country']}",
                "temperature": round(data['main']['temp']),
                "feels_like": round(data['main']['feels_like']),
                "description": data['weather'][0]['description'].title(),
                "humidity": data['main']['humidity'],
                "wind_speed": round(data['wind']['speed']),
                "wind_direction": data['wind'].get('deg', 0),
                "visibility": data.get('visibility', 0) // 1609,  # Convert to miles
                "uv_index": None,  # Need separate call for UV
                "timestamp": datetime.now().isoformat(),
                "success": True
            }

        except requests.exceptions.RequestException as e:
            return {
                "error": f"Failed to fetch weather data: {str(e)}",
                "success": False
            }
        except KeyError as e:
            return {
                "error": f"Unexpected weather data format: {str(e)}",
                "success": False
            }

    def get_forecast(self, location: Optional[str] = None, days: int = 5) -> Dict:
        loc = location or self.default_location
        url = f"{self.base_url}/forecast"
        params = {
            "q": loc,
            "appid": self.api_key,
            "units": "imperial",
            "cnt": days * 8
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            daily_forecasts = []
            current_date = None
            day_data = []

            for item in data['list']:
                forecast_date = datetime.fromtimestamp(item['dt']).date()
                if current_date != forecast_date:
                    if day_data:
                        daily_forecasts.append(self._process_day_forecast(day_data, current_date))
                    current_date = forecast_date
                    day_data = [item]
                else:
                    day_data.append(item)

            if day_data:
                daily_forecasts.append(self._process_day_forecast(day_data, current_date))

            return {
                "location": f"{data['city']['name']}, {data['city']['country']}",
                "forecasts": daily_forecasts[:days],
                "success": True
            }

        except requests.exceptions.RequestException as e:
            return {
                "error": f"Failed to fetch forecast data: {str(e)}",
                "success": False
            }
        except (KeyError, IndexError) as e:
            return {
                "error": f"Unexpected forecast data format: {str(e)}",
                "success": False
            }


    def _process_day_forecast(self, day_data: List[Dict], date) -> Dict:
        """Process a day's worth of forecast data into daily summary"""
        temps = [item['main']['temp'] for item in day_data]
        descriptions = [item['weather'][0]['description'] for item in day_data]

        # Find most common weather description
        most_common_desc = max(set(descriptions), key=descriptions.count)

        return {
            "date": date.strftime("%Y-%m-%d"),
            "day": date.strftime("%A"),
            "high_temp": round(max(temps)),
            "low_temp": round(min(temps)),
            "description": most_common_desc.title(),
            "humidity": round(sum(item['main']['humidity'] for item in day_data) / len(day_data)),
            "wind_speed": round(sum(item['wind']['speed'] for item in day_data) / len(day_data))
        }

    def get_weather_suggestions(self, location: Optional[str] = None) -> Dict:
        """Get clothing and activity suggestions based on current weather"""
        weather_data = self.get_current_weather(location)

        if not weather_data.get('success'):
            return weather_data

        temp = weather_data['temperature']
        description = weather_data['description'].lower()
        wind_speed = weather_data['wind_speed']
        humidity = weather_data['humidity']

        suggestions = {
            "clothing": [],
            "activities": [],
            "alerts": []
        }

        # Temperature-based clothing suggestions
        if temp >= 80:
            suggestions["clothing"].extend(["Light, breathable clothing", "Shorts and t-shirt", "Sunglasses"])
        elif temp >= 65:
            suggestions["clothing"].extend(["Light layers", "Long pants", "Light jacket or sweater"])
        elif temp >= 50:
            suggestions["clothing"].extend(["Warm layers", "Jacket", "Long pants"])
        elif temp >= 32:
            suggestions["clothing"].extend(["Heavy coat", "Warm layers", "Hat and gloves"])
        else:
            suggestions["clothing"].extend(["Winter coat", "Multiple layers", "Hat, gloves, and scarf"])

        # Weather condition suggestions
        if "rain" in description or "drizzle" in description:
            suggestions["clothing"].append("Umbrella or rain jacket")
            suggestions["alerts"].append("Rain expected - bring umbrella")

        if "snow" in description:
            suggestions["clothing"].extend(["Waterproof boots", "Extra warm layers"])
            suggestions["alerts"].append("Snow conditions - drive carefully")

        if wind_speed > 15:
            suggestions["clothing"].append("Wind-resistant jacket")
            suggestions["alerts"].append(f"Windy conditions ({wind_speed} mph)")

        if humidity > 80:
            suggestions["alerts"].append("High humidity - may feel warmer than actual temperature")

        # Activity suggestions
        if temp >= 70 and temp <= 85 and "rain" not in description:
            suggestions["activities"].extend(["Great weather for outdoor activities", "Perfect for biking or walking"])
        elif temp < 32 or "storm" in description:
            suggestions["activities"].append("Good day to stay indoors")
        else:
            suggestions["activities"].append("Dress appropriately for outdoor activities")

        return {
            "current_weather": weather_data,
            "suggestions": suggestions,
            "success": True
        }