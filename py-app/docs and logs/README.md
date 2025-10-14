# Restaurant Recommender - Shiny for Python App

A machine learning-powered restaurant recommendation system using TF-IDF, cosine similarity, sentiment analysis, and topic modeling.

## Features

- **Advanced Search**: Natural language search using TF-IDF vectorization
- **Smart Filtering**: Filter by cuisine, rating, distance, and amenities
- **Interactive Map**: Visualize restaurant locations with Plotly
- **Sentiment Analysis**: View review sentiment distribution
- **Topic Modeling**: Discover key themes in reviews
- **Analytics Dashboard**: Explore rating distributions and trends

## Prerequisites

- Python 3.12+
- Virtual environment already set up in `datascience_env/`

## Database Connection

The app connects to `austin_restaurants.db` located in the parent directory. The database contains:
- **3,566 restaurants** in Austin, TX
- **16,509 reviews** with text and ratings
- Detailed place information (hours, amenities, contact info)

## Running the App

### Option 1: Using the activation script
```bash
cd py-app
source activate_env.sh
shiny run app.py --reload
```

### Option 2: Manual activation
```bash
cd py-app
source datascience_env/bin/activate
shiny run app.py --reload
```

The app will be available at `http://127.0.0.1:8000`

## Testing Database Connection

To verify the database connection works correctly:

```bash
cd py-app
source datascience_env/bin/activate
python test_db_connection.py
```

## Project Structure

```
py-app/
├── app.py                      # Main Shiny application
├── test_db_connection.py       # Database connection test script
├── activate_env.sh             # Environment activation helper
├── datascience_env/            # Python virtual environment
└── README.md                   # This file
```

## Key Technologies

- **Shiny for Python**: Web application framework
- **Pandas**: Data manipulation
- **scikit-learn**: TF-IDF vectorization and cosine similarity
- **Plotly**: Interactive visualizations
- **SQLite**: Database backend

## Data Schema

### Restaurants Table
- Basic info: name, address, rating, price_level
- Location: lat, lng
- Amenities: dine_in, takeout, delivery, vegetarian options
- Tags: cuisine types and categories

### Reviews Table
- Author, rating, text, timestamp
- Linked to restaurants by place_id

### Place Details Table
- Extended information: hours, website, phone
- Service options: beer, wine, meal types
- Accessibility features

## ML/NLP Concepts Implemented

1. **TF-IDF Vectorization**: Convert text to numerical vectors for ranking
2. **Cosine Similarity**: Measure relevance between query and restaurants
3. **Sentiment Analysis**: Classify reviews as positive/neutral/negative
4. **Topic Modeling**: Extract key themes and keywords from reviews

## Future Enhancements

- [ ] BERT embeddings for semantic search
- [ ] Collaborative filtering for personalized recommendations
- [ ] Image analysis from restaurant photos
- [ ] Real-time review scraping and updates


