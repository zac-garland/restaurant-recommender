from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import sqlite3
import json
import math
import os

app = FastAPI(title="Restaurant Recommender API")

# CORS - be specific for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Posit Connect will handle the domain
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Load model and data - use absolute paths
base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, '../austin_restaurants.db')

model = SentenceTransformer('all-MiniLM-L6-v2')
conn = sqlite3.connect(db_path)
restaurants_df = pd.read_sql('SELECT * FROM restaurants', conn)
reviews_df = pd.read_sql('SELECT * FROM reviews', conn)

class SearchRequest(BaseModel):
    query: str
    user_lat: float = None
    user_lng: float = None
    radius: float = 100
    max_price: int = 4

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in miles between two coordinates"""
    R = 3959
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.post("/api/search")
def search_restaurants(request: SearchRequest):
    # ... (keep your existing search logic unchanged)
    query = request.query
    
    filtered = restaurants_df.copy()
    
    if request.max_price < 4:
        filtered = filtered[filtered['price_level'].fillna(1) <= request.max_price]
    
    if request.user_lat and request.user_lng:
        filtered['distance'] = filtered.apply(
            lambda row: haversine_distance(request.user_lat, request.user_lng, row['lat'], row['lng']) 
            if pd.notnull(row['lat']) and pd.notnull(row['lng']) else None,
            axis=1
        )
        if request.radius < 100:
            filtered = filtered[filtered['distance'].fillna(999) <= request.radius]
    
    if not filtered.empty:
        search_texts = []
        for idx, row in filtered.iterrows():
            restaurant_reviews = reviews_df[reviews_df['id'] == row['id']]
            review_text = ''
            if not restaurant_reviews.empty:
                top_reviews = restaurant_reviews.head(5)['text'].fillna('').tolist()
                review_text = ' '.join(top_reviews)[:1000]
            
            combined = f"{row['name']} {row['place_tags']} {review_text}"
            search_texts.append(combined)
        
        query_emb = model.encode([query])
        rest_emb = model.encode(search_texts)
        sim = cosine_similarity(query_emb, rest_emb)[0]
        filtered['similarity'] = sim
        
        if 'distance' in filtered.columns:
            filtered = filtered.sort_values(['similarity', 'distance'], ascending=[False, True]).head(10)
        else:
            filtered = filtered.sort_values('similarity', ascending=False).head(10)
        
        for idx, row in filtered.iterrows():
            restaurant_reviews = reviews_df[reviews_df['id'] == row['id']]
            if not restaurant_reviews.empty:
                top_review = restaurant_reviews.iloc[0]['text'] if 'text' in restaurant_reviews.columns else None
                if top_review and len(top_review) > 150:
                    top_review = top_review[:150] + '...'
                filtered.at[idx, 'top_review'] = top_review
        
        filtered['latitude'] = filtered['lat']
        filtered['longitude'] = filtered['lng']
    
    filtered = filtered.fillna('')
    filtered = filtered.replace([float('inf'), float('-inf')], '')
    
    results = []
    for _, row in filtered.iterrows():
        result = {}
        for col in filtered.columns:
            val = row[col]
            if pd.isna(val) or val == float('nan'):
                result[col] = None
            elif isinstance(val, float) and (val == float('inf') or val == float('-inf')):
                result[col] = None
            else:
                result[col] = val
        results.append(result)
    
    return results

# Serve frontend - MUST be last
frontend_path = os.path.join(base_dir, '../frontend')
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")
