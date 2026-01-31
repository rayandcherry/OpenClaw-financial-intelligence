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
        self.model = genai.GenerativeModel('gemini-1.5-flash') # Using Flash for speed/efficiency

    def generate_report(self, market_data, news_context, system_prompt):
        """
        Generates a financial intelligence report based on technical data and news.
        """
        prompt = f"""
        {system_prompt}

        ### MARKET DATA (Technical Signals)
        {market_data}

        ### NEWS CONTEXT (Fundamental Check)
        {news_context}

        Task: Analyze the above data and generate a structured intelligence report.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error generating report: {e}"
