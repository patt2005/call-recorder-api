from g4f.client import Client
import logging

class SummaryService:
    def __init__(self):
        self.client = Client()
        self.logger = logging.getLogger(__name__)

    def get_summary(self, call_transcribe):
        if not call_transcribe or not call_transcribe.strip():
            return "No transcription available to summarize."
        
        prompt = f"""You are an AI assistant specializing in creating professional call summaries for business executives, lawyers, directors, and other professionals who use call recording applications.

Please analyze the following call transcription and provide a comprehensive, professional summary that includes:

1. **Call Overview**: A brief executive summary (2-3 sentences) highlighting the main purpose and outcome
2. **Key Discussion Points**: Bullet points of the main topics discussed
3. **Action Items**: Clear list of any commitments, tasks, or follow-ups mentioned
4. **Decisions Made**: Any important decisions or agreements reached
5. **Important Details**: Names, dates, numbers, or specific information mentioned
6. **Next Steps**: Any planned future actions or meetings

Format the summary in a clear, professional manner that would be suitable for business documentation and easy reference.

CALL TRANSCRIPTION:
{call_transcribe}

Please provide a structured, professional summary:"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional call summarization assistant for business professionals."},
                    {"role": "user", "content": prompt}
                ],
                web_search=False
            )

            content = response.choices[0].message.content
            return content
        
        except Exception as e:
            self.logger.error(f"Error generating summary: {str(e)}")
            return self._generate_fallback_summary(call_transcribe)
    
    def _generate_fallback_summary(self, call_transcribe):
        """Simple fallback summary if AI service fails"""
        words = call_transcribe.split()
        word_count = len(words)
        
        summary = f"**Call Summary**\n\n"
        summary += f"**Overview**: This call contained {word_count} words of conversation.\n\n"
        summary += f"**Transcription Preview**: {' '.join(words[:50])}...\n\n"
        summary += f"**Note**: Automated summary generation was unavailable. Please review the full transcription for details."
        
        return summary
    
    def get_title(self, call_transcribe):
        """Generate a concise, professional title for the call"""
        if not call_transcribe or not call_transcribe.strip():
            return "Untitled Call"
        
        prompt = f"""Based on the following call transcription, generate a concise, professional title (maximum 10 words) that captures the main topic or purpose of the call.

Examples of good titles:
- "Q4 Financial Review Meeting"
- "Contract Negotiation with ABC Corp"
- "Project Status Update - Marketing Campaign"
- "Legal Consultation - Merger Agreement"
- "Sales Strategy Discussion"

CALL TRANSCRIPTION (first 500 characters):
{call_transcribe[:500]}...

Provide only the title, nothing else:"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional assistant that creates concise titles for business calls."},
                    {"role": "user", "content": prompt}
                ],
                web_search=False,
                temperature=0.3
            )

            title = response.choices[0].message.content.strip()
            title = title.strip('"\'')
            if len(title) > 100:
                title = title[:97] + "..."
            return title
        
        except Exception as e:
            self.logger.error(f"Error generating title: {str(e)}")
            words = call_transcribe.split()[:5]
            return ' '.join(words) + "..." if len(words) >= 5 else "Call Recording"