from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import sqlite3
import json
import math

app = FastAPI(title="Restaurant Recommender API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Load model and data
model = SentenceTransformer('all-MiniLM-L6-v2')
conn = sqlite3.connect('../austin_restaurants.db')
restaurants_df = pd.read_sql('SELECT * FROM restaurants', conn)
reviews_df = pd.read_sql('SELECT * FROM reviews', conn)

class SearchRequest(BaseModel):
    query: str
    user_lat: float = None
    user_lng: float = None
    radius: float = 100  # miles
    max_price: int = 4  # 1-4 scale

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in miles between two coordinates"""
    R = 3959  # Earth's radius in miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

@app.get("/")
def read_root():
    return {"message": "Restaurant Recommender API"}

@app.post("/search")
def search_restaurants(request: SearchRequest):
    query = request.query
    
    # Filter restaurants - use all restaurants initially
    filtered = restaurants_df.copy()
    
    # Filter by price level
    if request.max_price < 4:
        filtered = filtered[filtered['price_level'].fillna(1) <= request.max_price]
    
    # Calculate distance if user location provided
    if request.user_lat and request.user_lng:
        filtered['distance'] = filtered.apply(
            lambda row: haversine_distance(request.user_lat, request.user_lng, row['lat'], row['lng']) 
            if pd.notnull(row['lat']) and pd.notnull(row['lng']) else None,
            axis=1
        )
        # Filter by radius
        if request.radius < 100:
            filtered = filtered[filtered['distance'].fillna(999) <= request.radius]
    
    # BERT similarity on restaurant names and tags
    if not filtered.empty:
        # Combine name and place_tags for better semantic matching
        search_text = filtered['name'] + ' ' + filtered['place_tags'].fillna('')
        query_emb = model.encode([query])
        rest_emb = model.encode(search_text.tolist())
        sim = cosine_similarity(query_emb, rest_emb)[0]
        filtered['similarity'] = sim
        
        # Sort by similarity, then distance if available
        if 'distance' in filtered.columns:
            filtered = filtered.sort_values(['similarity', 'distance'], ascending=[False, True]).head(10)
        else:
            filtered = filtered.sort_values('similarity', ascending=False).head(10)
        
        # Add top review for each restaurant
        for idx, row in filtered.iterrows():
            # In the reviews table, 'id' column contains the restaurant id
            restaurant_reviews = reviews_df[reviews_df['id'] == row['id']]
            if not restaurant_reviews.empty:
                # Get the most helpful or recent review
                top_review = restaurant_reviews.iloc[0]['text'] if 'text' in restaurant_reviews.columns else None
                if top_review and len(top_review) > 150:
                    top_review = top_review[:150] + '...'
                filtered.at[idx, 'top_review'] = top_review
        
        # Add latitude/longitude aliases for frontend compatibility
        filtered['latitude'] = filtered['lat']
        filtered['longitude'] = filtered['lng']
    
    # Clean data for JSON serialization
    filtered = filtered.fillna('')
    filtered = filtered.replace([float('inf'), float('-inf')], '')
    
    # Convert to list of dicts and ensure JSON serializable
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

@app.options("/search")
def options_search():
    return {"message": "OK"}

def parse_query(query):
    filters = {}
    if 'vegan' in query.lower():
        filters['dietary'] = 'vegan'
    if 'italian' in query.lower():
        filters['cuisine'] = 'Italian'
    # Add more parsing logic
    return filters

# Add more endpoints as needed