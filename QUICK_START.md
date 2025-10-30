# 🚀 Quick Start Guide for Friends

Hey! Thanks for checking out my Restaurant Recommender project! Here's how to get it running in **5 minutes**.

## What You'll Need
- Python 3.9 or higher
- Terminal/Command Prompt
- Web browser

## Step-by-Step Setup

### 1. Clone the Repository
```bash
git clone https://github.com/zac-garland/restaurant-recommender.git
cd restaurant-recommender
git checkout main-2  # Important: Use main-2 branch, not master!
```

### 2. Set Up Python Environment
```bash
# Create virtual environment
python3 -m venv env

# Activate it
source env/bin/activate  # Mac/Linux
# OR
env\Scripts\activate     # Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```
⏱️ *This takes ~2-3 minutes (downloads BERT model)*

### 4. Run Backend (Terminal Window 1)
```bash
cd backend
source ../env/bin/activate  # If not already activated
uvicorn app:app --reload --port 8001
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8001
INFO:     Application startup complete.
```

### 5. Run Frontend (Terminal Window 2)
Open a **NEW** terminal window:
```bash
cd restaurant-recommender/frontend
python3 -m http.server 8000
```

You should see:
```
Serving HTTP on :: port 8000 (http://[::]:8000/) ...
```

### 6. Open Your Browser
Go to: **http://localhost:8000**

## 🎮 How to Use

1. **Click "Grant Location Access"** (the big orange button)
   - This lets the app find restaurants near you
   - Use Austin coordinates if not in Austin: 30.2672, -97.7431

2. **Type a natural language query**, like:
   - "spicy Thai noodles with outdoor seating"
   - "romantic Italian dinner for anniversary"
   - "cheap breakfast tacos near downtown"

3. **Press Enter** and watch the smooth slide animation!

4. **Explore the results**:
   - Map View: Click markers to see reviews
   - List View: Click cards to jump to map
   - Adjust filters for radius and price

## 🧪 Test the API Directly

Open another terminal and try:

```bash
# Simple query
curl -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"query": "pizza"}'

# With location filters (Austin downtown)
curl -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "vegan brunch",
    "user_lat": 30.2672,
    "user_lng": -97.7431,
    "radius": 5,
    "max_price": 2
  }'
```

## 🎯 Cool Queries to Try

1. **"late night burger and beer after a concert"**
2. **"healthy plant-based lunch with gluten-free options"**
3. **"upscale sushi date night impressive presentation"**
4. **"family-friendly Mexican restaurant with patio"**
5. **"authentic Vietnamese pho comfort food"**

The BERT model understands context and intent, not just keywords!

## ❓ Common Issues

**"ModuleNotFoundError"**
- Make sure virtual environment is activated
- Run `pip install -r requirements.txt` again

**"Address already in use"**
- Kill existing servers: `pkill -f uvicorn` or `pkill -f http.server`
- Try different ports: `--port 8002` for backend

**"Search failed" in browser**
- Check backend is running: `curl http://localhost:8001/`
- Check browser console (F12) for errors

**No restaurants showing**
- Increase radius filter to 20+ miles
- Try simpler query: just "pizza" or "tacos"

## 🛑 Stopping the Servers

In each terminal window, press: **Ctrl + C**

To deactivate virtual environment:
```bash
deactivate
```

## 📊 What's Under the Hood?

- **Backend**: FastAPI serving BERT embeddings for semantic search
- **Frontend**: Vanilla JavaScript with Leaflet maps
- **Database**: SQLite with 1,500 Austin restaurants + 10,000 reviews
- **AI Model**: sentence-transformers (all-MiniLM-L6-v2)
- **Search**: Cosine similarity on 384-dimensional embeddings

## 💬 Questions?

Check the full README.md for detailed documentation!

---

**Enjoy exploring Austin's food scene! 🌮🍕🍜**
