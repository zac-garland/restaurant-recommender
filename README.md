
# 🍽️ Restaurant Recommender - Semantic Search with BERT

An intelligent restaurant recommendation system for Austin, TX that uses **BERT semantic search** to understand natural language queries and find the perfect dining spot based on your description, location, and preferences.

## 🎯 What Does This Do?

Instead of searching by keywords, you can describe what you want in natural language:
- *"I want authentic spicy Mexican tacos with fresh salsa and a casual vibe"*
- *"romantic upscale Italian dinner spot with wine selection perfect for anniversaries"*
- *"late night comfort food greasy burger and fries after a concert downtown"*

The system understands the **context** and **intent** behind your query using BERT embeddings and returns restaurants ranked by semantic similarity!

## 🧠 How It Works

### 1. **Semantic Search with BERT**
- Uses `sentence-transformers` (all-MiniLM-L6-v2 model)
- Converts your query into a 384-dimensional embedding vector
- Compares against restaurant names + place tags using cosine similarity
- Ranks results by how well they match your **intent**, not just keywords

### 2. **Smart Filtering**
- **Distance-based**: Uses Haversine formula to calculate actual miles from your location
- **Radius filter**: 5, 10, 15, 20, or 100 miles
- **Price filter**: $, $$, $$$, $$$$ (1-4 scale)
- **Multi-constraint**: Handles complex queries with 6-8 different requirements

### 3. **Rich Results**
- Top 10 most relevant restaurants
- Actual reviews from real users (pulled from database)
- Distance calculation in miles
- Match score (similarity percentage)
- Rating, price level, and address

## 📊 Database Schema

### austin_restaurants.db

**restaurants table** (main data):
```
- id: Google Place ID (unique identifier)
- name: Restaurant name
- business_status: OPERATIONAL/CLOSED_TEMPORARILY/etc.
- price_level: 1-4 scale ($-$$$$)
- rating: Google rating (1-5 stars)
- user_ratings_total: Number of reviews
- address: Full street address
- lat/lng: GPS coordinates
- place_tags: Comma-separated tags (e.g., "restaurant,food,bar")
```

**reviews table** (user reviews):
```
- id: Restaurant ID (links to restaurants.id)
- author_name: Reviewer name
- text: Review content
- rating: Individual review rating
- time: Unix timestamp
- language: Review language
```

**Sample Data**: ~2,500 Austin restaurants with 190,000+ reviews

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- Virtual environment (recommended)

### Installation

1. **Clone and navigate**:
```bash
git clone <repo-url>
cd restaurant-recommender
```

2. **Create virtual environment**:
```bash
python3 -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

### Running the Application

You need to run **two servers** in separate terminal windows:

#### Terminal 1 - Backend (FastAPI)
```bash
cd backend
source ../env/bin/activate
uvicorn app:app --reload --port 8001
```
Backend will be available at: `http://localhost:8001`

#### Terminal 2 - Frontend (Static Server)
```bash
cd frontend
python3 -m http.server 8000
```
Frontend will be available at: `http://localhost:8000`

### Using the App

1. **Open browser** to `http://localhost:8000`
2. **Grant location access** (click the big orange button)
3. **Type your query** in natural language
4. **Press Enter** - smooth slide animation transitions to results!
5. **Explore**:
   - **Map View**: See restaurants plotted with enhanced popups
   - **List View**: Click cards to jump to map location
   - **Filters**: Adjust radius and price level

## 🧪 Testing the Backend API

### Test with cURL

**Basic search**:
```bash
curl -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Italian pizza"}'
```

**With location and filters**:
```bash
curl -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "romantic Italian dinner with wine",
    "user_lat": 30.2672,
    "user_lng": -97.7431,
    "radius": 10,
    "max_price": 3
  }'
```

**Complex NLP query**:
```bash
curl -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "healthy plant-based vegan brunch with gluten-free options",
    "user_lat": 30.2672,
    "user_lng": -97.7431,
    "radius": 5,
    "max_price": 2
  }'
```

### API Response Format

```json
[
  {
    "id": "ChIJ...",
    "name": "Restaurant Name",
    "business_status": "OPERATIONAL",
    "price_level": 2.0,
    "rating": 4.5,
    "user_ratings_total": 500.0,
    "address": "123 Street, Austin",
    "lat": 30.2672,
    "lng": -97.7431,
    "place_tags": "restaurant,food,bar",
    "distance": 1.23,
    "similarity": 0.645,
    "top_review": "Amazing food! The pasta was...",
    "latitude": 30.2672,
    "longitude": -97.7431
  }
]
```

## 🎨 Frontend Features

### Landing Page
- Centered, minimal design
- Location access prompt (encouraged before search)
- Smooth slide-in animation when you search

### Main App
- **Search Bar**: Natural language input
- **Filters**: 
  - Radius: 5-20 miles or "All of Austin"
  - Price: $-$$$$ or "Any Price"
- **Map View**: 
  - Leaflet.js with OpenStreetMap (free, no API key!)
  - User location shown as blue marker
  - Enhanced popups with reviews, tags, distance, match score
- **List View**: 
  - Scrollable restaurant cards
  - Click to jump to map location

## 📁 Project Structure

```
restaurant-recommender/
├── backend/
│   ├── app.py                 # FastAPI backend with BERT
│   └── TEST_RESULTS.md        # Backend validation tests
├── frontend/
│   ├── index.html             # Landing page + main app
│   ├── styles.css             # Advanced CSS with animations
│   └── script.js              # Map, search, transitions
├── austin_restaurants.db      # SQLite database
├── requirements.txt           # Python dependencies
├── env/                       # Virtual environment
└── README.md                  # This file!
```

## 🔧 Technology Stack

**Backend**:
- FastAPI - Modern Python web framework
- sentence-transformers - BERT embeddings
- scikit-learn - Cosine similarity
- pandas - Data manipulation
- SQLite - Database

**Frontend**:
- Vanilla JavaScript (no frameworks!)
- Leaflet.js - Interactive maps
- OpenStreetMap - Free map tiles
- CSS3 - Gradients, animations, transitions

## 🎓 How BERT Similarity Works

1. **Query Processing**:
   ```python
   query = "romantic Italian dinner"
   query_embedding = model.encode([query])  # Shape: (1, 384)
   ```

2. **Restaurant Encoding**:
   ```python
   # Combine name + tags for richer context
   rest_text = "Juliet Italian Kitchen restaurant,food,bar"
   rest_embedding = model.encode([rest_text])  # Shape: (1, 384)
   ```

3. **Similarity Calculation**:
   ```python
   similarity = cosine_similarity(query_embedding, rest_embedding)
   # Returns: 0.63 (63% match!)
   ```

4. **Ranking**:
   - Sort by similarity score (highest first)
   - Then by distance (closest first)
   - Return top 10 results

## 📈 Performance Metrics

- **Response Time**: ~500-800ms per search
- **Similarity Range**: 0.25-0.70 (25%-70% match)
- **Database Size**: 1,500 restaurants, 10,000+ reviews
- **Model**: all-MiniLM-L6-v2 (22M parameters, 384 dimensions)

## 🐛 Troubleshooting

**Backend won't start**:
- Make sure you're in the virtual environment: `source env/bin/activate`
- Check if port 8001 is free: `lsof -i :8001`

**Frontend shows "Search failed"**:
- Verify backend is running: `curl http://localhost:8001/`
- Check browser console for CORS errors

**No results returned**:
- Try a simpler query first: "pizza"
- Increase radius filter to 20+ miles
- Remove price filter constraints

**Map not showing markers**:
- Ensure restaurants have valid lat/lng coordinates
- Check browser console for JavaScript errors

## 🌟 Cool Features to Try

1. **Multi-cuisine fusion**: "Korean Mexican fusion tacos"
2. **Dietary restrictions**: "gluten-free vegan Thai"
3. **Occasion-based**: "birthday celebration upscale steakhouse"
4. **Time context**: "Sunday brunch with bottomless mimosas"
5. **Atmosphere**: "cozy coffee shop with wifi for laptop work"

## 📝 Future Enhancements

- [ ] Cache BERT embeddings for faster responses
- [ ] Add pagination for >10 results
- [ ] Implement fuzzy matching for typos
- [ ] Add cuisine type dropdown filter
- [ ] Time-based filtering (breakfast/lunch/dinner hours)
- [ ] Save favorite restaurants
- [ ] User ratings and feedback loop

## 👥 Contributing

This is a final project for demonstration purposes. Feel free to fork and experiment!

## 📄 License

MIT License - Feel free to use for learning and personal projects.

---

**Built with ❤️ using BERT, FastAPI, and lots of Austin tacos** 🌮

## 🚀 Quick Start

```bash
# 1) (Recommended) use the provided venv or create your own
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate

# 2) Install Python dependencies
pip install -r requirements.txt

# 3) Run the backend API
cd backend
uvicorn app:app --reload --port 8001

# 4) In another terminal, serve the frontend
cd frontend
python -m http.server 8000
```

Access the app at: http://127.0.0.1:8000

## ✨ Features

- 🔍 Smart Search: BERT-based semantic similarity
- �️ Interactive Maps: Leaflet.js with OpenStreetMap
- � Geolocation: Find restaurants near you
- 🎯 Auto-navigation: Search automatically switches to map view
- 📱 Responsive Design: Modern, mobile-friendly interface
- 🛡️ Robust Error Handling: Graceful fallbacks for all operations

## 🛠️ Technical Stack (Python)

- Backend: FastAPI
- Frontend: HTML5, CSS3, JavaScript
- NLP: sentence-transformers, BERT models
- Maps: Leaflet.js, OpenStreetMap
- Data: SQLite integration, pandas

## 📋 Setup Details

Prerequisites:

- Python 3.9+ with pip
- SQLite database file: austin_restaurants.db (included)

## 🎯 How to Use

1) Search: Enter cuisine preferences (e.g., "Italian vegan pizza under $20").
2) Browse: View results on the interactive map or in list view.
3) Explore: Click markers to see restaurant details.
4) Locate: Use geolocation to find nearby restaurants.

## 🔧 Advanced Features

Search Methods

- TF-IDF: Traditional text-based similarity
- BERT: Semantic similarity using transformer models
- Hybrid: Combines both approaches for optimal results

Analytics Dashboard

- Topic Modeling: LDA-based topic discovery from reviews
- Sentiment Analysis: BERT-powered sentiment classification
- Rating Distribution: Visual analytics of restaurant ratings

Interactive Elements

- Rich Map Popups: Reviews, amenities, contact info, photos
- Clickable Cards: Visual feedback and map navigation
- Responsive Design: Works on desktop, tablet, and mobile

## 🗂️ Project Structure

    restaurant-recommender/
    ├── README.md                 # You are here (Python-only)
    ├── requirements.txt          # Python dependencies
    ├── austin_restaurants.db     # SQLite database
    ├── backend/
    │   └── app.py               # FastAPI backend
    ├── frontend/
    │   ├── index.html           # Main HTML page
    │   ├── styles.css           # Advanced CSS styling
    │   └── script.js            # Frontend JavaScript
    ├── py-app/                  # Legacy Shiny app (for reference)
    │   ├── app.py
    │   └── docs and logs/
    ├── scraper/
    │   └── tji_new_scraper.py   # Python scraper
    ├── figures/                 # Documentation images
    └── notes/                   # Development notes

Example map of the underlying data

<img src="figures/example_map.png" width="100%" />

## Data Access (Python)

```python
import sqlite3
import pandas as pd

con = sqlite3.connect("austin_restaurants.db")

# List tables
cursor = con.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

query = """
SELECT 
    name,
    id,
    rating,
    price_level,
    user_ratings_total,
    lat,
    lng,
    address,
    place_tags
FROM restaurants
WHERE business_status = 'OPERATIONAL'
  AND lower(place_tags) NOT LIKE '%convenience%'
LIMIT 10
"""

sql_example = pd.read_sql_query(query, con)
print(sql_example)

con.close()
```

## 🚨 Troubleshooting

- Virtual Environment: Always use a virtual environment for dependencies.
- PyTorch/Transformers: If you need GPU or specific versions, install PyTorch separately.
- Port Conflicts: Change the run port (e.g., `--port 8001`).

Performance Notes

- BERT Models: First run downloads pre-trained models (~500MB)
- Dataset Size: App uses 3,566 restaurants and 16,509 reviews
- Memory Usage: ~2GB RAM recommended for optimal performance

## 🔬 Development

Contributing

1) Fork the repository
2) Create a feature branch
3) Make changes to the Python app
4) Test thoroughly
5) Submit a pull request

Code Structure

- Python Version: Single `py-app/app.py` with organized functions
- Database: SQLite with restaurants, reviews, and place_details tables

Testing

```bash
cd py-app
python -c "from app import load_data; load_data()"
```

## 📊 Data Schema

The SQLite database contains three main tables:

- restaurants: Basic restaurant information (name, rating, location, etc.)
- reviews: User reviews with text and ratings
- place_details: Extended details (amenities, contact info, etc.)

All tables join on the `id` field (restaurant identifier).
