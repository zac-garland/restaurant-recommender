"""
Restaurant Recommender - Shiny for Python Backend
Deployed to Posit Connect (RsConnect free tier)

Frontend: HTML/JS/CSS with Leaflet maps (served as static files)
Backend: Starlette ASGI app with search logic + SQLite
"""

from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.routing import Route
import pandas as pd
import sqlite3
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import math
from pathlib import Path
import json
import asyncio

# ============================================================================
# CONFIGURATION
# ============================================================================

base_dir = Path(__file__).parent
db_path = base_dir / 'austin_restaurants.db'
frontend_dir = base_dir / 'frontend'

print(f"[INFO] Base directory: {base_dir}")
print(f"[INFO] Database path: {db_path}")
print(f"[INFO] Frontend directory: {frontend_dir}")

# ============================================================================
# LOAD DATA & MODEL
# ============================================================================

print("[INFO] Loading SentenceTransformer model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

print("[INFO] Loading data from SQLite database...")
conn = sqlite3.connect(str(db_path))
restaurants_df = pd.read_sql('SELECT * FROM restaurants', conn)
reviews_df = pd.read_sql('SELECT * FROM reviews', conn)
conn.close()

print(f"[INFO] Loaded {len(restaurants_df)} restaurants and {len(reviews_df)} reviews")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two geographic points in miles
    using the Haversine formula.
    """
    R = 3959  # Earth's radius in miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def search_restaurants(query, user_lat=None, user_lng=None, radius=100, max_price=4):
    """
    Search restaurants with filters and semantic similarity scoring.
    """
    
    filtered = restaurants_df.copy()
    
    # ---- PRICE FILTER ----
    if max_price < 4:
        filtered = filtered[filtered['price_level'].fillna(1) <= max_price]
    
    # ---- DISTANCE FILTER ----
    if user_lat and user_lng:
        filtered['distance'] = filtered.apply(
            lambda row: haversine_distance(user_lat, user_lng, row['lat'], row['lng'])
            if pd.notnull(row['lat']) and pd.notnull(row['lng']) else None,
            axis=1
        )
        if radius < 100:
            filtered = filtered[filtered['distance'].fillna(999) <= radius]
    
    # ---- SEMANTIC SIMILARITY ----
    if not filtered.empty:
        search_texts = []
        
        for idx, row in filtered.iterrows():
            # Get top 5 reviews for this restaurant
            restaurant_reviews = reviews_df[reviews_df['id'] == row['id']]
            review_text = ''
            
            if not restaurant_reviews.empty:
                top_reviews = restaurant_reviews.head(5)['text'].fillna('').tolist()
                review_text = ' '.join(top_reviews)[:1000]  # Limit to 1000 chars
            
            # Combine name, tags, and reviews
            combined = f"{row['name']} {row.get('place_tags', '')} {review_text}"
            search_texts.append(combined)
        
        # Encode query and restaurant texts
        query_emb = model.encode([query])
        rest_emb = model.encode(search_texts)
        
        # Calculate cosine similarity
        sim = cosine_similarity(query_emb, rest_emb)[0]
        filtered['similarity'] = sim
        
        # ---- SORT & LIMIT ----
        if 'distance' in filtered.columns:
            filtered = filtered.sort_values(
                ['similarity', 'distance'],
                ascending=[False, True]
            ).head(10)
        else:
            filtered = filtered.sort_values('similarity', ascending=False).head(10)
        
        # ---- ADD TOP REVIEW EXCERPT ----
        for idx, row in filtered.iterrows():
            restaurant_reviews = reviews_df[reviews_df['id'] == row['id']]
            if not restaurant_reviews.empty and 'text' in restaurant_reviews.columns:
                top_review = restaurant_reviews.iloc[0]['text']
                if top_review and len(top_review) > 150:
                    top_review = top_review[:150] + '...'
                filtered.at[idx, 'top_review'] = top_review
        
        # ---- FRONTEND-COMPATIBLE COLUMNS ----
        filtered['latitude'] = filtered['lat']
        filtered['longitude'] = filtered['lng']
    
    # ---- CLEAN DATA ----
    filtered = filtered.fillna('')
    filtered = filtered.replace([float('inf'), float('-inf')], '')
    
    # ---- CONVERT TO JSON ----
    results = []
    for _, row in filtered.iterrows():
        result_dict = {}
        for col in filtered.columns:
            val = row[col]
            if pd.isna(val):
                result_dict[col] = None
            elif isinstance(val, float) and (math.isinf(val) or math.isnan(val)):
                result_dict[col] = None
            else:
                result_dict[col] = val
        results.append(result_dict)
    
    return results

# ============================================================================
# ROUTE HANDLERS
# ============================================================================

async def health_check(request):
    """Health check endpoint"""
    return JSONResponse({
        "status": "ok",
        "database": "loaded",
        "model": "ready",
        "restaurants": len(restaurants_df),
        "reviews": len(reviews_df)
    })


async def api_search(request):
    """
    Main search endpoint.
    
    POST body:
    {
        "query": "Italian vegan pizza",
        "user_lat": 30.2672,
        "user_lng": -97.7431,
        "radius": 10,
        "max_price": 3
    }
    """
    try:
        body = await request.json()
        
        # Extract and validate parameters
        query = body.get('query', '').strip()
        user_lat = body.get('user_lat')
        user_lng = body.get('user_lng')
        radius = float(body.get('radius', 100))
        max_price = int(body.get('max_price', 4))
        
        if not query:
            return JSONResponse(
                {"error": "query parameter is required"},
                status_code=400
            )
        
        print(f"[SEARCH] Query: {query}, Location: ({user_lat}, {user_lng}), Radius: {radius}, Max Price: {max_price}")
        
        # Perform search
        results = search_restaurants(query, user_lat, user_lng, radius, max_price)
        
        print(f"[SEARCH] Found {len(results)} results")
        
        return JSONResponse(results)
    
    except json.JSONDecodeError:
        return JSONResponse(
            {"error": "Invalid JSON in request body"},
            status_code=400
        )
    except ValueError as e:
        return JSONResponse(
            {"error": f"Invalid parameter value: {str(e)}"},
            status_code=400
        )
    except Exception as e:
        print(f"[ERROR] Search failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            {"error": f"Search failed: {str(e)}"},
            status_code=500
        )

# ============================================================================
# CREATE STARLETTE APP
# ============================================================================

routes = [
    Route("/api/health", health_check, methods=["GET"]),
    Route("/api/search", api_search, methods=["POST"]),
]

app = Starlette(routes=routes)

# ============================================================================
# ADD MIDDLEWARE
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ============================================================================
# SERVE STATIC FRONTEND
# ============================================================================

if frontend_dir.exists():
    print(f"[INFO] Mounting frontend from {frontend_dir}")
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")
else:
    print(f"[WARNING] Frontend directory not found at {frontend_dir}")

# ============================================================================
# DEPLOYMENT NOTES
# ============================================================================
"""
To deploy to RsConnect:

1. Ensure your app.py is in the root directory with:
   - austin_restaurants.db
   - /frontend (with index.html, script.js, styles.css)

2. Create requirements.txt:
   starlette>=0.27.0
   pandas>=1.5.0
   sentence-transformers>=2.2.0
   scikit-learn>=1.2.0
   uvicorn>=0.20.0

3. Deploy:
   rsconnect deploy python /path/to/app --new

4. RsConnect will:
   - Install dependencies
   - Run the Starlette app via ASGI
   - Serve frontend static files
   - Expose API routes (/api/search, /api/health)

This is a pure Starlette ASGI app (no Shiny UI) but still compatible 
with RsConnect and much simpler than the Shiny wrapper approach.
"""
