import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class GeminiClient:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables.")
        genai.configure(api_key=api_key)
        
        # Priority list of models to try (Best -> Fastest -> Legacy)
        self.model_candidates = [
            'gemini-3-pro-preview',
            'gemini-2.0-flash',
            'gemini-2.5-flash',
            'gemini-1.5-pro',
            'gemini-1.5-flash',
            'gemini-pro'
        ]

    def generate_report(self, market_data, news_context, system_prompt):
        """
        Generates a financial intelligence report based on technical data and news.
        Tries multiple models in fallback order.
        """
        prompt = f"""
        {system_prompt}

        ### MARKET DATA (Technical Signals)
        {market_data}

        ### NEWS CONTEXT (Fundamental Check)
        {news_context}

        Task: Analyze the above data and generate a structured intelligence report.
        """
        
        last_error = None

        for model_name in self.model_candidates:
            try:
                print(f"🤖 Attempting generation with model: {model_name}...")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                return response.text
            except Exception as e:
                print(f"⚠️ Model {model_name} failed: {e}")
                last_error = e
                continue
        
        return f"Error generating report after trying all models. Last error: {last_error}"
