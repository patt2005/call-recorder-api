from fastapi import FastAPI
#import uvicorn
from pydantic import BaseModel
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Declaring our FastAPI instance
app = FastAPI()
 
output = {}

class request_body(BaseModel):
    sentsent : str

@app.post('/predict')
def predict(data : request_body):
    test_data = data.sentsent

    nltk.download("vader_lexicon")
    sid = SentimentIntensityAnalyzer()
    score = sid.polarity_scores(test_data)["compound"]
    if score > 0:
        output["sentiment"] = "Positive"    
    else:
        output["sentiment"] = "Negative"  

    return (output)
