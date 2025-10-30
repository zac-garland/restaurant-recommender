"""
Pre-compute embeddings locally and save to file.

Run this ONCE locally to generate embeddings.npy:
    python precompute_embeddings.py

This will create embeddings.npy in the same directory.
Include this file in your deployment.
"""

import pandas as pd
import numpy as np
import sqlite3
from sentence_transformers import SentenceTransformer
from pathlib import Path
import pickle

# ============================================================================
# CONFIGURATION
# ============================================================================

base_dir = Path(__file__).parent
db_path = base_dir / 'austin_restaurants.db'
embeddings_file = base_dir / 'restaurant_embeddings.npz'
metadata_file = base_dir / 'embeddings_metadata.pkl'

print(f"Database: {db_path}")
print(f"Output embeddings file: {embeddings_file}")
print(f"Output metadata file: {metadata_file}")

# ============================================================================
# LOAD DATA
# ============================================================================

print("\n[1] Loading data from SQLite database...")
conn = sqlite3.connect(str(db_path))

# Load all restaurants first
restaurants_df = pd.read_sql('SELECT * FROM restaurants', conn)
print(f"  Loaded {len(restaurants_df)} total restaurants")

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
print(f"  Loaded {len(reviews_df)} reviews from restaurants with > 5 reviews")

# Get unique restaurant IDs that have > 5 reviews
restaurants_with_reviews = reviews_df['restaurant_id'].unique()
print(f"  {len(restaurants_with_reviews)} restaurants have > 5 reviews")

# Filter restaurants to only those with > 5 reviews
restaurants_df = restaurants_df[restaurants_df['id'].isin(restaurants_with_reviews)]
print(f"  Filtered to {len(restaurants_df)} restaurants with > 5 reviews")

conn.close()

# ============================================================================
# LOAD MODEL
# ============================================================================

print("\n[2] Loading SentenceTransformer model...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("  Model loaded")

# ============================================================================
# BUILD EMBEDDING TEXTS
# ============================================================================

print("\n[3] Building embedding texts (name + tags + top 5 reviews)...")

search_texts = []
restaurant_ids_list = []

for idx, row in restaurants_df.iterrows():
    if idx % 500 == 0:
        print(f"  Processing restaurant {idx} / {len(restaurants_df)}")
    
    # Get top 5 reviews for this restaurant
    restaurant_reviews = reviews_df[reviews_df['restaurant_id'] == row['id']]
    review_text = ''
    
    if not restaurant_reviews.empty:
        top_reviews = restaurant_reviews.head(5)['text'].fillna('').tolist()
        review_text = ' '.join(top_reviews)[:1000]
    
    # Combine name, tags, and reviews
    combined = f"{row['name']} {row.get('place_tags', '')} {review_text}"
    search_texts.append(combined)
    restaurant_ids_list.append(row['id'])

print(f"  Built {len(search_texts)} texts")

# ============================================================================
# COMPUTE EMBEDDINGS
# ============================================================================

print("\n[4] Computing embeddings (this will take ~30-60 seconds)...")
embeddings = model.encode(search_texts, show_progress_bar=True)
print(f"  Embeddings computed! Shape: {embeddings.shape}")

# ============================================================================
# SAVE TO FILES
# ============================================================================

print(f"\n[5] Saving embeddings and metadata...")

# Save embeddings as numpy compressed format
np.savez_compressed(embeddings_file, embeddings=embeddings)
print(f"  Saved embeddings to {embeddings_file}")
print(f"  File size: {embeddings_file.stat().st_size / 1024 / 1024:.1f} MB")

# Save metadata (restaurant IDs) as pickle
metadata = {
    'restaurant_ids': restaurant_ids_list,
    'count': len(restaurant_ids_list)
}
with open(metadata_file, 'wb') as f:
    pickle.dump(metadata, f)
print(f"  Saved metadata to {metadata_file}")

print("\n✅ Done! You can now include these files in your deployment:")
print(f"  - {embeddings_file}")
print(f"  - {metadata_file}")
