# Quick Start Guide

## 🚀 Your Restaurant Recommender App is Ready!

The app is now connected to `austin_restaurants.db` with **3,566 restaurants** and **16,509 reviews**.

## Start the App

```bash
cd py-app
source datascience_env/bin/activate
shiny run app.py --reload
```

Then open your browser to: **http://127.0.0.1:8000**

## What's New

✅ **Database Integration**: Connected to SQLite database with real Austin restaurant data  
✅ **3,566 Restaurants**: Complete with ratings, locations, and amenities  
✅ **16,509 Reviews**: Real review text for sentiment analysis and topic modeling  
✅ **Smart Queries**: SQL joins between restaurants, place_details, and reviews tables  
✅ **Data Preprocessing**: Automatic type conversion and data cleaning  

## App Features

### 🏠 Home Tab
- Hero landing page with search bar
- Natural language query input

### 🔍 Search Results Tab
- **Left Panel**: Advanced filters (rating, cuisine, distance, amenities)
- **Center Panel**: Interactive map + restaurant cards
- **Right Panel**: ML analytics
  - TF-IDF match scores
  - Key topics from reviews
  - Sentiment distribution
  - Cosine similarity scores

### 📊 Analytics Tab
- Rating distribution histogram
- Price range analysis
- Sentiment trends over time

## Database Schema Used

### From `restaurants` table:
- id, name, address, rating, price_level
- user_ratings_total, lat, lng, place_tags

### From `place_details` table:
- serves_vegetarian_food, dine_in, takeout, delivery
- serves_beer, serves_wine
- serves_breakfast, serves_brunch, serves_lunch, serves_dinner
- website, formatted_phone_number

### From `reviews` table:
- author_name, rating, text, time (converted from Unix timestamp)

## Testing

Verify database connection:
```bash
python test_db_connection.py
```

## Troubleshooting

**Port already in use?**
```bash
# Find process using port 8000
lsof -ti:8000 | xargs kill -9

# Then restart
shiny run app.py --reload
```

**Virtual environment issues?**
```bash
# Reactivate
source datascience_env/bin/activate

# Verify packages
pip list | grep shiny
```

## Next Steps

Try these searches:
- "romantic Italian restaurant with outdoor seating"
- "best tacos in Austin"
- "vegetarian brunch spots"
- "craft beer and burgers"

Happy exploring! 🍽️✨


