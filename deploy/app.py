"""
Restaurant Recommender - Starlette ASGI Backend
Deployed to Posit Connect (RsConnect)

Frontend: HTML/JS/CSS with Leaflet maps (served as static files)
Backend: Starlette ASGI app with search logic + SQLite + pre-loaded embeddings
"""

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.routing import Route
import pandas as pd
import numpy as np
import sqlite3
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import math
from pathlib import Path
import json
import traceback
import pickle

# ============================================================================
# CONFIGURATION
# ============================================================================

base_dir = Path(__file__).parent
db_path = base_dir / 'austin_restaurants.db'
frontend_dir = base_dir / 'frontend'
embeddings_file = base_dir / 'restaurant_embeddings.npz'
metadata_file = base_dir / 'embeddings_metadata.pkl'

print(f"[INFO] Base directory: {base_dir}")
print(f"[INFO] Database path: {db_path}")
print(f"[INFO] Database exists: {db_path.exists()}")
print(f"[INFO] Frontend directory: {frontend_dir}")
print(f"[INFO] Frontend exists: {frontend_dir.exists()}")
print(f"[INFO] Embeddings file: {embeddings_file}")
print(f"[INFO] Embeddings file exists: {embeddings_file.exists()}")

# ============================================================================
# LOAD DATA & PRE-COMPUTED EMBEDDINGS
# ============================================================================

restaurants_df = None
reviews_df = None
model = None
restaurant_embeddings = None  # Pre-computed embeddings
restaurant_ids_list = None    # Mapping for embeddings

def load_data():
    """Load data and pre-computed embeddings"""
    global restaurants_df, reviews_df, model, restaurant_embeddings, restaurant_ids_list
    
    try:
        print("[INFO] Loading SentenceTransformer model...")
        model = SentenceTransformer('all-MiniLM-L6-v2')
        print("[INFO] Model loaded successfully")
    except Exception as e:
        print(f"[ERROR] Failed to load SentenceTransformer model: {str(e)}")
        traceback.print_exc()
        model = None
    
    try:
        print(f"[INFO] Loading data from SQLite database at {db_path}...")
        if not db_path.exists():
            raise FileNotFoundError(f"Database file not found at {db_path}")
        
        conn = sqlite3.connect(str(db_path))
        
        # Load all restaurants first
        restaurants_df = pd.read_sql('SELECT * FROM restaurants', conn)
        print(f"[INFO] Loaded {len(restaurants_df)} total restaurants")
        
        # Load reviews, only keeping restaurants with > 5 reviews
        reviews_query = """
        WITH review_data AS (
            SELECT
                id as restaurant_id,
                author_name as author,
                rating,
                text,
                time,
                COUNT(*) OVER (PARTITION BY id) as review_count
            FROM reviews
            WHERE text IS NOT NULL AND text != ''
        )
        SELECT * FROM review_data
        WHERE review_count > 5
        """
        
        reviews_df = pd.read_sql(reviews_query, conn)
        print(f"[INFO] Loaded {len(reviews_df)} reviews from restaurants with > 5 reviews")
        
        # Get unique restaurant IDs that have > 5 reviews
        restaurants_with_reviews = reviews_df['restaurant_id'].unique()
        print(f"[INFO] {len(restaurants_with_reviews)} restaurants have > 5 reviews")
        
        # Filter restaurants to only those with > 5 reviews
        restaurants_df = restaurants_df[restaurants_df['id'].isin(restaurants_with_reviews)]
        print(f"[INFO] Filtered to {len(restaurants_df)} restaurants with > 5 reviews")
        
        conn.close()
        
    except Exception as e:
        print(f"[ERROR] Failed to load database: {str(e)}")
        traceback.print_exc()
        restaurants_df = None
        reviews_df = None
        return
    
    # ========================================================================
    # LOAD PRE-COMPUTED EMBEDDINGS
    # ========================================================================
    try:
        if not embeddings_file.exists():
            raise FileNotFoundError(
                f"Embeddings file not found at {embeddings_file}\n"
                "Please run: python precompute_embeddings.py"
            )
        
        print(f"[INFO] Loading pre-computed embeddings from {embeddings_file}...")
        embeddings_data = np.load(embeddings_file)
        restaurant_embeddings = embeddings_data['embeddings']
        print(f"[INFO] Loaded embeddings with shape: {restaurant_embeddings.shape}")
        
        # Load metadata
        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file not found at {metadata_file}")
        
        with open(metadata_file, 'rb') as f:
            metadata = pickle.load(f)
        
        restaurant_ids_list = metadata['restaurant_ids']
        print(f"[INFO] Loaded metadata for {len(restaurant_ids_list)} restaurants")
        
        # Verify consistency
        if len(restaurant_ids_list) != restaurant_embeddings.shape[0]:
            raise ValueError(
                f"Mismatch: {len(restaurant_ids_list)} IDs but {restaurant_embeddings.shape[0]} embeddings"
            )
        
    except Exception as e:
        print(f"[ERROR] Failed to load embeddings: {str(e)}")
        traceback.print_exc()
        restaurant_embeddings = None
        restaurant_ids_list = None

# Load on startup
load_data()

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
    
    Uses PRE-LOADED embeddings for speed.
    """
    
    if restaurants_df is None or reviews_df is None:
        raise Exception("Database not loaded")
    
    if model is None:
        raise Exception("Model not loaded")
    
    if restaurant_embeddings is None or restaurant_ids_list is None:
        raise Exception("Embeddings not loaded. Check deployment files.")
    
    filtered = restaurants_df.copy()
    
    print(f"[SEARCH] Starting with {len(filtered)} restaurants (all have > 5 reviews)")
    
    # ---- PRICE FILTER ----
    if max_price < 4:
        filtered = filtered[filtered['price_level'].fillna(1) <= max_price]
        print(f"[SEARCH] After price filter: {len(filtered)} restaurants")
    
    # ---- DISTANCE FILTER ----
    if user_lat and user_lng:
        filtered['distance'] = filtered.apply(
            lambda row: haversine_distance(user_lat, user_lng, row['lat'], row['lng'])
            if pd.notnull(row['lat']) and pd.notnull(row['lng']) else None,
            axis=1
        )
        if radius < 100:
            filtered = filtered[filtered['distance'].fillna(999) <= radius]
            print(f"[SEARCH] After distance filter: {len(filtered)} restaurants")
    
    # ---- SEMANTIC SIMILARITY (using pre-loaded embeddings) ----
    if not filtered.empty:
        print(f"[SEARCH] Encoding query...")
        query_emb = model.encode([query])
        
        # Find indices of filtered restaurants in the pre-computed embeddings
        filtered_ids = set(filtered['id'].values)
        indices_to_use = [i for i, rid in enumerate(restaurant_ids_list) if rid in filtered_ids]
        
        print(f"[SEARCH] Computing similarity for {len(indices_to_use)} restaurants...")
        
        # Get embeddings for filtered restaurants only
        filtered_embeddings = restaurant_embeddings[indices_to_use]
        
        # Calculate cosine similarity
        sim = cosine_similarity(query_emb, filtered_embeddings)[0]
        
        # Create mapping of restaurant ID to similarity score
        id_to_similarity = {}
        for idx, emb_idx in enumerate(indices_to_use):
            restaurant_id = restaurant_ids_list[emb_idx]
            id_to_similarity[restaurant_id] = sim[idx]
        
        # Add similarity scores to filtered dataframe
        filtered['similarity'] = filtered['id'].map(id_to_similarity)
        
        # ---- SORT & LIMIT ----
        if 'distance' in filtered.columns:
            filtered = filtered.sort_values(
                ['similarity', 'distance'],
                ascending=[False, True]
            ).head(10)
        else:
            filtered = filtered.sort_values('similarity', ascending=False).head(10)
        
        print(f"[SEARCH] After sorting: {len(filtered)} results")
        
        # ---- ADD TOP REVIEW EXCERPT ----
        for idx, row in filtered.iterrows():
            restaurant_reviews = reviews_df[reviews_df['restaurant_id'] == row['id']]
            if not restaurant_reviews.empty and 'text' in restaurant_reviews.columns:
                top_review = restaurant_reviews.iloc[0]['text']
                if top_review and len(str(top_review)) > 150:
                    top_review = str(top_review)[:150] + '...'
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
        "database": "loaded" if restaurants_df is not None else "not_loaded",
        "model": "ready" if model is not None else "not_ready",
        "embeddings": "ready" if restaurant_embeddings is not None else "not_ready",
        "restaurants": len(restaurants_df) if restaurants_df is not None else 0,
        "reviews": len(reviews_df) if reviews_df is not None else 0,
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "embeddings_file": str(embeddings_file),
        "embeddings_file_exists": embeddings_file.exists()
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
        
        # Check if data is loaded
        if restaurants_df is None or reviews_df is None or model is None or restaurant_embeddings is None:
            raise Exception("Application data not loaded. Check logs for errors.")
        
        # Perform search
        results = search_restaurants(query, user_lat, user_lng, radius, max_price)
        
        print(f"[SEARCH] Found {len(results)} results")
        
        return JSONResponse(results)
    
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON decode error: {str(e)}")
        return JSONResponse(
            {"error": "Invalid JSON in request body"},
            status_code=400
        )
    except ValueError as e:
        print(f"[ERROR] Value error: {str(e)}")
        return JSONResponse(
            {"error": f"Invalid parameter value: {str(e)}"},
            status_code=400
        )
    except Exception as e:
        print(f"[ERROR] Search failed: {str(e)}")
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

print("[INFO] Application initialized - ready for searches")
