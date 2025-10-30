# Restaurant Recommender - Posit Connect Deployment Guide

## 🚀 Quick Deployment

### Option 1: Shiny for Python (Recommended)
Your app has been converted to **Shiny for Python** which retains all your BERT functionality with minimal code changes.

**Advantages:**
- ✅ Keeps your existing Python/BERT code
- ✅ Minimal changes from FastAPI version
- ✅ Full NLP functionality preserved
- ✅ Native rsconnect support

### Option 2: R Shiny (Alternative)
If you prefer R, there's also an R version available, but it uses simpler text processing instead of BERT.

## 📁 Files for Deployment

### For Shiny Python (Recommended):
- `app.py` - Main Shiny application
- `requirements.txt` - Python dependencies
- `austin_restaurants.db` - SQLite database

### For R Shiny (Alternative):
- `app.R` - R Shiny application
- `install_packages.R` - R package installer
- `austin_restaurants.db` - SQLite database

## 🔧 Deployment Steps

### 1. Install rsconnect CLI
```bash
pip install rsconnect-python
```

### 2. Configure rsconnect
```bash
rsconnect add --server https://your-posit-connect-server.com \
              --name your-server \
              --api-key your-api-key
```

### 3. Deploy Shiny Python App
```bash
cd deploy
rsconnect deploy shiny . --name restaurant-recommender --title "Restaurant Recommender"
```

### 4. Deploy R Shiny App (Alternative)
```bash
cd deploy
rsconnect deploy shiny . --name restaurant-recommender-r --title "Restaurant Recommender (R)"
```

## 🎯 Framework Selection

When deploying, select **"Shiny"** from the framework options:
- For Python version: Choose "Shiny" (it will detect Python automatically)
- For R version: Choose "Shiny" (it will detect R automatically)

## 📊 Features Preserved

### Shiny Python Version:
- ✅ BERT embeddings for semantic search
- ✅ Cosine similarity matching
- ✅ Interactive maps with Plotly
- ✅ Location-based filtering
- ✅ Price level filtering
- ✅ Rich popup content
- ✅ Responsive design

### R Shiny Version:
- ✅ TF-IDF similarity matching
- ✅ Interactive Leaflet maps
- ✅ Location-based filtering
- ✅ Price level filtering
- ✅ Topic modeling
- ✅ Sentiment analysis

## 🐛 Troubleshooting

### Common Issues:
1. **Database not found**: Ensure `austin_restaurants.db` is in the deploy folder
2. **Missing dependencies**: Check `requirements.txt` is complete
3. **Location access**: App will work without location, just demands less precise results
4. **BERT model download**: First deployment may take longer as models download

### Performance Notes:
- BERT models are ~500MB and download on first run
- Consider using lighter models for faster deployment
- Database queries are optimized for performance

## 🔄 Migration from FastAPI

The conversion preserves:
- All search logic and algorithms
- Database structure and queries
- UI/UX design and functionality
- Filtering and sorting capabilities
- Map integration and interactivity

Only the web framework changed from FastAPI to Shiny, keeping all your business logic intact!
