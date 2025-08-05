import gc
try:
    import ujson as json
except ImportError:
    import json
import urequests
import config

class SentimentAnalyzer:
    def __init__(self, api_key, model="gpt-4.1-nano", status_indicator=None):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.status_indicator = status_indicator

    async def analyze_sentiment(self, text):
        """Analyze sentiment and return urgency/anger level 0-5"""
        if not text.strip():
            return {"urgency_level": 0}

        # Set status to processing (blue)
        if self.status_indicator:
            self.status_indicator.set_status('processing')

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Analyze the urgency and anger level of the text, giving MORE WEIGHT to the most recent statements and events mentioned. The latest words in the conversation are more important than earlier ones. Focus especially on the tone and sentiment of the final sentences. Respond with ONLY a single number from 0-5, where 0 is calm/neutral and 5 is extremely urgent/angry."
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            "max_tokens": 10,
            "temperature": 0.1
        }

        try:
            response = urequests.post(
                self.base_url,
                headers=headers,
                data=json.dumps(payload)
            )

            if response.status_code == 200:
                result = json.loads(response.text)
                content = result["choices"][0]["message"]["content"].strip()
                level = int(content)
                # Set status back to idle (green) after successful processing
                if self.status_indicator:
                    self.status_indicator.set_status('idle')
                return {"urgency_level": max(0, min(5, level))}  # Clamp to 0-5
            else:
                if config.DEBUG:
                    print(f"OpenAI API Error: {response.status_code}")
                # Set error status (red) on API error
                if self.status_indicator:
                    self.status_indicator.set_status('error')
                return {"urgency_level": 0}

        except Exception as e:
            if config.DEBUG:
                print(f"Sentiment analysis error: {e}")
            # Set error status (red) on exception
            if self.status_indicator:
                self.status_indicator.set_status('error')
            return {"urgency_level": 0}
        finally:
            if 'response' in locals():
                response.close()